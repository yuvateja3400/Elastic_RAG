# app/ingestion/pdf_extractor.py
from typing import List
import fitz  # PyMuPDF

from app.ingestion.models import PageText

def extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> List[PageText]:
    pages: List[PageText] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            # "text" gives reading-order text; "blocks" can be used if you need structure later
            txt = page.get_text("text") or ""
            # normalize whitespace a bit
            cleaned = " ".join(txt.split())
            pages.append(PageText(page_number=i + 1, text=cleaned))
    return pages
