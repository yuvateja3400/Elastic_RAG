# app/generation/guardrails.py
# from __future__ import annotations
#
# import re
#
# MAX_Q_LEN = 2000  # trim extreme inputs
#
#
# def sanitize_question(q: str) -> str:
#     """
#     Collapse whitespace, strip control chars, and cap length.
#     """
#     q = re.sub(r"\s+", " ", (q or "")).strip()
#     q = q.replace("\x00", "")
#     return q[:MAX_Q_LEN]
#
#
# def allow_question(q: str) -> bool:
#     """
#     Minimal allow-listing; expand with your policies as needed.
#     """
#     if not q:
#         return False
#     if len(q) < 2:
#         return False
#     return True
# app/generation/guardrails.py
from __future__ import annotations

import re
from typing import Tuple

MAX_Q_LEN = 2000  # trim extreme inputs

# --- tiny false-positive safelist (add as needed) ---
SAFE_TERMS = [
    r"\bkill switch(es)?\b",
    r"\bbomb calorimeter\b",
    r"\bmurder mystery\b",
    r"\bbombus\b",                 # the bumblebee genus
    r"\bsteal like an artist\b",   # book title
]

# --- clearly harmful / illegal intents (keep concise & obvious) ---
UNSAFE_PATTERNS = [
    # Violence against people
    r"\b(kill|murder|assassinate|stab|shoot|poison|strangle)\b",
    r"\bhow (do|to) (i|you) (kill|murder|hurt|harm|kidnap)\b",

    # Explosives / weapons construction
    r"\b(make|build|craft)\s+(a\s+)?(bomb|explosive|pipe\s*bomb|molotov|napalm|ied)\b",
    r"\bhow (do|to) (i|you)\s+(make|build)\s+(a\s+)?(bomb|explosive|detonator)\b",

    # Illegal acquisition of money / property
    r"\b(steal|rob|burglarize|shoplift)\b",
    r"\bhow (do|to) (i|you)\s+(steal|rob|break\s*in|pick\s*lock)\b",
    r"\b(counterfeit|fake)\s+(money|currency)\b",

    # Cybercrime (keep broad but obvious)
    r"\b(hack|ddos|phish|keylogger|ransomware|malware|virus)\b",
    r"\bhow (do|to) (i|you)\s+(hack|bypass|crack)\b",
    r"\b(stolen|leaked)\s+passwords?\b",
    r"\bcredit\s*card\s*(numbers?|dumps?)\b",
]

# Optional “off-topic” filter — keep minimal
OFF_TOPIC_PATTERNS = [
    r"\bcelebrity\s+gossip\b",
    r"\blottery numbers?\b",
    r"\bsports betting tips?\b",
]

# Educational/news/legal context that we let through (no “how to do crime”)
CONTEXT_EXCEPTIONS = [
    r"\bhistory\b", r"\bnews\b", r"\bpolicy\b", r"\blaw\b", r"\blegal\b",
    r"\beducation(al)?\b", r"\bresearch\b", r"\bfiction|novel|movie\b",
]

def _match_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

def sanitize_question(q: str) -> str:
    """
    Collapse whitespace, strip control chars, and cap length.
    """
    q = re.sub(r"\s+", " ", (q or "")).strip()
    q = q.replace("\x00", "")
    return q[:MAX_Q_LEN]

def allow_question(q: str) -> Tuple[bool, str | None]:
    """
    Lightweight guardrail:
    - refuse obvious harmful/illegal queries
    - (optionally) refuse very off-topic queries
    - allow educational/legal/news context
    - avoid a few common false positives via SAFE_TERMS
    Returns: (allowed, reason_if_blocked)
    """
    q_norm = sanitize_question(q)
    if not q_norm or len(q_norm) < 2:
        return False, "Please provide a meaningful question."

    # tiny safelist first (prevents false positives)
    if _match_any(SAFE_TERMS, q_norm):
        return True, None

    # strong “how to do harm/illegal” patterns
    if _match_any(UNSAFE_PATTERNS, q_norm):
        # allow if clearly about law/history/news/etc. and *not* procedural
        if _match_any(CONTEXT_EXCEPTIONS, q_norm) and not re.search(r"\bhow (do|to)\b", q_norm, re.IGNORECASE):
            return True, None
        return False, "I can’t help with harmful or illegal requests."

    # gentle off-topic filter (optional; keep minimal)
    if _match_any(OFF_TOPIC_PATTERNS, q_norm):
        return False, "This looks outside the scope of your indexed documents."

    return True, None
