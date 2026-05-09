from app.services.guardrails import (
    is_offtopic,
    REFUSAL,
)

from app.services.reranker import rerank

from app.models.schemas import (
    ChatResponse,
    Recommendation,
)

class SHLAgent:

    def __init__(
        self,
        retriever,
    ):
        self.retriever = retriever

    def handle_chat(
        self,
        messages
    ):
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )

        if is_offtopic(last_user):
            return ChatResponse(
                reply=REFUSAL,
                recommendations=[],
                end_of_conversation=True,
            )

        if self.needs_clarification(messages):
            return ChatResponse(
                reply=(
                    "What role and seniority level are you hiring for?"
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        conversation_context = " ".join([
            m["content"]
            for m in messages
            if m["role"] == "user"
        ])

        retrieved = self.retriever.retrieve(
            conversation_context,
            k=20
        )

        ranked = rerank(
            query=last_user,
            candidates=retrieved,
            top_k=10
        )

        recommendations = []

        for r in ranked:
            recommendations.append(
                Recommendation(
                    name=r.item.name,
                    url=r.item.link,
                    test_type=", ".join(r.item.keys) if r.item.keys else "Unknown",
                )
            )

        return ChatResponse(
            reply=(
                f"Here are {len(recommendations)} "
                "recommended SHL assessments."
            ),
            recommendations=recommendations,
            end_of_conversation=False,
        )

    def needs_clarification(self, messages):
        text = " ".join([
            m["content"]
            for m in messages
            if m["role"] == "user"
        ]).strip().lower()

        vague_phrases = [
            "i need an assessment",
            "need an assessment",
            "assessment",
            "test",
            
        ]

        return (
    text in vague_phrases
    or (
        len(text.split()) < 5
        and any(p in text for p in vague_phrases)
    )
)