import httpx
from config import PIPEDRIVE_BASE, PIPEDRIVE_API_TOKEN, ADI_SHARON_USER_ID

_TIMEOUT = 30.0
def _params(): return {"api_token": PIPEDRIVE_API_TOKEN}

async def find_person_by_email(email):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.get(f"{PIPEDRIVE_BASE}/persons/search", params={**_params(),"term":email,"fields":"email","limit":1})
        r.raise_for_status()
        items = r.json().get("data",{}).get("items",[])
        return items[0]["item"] if items else None

async def create_person(name, email, phone="", company=""):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        payload = {"name":name,"email":[{"value":email,"primary":True}]}
        if phone: payload["phone"] = [{"value":phone,"primary":True}]
        r = await c.post(f"{PIPEDRIVE_BASE}/persons", params=_params(), json=payload)
        r.raise_for_status(); return r.json()["data"]

async def create_deal(person_id, title, value=0):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"{PIPEDRIVE_BASE}/deals", params=_params(), json={"title":title,"person_id":person_id,"user_id":ADI_SHARON_USER_ID,"value":value,"currency":"EUR"})
        r.raise_for_status(); return r.json()["data"]

async def add_note(deal_id, content):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"{PIPEDRIVE_BASE}/notes", params=_params(), json={"content":content,"deal_id":deal_id})
        r.raise_for_status(); return r.json()["data"]

async def add_activity(person_id, deal_id, subject, note=""):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"{PIPEDRIVE_BASE}/activities", params=_params(), json={"subject":subject,"type":"task","person_id":person_id,"deal_id":deal_id,"user_id":ADI_SHARON_USER_ID,"done":0,"note":note})
        r.raise_for_status(); return r.json()["data"]
