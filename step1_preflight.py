#!/usr/bin/env python3
"""
Schritt 1 – Vorarbeit:
  1a) Alle Pipedrive Label-IDs + Klarnamen ausgeben
  1b) Alle Brevo Kontakt-Attribute (inkl. erlaubte Enum-Werte) ausgeben

Ausführen mit:  python step1_preflight.py
"""
import asyncio
import json
import pipedrive_client as pd
import brevo_client as brevo


async def fetch_label_map() -> dict[int, str]:
    print("=== 1a) Pipedrive Label-IDs ===")
    fields = await pd.get_person_fields()
    label_map: dict[int, str] = {}
    for field in fields:
        if field.get("key") == "label" or field.get("name", "").lower() == "label":
            options = field.get("options") or []
            for opt in options:
                label_map[opt["id"]] = opt["label"]
            break

    if label_map:
        print("\nGefundenes Label-Mapping (für config.py):")
        print("LABEL_MAP = {")
        for lid, name in sorted(label_map.items()):
            print(f'    {lid}: "{name}",')
        print("}")
    else:
        print("Kein 'label'-Feld gefunden. Alle personFields:")
        for f in fields:
            print(f"  key={f.get('key')!r:30s} name={f.get('name')!r}")
    return label_map


async def fetch_brevo_attributes() -> None:
    print("\n=== 1b) Brevo Kontakt-Attribute ===")
    attrs = await brevo.get_contact_attributes()
    for attr in attrs:
        name = attr.get("name")
        category = attr.get("category")
        enum_vals = attr.get("enumeration")
        if enum_vals:
            values = [e.get("value") for e in enum_vals]
            print(f"  [{category}] {name}: {values}")
        else:
            print(f"  [{category}] {name}: (freies Feld, Typ={attr.get('type')})")


async def main() -> None:
    label_map = await fetch_label_map()
    await fetch_brevo_attributes()

    print("\n=== Zusammenfassung ===")
    print("Trage das LABEL_MAP oben in config.py ein, bevor du bulk_sync.py ausführst.")
    print("Prüfe die erlaubten Enum-Werte für LABEL und STATUS in Brevo.")
    print("Fertig.")


if __name__ == "__main__":
    asyncio.run(main())
