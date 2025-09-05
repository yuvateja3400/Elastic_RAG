UNSAFE_KEYWORDS = [
    "build a bomb", "make a weapon", "self-harm", "suicide", "credit card generator"
]

def is_safe(query: str) -> bool:
    q = query.lower()
    return not any(bad in q for bad in UNSAFE_KEYWORDS)

REFUSAL = "I can’t help with that."
