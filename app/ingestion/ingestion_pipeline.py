# app/ingestion/ingestion_pipeline.py
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

from tqdm import tqdm
from elasticsearch import helpers

from app.ingestion.google_drive_client import DriveClient
from app.ingestion.pdf_extractor import extract_pages_from_pdf_bytes
from app.ingestion.chunker import chunk_pages
from app.ingestion.models import Chunk
from app.storage.elastic_client import make_es
from app.retrieval.dense import embed_texts
from app.utils.settings import settings


def run_ingestion(
    folder_id: Optional[str] = None,
    limit_files: Optional[int] = None,
) -> tuple[Dict[str, Any], List[Chunk]]:
    """
    Drive folder -> download PDFs -> extract page text -> chunk (~300 tokens, overlap).
    Returns a (report, chunks) tuple. Does NOT index to Elasticsearch.
    """
    dc = DriveClient(folder_id)
    files = dc.list_pdfs(page_size=100)
    if limit_files:
        files = files[:limit_files]

    out_chunks: List[Chunk] = []
    file_summaries: List[Dict[str, Any]] = []

    for f in tqdm(files, desc="Ingesting PDFs", unit="file"):
        try:
            pdf_bytes = dc.download_pdf_bytes(f.file_id)
            pages = extract_pages_from_pdf_bytes(pdf_bytes)
            chunks = chunk_pages(
                pages,
                file_id=f.file_id,
                filename=f.filename,
                drive_url=f.drive_url,
            )
            out_chunks.extend(chunks)
            file_summaries.append(
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "drive_url": f.drive_url,
                    "pages": len(pages),
                    "chunks": len(chunks),
                }
            )
        except Exception as e:
            file_summaries.append(
                {
                    "file_id": f.file_id,
                    "filename": f.filename,
                    "drive_url": f.drive_url,
                    "error": str(e),
                }
            )

    report = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "folder_id": folder_id or settings.gdrive_folder_id,
        "files_seen": len(files),
        "chunks_total": len(out_chunks),
        "files": file_summaries,
    }
    return report, out_chunks


def write_report(report: Dict[str, Any], path: str = "./tmp/ingestion_report.json") -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2))
    return str(p.resolve())


def index_chunks(chunks: List[Chunk]) -> Dict[str, Any]:
    """
    Bulk-index chunks into Elasticsearch using the ELSER ingest pipeline.
    Populates:
      - text (BM25)
      - vector (dense: MiniLM)
      - ml.tokens (ELSER via ingest pipeline)
    """
    if not chunks:
        return {"indexed": 0, "errors": 0}

    es = make_es()
    index = os.getenv("ELASTIC_INDEX_NAME", "rag_documents_v1")
    pipeline = os.getenv("ELSER_PIPELINE_ID", "elser_v2_pipeline")

    # Embed in one go (your embedder already batches internally if needed)
    dense_vectors = embed_texts([c.text for c in chunks])

    actions = []
    for c, v in zip(chunks, dense_vectors):
        # NOTE: we set the ingest pipeline per op so ELSER writes ml.tokens
        actions.append({
            "_op_type": "index",
            "_index": index,
            "_id": c.chunk_id,
            "pipeline": pipeline,
            "_source": {
                "text": c.text,
                "vector": v,
                "file_id": c.file_id,
                "filename": c.filename,
                "drive_url": c.drive_url,
                "chunk_id": c.chunk_id,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "ingested_at": c.ingested_at,
            },
        })

    # Tunables via env (good defaults for Elastic Cloud)
    chunk_size       = int(os.getenv("INDEX_BULK_CHUNK", "100"))
    request_timeout  = int(os.getenv("INDEX_REQUEST_TIMEOUT", "120"))
    max_retries      = int(os.getenv("INDEX_MAX_RETRIES", "2"))
    initial_backoff  = float(os.getenv("INDEX_BACKOFF", "0.5"))

    indexed = 0
    errors = 0

    # streaming_bulk + refresh="wait_for": data is searchable when we return
    for ok, info in helpers.streaming_bulk(
        es,
        actions,
        chunk_size=chunk_size,
        request_timeout=request_timeout,
        max_retries=max_retries,
        initial_backoff=initial_backoff,
        yield_ok=True,
        raise_on_error=False,
        raise_on_exception=False,
        refresh="wait_for",
    ):
        if ok:
            indexed += 1
        else:
            errors += 1
            try:
                cause = info.get("index", {}).get("error") or info
                print(f"[bulk] failed id={info.get('index', {}).get('_id')} reason={cause}")
            except Exception:
                print(f"[bulk] failed item: {info}")

    # Best-effort final refresh
    try:
        es.indices.refresh(index=index)
    except Exception:
        pass

    return {"indexed": indexed, "errors": errors}
