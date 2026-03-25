# Projektdokumentation: Angebotsautomatisierung G+C Facility

## Übersicht

Automatisiertes System zur Angebotserstellung für die G+C Facility GmbH. Ein Superforms-Formular erfasst Kundendaten und Reinigungsanforderungen, ein Webhook generiert daraus automatisch ein professionelles PDF-Angebot und legt alle Daten in Pipedrive (CRM), Lexoffice (Buchhaltung) und Google Drive (Ablage) an.

**Deployment:** Railway (deployt automatisch von `main`)
**Repo:** `Alexis-beep-debug/Angebots-Automatisierung`
**Stundensatz:** €36/h netto = €0,60/min

---

## Architektur

```
Superforms-Formular
        ↓ Webhook (POST /webhook/generate-proposal)
  webhook_server.py (FastAPI)
        ↓ Antwort sofort 200 OK, Verarbeitung im Hintergrund
        ├─→ proposal_generator.py  → PDF generieren (Jinja2 + WeasyPrint)
        ├─→ pipedrive_client.py    → Person anlegen/finden, Deal, Aktivität
        ├─→ lexoffice_client.py    → Kontakt + Angebot mit Einzelposten
        └─→ google_drive_client.py → Ordner erstellen, 2 PDFs hochladen

Brevo-Email-Events (Öffnungen, Link-Klicks)
        ↓ Webhooks
  webhook_server.py
        └─→ Pipedrive Notizen + Aktivitäten

Cron-Jobs (alle 15 Min)
        ├─→ cron_persons.py  → Pipedrive Kontakte → Brevo sync
        └─→ cron_deals.py    → Pipedrive Deal-Status → Brevo sync
```

---

## Dateien & Module

### Kern-Anwendung

| Datei | Beschreibung |
|-------|-------------|
| `webhook_server.py` | FastAPI-Server mit allen Webhook-Endpunkten. Empfängt Superforms-Daten, antwortet sofort mit 200 OK, verarbeitet im Hintergrund. |
| `proposal_generator.py` | PDF-Generierung: Mappt Superforms-Felder → Template-Variablen, berechnet Preise (€36/h), rendert PDF via Jinja2 + WeasyPrint. |
| `templates/angebot.html` | Jinja2-Template: 6-seitiges A4-Landscape-PDF im G+C-Design (Cover, Optimierungspotenzial, Daten & Fakten, Kalkulation, Zusatzmodule, Abschluss). |
| `config.py` | Zentrale Konfiguration: API-Keys aus Umgebungsvariablen, Base-URLs, Mappings. |

### API-Clients

| Datei | Beschreibung |
|-------|-------------|
| `pipedrive_client.py` | Async Pipedrive API-Wrapper: Personen suchen/anlegen, Deals, Notizen, Aktivitäten. |
| `lexoffice_client.py` | Lexoffice API: Kontakte mit Billing-Adresse, finalisierte Angebote mit Einzelposten, PDF-Download. |
| `google_drive_client.py` | Google Drive: Ordner erstellen, PDFs hochladen (OAuth, nicht Service Account). |
| `brevo_client.py` | Brevo (Sendinblue): Kontakte anlegen/aktualisieren für Email-Marketing. |

### Synchronisation & Tools

| Datei | Beschreibung |
|-------|-------------|
| `cron_persons.py` | Delta-Sync alle 15 Min: Geänderte Pipedrive-Kontakte → Brevo. |
| `cron_deals.py` | Delta-Sync alle 15 Min: Deal-Status-Änderungen → Brevo STATUS-Attribut. |
| `sync_helpers.py` | Gemeinsame Hilfsfunktionen für Brevo-Payload-Erstellung. |
| `bulk_sync.py` | Einmalige Bulk-Migration aller Pipedrive-Kontakte → Brevo. |
| `step1_preflight.py` | Konfigurationserkennung: Mappt Pipedrive Labels, listet Brevo-Attribute. |
| `generate_test_pdf.py` | Test-PDF mit Beispieldaten generieren (ohne Webhook). |

### Deployment

| Datei | Beschreibung |
|-------|-------------|
| `Dockerfile` | Python 3.12-slim + WeasyPrint-Dependencies (Pango, Cairo, Roboto Fonts). |
| `Procfile` | `uvicorn webhook_server:app --host 0.0.0.0 --port $PORT` |
| `railway.json` | Railway-Konfiguration: Dockerfile-Builder, Restart on Failure (max 3). |
| `requirements.txt` | Python-Dependencies (FastAPI, WeasyPrint, httpx, google-api, etc.). |

---

## Webhook-Endpunkte

### `POST /webhook/generate-proposal` (Hauptendpunkt)

**Trigger:** Superforms-Formular wird abgeschickt.

**Payload-Format:** Superforms sendet `{"files": [], "data": {field: {name, value, option_label, type}}}`.

