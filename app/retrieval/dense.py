from functools import lru_cache
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def _model():
    return SentenceTransformer(MODEL_NAME)

def embed_texts(texts: List[str]) -> List[List[float]]:
    vecs = _model().encode(texts, normalize_embeddings=True)
    if isinstance(vecs, np.ndarray):
        return vecs.tolist()
    return [v for v in vecs]
