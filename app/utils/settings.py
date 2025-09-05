# app/utils/settings.py

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
class Settings(BaseSettings):
    # Google Drive
    gdrive_folder_id: Optional[str] = Field(None, alias="GDRIVE_FOLDER_ID")
    gdrive_sa_json_path: str = Field(..., alias="GDRIVE_SERVICE_ACCOUNT_JSON_PATH")

    # Chunking
    chunk_size_tokens: int = Field(300, alias="CHUNK_SIZE_TOKENS")
    chunk_overlap_tokens: int = Field(60, alias="CHUNK_OVERLAP_TOKENS")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

settings = Settings()  # loads from .env
