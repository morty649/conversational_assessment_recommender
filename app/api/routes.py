from fastapi import APIRouter

from app.models.schemas import (
    ChatRequest,
)

router = APIRouter()

agent_instance = None

@router.get("/health")
def health():
    return {
        "status": "ok"
    }

@router.post("/chat")
def chat(request: ChatRequest):

    return agent_instance.handle_chat(
        [
            m.model_dump()
            for m in request.messages
        ]
    )