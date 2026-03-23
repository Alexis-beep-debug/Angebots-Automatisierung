import os, json

PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN", "")
PIPEDRIVE_BASE = "https://api.pipedrive.com/v1"
ADI_SHARON_USER_ID = 20546477

LEXOFFICE_API_KEY = os.getenv("LEXOFFICE_API_KEY", "JtpM-5ERh_b1ZdPCikR3kTiSPdk860mDf.mgrbHHarXRVd0v")
LEXOFFICE_BASE = "https://api.lexoffice.io/v1"

GOOGLE_SLIDES_TEMPLATE_ID = "1M4nknlrfswWB_hGFpmHvp_9NbHgo88kJY5hZumcLh6c"
GOOGLE_DRIVE_PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "")

_sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
if _sa_json:
    SERVICE_ACCOUNT_INFO = json.loads(_sa_json)
else:
    _sa_file = os.path.join(os.path.dirname(__file__), "service_account.json")
    SERVICE_ACCOUNT_INFO = json.load(open(_sa_file)) if os.path.exists(_sa_file) else {}

OWNER_EMAIL = os.getenv("OWNER_EMAIL", "")
