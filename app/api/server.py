# app/api/server.py
from __future__ import annotations

import os, sys, subprocess
from typing import Any, Dict, List

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

from app.infra.es_client import get_es
from app.retrieval.searcher import elser_only, hybrid_rrf
from app.generation.generator import generate_answer
from app.generation.guardrails import sanitize_question, allow_question

app = FastAPI(title="Elastic RAG API", version="1.0")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic models ----------
class QueryIn(BaseModel):
    q: str = Field(..., description="User question")
    k: int = Field(5, ge=1, le=50)
    mode: str = Field("hybrid", pattern="^(hybrid|elser)$")

class Citation(BaseModel):
    rank: int
    score: float | None = None
    filename: str | None = None
    drive_url: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    page_range: str | None = None
    snippet: str | None = None
    text: str | None = None

class QueryOut(BaseModel):
    answer: str
    citations: List[Citation]

class IngestIn(BaseModel):
    limit: int | None = None
    index: bool = True

# ---------- Helpers ----------
def _format_page_range(h: Dict[str, Any]) -> str | None:
    ps, pe = h.get("page_start"), h.get("page_end")
    if ps is None and pe is None:
        return None
    if ps == pe or pe is None:
        return f"p. {ps}"
    return f"pp. {ps}–{pe}"

def _short_snippet(text: str | None, max_len: int = 240) -> str | None:
    if not text:
        return None
    s = " ".join(text.split())
    return (s[:max_len] + "…") if len(s) > max_len else s

def _synthesize_snippet(hit: Dict[str, Any], q: str, fallback_len: int = 240) -> str | None:
    """
    If searcher didn’t attach a 'snippet', make a simple one from 'text'.
    (You can replace this with a smarter highlighter later.)
    """
    if hit.get("snippet"):
        return hit["snippet"]
    return _short_snippet(hit.get("text") or "", fallback_len)

def _build_citations(hits: List[Dict[str, Any]], q: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, h in enumerate(hits, start=1):
        pr = _format_page_range(h)
        out.append({
            "rank": i,
            "score": h.get("_score") or h.get("score"),
            "filename": h.get("filename"),
            "drive_url": h.get("drive_url"),
            "chunk_id": h.get("chunk_id"),
            "page_start": h.get("page_start"),
            "page_end": h.get("page_end"),
            "page_range": pr,
            "snippet": _synthesize_snippet(h, q),
            "text": h.get("text"),
        })
    return out

# ---------- Routes ----------
@app.post("/query", response_model=QueryOut)
def query(body: QueryIn) -> QueryOut:
    # Guardrails (very light-weight)
    question = sanitize_question(body.q)
    if not allow_question(question):
        raise HTTPException(400, "Question not allowed. (Try rephrasing.)")

    # Retrieval
    hits = elser_only(question, body.k) if body.mode == "elser" else hybrid_rrf(question, body.k)

    # Answer generation
    answer = generate_answer(question, hits).strip()

    # Citations
    citations = _build_citations(hits, question)
    return QueryOut(answer=answer, citations=citations)

@app.post("/ingest")
def ingest(body: IngestIn):
    """
    Runs your existing scripts.ingest_drive_folder module.
    """
    cmd = [sys.executable, "-m", "scripts.ingest_drive_folder"]
    if body.limit: cmd += ["--limit", str(body.limit)]
    if body.index: cmd += ["--index"]

    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise HTTPException(500, f"ingest failed\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}")
    return {"ok": True, "stdout": p.stdout}

@app.get("/healthz")
def healthz():
    """
    Return *real* Elastic Cloud health + Ollama readiness.
    """
    es_info: Dict[str, Any] | None = None
    es_health: Dict[str, Any] | None = None
    try:
        es = get_es()
        # cluster health
        es_health = es.cluster.health()
        # info / version
        info = es.info()
        es_info = {
            "name": info.get("name"),
            "cluster_name": info.get("cluster_name"),
            "version": info.get("version", {}).get("number"),
            "build_flavor": info.get("version", {}).get("build_flavor"),
            "tagline": info.get("tagline"),
        }
    except Exception as e:
        es_health = {"status": "unknown", "error": str(e)}
        es_info = None

    ollama_ok = False
    try:
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        r = requests.get(base + "/api/tags", timeout=5)
        ollama_ok = r.ok
    except Exception:
        ollama_ok = False

    return {
        "elasticsearch": {
            "health": es_health,  # contains status: green|yellow|red, number_of_nodes, etc.
            "info": es_info,
        },
        "ollama": ollama_ok,
    }
