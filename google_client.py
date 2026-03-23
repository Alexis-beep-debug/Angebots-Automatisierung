import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import GOOGLE_SLIDES_TEMPLATE_ID, GOOGLE_DRIVE_PARENT_FOLDER_ID

def _drive():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

def _slides():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    creds.refresh(Request())
    return build("slides", "v1", credentials=creds)

def create_folder(name):
    drive = _drive()
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if GOOGLE_DRIVE_PARENT_FOLDER_ID:
        body["parents"] = [GOOGLE_DRIVE_PARENT_FOLDER_ID]
    folder = drive.files().create(body=body, fields="id").execute()
    return folder["id"]

def copy_template(folder_id, name):
    drive = _drive()
    file_id = drive.files().copy(
        fileId=GOOGLE_SLIDES_TEMPLATE_ID,
        body={"name": name, "parents": [folder_id]},
        fields="id"
    ).execute()["id"]
    return file_id

def fill_presentation(presentation_id, replacements):
    slides = _slides()
    requests = [
        {"replaceAllText": {"containsText": {"text": k, "matchCase": True}, "replaceText": v}}
        for k, v in replacements.items()
    ]
    slides.presentations().batchUpdate(presentationId=presentation_id, body={"requests": requests}).execute()

def get_presentation_url(presentation_id):
    return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
