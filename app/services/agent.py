import re

from app.models.schemas import ChatResponse, Recommendation
from app.prompts.prompts import COMPARE_PROMPT, SYSTEM_PROMPT
from app.services.llm import generate_reply
from app.services.reranker import rerank

REFUSAL = (
    "I can only help with SHL assessment recommendations using the supplied "
    "SHL catalog. Share the role, seniority, skills, or hiring context and "
    "I can recommend relevant assessments."
)

OFF_TOPIC_TERMS = {
    "legal",
    "legal advice",
    "lawsuit",
    "visa",
    "immigration",
    "medical",
    "diagnosis",
    "therapy",
    "investment",
    "stock",
    "crypto",
    "politics",
    "recipe",
    "weather",
    "ignore previous instructions",
    "ignore the previous instructions",
    "system prompt",
    "developer message",
    "jailbreak",
    "pretend you are",
}

LANGUAGE_TERMS = {
    "english",
    "spanish",
    "french",
    "german",
    "dutch",
    "italian",
    "portuguese",
    "chinese",
    "japanese",
    "korean",
    "arabic",
}

ENGLISH_ACCENT_TERMS = {
    "us",
    "usa",
    "u.s.",
    "u.s.a.",
    "uk",
    "u.k.",
    "british",
    "australian",
    "australia",
    "indian",
    "india",
    "international",
}


def is_offtopic(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in OFF_TOPIC_TERMS)


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _is_compare_request(text: str) -> bool:
    normalized = text.lower()
    return any(
        phrase in normalized
        for phrase in [
            "compare",
            "difference between",
            "different from",
            "how is",
            "versus",
            " vs ",
        ]
    )


def _is_confirmation(text: str) -> bool:
    normalized = text.lower()
    return any(
        phrase in normalized
        for phrase in [
            "confirmed",
            "perfect",
            "looks good",
            "that works",
            "final",
            "go with",
            "sounds good",
        ]
    )


def _contact_center_needs_language(context: str) -> bool:
    normalized = context.lower()
    is_contact_center = any(
        term in normalized
        for term in [
            "contact centre",
            "contact center",
            "call center",
            "call centre",
            "inbound call",
            "customer service",
        ]
    )
    has_language = any(_has_word(normalized, term) for term in LANGUAGE_TERMS)
    return is_contact_center and not has_language


def _contact_center_needs_english_accent(context: str) -> bool:
    normalized = context.lower()
    is_contact_center = any(
        term in normalized
        for term in [
            "contact centre",
            "contact center",
            "call center",
            "call centre",
            "inbound call",
            "customer service",
        ]
    )
    has_english = _has_word(normalized, "english")
    has_accent = any(_has_word(normalized, term) for term in ENGLISH_ACCENT_TERMS)
    return is_contact_center and has_english and not has_accent


def _expanded_retrieval_query(context: str) -> str:
    normalized = context.lower()
    is_contact_center = any(
        term in normalized
        for term in [
            "contact centre",
            "contact center",
            "call center",
            "call centre",
            "inbound call",
            "customer service",
        ]
    )

    if not is_contact_center:
        return context

    expansion = [
        "spoken language screen",
        "SVAR Spoken English",
        "Contact Center Call Simulation",
        "Customer Service Phone Simulation",
        "Entry Level Customer Serv Retail Contact Center",
        "high volume inbound customer service simulation",
    ]

    if any(_has_word(normalized, term) for term in ["us", "usa", "u.s.", "u.s.a."]):
        expansion.append("English USA US")

    return f"{context} {' '.join(expansion)}"


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


def _fallback_reply(recommendations: list[Recommendation]) -> str:
    if not recommendations:
        return (
            "I could not find a grounded SHL catalog match for that request. "
            "Please share the role, seniority, skills, and any constraints."
        )

    names = ", ".join(r.name for r in recommendations[:5])
    return (
        f"I found {len(recommendations)} SHL catalog-backed recommendations: "
        f"{names}. These are grounded in the retrieved SHL assessment catalog."
    )


class SHLAgent:
    def __init__(self, retriever):
        self.retriever = retriever

    def handle_chat(self, messages):
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )

        if is_offtopic(last_user):
            return ChatResponse(
                reply=REFUSAL,
                recommendations=[],
                end_of_conversation=True,
            )

        if self.needs_clarification(messages):
            return ChatResponse(
                reply="What role and seniority level are you hiring for?",
                recommendations=[],
                end_of_conversation=False,
            )

        conversation_context = " ".join(
            m["content"] for m in messages if m["role"] == "user"
        )

        if _contact_center_needs_language(conversation_context):
            return ChatResponse(
                reply=(
                    "What language will the contact centre calls be in? "
                    "That determines the right spoken-language screen."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        if _contact_center_needs_english_accent(conversation_context):
            return ChatResponse(
                reply=(
                    "Which English accent should the spoken-language screen use: "
                    "US, UK, Australian, Indian, or International?"
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        retrieval_query = _expanded_retrieval_query(conversation_context)
        retrieved = self.retriever.retrieve(retrieval_query, k=40)
        ranked = rerank(query=retrieval_query, candidates=retrieved, top_k=10)

        if _is_compare_request(last_user):
            compare_messages = [
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {
                    "role": "assistant",
                    "content": (
                        f"{COMPARE_PROMPT.strip()}\n\n"
                        f"Retrieved SHL catalog context:\n{_catalog_context(ranked)}"
                    ),
                },
                *messages,
            ]

            try:
                reply = generate_reply(compare_messages)
            except Exception:
                reply = _fallback_reply([])

            return ChatResponse(
                reply=reply,
                recommendations=[],
                end_of_conversation=False,
            )

        recommendations = [
            Recommendation(
                name=r.item.name,
                url=r.item.link,
                test_type=", ".join(r.item.keys) if r.item.keys else "Unknown",
            )
            for r in ranked
        ]

        llm_messages = [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {
                "role": "assistant",
                "content": (
                    "Use this retrieved SHL catalog context as the only source "
                    "for recommendations. Do not invent assessment names or URLs.\n\n"
                    f"{_catalog_context(ranked)}"
                ),
            },
            *messages,
        ]

        try:
            reply = generate_reply(llm_messages)
        except Exception:
            reply = _fallback_reply(recommendations)

        return ChatResponse(
            reply=reply,
            recommendations=recommendations,
            end_of_conversation=_is_confirmation(last_user),
        )

    def needs_clarification(self, messages):
        text = " ".join(
            m["content"] for m in messages if m["role"] == "user"
        ).strip().lower()

        vague_phrases = {
            "i need an assessment",
            "need an assessment",
            "assessment",
            "test",
        }

        return text in vague_phrases or (
            len(text.split()) < 5 and any(p in text for p in vague_phrases)
        )
