import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
KEY_PATH = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON_PATH")

def main():
    if not FOLDER_ID or not KEY_PATH:
        raise RuntimeError("Set GDRIVE_FOLDER_ID and GDRIVE_SERVICE_ACCOUNT_JSON_PATH in your .env")

    creds = service_account.Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )

    svc = build("drive", "v3", credentials=creds)

    # List PDFs in the folder
    query = f"'{FOLDER_ID}' in parents and mimeType='application/pdf' and trashed=false"
    results = svc.files().list(
        q=query,
        fields="files(id, name, webViewLink, modifiedTime, mimeType)",
        pageSize=20,
        orderBy="modifiedTime desc"
    ).execute()

    files = results.get("files", [])
    print(f"[{datetime.utcnow().isoformat()}Z] Found {len(files)} PDFs in folder {FOLDER_ID}")
    for f in files[:10]:
        print(f"- {f['name']}  | id={f['id']}  | link={f.get('webViewLink')}  | modified={f.get('modifiedTime')}")

if __name__ == "__main__":
    main()
