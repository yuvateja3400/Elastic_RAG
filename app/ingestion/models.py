# app/ingestion/models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import uuid4

class DriveFile(BaseModel):
    file_id: str
    filename: str
    drive_url: str
    modified_time: Optional[str] = None  # RFC3339 from Drive

class PageText(BaseModel):
    page_number: int  # 1-indexed
    text: str

class Chunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid4()))
    file_id: str
    filename: str
    drive_url: str
    page_start: int
    page_end: int
    ingested_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    text: str
