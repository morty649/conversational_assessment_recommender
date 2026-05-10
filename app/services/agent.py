import logging
from time import perf_counter
from uuid import uuid4

from app.models.schemas import AgentResponse, ChatResponse, Recommendation
from app.core.config import settings
from app.prompts.prompts import (
    SYSTEM_PROMPT,
    QUERY_SYSTEM_PROMPT,
)
from app.services.llm import generate_reply
from app.services.reranker import rerank

logger = logging.getLogger("uvicorn.error")


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


def _build_retrieval_query(messages, latest_user_message: str) -> str:
    low_signal_messages = {
        "perfect",
        "confirmed",
        "sounds good",
        "great",
        "that's what we need",
        "thats what we need",
        "works for us",
    }

    user_messages = [
        m["content"].strip()
        for m in messages
        if m["role"] == "user" and m["content"].strip()
    ]

    filtered = [
        msg for msg in user_messages
        if msg.lower() not in low_signal_messages
    ]

    if not filtered:
        filtered = [latest_user_message.strip()]

    recent_messages = filtered[-3:]
    deduped: list[str] = []
    seen = set()

    for msg in recent_messages:
        key = msg.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(msg)

    return " | ".join(deduped)


class SHLAgent:
    def __init__(self, retriever):
        self.retriever = retriever

    def _log_timing(self, request_id: str, timings: dict, **extra):
        if not settings.ENABLE_CHAT_TIMING_LOGS:
            return

        timing_text = " ".join(
            f"{name}_ms={elapsed * 1000:.1f}"
            for name, elapsed in timings.items()
        )
        extra_text = " ".join(
            f"{name}={value}"
            for name, value in extra.items()
        )
        logger.info(
            "chat_timing request_id=%s %s %s",
            request_id,
            timing_text,
            extra_text,
        )

    def handle_chat(self, messages):
        request_id = uuid4().hex[:8]
        timings = {}
        request_started = perf_counter()

        user_messages = [
            m["content"]
            for m in messages
            if m["role"] == "user"
        ]

        latest_user_message = user_messages[-1]

        stage_started = perf_counter()
        retrieval_query = _build_retrieval_query(
            messages,
            latest_user_message,
        )
        timings["query_build"] = perf_counter() - stage_started

        if settings.ENABLE_LLM_QUERY_OPTIMIZER:
            stage_started = perf_counter()
            conversation_context = []

            for m in messages:
                if m["role"] == "user":
                    conversation_context.append({
                        "role": "user",
                        "content": m["content"],
                    })

                elif m["role"] == "assistant":
                    conversation_context.append({
                        "role": "assistant",
                        "content": m["content"][:500],
                    })

            query_messages = [
                {
                    "role": "system",
                    "content": QUERY_SYSTEM_PROMPT,
                },
                *conversation_context,
            ]

            try:
                retrieval_query = generate_reply(query_messages)
            except Exception as exc:
                logger.warning(
                    "query_optimizer_failed request_id=%s error=%s",
                    request_id,
                    exc,
                )
                pass
            finally:
                timings["query_optimizer"] = perf_counter() - stage_started

        stage_started = perf_counter()
        retrieved = self.retriever.retrieve(
            retrieval_query,
            k=settings.TOP_K_RETRIEVAL,
        )
        timings["retrieval"] = perf_counter() - stage_started
        for name, elapsed in getattr(self.retriever, "last_timings", {}).items():
            timings[name] = elapsed

        stage_started = perf_counter()
        ranked = rerank(
            query=retrieval_query,
            candidates=retrieved,
            top_k=settings.TOP_K_FINAL,
        )
        timings["rerank"] = perf_counter() - stage_started
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
            stage_started = perf_counter()
            agent_response = _parse_agent_response(
                generate_reply(
                    llm_messages,
                    response_format={"type": "json_object"},
                )
            )
            timings["final_llm"] = perf_counter() - stage_started
        except Exception as exc:
            timings["final_llm"] = perf_counter() - stage_started
            logger.warning(
                "final_llm_failed request_id=%s error=%s",
                request_id,
                exc,
            )
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
                duration=(
                    catalog_by_name[name].duration
                    or "Unknown"
                ),
                languages=(
                    ", ".join(catalog_by_name[name].languages)
                    if catalog_by_name[name].languages
                    else "Unknown"
                ),
            )
            for name in recommendation_names
            if name in catalog_by_name
        ]

        final_reply = (
            agent_response.reply
            or agent_response.clarification_question
            or ""
        )

        if recommendations:
            final_reply += "\n\nRecommended assessments:\n"
            final_reply += "\n".join(
                f"- {r.name}" for r in recommendations
            )

        timings["total"] = perf_counter() - request_started
        self._log_timing(
            request_id,
            timings,
            messages=len(messages),
            retrieved=len(retrieved),
            ranked=len(ranked),
            recommendations=len(recommendations),
            optimizer_enabled=settings.ENABLE_LLM_QUERY_OPTIMIZER,
            semantic_enabled=settings.ENABLE_SEMANTIC_RETRIEVAL,
        )

        return ChatResponse(
            reply=final_reply,
            recommendations=recommendations,
            end_of_conversation=agent_response.intent in {
                "conversation_complete",
                "off_topic",
            },
        )
