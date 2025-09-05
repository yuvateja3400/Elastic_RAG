# app/api/server.py
import os, sys, subprocess, requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.infra.es_client import get_es
from app.retrieval.searcher import elser_only, hybrid_rrf

app = FastAPI(title="Elastic RAG API")

# (optional) CORS if you’ll call from a web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ---------- Models ----------
class QueryIn(BaseModel):
    q: str
    k: int = 5
    mode: str = "hybrid"       # "elser" | "hybrid"

class QueryOut(BaseModel):
    answer: str
    citations: list

class IngestIn(BaseModel):
    limit: int | None = None
    index: bool = True

# ---------- Helpers ----------
def call_ollama(prompt: str, model: str | None = None, base_url: str | None = None, timeout=120) -> str:
    url = f"{base_url or os.getenv('OLLAMA_BASE_URL','http://127.0.0.1:11434')}/api/generate"
    data = {
        "model": model or os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    }
    r = requests.post(url, json=data, timeout=timeout)
    if r.status_code != 200:
        raise HTTPException(502, f"Ollama error {r.status_code}: {r.text[:200]}")
    return r.json().get("response", "")

def make_prompt(question, hits):
    parts = []
    for i, h in enumerate(hits, start=1):
        p0, p1 = (h.get("page_range") or [None, None])
        meta = f"[{i}] {h.get('filename','')} p.{p0}-{p1} {h.get('drive_url','')}".strip()
        txt = (h.get("snippet") or h.get("text") or "").strip()
        parts.append(meta + "\n" + txt)
    context = "\n\n".join(parts[:10])
    return f"""You are a helpful assistant. Answer the QUESTION using only the CONTEXT.
If the answer cannot be found, say "I don't know." Be concise.

QUESTION:
{question}

CONTEXT:
{context}

Answer:"""

# ---------- Endpoints ----------
@app.post("/query", response_model=QueryOut)
def query(body: QueryIn):
    hits = elser_only(body.q, body.k) if body.mode == "elser" else hybrid_rrf(body.q, body.k)
    prompt = make_prompt(body.q, hits)
    answer = call_ollama(prompt).strip()

    citations = []
    for i, h in enumerate(hits, start=1):
        citations.append({
            "rank": i,
            "score": h.get("score"),
            "filename": h.get("filename"),
            "drive_url": h.get("drive_url"),
            "chunk_id": h.get("chunk_id"),
            "page_range": h.get("page_range"),
            "snippet": (h.get("snippet") or "")[:300],
        })
    return {"answer": answer, "citations": citations}

@app.post("/ingest")
def ingest(body: IngestIn):
    cmd = [sys.executable, "-m", "scripts.ingest_drive_folder"]
    if body.limit: cmd += ["--limit", str(body.limit)]
    if body.index: cmd += ["--index"]

    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise HTTPException(500, f"ingest failed\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}")
    return {"ok": True, "stdout": p.stdout}

@app.get("/healthz")
def healthz():
    es_ok = False
    try:
        es_ok = get_es().ping()
    except Exception:
        es_ok = False

    ollama_ok = False
    try:
        base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        r = requests.get(base + "/api/tags", timeout=5)
        ollama_ok = r.ok
    except Exception:
        ollama_ok = False

    return {"elasticsearch": es_ok, "ollama": ollama_ok}
