# app/retrieval/searcher.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import os
import textwrap

from elasticsearch import Elasticsearch

from app.core.config import (
    ES_URL,
    ES_USERNAME,
    ES_PASSWORD,
    ES_INDEX,
    ELSER_MODEL_ID,
)
from app.retrieval.embedder import embed_query  # for hybrid dense kNN


# ---------- Elasticsearch client (Cloud-friendly) ----------
# Prefer API key on Cloud; fallback to basic auth for local/dev.
ES_API_KEY = os.getenv("ES_API_KEY") or os.getenv("ES_CLOUD_API_KEY")
if ES_API_KEY:
    es = Elasticsearch(ES_URL, api_key=ES_API_KEY, verify_certs=True)
else:
    es = Elasticsearch(ES_URL, basic_auth=(ES_USERNAME, ES_PASSWORD), verify_certs=True)

INDEX = ES_INDEX
ELSER_MODEL = ELSER_MODEL_ID  # e.g. ".elser_model_2_linux-x86_64" on Cloud

SOURCE_FIELDS = [
    "filename",
    "drive_url",
    "chunk_id",
    "page_start",
    "page_end",
    "text",
]


# ---------- Helpers ----------
def _display_page_range(ps: Optional[int], pe: Optional[int]) -> Optional[str]:
    if ps is None and pe is None:
        return None
    if ps == pe or pe is None:
        return f"p. {ps}"
    return f"pp. {ps}–{pe}"


def _make_snippet_from_text(text: str, q: Optional[str], max_len: int = 320) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    if q:
        # naive centering around first match if present
        i = text.lower().find(q.lower())
        if i >= 0:
            start = max(0, i - max_len // 2)
            end = min(len(text), start + max_len)
            chunk = text[start:end]
            if start > 0:
                chunk = "…" + chunk
            if end < len(text):
                chunk = chunk + "…"
            return chunk
    return (text[:max_len] + "…") if len(text) > max_len else text


def _format_hits(resp: Dict[str, Any], q: Optional[str] = None) -> List[Dict[str, Any]]:
    """Normalize ES hits and synthesize a stable snippet."""
    out: List[Dict[str, Any]] = []
    for h in resp.get("hits", {}).get("hits", []):
        src = h.get("_source", {}) or {}
        ps, pe = src.get("page_start"), src.get("page_end")

        # Prefer ES highlight when present (ELSER-only path)
        hi = h.get("highlight", {}) or {}
        hl_fragments = hi.get("text") or hi.get("text_field") or []
        if hl_fragments and isinstance(hl_fragments, list):
            snippet = " … ".join(hl_fragments)
        else:
            snippet = _make_snippet_from_text(src.get("text", ""), q)

        out.append(
            {
                "filename": src.get("filename"),
                "drive_url": src.get("drive_url"),
                "chunk_id": src.get("chunk_id"),
                "page_start": ps,
                "page_end": pe,
                "page_range": _display_page_range(ps, pe),
                "text": src.get("text"),
                "snippet": snippet,
                "score": h.get("_score"),
            }
        )
    return out


# ---------- Queries ----------
def elser_only(q: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    ELSER sparse retrieval only.
    We can request highlight here (allowed outside retrievers/RRF).
    """
    body: Dict[str, Any] = {
        "size": k,
        "query": {
            "text_expansion": {
                "ml.tokens": {"model_id": ELSER_MODEL, "model_text": q}
            }
        },
        "_source": SOURCE_FIELDS,
        "highlight": {
            "fields": {"text": {"fragment_size": 180, "number_of_fragments": 1}}
        },
    }
    resp = es.search(index=INDEX, body=body, request_timeout=60)
    return _format_hits(resp, q=q)


def hybrid_rrf(q: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Hybrid = BM25 + ELSER + kNN (MiniLM) combined via RRF.
    NOTE: ES does not support highlight with retrievers/RRF, so we synthesize snippets.
    """
    qvec = embed_query(q)  # 384-d cosine-normalized
    body: Dict[str, Any] = {
        "size": k,
        "retriever": {
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": {
                                "multi_match": {
                                    "query": q,
                                    "fields": ["text^2", "filename"],
                                    "type": "best_fields",
                                }
                            }
                        }
                    },
                    {
                        "standard": {
                            "query": {
                                "text_expansion": {
                                    "ml.tokens": {
                                        "model_id": ELSER_MODEL,
                                        "model_text": q,
                                    }
                                }
                            }
                        }
                    },
                    {
                        "knn": {
                            "field": "vector",
                            "query_vector": qvec,
                            "k": 50,
                            "num_candidates": 100,
                        }
                    },
                ],
                "rank_window_size": 50,
                "rank_constant": 60,
            }
        },
        "_source": SOURCE_FIELDS,
    }
    resp = es.search(index=INDEX, body=body, request_timeout=60)
    return _format_hits(resp, q=q)
