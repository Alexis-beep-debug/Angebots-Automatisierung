"""Einmalig ausführen um Service Account Drive zu leeren"""
import json, os
from google.oauth2 import service_account
from googleapiclient.discovery import build

sa_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
creds = service_account.Credentials.from_service_account_info(sa_info, scopes=["https://www.googleapis.com/auth/drive"])
drive = build("drive", "v3", credentials=creds)

deleted = 0
while True:
    files = drive.files().list(fields="files(id,name)", pageSize=1000, q="trashed=false").execute().get("files", [])
    if not files:
        break
    for f in files:
        try:
            drive.files().delete(fileId=f["id"]).execute()
            deleted += 1
            print(f"Gelöscht: {f['name']}")
        except Exception as e:
            print(f"Fehler: {e}")

drive.files().emptyTrash().execute()
print(f"Fertig! {deleted} Dateien gelöscht.")
