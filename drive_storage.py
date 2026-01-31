from __future__ import annotations
import io
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def get_drive_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)

def _client():
    return get_drive_service()

FOLDER_MIME = "application/vnd.google-apps.folder"

def ensure_folder(service, parent_id: str, folder_name: str) -> str:
    q = (
        f"mimeType='{FOLDER_MIME}' and "
        f"name='{folder_name}' and "
        f"'{parent_id}' in parents and trashed=false"
    )
    res = service.files().list(q=q, spaces="drive", fields="files(id,name)", pageSize=10).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    meta = {"name": folder_name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
    created = service.files().create(body=meta, fields="id").execute()
    return created["id"]

def list_children(parent_id: str):
    service = get_drive_service()
    res = service.files().list(
        q=f"'{parent_id}' in parents and trashed=false",
        spaces="drive",
        fields="files(id,name,mimeType,webViewLink)",
        pageSize=1000,
    ).execute()
    return res.get("files", [])

def upload_bytes(parent_id: str, filename: str, content: bytes, mime: str):
    service = get_drive_service()
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime, resumable=False)
    meta = {"name": filename, "parents": [parent_id]}
    return service.files().create(body=meta, media_body=media, fields="id,webViewLink").execute()

def upload_file(parent_id: str, content, filename: str, mime: str):
    if isinstance(content, str) and os.path.exists(content):
        with open(content, "rb") as f:
            data = f.read()
        return upload_bytes(parent_id, filename, data, mime)
    if isinstance(content, (bytes, bytearray)):
        return upload_bytes(parent_id, filename, bytes(content), mime)
    raise TypeError(f"Unsupported content type: {type(content)}")
