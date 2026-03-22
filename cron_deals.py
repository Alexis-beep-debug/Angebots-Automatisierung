#!/usr/bin/env python3
"""
Schritt 3b – Delta-Sync Deals: geänderte Deal-Status → Brevo STATUS-Attribut.

Wird als Cron-Job ausgeführt, z. B. alle 15 Minuten:
  python cron_deals.py

Speichert den letzten Lauf-Zeitstempel in last_run_deals.txt.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from config import DEAL_STATUS_MAP
import pipedrive_client as pd
import brevo_client as brevo

STATE_FILE = "last_run_deals.txt"
LOOKBACK_MINUTES = 20


def read_last_run() -> str:
    if os.path.exists(STATE_FILE):
        ts = open(STATE_FILE).read().strip()
        if ts:
            return ts
    return (datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()


def write_last_run(ts: str) -> None:
    with open(STATE_FILE, "w") as f:
        f.write(ts)


def _get_email_from_person(person: dict) -> str | None:
    for e in person.get("email") or []:
        val = e.get("value", "").strip()
        if val:
            return val
    return None


async def main() -> None:
    since = read_last_run()
    run_start = datetime.now(timezone.utc).isoformat()
    print(f"[{run_start}] Delta-Sync Deals seit {since} …")

    deals = await pd.get_deals_since(since_timestamp=since)
    print(f"  {len(deals)} Deals gefunden.")

    updated = 0
    skipped = 0

    for deal in deals:
        person_ref = deal.get("person_id")
        if not person_ref:
            skipped += 1
            continue
        person_id = person_ref if isinstance(person_ref, int) else person_ref.get("value")
        if not person_id:
            skipped += 1
            continue

        person = await pd.get_person(person_id)
        if not person:
            skipped += 1
            continue

        email = _get_email_from_person(person)
        if not email:
            skipped += 1
            continue

        raw_status = deal.get("status")
        brevo_status = DEAL_STATUS_MAP.get(raw_status, DEAL_STATUS_MAP[None])

        try:
            await brevo.update_contact_attributes(email, {"STATUS": brevo_status})
            updated += 1
        except Exception as exc:
            print(f"  [ERROR] Deal {deal.get('id')} / {email}: {exc}")
            skipped += 1

    print(f"  {updated} aktualisiert, {skipped} übersprungen.")
    write_last_run(run_start)
    print("Fertig.")


if __name__ == "__main__":
    asyncio.run(main())
