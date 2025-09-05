# app/retrieval/dense.py
from sentence_transformers import SentenceTransformer
from functools import lru_cache
import numpy as np
from typing import List

@lru_cache(maxsize=1)
def _model():
    # CPU-friendly; downloads on first use
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed_texts(texts: List[str]) -> List[List[float]]:
    m = _model()
    vecs = m.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    return [v.astype(np.float32).tolist() for v in vecs]
