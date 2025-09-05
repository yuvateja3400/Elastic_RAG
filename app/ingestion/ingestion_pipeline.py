# app/ingestion/ingestion_pipeline.py
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from tqdm import tqdm

from app.ingestion.google_drive_client import DriveClient
from app.ingestion.pdf_extractor import extract_pages_from_pdf_bytes
from app.ingestion.chunker import chunk_pages
from app.ingestion.models import Chunk
from app.utils.settings import settings

def run_ingestion(
    folder_id: Optional[str] = None,
    limit_files: Optional[int] = None,
) -> Dict[str, Any]:
    dc = DriveClient(folder_id)
    files = dc.list_pdfs(page_size=100)
    if limit_files:
        files = files[:limit_files]

    out_chunks: List[Chunk] = []
    file_summaries = []

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
        # NOTE: We do not include full chunk texts in the report to keep it small.
    }
    return report, out_chunks

def write_report(report: Dict[str, Any], path: str = "./tmp/ingestion_report.json") -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2))
    return str(p.resolve())
