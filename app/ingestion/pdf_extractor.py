#
# # app/ingestion/pdf_extractor.py
# from typing import List
# import fitz  # PyMuPDF
#
# from app.ingestion.models import PageText
#
# def extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> List[PageText]:
#     pages: List[PageText] = []
#     with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
#         for i, page in enumerate(doc):
#             # "text" gives reading-order text; "blocks" can be used if you need structure later
#             txt = page.get_text("text") or ""
#             # normalize whitespace a bit
#             cleaned = " ".join(txt.split())
#             pages.append(PageText(page_number=i + 1, text=cleaned))
#     return pages

# app/ingestion/pdf_extractor.py
from typing import List

from pdf2image import convert_from_bytes
import pytesseract

from app.ingestion.models import PageText

def extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> List[PageText]:
    """
    Render each PDF page to an image and OCR it with pytesseract.
    Returns a list of PageText(page_number, text).
    """
    pages: List[PageText] = []

    # Render PDF -> images (use higher DPI for better OCR)
    images = convert_from_bytes(pdf_bytes, dpi=150)  # requires poppler

    for i, img in enumerate(images, start=1):
        # OCR the page image
        txt = pytesseract.image_to_string(img) or ""

        # Normalize whitespace a bit
        cleaned = " ".join(txt.split())

        pages.append(PageText(page_number=i, text=cleaned))

    return pages
