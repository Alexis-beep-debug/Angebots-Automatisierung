"""Thin async wrapper around the Brevo (Sendinblue) API v3."""
import httpx
from config import BREVO_API_KEY, BREVO_BASE

_TIMEOUT = httpx.Timeout(30.0)


def _headers() -> dict:
    return {"api-key": BREVO_API_KEY, "Content-Type": "application/json"}


async def get_contact_attributes() -> list[dict]:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{BREVO_BASE}/contacts/attributes", headers=_headers())
        r.raise_for_status()
        return r.json().get("attributes") or []


async def upsert_contact(email: str, attributes: dict, list_ids: list[int] | None = None) -> None:
    """Create or update a contact in Brevo (updateEnabled=true)."""
    payload: dict = {"email": email, "attributes": attributes, "updateEnabled": True}
    if list_ids:
        payload["listIds"] = list_ids
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{BREVO_BASE}/contacts", headers=_headers(), json=payload)
        if r.status_code not in (200, 201, 204):
            raise ValueError(f"Brevo upsert failed {r.status_code}: {r.text}")


async def update_contact_attributes(email: str, attributes: dict) -> None:
    """PATCH a contact's attributes by email."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.put(
            f"{BREVO_BASE}/contacts/{email}",
            headers=_headers(),
            json={"attributes": attributes},
        )
        if r.status_code not in (200, 204):
            raise ValueError(f"Brevo update failed {r.status_code}: {r.text}")
