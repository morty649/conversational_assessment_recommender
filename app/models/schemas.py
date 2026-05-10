from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str
    duration: str
    languages: str

class AgentResponse(BaseModel):
    intent: Literal[
        "recommendation_request",
        "clarification_needed",
        "comparison_request",
        "off_topic",
        "conversation_complete",
    ]
    reply: str
    clarification_question: Optional[str] = None
    recommendations: List[str] = Field(default_factory=list)
    needs_clarification: bool = False

class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation]
    end_of_conversation: bool
