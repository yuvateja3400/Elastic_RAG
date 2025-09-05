
## Status
- FR1 Ingestion ✅ (Drive → chunking + metadata)
- FR2 Indexing ✅ (BM25 + dense vectors; ELSER tokens via pipeline/backfill)
- Next: FR3 Retrieval (ELSER-only, Hybrid RRF)

### Backfill task I ran (for reference)
POST /rag_documents_v1/_update_by_query?pipeline=elser_v2_pipeline&conflicts=proceed&wait_for_completion=false&slices=auto
