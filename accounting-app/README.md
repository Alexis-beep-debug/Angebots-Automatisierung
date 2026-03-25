# Buchhaltungs-Automatisierung

Vollautomatische Buchhaltungs-App für Freelancer (regelbesteuert, 19% MwSt).

**Features:**
- PWA für iPhone Safari (Homescreen-Icon)
- Belege scannen mit Claude Vision (KI-Erkennung)
- Automatischer Gmail-Import von Rechnungen (alle 4h)
- Kontist-Banking-Integration (alle 4h)
- Automatisches Matching: Belege ↔ Transaktionen
- Ausgehende Rechnungen ↔ Geldeingänge Matching
- Google Sheets als Buchhaltungs-Tabelle mit MwSt-Übersicht
- GoBD-konform: Belege werden nur archiviert, nie gelöscht

---

## Schritt-für-Schritt Setup

### 1. API Keys besorgen

#### Anthropic API Key (Claude Vision)
1. Gehe zu https://console.anthropic.com/
2. Erstelle einen Account / logge dich ein
3. Unter "API Keys" → "Create Key"
4. Kopiere den Key → `ANTHROPIC_API_KEY`

#### Google OAuth2 (Gmail + Sheets)
1. Gehe zu https://console.cloud.google.com/
2. Erstelle ein neues Projekt
3. Aktiviere diese APIs:
   - Google Sheets API
   - Gmail API
4. Unter "APIs & Services" → "Credentials" → "Create Credentials" → "OAuth client ID"
5. Application type: "Web application"
6. Authorized redirect URI: `https://deine-app.railway.app/auth/google/callback`
   (lokal: `http://localhost:3000/auth/google/callback`)
7. Kopiere Client ID → `GOOGLE_CLIENT_ID`
8. Kopiere Client Secret → `GOOGLE_CLIENT_SECRET`

#### Google Sheets ID
1. Erstelle ein neues Google Spreadsheet
2. Die ID ist der lange String in der URL:
   `https://docs.google.com/spreadsheets/d/DIESE_ID_HIER/edit`
3. Kopiere die ID → `GOOGLE_SHEETS_ID`

#### Kontist API (optional)
1. Gehe zu https://kontist.com/
2. Unter Entwickler-Einstellungen → OAuth2 App erstellen
3. Redirect URI: `https://deine-app.railway.app/auth/kontist/callback`
4. Kopiere Client ID → `KONTIST_CLIENT_ID`
5. Kopiere Client Secret → `KONTIST_CLIENT_SECRET`

### 2. Lokale Installation

```bash
cd accounting-app
npm install
cp .env.example .env
# .env mit deinen API Keys befüllen
npm run dev
```

### 3. Erstverbindung

1. Öffne http://localhost:3000
2. Gehe zu "Tools" Tab
3. Klicke "Google verbinden" → OAuth2 Autorisierung durchführen
4. (Optional) Klicke "Kontist verbinden"
5. Die Google Sheets Tabelle wird automatisch initialisiert

### 4. Railway Deployment

```bash
# Railway CLI installieren
npm i -g @railway/cli

# Einloggen und Projekt erstellen
railway login
railway init

# Environment Variables setzen
railway variables set ANTHROPIC_API_KEY=sk-...
railway variables set GOOGLE_CLIENT_ID=...
railway variables set GOOGLE_CLIENT_SECRET=...
railway variables set GOOGLE_SHEETS_ID=...
railway variables set GOOGLE_REDIRECT_URI=https://deine-app.railway.app/auth/google/callback
railway variables set KONTIST_CLIENT_ID=...
railway variables set KONTIST_CLIENT_SECRET=...
railway variables set KONTIST_REDIRECT_URI=https://deine-app.railway.app/auth/kontist/callback

# Deployen
railway up
```

**Wichtig:** Nach dem Deployment die Redirect URIs in Google Cloud Console und Kontist auf die Railway-URL aktualisieren.

### 5. PWA auf iPhone installieren

1. Öffne die Railway-URL in Safari auf dem iPhone
2. Tippe auf das Teilen-Symbol (Quadrat mit Pfeil)
3. "Zum Home-Bildschirm" wählen
4. Die App erscheint als Icon auf dem Homescreen

---

## Nutzung

### Beleg scannen
1. Öffne die App → "Scannen" Tab
2. Tippe "Beleg scannen" → Kamera öffnet sich
3. Foto machen → Claude Vision analysiert den Beleg
4. Erkannte Daten prüfen/korrigieren
5. "Bestätigen" → wird in Google Sheets gespeichert

### Ausgehende Rechnung erfassen
1. "Tools" Tab → "Ausgehende Rechnung erfassen"
2. Kunde, Betrag, Datum eingeben
3. Wird als Einnahme mit Status "Rechnung gestellt" gespeichert
4. Bei Geldeingang über Kontist wird automatisch gematcht

### Automatische Imports
- Alle 4 Stunden automatisch: Gmail + Kontist + Matching
- Manuell auslösbar über "Tools" Tab

---

## Google Sheets Struktur

### Tab "Transaktionen"
| Datum | Betrag Brutto | Netto | MwSt | MwSt-Satz | Händler | Kategorie | Typ | Beleg-Status | Beschreibung |

### Tab "Zusammenfassung"
Automatische Monatsübersicht mit:
- Einnahmen / Ausgaben pro Monat
- MwSt-Zahllast für Voranmeldung

---

## GoBD-Konformität

- Belege werden nur archiviert, nie gelöscht
- Verarbeitete Emails erhalten Gmail-Label "Verarbeitet"
- Jede Transaktion hat Zeitstempel und Status
- Änderungen an Beträgen sollten über neue Einträge korrigiert werden (Storno + Neuerfassung)
- Google Sheets Versionsverlauf dient als Änderungsprotokoll

---

## Architektur

```
accounting-app/
├── public/           # PWA Frontend
│   ├── index.html    # Single-Page App
│   ├── manifest.json # PWA Manifest
│   └── sw.js         # Service Worker
├── src/
│   ├── server.js         # Express Server + Cron
│   ├── claude-vision.js  # Beleg-Analyse mit Claude
│   ├── google-sheets.js  # Sheets API + OAuth
│   ├── gmail-import.js   # Email-Rechnungsimport
│   ├── kontist.js        # Banking API
│   └── matching.js       # Beleg ↔ Transaktion Matching
├── tokens/           # OAuth Tokens (gitignored)
├── .env.example
├── package.json
└── railway.json
```
