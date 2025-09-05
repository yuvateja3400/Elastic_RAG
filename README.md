# Elastic-RAG (Local Ollama + Elasticsearch + FastAPI + Streamlit)

End-to-end Retrieval-Augmented Generation (RAG) you can run locally:
- **Retrieval**: BM25, ELSER v2 (sparse encoder), and dense vector (MiniLM) combined with RRF.
- **Generation**: Ollama running locally on your Mac (default: phi3:mini).
- **API**: FastAPI with `/query`, `/ingest`, `/healthz`.
- **UI**: Streamlit app to ask questions, toggle retrieval mode (ELSER-only vs Hybrid), pick top-K, and view citations.
- **Guardrails**: safe + grounded answers; refuses or answers "I don't know." when evidence is weak.

This README walks you through running the whole stack locally, explains the folder structure, 

If you prefer a one-liner dev script: you already have `dev_up.sh` — we use it below.

## ✨ Features

### Elastic retrieval
- **BM25** (multi-match) on text.
- **ELSER v2** (`.elser_model_2`) via ingest pipeline → `ml.tokens` rank_features.
- **Dense vectors** (`vector`, 384-dims, cosine) using `sentence-transformers/all-MiniLM-L6-v2`.
- **Hybrid RRF**: rank-fusion across BM25 + ELSER + dense KNN (`rank_window_size=50`, `rank_constant=60`).

### Generation: Local Ollama (phi3:mini), fast and offline.

### API: POST `/query`, POST `/ingest`, GET `/healthz`.

### UI: Streamlit with answer, snippets, links, mode toggle, and K slider.

### Guardrails: very short safety check + grounded answers; sources attached.

## 📁 Project Structure

```
elastic-rag/
├─ app/
│  ├─ api/
│  │  └─ server.py                # FastAPI app with /healthz /query /ingest
│  ├─ generation/
│  │  ├─ generator.py             # Calls Ollama (phi3:mini) w/ grounded prompt
│  │  └─ guardrails.py            # is_safe + fallback "I don't know."
│  ├─ infra/
│  │  └─ es_client.py             # Elasticsearch client from .env
│  ├─ retrieval/
│  │  ├─ embedder.py              # MiniLM encoder (384) for dense vectors
│  │  └─ searcher.py              # BM25, ELSER, Dense, Hybrid RRF
│  └─ ui/
│     └─ streamlit_app.py         # Streamlit UI
│
├─ scripts/
│  ├─ ingest_drive_folder.py      # Ingest PDFs (Drive or local), chunk & index
│  ├─ answer.py                   # CLI: generate answer + citations
│  ├─ search.py                   # CLI: run ELSER or Hybrid search
│  └─ bootstrap_es.sh             # Idempotent: create index, ELSER, pipeline
│
├─ data/
│  └─ pdfs/                       # (optional) local PDFs for ingestion
│
├─ dev_up.sh                      # Start: Ollama (local) + FastAPI + UI
├─ docker-compose.yml             # Elasticsearch only (single node, trial)
├─ Makefile                       # Convenience targets (optional)
├─ .env.example                   # Copy → .env and fill in values
└─ README.md
```

## ✅ Prerequisites

