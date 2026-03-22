"""Thin async wrapper around the Pipedrive REST API v1."""
import httpx
from config import PIPEDRIVE_API_KEY, PIPEDRIVE_BASE

_TIMEOUT = httpx.Timeout(30.0)


def _params(**extra) -> dict:
    return {"api_token": PIPEDRIVE_API_KEY, **extra}


async def get_person_fields() -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/personFields", params=_params())
        r.raise_for_status()
        return r.json()["data"] or []


async def get_persons_page(start: int = 0, limit: int = 100) -> tuple[list[dict], bool]:
    """Returns (persons, has_more)."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{PIPEDRIVE_BASE}/persons",
            params=_params(start=start, limit=limit),
        )
        r.raise_for_status()
        data = r.json()
        persons = data.get("data") or []
        has_more = (data.get("additional_data", {}) or {}).get("pagination", {}).get("more_items_in_collection", False)
        return persons, has_more


async def get_persons_since(since_timestamp: str, limit: int = 100) -> list[dict]:
    """Fetch all persons modified since ISO-timestamp (for delta sync)."""
    results: list[dict] = []
    start = 0
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while True:
            r = await client.get(
                f"{PIPEDRIVE_BASE}/persons",
                params=_params(since_timestamp=since_timestamp, start=start, limit=limit),
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("data") or []
            results.extend(batch)
            has_more = (data.get("additional_data", {}) or {}).get("pagination", {}).get("more_items_in_collection", False)
            if not has_more:
                break
            start += limit
    return results


async def get_organization(org_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/organizations/{org_id}", params=_params())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("data")


async def get_person_deals(person_id: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/persons/{person_id}/deals", params=_params(limit=50))
        r.raise_for_status()
        return r.json().get("data") or []


async def get_deals_since(since_timestamp: str, limit: int = 100) -> list[dict]:
    results: list[dict] = []
    start = 0
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        while True:
            r = await client.get(
                f"{PIPEDRIVE_BASE}/deals",
                params=_params(since_timestamp=since_timestamp, start=start, limit=limit),
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get("data") or []
            results.extend(batch)
            has_more = (data.get("additional_data", {}) or {}).get("pagination", {}).get("more_items_in_collection", False)
            if not has_more:
                break
            start += limit
    return results


async def get_person(person_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{PIPEDRIVE_BASE}/persons/{person_id}", params=_params())
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("data")


async def search_person_by_email(email: str) -> dict | None:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(
            f"{PIPEDRIVE_BASE}/persons/search",
            params=_params(term=email, fields="email", exact_match=1, limit=1),
        )
        r.raise_for_status()
        items = r.json().get("data", {}).get("items") or []
        return items[0]["item"] if items else None


async def add_note(person_id: int, content: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(
            f"{PIPEDRIVE_BASE}/notes",
            params=_params(),
            json={"content": content, "person_id": person_id},
        )
        r.raise_for_status()
        return r.json()["data"]


async def add_activity(person_id: int, subject: str, note: str = "", user_id: int | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        payload = {
            "subject": subject,
            "type": "task",
            "person_id": person_id,
            "done": 0,
            "note": note,
        }
        if user_id:
            payload["user_id"] = user_id
        r = await client.post(
            f"{PIPEDRIVE_BASE}/activities",
            params=_params(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()["data"]
