from groq import Groq

from app.core.config import settings

def generate_reply(messages, response_format=None):
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is required for chat generation.")

    client = Groq(
        api_key=settings.GROQ_API_KEY
    )

    kwargs = {}
    if response_format is not None:
        kwargs["response_format"] = response_format

    completion = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0.1,
        messages=messages,
        **kwargs,
    )

    return completion.choices[0].message.content
