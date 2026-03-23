from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import SERVICE_ACCOUNT_INFO, GOOGLE_SLIDES_TEMPLATE_ID, GOOGLE_DRIVE_PARENT_FOLDER_ID

SCOPES = ["https://www.googleapis.com/auth/drive","https://www.googleapis.com/auth/presentations"]

def _creds(): return service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
def _drive(): return build("drive","v3",credentials=_creds())
def _slides(): return build("slides","v1",credentials=_creds())

def create_folder(name):
    meta = {"name":name,"mimeType":"application/vnd.google-apps.folder"}
    if GOOGLE_DRIVE_PARENT_FOLDER_ID: meta["parents"] = [GOOGLE_DRIVE_PARENT_FOLDER_ID]
    drive = _drive()
    folder_id = drive.files().create(body=meta,fields="id").execute()["id"]
    drive.permissions().create(fileId=folder_id, body={"role":"reader","type":"anyone"}).execute()
    return folder_id

def copy_template(folder_id, name):
    return _drive().files().copy(fileId=GOOGLE_SLIDES_TEMPLATE_ID,body={"name":name,"parents":[folder_id]},fields="id").execute()["id"]

def fill_presentation(presentation_id, replacements):
    requests = [{"replaceAllText":{"containsText":{"text":k,"matchCase":False},"replaceText":str(v)}} for k,v in replacements.items()]
    if requests: _slides().presentations().batchUpdate(presentationId=presentation_id,body={"requests":requests}).execute()

def get_presentation_url(presentation_id): return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
