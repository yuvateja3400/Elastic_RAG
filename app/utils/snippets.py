import re

def make_snippet(text: str, query: str, width: int = 140) -> str:
    tokens = [re.escape(t) for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    if not tokens:
        return text[:width]
    pattern = re.compile(r"(?i)\b(" + "|".join(tokens) + r")\b")
    m = pattern.search(text)
    if not m:
        return text[:width]
    start = max(0, m.start() - width // 2)
    end = min(len(text), start + width)
    snippet = text[start:end]
    # optional mark
    return pattern.sub(lambda mm: f"<mark>{mm.group(0)}</mark>", snippet)
