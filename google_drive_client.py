"""Google Drive client – create folders and upload PDFs."""
from __future__ import annotations

import io
import json
import logging
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_credentials() -> service_account.Credentials:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def _drive():
    return build("drive", "v3", credentials=_get_credentials(), cache_discovery=False)


def create_folder(name: str, parent_id: str | None = None) -> str:
    """Create a folder in Google Drive. Returns folder ID."""
    parent = parent_id or os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID", "")
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent:
        metadata["parents"] = [parent]

    folder = _drive().files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    logger.info("Created Drive folder '%s' → %s", name, folder_id)
    return folder_id


def upload_pdf(file_bytes: bytes, filename: str, folder_id: str) -> str:
    """Upload PDF bytes to a Drive folder. Returns file ID."""
    media = MediaIoBaseUpload(
        io.BytesIO(file_bytes),
        mimetype="application/pdf",
        resumable=False,
    )
    uploaded = _drive().files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    file_id = uploaded["id"]
    logger.info("Uploaded '%s' → %s", filename, file_id)
    return file_id


def get_folder_link(folder_id: str) -> str:
    """Return a shareable link to a Drive folder."""
    return f"https://drive.google.com/drive/folders/{folder_id}"
