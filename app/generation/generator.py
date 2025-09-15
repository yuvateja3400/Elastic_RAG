# app/generation/generator.py
from __future__ import annotations

import os
import requests
from typing import Dict, List, Optional


def _format_page_range(h: dict) -> Optional[str]:
    ps, pe = h.get("page_start"), h.get("page_end")
    if ps is None and pe is None:
        return None
    if ps == pe or pe is None:
        return f"p. {ps}"
    return f"pp. {ps}–{pe}"


def _make_prompt(question: str, hits: List[Dict]) -> str:
    """
    Build a compact prompt for the LLM from retrieved hits.
    """
    blocks: List[str] = []
    for i, h in enumerate(hits, start=1):
        title = h.get("filename") or f"Doc {i}"
        pr = _format_page_range(h)
        header = f"[{title}]"
        if pr:
            header += f" ({pr})"
        text = h.get("text") or ""
        blocks.append(f"{header}\n{text}")

    context = "\n\n---\n\n".join(blocks[:10])  # cap context size
    return (
        "You are a precise assistant. Answer using ONLY the context. "
        'If the answer is not contained in the context, say "I don\'t know." '
        "Keep answers concise.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:"
    )


def _call_ollama(
    prompt: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 120,
) -> str:
    url = f"{base_url or os.getenv('OLLAMA_BASE_URL','http://127.0.0.1:11434')}/api/generate"
    data = {
        "model": model or os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    r = requests.post(url, json=data, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "")


def generate_answer(question: str, hits: List[Dict]) -> str:
    prompt = _make_prompt(question, hits)
    return _call_ollama(prompt)
