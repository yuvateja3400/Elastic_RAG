#!/usr/bin/env bash
set -euo pipefail

ES_URL="${ELASTIC_URL:-http://localhost:9200}"
ES_USER="${ELASTIC_USERNAME:-elastic}"
ES_PASS="${ELASTIC_PASSWORD:-changeme}"
INDEX="${ELASTIC_INDEX_NAME:-rag_documents_v1}"
ELSER_EP="${ELSER_ENDPOINT_ID:-elser_v2_endpoint}"
PIPELINE="${ELSER_PIPELINE_ID:-elser_v2_pipeline}"

auth=(-u "$ES_USER:$ES_PASS" -H "Content-Type: application/json")

echo "1) Create index: $INDEX"
curl -sS "${auth[@]}" -X PUT "$ES_URL/$INDEX" \
  -d @- <<'JSON'
{
  "mappings": {
    "properties": {
      "text": { "type": "text" },
      "vector": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      },
      "ml": {
        "properties": {
          "tokens": { "type": "sparse_vector" }
        }
      },
      "file_id":   { "type": "keyword" },
      "filename":  { "type": "keyword" },
      "drive_url": { "type": "keyword" },
      "chunk_id":  { "type": "keyword" },
      "page_start":{ "type": "integer" },
      "page_end":  { "type": "integer" },
      "ingested_at": { "type": "date" }
    }
  }
}
JSON
echo

echo "2) Create ELSER inference endpoint (auto-download .elser_model_2) → $ELSER_EP"
curl -sS "${auth[@]}" -X PUT "$ES_URL/_inference/sparse_embedding/$ELSER_EP" \
  -d '{
    "service": "elasticsearch",
    "service_settings": {
      "adaptive_allocations": { "enabled": true, "min_number_of_allocations": 1, "max_number_of_allocations": 2 },
      "num_threads": 1,
      "model_id": ".elser_model_2"
    }
  }'
echo

echo "3) Create ingest pipeline to write ELSER tokens into ml.tokens"
curl -sS "${auth[@]}" -X PUT "$ES_URL/_ingest/pipeline/$PIPELINE" \
  -d "{
    \"description\": \"ELSER v2 tokens -> ml.tokens from text\",
    \"processors\": [
      {
        \"inference\": {
          \"model_id\": \"$ELSER_EP\",
          \"input_output\": [
            { \"input_field\": \"text\", \"output_field\": \"ml.tokens\" }
          ]
        }
      }
    ]
  }"
echo

echo "✅ Bootstrap complete."
