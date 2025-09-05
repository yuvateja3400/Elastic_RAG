import os, re, requests
from typing import List, Dict, Any

DEFAULT_REFUSAL = "I don't know."

def _ask_ollama(prompt: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "phi3:mini")
    temperature = float(os.getenv("GEN_TEMPERATURE", "0.1"))
    max_new_tokens = int(os.getenv("GEN_MAX_NEW_TOKENS", "256"))

    resp = requests.post(
        f"{host}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_new_tokens
            }
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()

def _build_prompt(question: str, hits: List[Dict[str, Any]]) -> str:
    # Attach chunk ids in square brackets so the model can cite them
    ctx_lines = []
    for h in hits:
        cid = h.get("chunk_id") or h.get("_id") or "chunk"
        filename = h.get("filename", "doc")
        pstart = h.get("page_range", [None, None])[0] or h.get("page_start")
        pend = h.get("page_range", [None, None])[1] or h.get("page_end")
        header = f"[{cid}] {filename} (p.{pstart}-{pend})"
        text = h.get("text") or h.get("_source", {}).get("text", "")
        ctx_lines.append(f"{header}\n{text}".strip())

    context = "\n\n---\n\n".join(ctx_lines)

    prompt = f"""You are a helpful RAG assistant.

Use only the CONTEXT to answer the QUESTION. If the answer isn't clearly supported by the context, reply exactly: {DEFAULT_REFUSAL}
When you borrow evidence, include square-bracket citations using the given chunk ids, e.g. [chunk_id].

QUESTION:
{question}

CONTEXT:
{context}

FINAL ANSWER (with citations):"""
    return prompt

def _extract_citations(text: str, allowed_ids: List[str]) -> List[str]:
    # find [chunk_id] patterns and keep those that exist in hits
    found = re.findall(r"\[([A-Za-z0-9_-]{6,})\]", text)
    allowed = set(allowed_ids)
    out = []
    for cid in found:
        if cid in allowed and cid not in out:
            out.append(cid)
    return out

def generate_answer(question: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not hits:
        return {"answer": DEFAULT_REFUSAL, "citations": []}

    llm_backend = os.getenv("LLM_BACKEND", "ollama").lower()
    prompt = _build_prompt(question, hits)
    known_ids = [h.get("chunk_id") or h.get("_id") for h in hits if h.get("chunk_id") or h.get("_id")]

    if llm_backend == "ollama":
        try:
            answer = _ask_ollama(prompt)
        except Exception as e:
            # If anything goes wrong, be graceful
            answer = DEFAULT_REFUSAL + " (generation error)"
    else:
        # Fallback behavior if someone set another backend by mistake
        answer = DEFAULT_REFUSAL

    cits = _extract_citations(answer, known_ids)
    return {"answer": answer, "citations": cits}
