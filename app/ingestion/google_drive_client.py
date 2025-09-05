# app/ingestion/google_drive_client.py
import io
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.ingestion.models import DriveFile
from app.utils.settings import settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

class DriveClient:
    def __init__(self, folder_id: str | None = None):
        self.folder_id = folder_id or settings.gdrive_folder_id
        if not self.folder_id:
            raise ValueError("GDRIVE_FOLDER_ID is not set (env or argument).")

        creds = service_account.Credentials.from_service_account_file(
            settings.gdrive_sa_json_path, scopes=SCOPES
        )
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_pdfs(self, page_size: int = 100) -> List[DriveFile]:
        q = f"'{self.folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        resp = self.svc.files().list(
            q=q,
            fields="files(id, name, webViewLink, modifiedTime)",
            orderBy="modifiedTime desc",
            pageSize=page_size,
        ).execute()
        files = resp.get("files", [])
        return [
            DriveFile(
                file_id=f["id"],
                filename=f["name"],
                drive_url=f.get("webViewLink", ""),
                modified_time=f.get("modifiedTime"),
            )
            for f in files
        ]

    def download_pdf_bytes(self, file_id: str) -> bytes:
        request = self.svc.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()
