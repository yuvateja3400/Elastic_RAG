import os
from elasticsearch import Elasticsearch

ES_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
ES_USER = os.getenv("ELASTIC_USERNAME", "elastic")
ES_PASS = os.getenv("ELASTIC_PASSWORD", "changeme")
INDEX   = os.getenv("ELASTIC_INDEX_NAME", "rag_documents_v1")
PIPE_ID = os.getenv("ELSER_PIPELINE_ID", "elser_v2_pipeline")

es = Elasticsearch(ES_URL, basic_auth=(ES_USER, ES_PASS), request_timeout=60)

# 1) Create index with mapping (idempotent)
mapping = {
  "mappings": {
    "properties": {
      "chunk_id":   {"type":"keyword"},
      "drive_url":  {"type":"keyword"},
      "file_id":    {"type":"keyword"},
      "filename":   {"type":"keyword"},
      "ingested_at":{"type":"date"},
      "page_start": {"type":"integer"},
      "page_end":   {"type":"integer"},
      "text":       {"type":"text"},
      "ml": {
        "properties": {
          "model_id": {"type":"keyword"},
          "tokens":   {"type":"rank_features"}
        }
      },
      "vector": {
        "type":"dense_vector", "dims":384, "index":True, "similarity":"cosine",
        "index_options":{"type":"int8_hnsw","m":16,"ef_construction":100}
      }
    }
  }
}

if not es.indices.exists(index=INDEX):
    es.indices.create(index=INDEX, **mapping)

# 2) Upsert pipeline (idempotent)
pipeline = {
  "description": "ELSER v2: write rank_features to ml.tokens from text",
  "processors": [{
    "inference": {
      "model_id": ".elser_model_2",
      "inference_config": { "text_expansion": { "results_field": "tokens" } },
      "field_map": { "text": "text" },
      "target_field": "ml"
    }
  }]
}
es.ingest.put_pipeline(id=PIPE_ID, processors=pipeline["processors"],
                       description=pipeline["description"])

# 3) Attach pipeline as default (idempotent)
es.indices.put_settings(index=INDEX, settings={
  "index": { "default_pipeline": PIPE_ID }
})

print("Bootstrap complete:", INDEX, PIPE_ID)