**Verarbeitungsschritte (Background):**
1. Payload flattening (verschachtelte Objekte → einfache Key-Value-Paare)
2. PDF generieren (6 Seiten, A4 Landscape)
3. Pipedrive: Person anlegen oder finden (per Email)
4. Pipedrive: Deal anlegen mit Duplikat-Prüfung
5. Lexoffice: Kontakt mit Billing-Adresse anlegen
6. Lexoffice: Finalisiertes Angebot mit Einzelposten erstellen, PDF downloaden
7. Google Drive: Ordner im Eltern-Ordner erstellen, beide PDFs hochladen
8. Pipedrive: Notiz + Aktivität mit Drive-Link erstellen

### `POST /webhook/email-opened`

**Trigger:** Brevo meldet Email-Öffnung.
**Aktion:** Pipedrive-Notiz bei der Person.

### `POST /webhook/link-clicked`

**Trigger:** Brevo meldet Link-Klick (mit Bot-Filter < 4 Sek).
**Aktion:** Pipedrive-Notiz + Aktivität "Heißer Lead".

### `GET /health`

Health-Check für Railway.

---

## PDF-Aufbau (6 Seiten)

| Seite | Inhalt |
|-------|--------|
| 1 | **Deckblatt** – Logo, Firma, Kontaktperson, Adresse, Datum, Angebots-Nr., Begrüßungstext |
| 2 | **Optimierungspotenzial** – 3 Karten: Angekreuzte Probleme (rot), Angekreuzte Wünsche (grün), G+C-Ansatz (blau, Standard) |
| 3 | **Daten & Fakten** – 3 Info-Karten: Reinigungsfläche (m²), Räume gesamt, Schreibtische/Ausstattung |
| 4 | **Kalkulation im Detail** – Tabelle mit Einzelposten (Schreibtische, Böden, Sanitär, Küche) + Gesamtbetrag |
| 5 | **Zusatzmodule** – Glasreinigung, Teppich, Kabelmanagement, Pflanzenpflege, etc. (nur aktivierte) |
| 6 | **Abschluss** – "Gemeinsam für ein sauberes Ergebnis", Kontaktdaten, Nächste Schritte |

---

## Superforms-Feldnamen

### Kontaktdaten

| Superforms-Feld | Bedeutung |
|-----------------|-----------|
| `Firmenname` | Firmenname |
| `Anschrift` | Straße + Hausnummer |
| `field_YSXLd` | PLZ |
| `field_ayedY` | Stadt |
| `first_name` | Vorname |
| `last_name` | Nachname |
| `Telefonnummer` | Telefon |
| `Email` | Email |
| `Rechnungsadresse` | "on"/"off" – andere Rechnungsadresse? |

### Räume & Ausstattung

| Feld | Bedeutung |
|------|-----------|
| `Menge_2_3` | Büroräume (Anzahl) |
| `Menge_27o7` | Bürotische |
| `Menge_2oipp` | Bürostühle |
| `field_rtCTb` | Schränke/Regale |
| `Menge_2_2` | Büro m² |
| `Menge_2uu` | Meetingräume |
| `Menge_2_37o7_2` | Meetingtische |
| `Menge_2ioup` | Meetingstühle |
| `field_LzyvM` | Meeting m² |
| `Menge_2_3hgt` | Küchen |
| `field_AJctI` | Spülen |
| `Menge_2_37o7` | Küchenzeilen |
| `Menge_2u55` | Spülmaschinen |
| `field_cHSyM` | Kaffeemaschinen |
| `field_fCOgh` | Küche m² |
| `Menge_2rr` | Sanitärräume |
| `Menge_2_3t7t7` | WCs |
| `Menge_2` | Waschbecken |
| `Menge_2_267i67i` | Spiegel |
| `field_Nsaox` | Duschen |
| `field_TgHWm` | Pissoirs |
| `field_sWVLz` | Sanitär m² |
| `Menge` | Weitere Räume |
| `Menge_2uzkiz` | Mülleimer |
| `field_LZShT` | Türen |
| `field_FjaFR` | Glastüren |
| `field_wZosx` | Weitere m² |

### Reinigungsintervalle

| Feld | Bedeutung |
|------|-----------|
| `Möglichkeit` | Müll entsorgen |
| `field_yhSgD` | Tische reinigen |
| `field_zHLCn` | Küche |
| `field_IsCve` | Sanitär |
| `field_LOxcA` | Boden staubsaugen |
| `field_pdGkr` | Schränke/Regale |
| `field_khHLN` | Griffspuren |

### Zusatzservices (on/off)

| Feld | Bedeutung |
|------|-----------|
| `field_MCsHM` | Kühlschrank |
| `Menge_2_2gff` | Mikrowelle |
| `field_kwRxo` | Kaffeemaschinenpflege |
| `field_QPFfk` | Spülmaschinenservice |
| `field_cPdkX` | Papier/Seife |
| `field_FEykX` | Pflanzenpflege |
| `field_GtKat` | Duftservice |
| `field_cHHIL` | Kabelmanagement |
| `Menge_2_2_2` | Fensterreinigung |

