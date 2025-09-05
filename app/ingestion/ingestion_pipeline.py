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
        return {"indexed": 0}

    es = make_es()
    index = os.getenv("ELASTIC_INDEX_NAME", "rag_documents_v1")
    pipeline = os.getenv("ELSER_PIPELINE_ID", "elser_v2_pipeline")

    dense = embed_texts([c.text for c in chunks])  # batch embed

    actions = []
    for c, v in zip(chunks, dense):
        doc = {
            "text": c.text,
            "vector": v,
            "file_id": c.file_id,
            "filename": c.filename,
            "drive_url": c.drive_url,
            "chunk_id": c.chunk_id,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "ingested_at": c.ingested_at,
        }
        actions.append(
            {
                "_op_type": "index",
                "_index": index,
              #  "pipeline": pipeline,
                "_id": c.chunk_id,
                "_source": doc,
            }
        )

    ok, resp = helpers.bulk(
        es,
        actions,
        request_timeout=600,  # more generous for first run
        chunk_size=50  # smaller batches avoid long single waits
    )
    # helpers.bulk returns (success_count, details). On some versions resp isn't a dict; handle safely.
    took = resp.get("took") if isinstance(resp, dict) else None
    return {"indexed": ok, "took": took}
