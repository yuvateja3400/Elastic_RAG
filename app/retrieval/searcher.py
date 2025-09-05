from typing import List, Dict, Any
from app.storage.elastic_client import make_es
import os
from app.infra.es_client import get_es
from app.retrieval.embedder import embed_query  # we added this earlier

es = get_es()
INDEX = os.getenv("ELASTIC_INDEX_NAME", "rag_documents_v1")

# INDEX = "rag_documents_v1"
ELSER_MODEL_ID = ".elser_model_2"
TEXT_FIELD = "text"           # BM25
ELSER_FIELD = "ml.tokens"     # ELSER tokens
VECTOR_FIELD = "vector"       # dense vectors

def _source_filter():
    return ["filename", "drive_url", "chunk_id", "text", "page_start", "page_end"]

def build_elser_only_query(question: str, top_k: int = 5) -> Dict[str, Any]:
    return {
        "size": top_k,
        "_source": _source_filter(),
        "query": {
            "text_expansion": {
                ELSER_FIELD: {
                    "model_id": ELSER_MODEL_ID,
                    "model_text": question
                }
            }
        },
        "highlight": {
            "fields": { TEXT_FIELD: {} },
            "fragment_size": 180,
            "number_of_fragments": 1
        }
    }

def build_hybrid_rrf_query(question: str, qvec: List[float], top_k: int = 5) -> Dict[str, Any]:
    window_size = max(50, top_k * 10)
    rank_constant = 60
    knn_k = max(50, top_k * 10)
    num_candidates = max(100, knn_k * 2)

    return {
        "size": top_k,
        "_source": _source_filter(),
        "rank": {
            "rrf": { "window_size": window_size, "rank_constant": rank_constant },
            "queries": [
                {"query": {"match": { TEXT_FIELD: {"query": question }}}},
                {"query": {
                    "text_expansion": {
                        ELSER_FIELD: {
                            "model_id": ELSER_MODEL_ID,
                            "model_text": question
                        }
                    }
                }},
                {"knn": {
                    "field": VECTOR_FIELD,
                    "query_vector": qvec,
                    "k": knn_k,
                    "num_candidates": num_candidates
                }}
            ]
        },
        "highlight": {
            "fields": { TEXT_FIELD: {} },
            "fragment_size": 180,
            "number_of_fragments": 1
        }
    }


def _format_hits(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for h in resp.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
        out.append({
            "score": h.get("_score"),
            "filename": src.get("filename"),
            "drive_url": src.get("drive_url"),
            "chunk_id": src.get("chunk_id"),
            "page_range": [src.get("page_start"), src.get("page_end")],
            "snippet": (h.get("highlight", {}).get(TEXT_FIELD, [src.get("text","")])[0])[:500],
        })
    return out

# def elser_only(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
#     es = make_es()
#     body = build_elser_only_query(question, top_k)
#     resp = es.search(index=INDEX, body=body, request_timeout=30)
#     return _format_hits(resp)
def elser_only(q: str, k: int = 5):
    body = {
        "size": k,
        "query": {
            "bool": {
                "should": [
                    {"multi_match": {"query": q, "fields": ["text^2", "filename"], "type": "best_fields"}},
                    {"text_expansion": {"ml.tokens": {"model_id": ".elser_model_2", "model_text": q}}},
                ]
            }
        },
        "_source": ["filename", "drive_url", "chunk_id", "page_start", "page_end", "text"],
        # (optional) You CAN use highlight here because this is NOT using 'retriever/rank'
        # "highlight": {"fields": {"text": {}}, "fragment_size": 140, "number_of_fragments": 1}
    }
    resp = es.search(index=INDEX, body=body, request_timeout=30)
    return format_hits(resp)

def format_hits(resp):
    out = []
    for h in resp["hits"]["hits"]:
        s = h.get("_source", {})
        out.append({
            "score": h.get("_score"),
            "filename": s.get("filename"),
            "drive_url": s.get("drive_url"),
            "chunk_id": s.get("chunk_id"),
            "page_range": [s.get("page_start"), s.get("page_end")],
            "snippet": (s.get("text") or "")[:200],
        })
    return out


# def hybrid_rrf(query: str, k: int = 5):
#
#     vec = embed_query(query)  # -> list[float] length 384
#
#     size = int(k)
#     rank_window_size = max(50, size)   # typical default; must be >= size
#     knn_k = max(rank_window_size, 50)  # ensure k is big enough for RRF
#     num_candidates = max(100, knn_k)
#
#     body = {
#         "size": size,
#         "retriever": {
#             "rrf": {
#                 "retrievers": [
#                     # Lexical (BM25)
#                     {
#                         "standard": {
#                             "query": {
#                                 "multi_match": {
#                                     "query": query,
#                                     "fields": ["text^2", "filename"],
#                                     "type": "best_fields"
#                                 }
#                             }
#                         }
#                     },
#                     # ELSER (sparse semantic) — still using text_expansion for now
#                     {
#                         "standard": {
#                             "query": {
#                                 "text_expansion": {
#                                     "ml.tokens": {
#                                         "model_id": ".elser_model_2",
#                                         "model_text": query
#                                     }
#                                 }
#                             }
#                         }
#                     },
#                     # Dense kNN
#                     {
#                         "knn": {
#                             "field": "vector",
#                             "query_vector": vec,
#                             "k": knn_k,
#                             "num_candidates": num_candidates
#                         }
#                     }
#                 ],
#                 "rank_window_size": rank_window_size,
#                 "rank_constant": 60
#             }
#         },
#         "_source": ["filename", "drive_url", "chunk_id", "page_start", "page_end", "text"],
#         "highlight": {
#             "fields": {"text": {}},
#             "fragment_size": 140,
#             "number_of_fragments": 1
#         }
#     }
#
#     resp = es.search(index=INDEX, body=body, request_timeout=30)
#     return format_hits(resp)
def hybrid_rrf(q: str, k: int = 5):
    qvec = embed_query(q)  # 384-dim normalized vector (MiniLM-L6-v2)

    body = {
        "size": k,
        "retriever": {
            "rrf": {
                "retrievers": [
                    {"standard": {"query": {"multi_match": {
                        "query": q, "fields": ["text^2", "filename"], "type": "best_fields"
                    }}}},
                    {"standard": {"query": {"text_expansion": {
                        "ml.tokens": {"model_id": ".elser_model_2", "model_text": q}
                    }}}},
                    {"knn": {"field": "vector", "query_vector": qvec, "k": 50, "num_candidates": 100}}
                ],
                "rank_window_size": 50,
                "rank_constant": 60
            }
        },
        "_source": ["filename", "drive_url", "chunk_id", "page_start", "page_end", "text"]
        # DO NOT include "highlight" here — ES forbids highlighter with rank/RRF
    }
    resp = es.search(index=INDEX, body=body, request_timeout=30)
    return format_hits(resp)


