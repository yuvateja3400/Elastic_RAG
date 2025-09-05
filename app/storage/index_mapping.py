# app/storage/index_mapping.py
def rag_index_mapping(dims: int = 384) -> dict:
    return {
        "mappings": {
            "properties": {
                # Core content
                "text": {"type": "text"},            # BM25
                "vector": {                          # Dense kNN
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine"
                },
                "ml": {                              # ELSER tokens
                    "properties": {
                        "tokens": {"type": "sparse_vector"}
                    }
                },

                # Metadata
                "file_id":   {"type": "keyword"},
                "filename":  {"type": "keyword"},
                "drive_url": {"type": "keyword"},
                "chunk_id":  {"type": "keyword"},
                "page_start":{"type": "integer"},
                "page_end":  {"type": "integer"},
                "ingested_at":{"type": "date"}
            }
        }
    }
