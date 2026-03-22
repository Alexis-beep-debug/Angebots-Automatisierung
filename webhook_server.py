#!/usr/bin/env python3
"""
Schritt 4 – FastAPI Webhook-Server.

Empfängt Brevo-Email-Events und schreibt Notizen / Aktivitäten nach Pipedrive.

Starten lokal:  uvicorn webhook_server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, HTTPException
import pipedrive_client as pd

app = FastAPI(title="Pipedrive↔Brevo Sync Webhook Server")

BOT_CLICK_THRESHOLD_SECONDS = 4  # Klicks kürzer als dies = Bot-Klick → ignorieren


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _resolve_person(email: str) -> dict | None:
    """Look up Pipedrive person by email. Returns person dict or None."""
    return await pd.search_person_by_email(email)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": _now_str()}


# ---------------------------------------------------------------------------
# 4a: Email geöffnet
# ---------------------------------------------------------------------------

@app.post("/webhook/email-opened")
async def email_opened(request: Request) -> dict:
    """
    Brevo sendet bei jedem 'opened'-Event einen POST.
    Payload-Felder (Brevo Marketing Email Events):
      - email: Empfänger-Email
      - subject: Betreff der Kampagne
      - campaign_name / message_id (optional)
    """
    payload: dict[str, Any] = await request.json()

    email: str = payload.get("email", "")
    subject: str = payload.get("subject", "unbekannte Kampagne")

    if not email:
        raise HTTPException(status_code=400, detail="'email' fehlt im Payload")

    person = await _resolve_person(email)
    if not person:
        # Kontakt existiert nicht in Pipedrive – still ignorieren
        return {"status": "skipped", "reason": "person not found", "email": email}

    note_content = f"[{_now_str()}] Email geöffnet: {subject}"
    await pd.add_note(person_id=person["id"], content=note_content)

    return {"status": "ok", "person_id": person["id"], "note": note_content}


# ---------------------------------------------------------------------------
# 4b: Link geklickt
# ---------------------------------------------------------------------------

@app.post("/webhook/link-clicked")
async def link_clicked(request: Request) -> dict:
    """
    Brevo sendet bei jedem 'clicked'-Event einen POST.
    Payload-Felder:
      - email: Empfänger-Email
      - subject: Betreff
      - link: geklickte URL
      - time_since_delivery: Sekunden seit Zustellung (für Bot-Filter)
    """
    payload: dict[str, Any] = await request.json()

    email: str = payload.get("email", "")
    subject: str = payload.get("subject", "unbekannter Betreff")
    link: str = payload.get("link", "")
    time_since_delivery = payload.get("time_since_delivery")

    if not email:
        raise HTTPException(status_code=400, detail="'email' fehlt im Payload")

    # Bot-Klick-Filter
    if time_since_delivery is not None:
        try:
            if float(time_since_delivery) < BOT_CLICK_THRESHOLD_SECONDS:
                return {"status": "skipped", "reason": "bot_click_filtered"}
        except (TypeError, ValueError):
            pass

    person = await _resolve_person(email)
    if not person:
        return {"status": "skipped", "reason": "person not found", "email": email}

    person_name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip() or email
    ts = _now_str()

    note_content = f"[{ts}] Link geklickt: {link} in Email \"{subject}\""
    activity_subject = f"Heißer Lead: {person_name} hat Link geklickt"
    activity_note = f"Geklickter Link: {link}\nEmail-Betreff: {subject}"

    await pd.add_note(person_id=person["id"], content=note_content)
    await pd.add_activity(person_id=person["id"], subject=activity_subject, note=activity_note, user_id=20546477)

    return {
        "status": "ok",
        "person_id": person["id"],
        "note": note_content,
        "activity": activity_subject,
    }
