# Elastic-RAG (ELSER + Hybrid Retrieval)

A RAG stack that ingests PDFs from Google Drive, chunks them, writes dense vectors + ELSER sparse tokens to Elasticsearch, and serves a QA API with a Streamlit UI. Generation uses a local Ollama model.

![Project Workflow Diagram](docs/Copy%20of%20Untitled%20Diagram.drawio%20(1).png)

*The diagram above illustrates the complete data flow from PDF ingestion through retrieval and generation.*

## Project Highlights
- **OCR-based text extraction**: Uses OCR + PDF parsing to handle both digital and scanned PDFs during ingestion.  
- **Elasticsearch Cloud Migration**: Originally built against on-prem Elasticsearch, now migrated to **Elastic Cloud** with API Key authentication for easier deployment and scaling.  
- **Hybrid Retrieval**: Combines BM25, ELSER v2 sparse vectors, and dense MiniLM embeddings.  
- **Citations**: Answers are grounded in evidence with citations (filename, Drive link, page ranges, snippets).  
- **Guardrails**: Refuses unsafe/off-topic queries and answers
## Stack

- **Ingestion**: Google Drive → PDF text extraction → chunking
- **Retrieval**: Hybrid (BM25 + ELSER sparse + dense kNN) or ELSER-only
- **Vector model**: MiniLM (384-d)
- **Sparse (ELSER)**: `.elser_model_2_linux-x86_64` via ingest pipeline
- **Store**: Elasticsearch (Cloud)
- **LLM**: Ollama (default: llama3.2:1b, changeable)
- **API**: FastAPI (/query, /ingest, /healthz)
- **UI**: Streamlit (simple QA app with citations)

## Project Structure

```
app/
  api/
    __init__.py
    server.py                 # FastAPI app + endpoints (query / ingest / health)
  core/
    config.py                 # env + settings helpers (ES, index name, etc.)
  generation/
    generator.py              # prompt builder + LLM call wrapper
    guardrails.py             # question sanitization + minimal guardrails
  infra/
    __init__.py
    es_client.py              # shared Elasticsearch client factory
  ingestion/
    __init__.py
    chunker.py                # chunking logic
    google_drive_client.py    # Drive listing + download
    ingestion_pipeline.py     # Orchestrates ingest + bulk index
    models.py                 # data models for chunks
    pdf_extractor.py          # extract text from PDFs
  retrieval/
    __init__.py
    dense.py                  # dense embedding model (MiniLM) for chunks
    embedder.py               # query embedding
    searcher.py               # ELSER-only & Hybrid RRF search
  storage/
    __init__.py
    elastic_client.py         # older ES client (kept for compatibility)
  ui/
    streamlit_app.py          # Streamlit UI
  utils/
    __init__.py
data/
docs/
infra/
logs/
  api.log
  ollama.log
  ui.log
scripts/
tmp/
    ingestion_report.json     #Ingestion report    
.env.example
requirements.txt
README.md  ← (this file)
```

## Prerequisites

- Python 3.11
- Elasticsearch Cloud deployment (8.15+)
- Ollama installed locally (`brew install ollama`) and a model pulled (default `llama3.2:1b`)
- (Optional) Google Drive service account creds if you plan to ingest from Drive

## Setup

### 1) Create and fill your .env

Copy `.env.example` → `.env` and fill these (minimum):

```bash
# ---- Elasticsearch Cloud ----
ES_URL=https://<your-deployment-id>.<region>.<provider>.elastic-cloud.com
ES_API_KEY=<your-base64-api-key>
ES_INDEX_NAME=rag_documents_v1

# In Cloud the ELSER artifact id includes arch
ELSER_MODEL_ID=.elser_model_2_linux-x86_64
ELSER_PIPELINE_ID=elser_v2_pipeline

# ---- Ollama ----
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b

# ---- Drive (optional) ----
GDRIVE_FOLDER_ID=<folder-with-pdfs>
GOOGLE_APPLICATION_CREDENTIALS=./secrets/service-account.json
```

**Note**: The code uses API Key auth for Elasticsearch Cloud. Don't set `ES_USERNAME`/`ES_PASSWORD` unless you really need Basic auth.

### 2) Create index mapping (once)

Your index needs a text field, a dense vector, and a rank_features field for ELSER tokens:

```bash
curl -X PUT "$ES_URL/$ES_INDEX_NAME" \
  -H "Authorization: ApiKey $ES_API_KEY" \
  -H "Content-Type: application/json" -d '{
  "mappings": {
    "properties": {
      "text":   { "type": "text" },
      "vector": { "type": "dense_vector", "dims": 384, "index": true, "similarity": "cosine" },
      "ml": {
        "properties": {
          "tokens": { "type": "rank_features" }
        }
      },
      "filename":  { "type": "keyword" },
      "drive_url": { "type": "keyword" },
      "chunk_id":  { "type": "keyword" },
      "page_start":{ "type": "integer" },
      "page_end":  { "type": "integer" },
      "ingested_at": { "type": "date" }
    }
  }
}'
```

If it already exists you'll get `resource_already_exists_exception` (that's fine).

