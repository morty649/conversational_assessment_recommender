from app.models.schemas import AgentResponse, ChatResponse, Recommendation
from app.prompts.prompts import SYSTEM_PROMPT
from app.services.llm import generate_reply
from app.services.reranker import rerank


def _catalog_context(ranked) -> str:
    blocks = []

    for idx, candidate in enumerate(ranked, start=1):
        item = candidate.item
        blocks.append(
            "\n".join(
                [
                    f"{idx}. Name: {item.name}",
                    f"URL: {item.link}",
                    f"Description: {item.description}",
                    f"Job levels: {', '.join(item.job_levels or ['Unknown'])}",
                    f"Languages: {', '.join(item.languages or ['Unknown'])}",
                    f"Duration: {item.duration or 'Unknown'}",
                    f"Remote: {item.remote or 'Unknown'}",
                    f"Adaptive: {item.adaptive or 'Unknown'}",
                    f"Categories: {', '.join(item.keys or ['Unknown'])}",
                ]
            )
        )

    return "\n\n".join(blocks)


def _parse_agent_response(content: str) -> AgentResponse:
    if hasattr(AgentResponse, "model_validate_json"):
        return AgentResponse.model_validate_json(content)
    return AgentResponse.parse_raw(content)


def _fallback_response() -> AgentResponse:
    return AgentResponse(
        intent="clarification_needed",
        reply=(
            "I need a little more context before recommending an SHL assessment. "
            "Who is this for, and is the use case hiring, development, or feedback?"
        ),
        needs_clarification=True,
    )


class SHLAgent:
    def __init__(self, retriever):
        self.retriever = retriever

    def handle_chat(self, messages):
        latest_user_message = next(
            m["content"]
            for m in reversed(messages)
            if m["role"] == "user"
            )

        retrieved = self.retriever.retrieve(latest_user_message, k=40)
        ranked = rerank(query=latest_user_message, candidates=retrieved, top_k=10)
        catalog_by_name = {r.item.name: r.item for r in ranked}

        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {
                "role": "assistant",
                "content": (
                    "Retrieved SHL catalog context. This is the only source you "
                    "may use for assessment names, URLs, and recommendation facts.\n\n"
                    f"{_catalog_context(ranked)}"
                ),
            },
            *messages,
        ]

        try:
            agent_response = _parse_agent_response(
                generate_reply(
                    llm_messages,
                    response_format={"type": "json_object"},
                )
            )
        except Exception:
            agent_response = _fallback_response()

        recommendation_names = (
            agent_response.recommendations
            if agent_response.intent in {
                "recommendation_request",
                "comparison_request",
                "conversation_complete",
            }
            else []
        )

        recommendations = [
            Recommendation(
                name=name,
                url=catalog_by_name[name].link,
                test_type=(
                    ", ".join(catalog_by_name[name].keys)
                    if catalog_by_name[name].keys
                    else "Unknown"
                ),
            )
            for name in recommendation_names
            if name in catalog_by_name
        ]

        return ChatResponse(
            reply=agent_response.reply or agent_response.clarification_question or "",
            recommendations=recommendations,
            end_of_conversation=agent_response.intent in {
                "conversation_complete",
                "off_topic",
            },
        )
