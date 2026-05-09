REFUSAL = (
    "I can only help with choosing SHL assessments."
)

BAD_PATTERNS = [
    "ignore previous instructions",
    "legal advice",
    "hiring law",
    "salary negotiation",
    "training cutoff date",
]

def is_offtopic(text: str):

    text = text.lower()

    return any(
        bad in text
        for bad in BAD_PATTERNS
    )