- **macOS** with a modern CPU
- **Python 3.10+** (3.11 recommended), pip, virtualenv
- **Docker + Docker Compose** (for Elasticsearch)
- **Ollama** (installed locally) → [https://ollama.com/download](https://ollama.com/download)
- **(Optional)** Google Drive API credentials if ingesting from Drive

## 🔐 Configuration (.env)

Copy `.env.example` → `.env` and adjust:

```bash
# Elasticsearch
ELASTIC_URL=http://localhost:9200
ELASTIC_USERNAME=elastic
ELASTIC_PASSWORD=changeme
ELASTIC_INDEX_NAME=rag_documents_v1

# Ollama (local)
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434
OLLAMA_MODEL=phi3:mini   # <-- you asked to keep this fixed

# Dense embeddings
SENTENCE_TRANSFORMERS_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Ingestion
DOCS_DIR=./data/pdfs                   # local fallback folder of PDFs
GOOGLE_APPLICATION_CREDENTIALS=./secrets/service_account.json  # (optional Drive)
GDRIVE_FOLDER_ID=...                   # (optional Drive folder)
```



## 🚀 Quick Start (Local, end-to-end)

### 1. Start Elasticsearch in Docker
```bash
docker compose up -d elasticsearch
```

### 2. Create a virtual environment & install deps
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 3. Bootstrap Elasticsearch (index, ELSER endpoint, ingest pipeline)
```bash
bash scripts/bootstrap_es.sh
```

### 4. Start everything else (Ollama + API + UI)
Your `dev_up.sh` handles it:
```bash
chmod +x dev_up.sh
./dev_up.sh
```

- API → [http://127.0.0.1:8000/healthz](http://127.0.0.1:8000/healthz)
- UI → [http://127.0.0.1:8501](http://127.0.0.1:8501)

### 5. Ingest documents




Google Drive (requires `GOOGLE_APPLICATION_CREDENTIALS` and `GDRIVE_FOLDER_ID` set in `.env`)

### 6. Ask a question (API)
```bash
curl -sS -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"q":"Who are the main characters in Two Little Soldiers?","k":5,"mode":"hybrid"}' | jq
```

### 7. Use the UI
Open [http://127.0.0.1:8501](http://127.0.0.1:8501), type your question, choose ELSER-only or Hybrid, set K, submit.

## 🧠 How Retrieval Works

### BM25:
`multi_match` over `"text^2"`, `"filename"`.

### ELSER v2 (sparse):
- **Ingest pipeline**: `_ingest/pipeline/elser_v2_pipeline` uses the `.elser_model_2` endpoint to write `ml.tokens` (rank_features).
- **Query**: `text_expansion` (Elastic may warn "deprecated"; in 8.15 it still works. Newer versions use `sparse_vector`.)

### Dense (MiniLM):
- Encode query with MiniLM (384-dims), stored chunks in `vector`.
- KNN with cosine similarity.

### RRF (Reciprocal Rank Fusion):
- Fuses three ranked lists (BM25, ELSER, Dense).
- Tunables: `rank_window_size=50`, `rank_constant=60`.

**Why Hybrid?** On domain PDFs, ELSER often boosts recall on niche wording; dense helps with paraphrase; BM25 keeps lexical precision. RRF gives the best of all three.

## 🧩 API

**Base**: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### GET `/healthz`
Returns status of Elasticsearch & Ollama.
```json
{"elasticsearch": true, "ollama": true}
```

### POST `/query`

**Body**
```json
{
  "q": "Who are the main characters in Two Little Soldiers?",
  "k": 5,
  "mode": "hybrid"      // "elser" or "hybrid"
}
```

**Response**
```json
{
  "answer": "Main characters are ...",
  "citations": [
    {
      "filename": "two-little-soldiers.pdf",
      "drive_url": "https://drive.google.com/...",
      "chunk_id": "uuid",
      "page_start": 2,
      "page_end": 2,
      "snippet": "…short highlighted excerpt…"
    }
  ]
}
```

**Guardrails:**
- If unsafe → `{"answer": "I can't help with that.", "citations":[]}`
- If not enough evidence → `{"answer": "I don't know.", "citations":[]}`

### POST `/ingest`
Re-scans Drive (if configured) or `DOCS_DIR` and indexes chunks.
Kicks off async ELSER token backfill via `update-by-query`.

## 🖥️ UI (Streamlit)

- Input your question
- Toggle ELSER-only vs Hybrid
- Choose K
- View answer + citations (title/link/snippet)

Run on its own (if needed):
```bash
export RAG_API_BASE=http://127.0.0.1:8000
streamlit run app/ui/streamlit_app.py --server.port 8501
```

## 🔄 Ingestion & Re-indexing

- **Initial indexing** writes: `filename`, `drive_url`, `text`, `vector` (dense), etc.
- **ELSER tokens** are added via `_update_by_query` pipeline:

```bash
curl -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" -H 'Content-Type: application/json' \
  -X POST "$ELASTIC_URL/$ELASTIC_INDEX_NAME/_update_by_query?pipeline=elser_v2_pipeline&conflicts=proceed&slices=auto" \
  -d '{"query":{"exists":{"field":"text"}}}'
```

- **Re-running ingestion** on the same files typically adds new chunks or updates existing ones by `chunk_id`. (Your ingestor is idempotent if `chunk_id` is stable.)
- **Persistence**: Once indexed, chunks remain until you delete the index. To reset:

```bash
curl -u "$ELASTIC_USERNAME:$ELASTIC_PASSWORD" -X DELETE "$ELASTIC_URL/$ELASTIC_INDEX_NAME"
```

## 🧰 CLI Utilities

```bash
# Search only (ELSER or Hybrid), print top K hits
python -m scripts.search --mode hybrid --q "refund policy for cancellations" --k 5

# Full answer (generation + citations)
python -m scripts.answer --mode hybrid --q "Who are the main characters in Two Little Soldiers?" --k 5
```

## 🛡️ Guardrails

- **Safety**: `is_safe()` blocks disallowed prompts with a short refusal.
- **Grounding**: the generator builds answers only from retrieved chunks; if evidence is weak or contradictory, it answers "I don't know."
- **Citations**: every answer includes the supporting chunks' filename, page range, link, and snippet.

## 🧪 Tips & Troubleshooting

### Ollama model not found
API says: `model 'phi3:mini' not found` → pull it:
```bash
ollama pull phi3:mini
```

### ELSER inference timeouts
First requests are slower. Ensure the ingest pipeline exists and `.elser_model_2` endpoint is up (bootstrap script does this).

### 401 from Elasticsearch
`.env` credentials must match the Docker ES (`ELASTIC_PASSWORD`).

### "text_expansion is deprecated" warning
Safe to ignore on 8.15; upgrade path is `sparse_vector` queries in 8.16+.

## 🧭 Evaluation Criteria Mapping

- **Correctness**: end-to-end RAG (ingest → retrieve → generate) is implemented and verified via API/UI/CLI.
- **Code quality**: modular packages (infra, retrieval, generation, api, ui) with docstrings and comments.
- **Elastic usage**: ELSER v2, dense vectors, BM25, Hybrid RRF all in place.
- **API & UI**: working FastAPI + Streamlit; answers include citations.
- **Guardrails**: safety check + grounded generation & "I don't know." policy.
- **Creativity (bonus)**: clean RRF, optional update-by-query token backfill, and a one-shot `dev_up.sh`.


## 📚 References / Sources

### Elasticsearch
- **ELSER v2 and inference pipeline**: [https://www.elastic.co/guide](https://www.elastic.co/guide)
- **Rank features & text expansion**: [https://www.elastic.co/guide/en/elasticsearch/reference/current/rank-feature.html](https://www.elastic.co/guide/en/elasticsearch/reference/current/rank-feature.html)
- **KNN dense vectors**: [https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html)
- **Reciprocal Rank Fusion**: [https://www.elastic.co/guide/en/elasticsearch/reference/current/search-ranker-rrf.html](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-ranker-rrf.html)

### Other Tools
- **Ollama (local LLMs)**: [https://ollama.com](https://ollama.com)
- **SentenceTransformers (MiniLM)**: [https://www.sbert.net](https://www.sbert.net)
- **FastAPI**: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Streamlit**: [https://streamlit.io](https://streamlit.io)


