from groq import Groq

from app.core.config import settings

_client = None


def _groq_client():
    global _client
    if _client is None:
        _client = Groq(
            api_key=settings.GROQ_API_KEY
        )
    return _client


def generate_reply(messages, response_format=None):
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for chat generation.")

    kwargs = {}
    if response_format is not None:
        kwargs["response_format"] = response_format

    completion = _groq_client().chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0.1,
        messages=messages,
        **kwargs,
    )

    return completion.choices[0].message.content
