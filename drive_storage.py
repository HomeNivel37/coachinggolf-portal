from __future__ import annotations
import io
from typing import Optional, Iterable
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive"]

def _client():
    info = dict(st.secrets["google_service_account"])
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)

def ensure_folder(service, parent_id: str, name: str) -> str:
    q = f"mimeType='application/vnd.google-apps.folder' and name='{name}' and '{parent_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id,name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType":"application/vnd.google-apps.folder", "parents":[parent_id]}
    f = service.files().create(body=meta, fields="id").execute()
    return f["id"]

def upload_bytes(parent_id: str, filename: str, data: bytes, mime: str) -> str:
    service = _client()
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
    meta = {"name": filename, "parents":[parent_id]}
    f = service.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
    return f["id"]

def upload_file(parent_id: str, filepath: str, filename: Optional[str]=None, mime: str="application/octet-stream") -> str:
    with open(filepath, "rb") as f:
        return upload_bytes(parent_id, filename or filepath.split("/")[-1], f.read(), mime)

def list_children(parent_id: str, mime_prefix: Optional[str]=None):
    service = _client()
    q = f"'{parent_id}' in parents and trashed=false"
    res = service.files().list(q=q, fields="files(id,name,mimeType,modifiedTime,webViewLink)").execute()
    files = res.get("files", [])
    if mime_prefix:
        files = [x for x in files if x["mimeType"].startswith(mime_prefix)]
    return files
