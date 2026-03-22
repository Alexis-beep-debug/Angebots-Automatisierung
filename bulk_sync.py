#!/usr/bin/env python3
"""
Schritt 2 – Bulk-Sync: alle ~4.500 Pipedrive-Kontakte → Brevo.

Ausführen mit:  python bulk_sync.py
Optionen:
  --dry-run   Nur ausgeben, was gesynct würde – kein Schreiben nach Brevo
  --limit N   Nur die ersten N Personen verarbeiten (zum Testen)
"""
import asyncio
import argparse
import time
from config import LABEL_MAP
import pipedrive_client as pd
import brevo_client as brevo
from sync_helpers import build_brevo_payload

PAGE_SIZE = 100
CONCURRENCY = 5  # gleichzeitige Brevo-Requests


async def process_batch(persons: list[dict], label_map: dict, dry_run: bool) -> tuple[int, int]:
    """Returns (synced, skipped)."""
    synced = 0
    skipped = 0
    sem = asyncio.Semaphore(CONCURRENCY)

    async def handle_one(person: dict) -> None:
        nonlocal synced, skipped
        async with sem:
            try:
                payload = await build_brevo_payload(person, label_map)
                if payload is None:
                    skipped += 1
                    return
                if not dry_run:
                    await brevo.upsert_contact(payload["email"], payload["attributes"])
                else:
                    print(f"  [DRY-RUN] {payload['email']}: {payload['attributes']}")
                synced += 1
            except Exception as exc:
                pid = person.get("id")
                name = f"{person.get('first_name', '')} {person.get('last_name', '')}".strip()
                print(f"  [ERROR] Person {pid} ({name}): {exc}")
                skipped += 1

    await asyncio.gather(*[handle_one(p) for p in persons])
    return synced, skipped


async def run(dry_run: bool = False, limit: int | None = None) -> None:
    print("Lade Label-Map aus config.py …")
    label_map = LABEL_MAP.copy()
    print(f"  {len(label_map)} Labels bekannt: {label_map}")

    total_synced = 0
    total_skipped = 0
    start_time = time.monotonic()
    start = 0
    page = 1

    print("\nStarte Bulk-Sync …")
    while True:
        persons, has_more = await pd.get_persons_page(start=start, limit=PAGE_SIZE)
        if not persons:
            break

        if limit is not None:
            remaining = limit - (total_synced + total_skipped)
            persons = persons[:remaining]

        print(f"  Seite {page}: {len(persons)} Personen …", end="", flush=True)
        synced, skipped = await process_batch(persons, label_map, dry_run)
        total_synced += synced
        total_skipped += skipped
        elapsed = time.monotonic() - start_time
        print(f" ✓ {synced} gesynct, {skipped} übersprungen (gesamt: {total_synced}/{total_synced + total_skipped}, {elapsed:.0f}s)")

        if not has_more:
            break
        if limit is not None and (total_synced + total_skipped) >= limit:
            break

        start += PAGE_SIZE
        page += 1

    elapsed = time.monotonic() - start_time
    print(f"\nFertig in {elapsed:.0f}s – {total_synced} gesynct, {total_skipped} übersprungen.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-Sync Pipedrive → Brevo")
    parser.add_argument("--dry-run", action="store_true", help="Keine Änderungen schreiben")
    parser.add_argument("--limit", type=int, default=None, help="Nur N Kontakte verarbeiten")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
