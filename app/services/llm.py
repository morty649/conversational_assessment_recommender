from groq import Groq

from app.core.config import settings

client = Groq(
    api_key=settings.GROQ_API_KEY
)

def generate_reply(messages):

    completion = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        temperature=0.1,
        messages=messages,
    )

    return completion.choices[0].message.content