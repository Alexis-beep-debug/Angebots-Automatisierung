import httpx
from config import PIPEDRIVE_BASE, PIPEDRIVE_API_TOKEN, ADI_SHARON_USER_ID

_TIMEOUT = 30.0

def _params():
    return {"api_token": PIPEDRIVE_API_TOKEN}

async def find_person_by_email(email: str):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/persons/search", params={**_params(), "term": email, "fields": "email", "limit": 1})
        r.raise_for_status()
        items = r.json().get("data", {}).get("items", [])
        return items[0]["item"] if items else None

async def find_open_deal_by_person(person_id: int):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/persons/{person_id}/deals", params={**_params(), "status": "open", "limit": 1})
        r.raise_for_status()
        items = r.json().get("data") or []
        return items[0] if items else None

async def create_person(name: str, email: str, phone: str = "", company: str = "") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        payload = {"name": name, "email": [{"value": email, "primary": True}]}
        if phone: payload["phone"] = [{"value": phone, "primary": True}]
        r = await client.post(f"{PIPEDRIVE_BASE}/persons", params=_params(), json=payload)
        r.raise_for_status()
        return r.json()["data"]

async def create_deal(person_id: int, title: str, value: float = 0) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{PIPEDRIVE_BASE}/deals", params=_params(), json={"title": title, "person_id": person_id, "user_id": ADI_SHARON_USER_ID, "value": value, "currency": "EUR", "stage_id": 47, "pipeline_id": 6})
        r.raise_for_status()
        return r.json()["data"]

async def add_note(deal_id: int, content: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{PIPEDRIVE_BASE}/notes", params=_params(), json={"content": content, "deal_id": deal_id})
        r.raise_for_status()
        return r.json()["data"]

async def add_activity(person_id: int, deal_id: int, subject: str, note: str = "") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{PIPEDRIVE_BASE}/activities", params=_params(), json={"subject": subject, "type": "task", "person_id": person_id, "deal_id": deal_id, "user_id": ADI_SHARON_USER_ID, "done": 0, "note": note})
        r.raise_for_status()
        return r.json()["data"]
