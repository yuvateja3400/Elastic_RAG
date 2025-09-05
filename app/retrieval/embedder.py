# app/retrieval/embedder.py
from functools import lru_cache
from typing import List
import os

# We use all-MiniLM-L6-v2 (384 dims) to match your index mapping
DEFAULT_MODEL = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer
    # Let ST/torch pick CPU automatically; works on any machine
    return SentenceTransformer(DEFAULT_MODEL)

def embed_query(text: str) -> List[float]:
    """
    Returns a single normalized embedding (list of floats) for the query string.
    """
    model = _get_model()
    # normalize_embeddings=True gives cosine-normalized vectors (what ES expects for cosine similarity)
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()

# Optional helper if you ever need batch embedding later
def embed_texts(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