### Probleme & Wünsche (Checkboxen)

**Feld `Möglichkeit_2_2` – Probleme der jetzigen Reinigung:**
1. Ineffektive und Inkonsistente Reinigungsqualität
2. Schlechte Urlaubs/ und Krankheitsvertretung
3. fehlende Kontrolle
4. Intransparenz bei Leistung, Kosten und Prozessen
5. Mangelnde Zuverlässigkeit (Reliabilität)
6. Schlechtes Beschwerdemanagement

**Feld `field_cCLhd` – Wünsche und Ziele:**
1. Fachbetrieb / Meisterbetrieb
2. Nachhaltigkeit und Compliance
3. Proaktivität in Beratung und Ausführung
4. Digitale Nachweis- und Kontrollsysteme
5. Kein Zeitverlust durch ständiges kontrollieren
6. Alles aus einer Hand

**Wichtig:** Superforms sendet Mehrfach-Checkboxen als komma-getrennten String im `option_label`-Feld. Da einige Labels selbst Kommas enthalten (z.B. "Intransparenz bei Leistung, Kosten und Prozessen"), wird ein Smart-Parser verwendet, der gegen die bekannten Labels matcht statt blind nach Komma zu splitten (`_parse_checkboxes_smart()`).

---

## Preiskalkulation

**Basis:** €36/h netto = €0,60/min

**Frequenz-Faktoren (Mal pro Monat):**

| Intervall | Faktor |
|-----------|--------|
| 1x Woche | 4,33 |
| 2x Woche | 8,67 |
| 3x Woche | 13,0 |
| 5x Woche | 21,67 |
| 7x Woche | 30,33 |
| 1x Monat | 1,0 |

**Zeitansätze pro Einheit:**

| Leistung | Minuten | Frequenz |
|----------|---------|----------|
| Schreibtisch | 1,5 min/Stck | 1x/Woche |
| Bürostuhl | 2,5 min/Stck | 1x/Monat |
| Mülleimer | 0,5 min/Stck | nach Auswahl |
| Schränke | 2 min/Stck | 1x/Woche |
| Büroboden | 0,24 min/m² | 2x/Woche |
| WC | 2,5 min/Stck | nach Auswahl |
| Waschbecken | 2,5 min/Stck | nach Auswahl |
| Dusche | 10 min/Stck | 1x/Woche |
| Spiegel | 2 min/Stck | nach Auswahl |
| Pissoir | 2,5 min/Stck | nach Auswahl |
| Küche komplett | 8 min/Raum | 5x/Woche |

**Formel:** `Menge × Minuten × €0,60 × Frequenz-Faktor = Monatspreis`

---

## Umgebungsvariablen (Railway)

```
PIPEDRIVE_API_KEY=...
BREVO_API_KEY=...
LEXOFFICE_API_KEY=...
PIPEDRIVE_OWNER_USER_ID=20546477
GOOGLE_DRIVE_PARENT_FOLDER_ID=...
GOOGLE_CREDENTIALS_JSON=...     # OAuth Credentials (base64 oder JSON)
GOOGLE_TOKEN_JSON=...           # OAuth Token
```

---

## Lokale Entwicklung

```bash
# Dependencies installieren
pip install -r requirements.txt

# .env anlegen (siehe .env.example)
cp .env.example .env

# Server starten
uvicorn webhook_server:app --host 0.0.0.0 --port 8000 --reload

# Test-PDF generieren (ohne Server)
python generate_test_pdf.py
```

---

## Deploy-Prozess

1. Code auf Feature-Branch pushen (z.B. `claude/continue-project-EkH80`)
2. Auf Mac manuell ins Angebots-Repo mergen: `git merge origin/<branch>`
3. `git push origin main` → Railway deployt automatisch
4. Railway-Logs prüfen auf Fehler

---

## Bekannte Besonderheiten

- **Superforms Checkbox-Komma-Problem:** Labels wie "Intransparenz bei Leistung, Kosten und Prozessen" enthalten Kommas. Der Smart-Parser in `_parse_checkboxes_smart()` löst das.
- **Background-Processing:** Der Webhook antwortet sofort mit 200 OK, die eigentliche Verarbeitung (PDF, APIs) läuft im Hintergrund via `asyncio.create_task()`. Das verhindert Timeouts.
- **Google Drive OAuth:** Verwendet OAuth-Tokens (nicht Service Account), damit Dateien dem Benutzer gehören.
- **Logo:** Wird von einer Google Drive URL geladen (`https://drive.google.com/uc?export=view&id=1RoInI8le_q6bx2Wo3kScu-229zQ7ZTBo`).
- **Lexoffice Wartezeit:** Nach Angebotserstellung 2 Sekunden Pause, bevor PDF heruntergeladen wird (Lexoffice braucht Zeit zum Finalisieren).
