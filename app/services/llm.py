from groq import Groq

from app.core.config import settings

client = Groq(
    api_key=settings.GROQ_API_KEY
)

def generate_reply(messages, response_format=None):
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