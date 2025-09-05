# app/ingestion/chunker.py
from typing import List, Tuple
from app.ingestion.models import PageText, Chunk
from app.utils.settings import settings

def _tokenize(text: str) -> List[str]:
    # Lightweight tokenization; good enough for chunk sizing.
    return text.split()

def chunk_pages(
    pages: List[PageText],
    chunk_size: int | None = None,
    overlap: int | None = None,
    file_id: str = "",
    filename: str = "",
    drive_url: str = "",
) -> List[Chunk]:
    """
    Greedy chunking across page boundaries.
    Keeps track of page_start/page_end for each chunk.
    """
    chunk_size = chunk_size or settings.chunk_size_tokens
    overlap = overlap or settings.chunk_overlap_tokens
    assert chunk_size > 0 and overlap >= 0 and overlap < chunk_size

    # Flatten tokens while remembering their originating page
    tokens_with_pages: List[Tuple[str, int]] = []
    for p in pages:
        toks = _tokenize(p.text)
        tokens_with_pages.extend((t, p.page_number) for t in toks)

    chunks: List[Chunk] = []
    if not tokens_with_pages:
        return chunks

    step = chunk_size - overlap
    start = 0
    n = len(tokens_with_pages)

    while start < n:
        end = min(start + chunk_size, n)
        window = tokens_with_pages[start:end]
        text = " ".join(t for t, _ in window).strip()
        pages_in_window = [pg for _, pg in window]
        page_start = min(pages_in_window) if pages_in_window else 1
        page_end = max(pages_in_window) if pages_in_window else page_start

        if text:
            chunks.append(
                Chunk(
                    file_id=file_id,
                    filename=filename,
                    drive_url=drive_url,
                    page_start=page_start,
                    page_end=page_end,
                    text=text,
                )
            )
        if end == n:
            break
        start += step

    return chunks
