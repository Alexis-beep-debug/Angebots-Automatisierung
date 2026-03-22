"""Shared helpers for building Brevo contact payloads from Pipedrive persons."""
from datetime import datetime, timezone
from config import DEAL_STATUS_MAP, LABEL_MAP
import pipedrive_client as pd
import brevo_client as brevo


def _extract_email(person: dict) -> str | None:
    for e in person.get("email") or []:
        val = e.get("value", "").strip()
        if val:
            return val
    return None


def _extract_phone(person: dict) -> str | None:
    for p in person.get("phone") or []:
        val = p.get("value", "").strip()
        if val:
            return val
    return None


def _label_names(person: dict, label_map: dict[int, str]) -> str:
    """Return comma-joined label names for the person's label_ids."""
    ids = person.get("label_ids") or []
    if not ids:
        # older Pipedrive API may use singular "label"
        raw = person.get("label")
        if raw:
            ids = [raw] if isinstance(raw, int) else []
    names = [label_map.get(lid, str(lid)) for lid in ids]
    return ", ".join(names) if names else ""


def _best_deal_status(deals: list[dict]) -> str:
    """Pick the most relevant deal status: prefer 'open', then most recent."""
    if not deals:
        return DEAL_STATUS_MAP[None]
    open_deals = [d for d in deals if d.get("status") == "open"]
    target = open_deals[0] if open_deals else deals[0]
    raw = target.get("status")
    return DEAL_STATUS_MAP.get(raw, DEAL_STATUS_MAP[None])


async def build_brevo_payload(person: dict, label_map: dict[int, str]) -> dict | None:
    """
    Build Brevo attributes dict for a Pipedrive person.
    Returns None if no valid email found (contact should be skipped).
    """
    email = _extract_email(person)
    if not email:
        return None

    # Organisation
    org_name = ""
    org = person.get("org_id")
    if org:
        org_id = org if isinstance(org, int) else org.get("value")
        if org_id:
            org_data = await pd.get_organization(org_id)
            if org_data:
                org_name = org_data.get("name", "")

    # Deal-Status
    deals = await pd.get_person_deals(person["id"])
    status = _best_deal_status(deals)

    attributes = {
        "VORNAME": person.get("first_name") or "",
        "NACHNAME": person.get("last_name") or "",
        "SMS": _extract_phone(person) or "",
        "ORGANISATION": org_name,
        "LABEL": _label_names(person, label_map),
        "STATUS": status,
    }
    return {"email": email, "attributes": attributes}


async def sync_person_to_brevo(person: dict, label_map: dict[int, str]) -> bool:
    """
    Sync a single Pipedrive person to Brevo.
    Returns True if synced, False if skipped (no email).
    """
    payload = await build_brevo_payload(person, label_map)
    if payload is None:
        return False
    await brevo.upsert_contact(payload["email"], payload["attributes"])
    return True


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
