#!/usr/bin/env python3
"""
Schritt 3a – Delta-Sync Personen: geänderte Pipedrive-Kontakte → Brevo.

Wird als Cron-Job ausgeführt, z. B. alle 15 Minuten:
  python cron_persons.py

Speichert den letzten Lauf-Zeitstempel in last_run_persons.txt.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from config import LABEL_MAP
import pipedrive_client as pd
from sync_helpers import sync_person_to_brevo

STATE_FILE = "last_run_persons.txt"
LOOKBACK_MINUTES = 20  # Puffer für Latenzen


def read_last_run() -> str:
    if os.path.exists(STATE_FILE):
        ts = open(STATE_FILE).read().strip()
        if ts:
            return ts
    # Erstes Mal: letzte 20 Minuten
    return (datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)).isoformat()


def write_last_run(ts: str) -> None:
    with open(STATE_FILE, "w") as f:
        f.write(ts)


async def main() -> None:
    since = read_last_run()
    run_start = datetime.now(timezone.utc).isoformat()
    print(f"[{run_start}] Delta-Sync Personen seit {since} …")

    label_map = LABEL_MAP.copy()
    persons = await pd.get_persons_since(since_timestamp=since)
    print(f"  {len(persons)} Personen gefunden.")

    synced = 0
    skipped = 0
    for person in persons:
        try:
            ok = await sync_person_to_brevo(person, label_map)
            if ok:
                synced += 1
            else:
                skipped += 1
        except Exception as exc:
            print(f"  [ERROR] Person {person.get('id')}: {exc}")
            skipped += 1

    print(f"  {synced} gesynct, {skipped} übersprungen.")
    write_last_run(run_start)
    print("Fertig.")


if __name__ == "__main__":
    asyncio.run(main())