### 3) Deploy ELSER in Elastic Cloud

Open Kibana → Machine Learning → Trained Models and deploy:
- **Model ID**: `.elser_model_2_linux-x86_64`
- Single allocation is fine for testing

Create the ingest pipeline to write ELSER tokens into `ml.tokens`. We index documents with field `text`, so map ELSER's default input (`text_field`) → `text`:

```bash
curl -X PUT "$ES_URL/_ingest/pipeline/$ELSER_PIPELINE_ID" \
  -H "Authorization: ApiKey $ES_API_KEY" \
  -H "Content-Type: application/json" -d '{
    "description": "ELSER v2 (Cloud) → ml.tokens from `text`",
    "processors": [
      {
        "inference": {
          "model_id": ".elser_model_2_linux-x86_64",
          "inference_config": { "text_expansion": { "results_field": "tokens" } },
          "field_map": { "text_field": "text" },
          "target_field": "ml"
        }
      }
    ]
  }'
```

**Quick sanity check**:

```bash
curl -X POST "$ES_URL/_ingest/pipeline/$ELSER_PIPELINE_ID/_simulate?pretty" \
  -H "Authorization: ApiKey $ES_API_KEY" \
  -H "Content-Type: application/json" -d '{
    "docs":[{"_source":{"text":"The Moon is Earth'\''s only natural satellite."}}]
  }'
```

You should see `ml.tokens` populated in the response.

### 4) Install & run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Ollama (if not already)
ollama serve &
ollama pull llama3.2:1b

# Start the FastAPI server
uvicorn app.api.server:app --reload --log-config logging.ini 2>&1 | tee logs/api.log

# In another terminal, launch the UI
streamlit run app/ui/streamlit_app.py 2>&1 | tee logs/ui.log
```

Open the UI at the URL printed by Streamlit (usually [http://localhost:8501](http://localhost:8501)).

### 5) Ingest PDFs

From the UI sidebar you can kick off **Re-ingest**. Or via API:

```bash
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" -d '{"limit": 50, "index": true}'
```

The ingestion pipeline:
1. Downloads PDFs from the configured Drive folder
2. Extracts text, chunks (~300 tokens w/ overlap)
3. Embeds each chunk to vector
4. Indexes to `$ES_INDEX_NAME` through `$ELSER_PIPELINE_ID` so `ml.tokens` is created

### 6) Ask questions

From the UI, choose **Hybrid** or **ELSER-only** and ask away.

**API example**:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"q":"What is the subscription business model?", "k":5, "mode":"hybrid"}'
```

Response contains the answer and a citations array (filename, drive_url, page range, snippet, score).

## Health Check

- UI sidebar shows API health.
- API endpoint: `GET /healthz` returns:

```json
{"elasticsearch":{"ok":true,"cluster":"yellow","model_deployed":true},"ollama":true}
```

## Notes, Gotchas & Troubleshooting

- **401 / auth errors**: ensure you are using `ES_API_KEY` (Cloud) and not Basic auth.
- **ELSER model not found**: use Cloud model id `.elser_model_2_linux-x86_64` and double-check the ingest pipeline `model_id`.
- **"Input field [text_field] does not exist"**: your pipeline `field_map` must map `"text_field": "text"` if your documents store content in `text`.
- **TLS warnings**: the ES client is created with `verify_certs=False` for simplicity. For production, configure the CA bundle and set verification to True.
- **Deprecated warning**: `text_expansion` shows a deprecation notice; it still works. Migrating to `sparse_vector` is a future improvement.
- **No snippet/page range**: the API now synthesizes a snippet from matching terms and returns `page_start`/`page_end`. Make sure your index actually stored those fields during ingest.
- **Model throughput**: ELSER single allocation is fine for dev; increase allocations/threads for production.

## Minimal Guardrails

Implemented in `app/generation/guardrails.py`:
- Sanitize & length-limit user questions
- Very small deny-list for harmful intent
- The prompt instructs the LLM to answer only from retrieved passages and say "I don't know." if evidence is weak/absent

You can extend the deny-list (`HARMFUL_PATTERNS`) to tighten behavior without over-blocking.

## Environment Variables

| Variable | Example | Notes |
|----------|---------|-------|
| `ES_URL` | `https://my-deployment.es.us-central1.gcp.elastic.cloud` | Cloud endpoint |
| `ES_API_KEY` | `abc123...` | Prefer API Key in Cloud |
| `ES_INDEX_NAME` | `rag_documents_v1` | Target index |
| `ELSER_MODEL_ID` | `.elser_model_2_linux-x86_64` | Cloud model id |
| `ELSER_PIPELINE_ID` | `elser_v2_pipeline` | Ingest pipeline name |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama |
| `OLLAMA_MODEL` | `llama3.2:1b` | Any pulled model |
| `GDRIVE_FOLDER_ID` | `1AbC...` | Folder with PDFs |

## Roadmap / Nice-to-haves

- Batch ingest progress reporting via websocket
- Optional Azure/GCS S3-like storage for PDFs
- Auth for the API/UI

## License

MIT (see LICENSE)
