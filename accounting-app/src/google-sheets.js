const { google } = require("googleapis");
const fs = require("fs");
const path = require("path");

const TOKENS_PATH = path.join(__dirname, "..", "tokens", "google-tokens.json");
const SCOPES = [
  "https://www.googleapis.com/auth/spreadsheets",
  "https://www.googleapis.com/auth/gmail.modify",
  "https://www.googleapis.com/auth/gmail.readonly",
];

function getOAuth2Client() {
  return new google.auth.OAuth2(
    process.env.GOOGLE_CLIENT_ID,
    process.env.GOOGLE_CLIENT_SECRET,
    process.env.GOOGLE_REDIRECT_URI
  );
}

function getAuthUrl() {
  const oauth2Client = getOAuth2Client();
  return oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });
}

async function getAuthenticatedClient() {
  if (!fs.existsSync(TOKENS_PATH)) {
    throw new Error("Google nicht autorisiert. Bitte zuerst /auth/google aufrufen.");
  }

  const tokens = JSON.parse(fs.readFileSync(TOKENS_PATH, "utf8"));
  const oauth2Client = getOAuth2Client();
  oauth2Client.setCredentials(tokens);

  // Token-Refresh falls nötig
  oauth2Client.on("tokens", (newTokens) => {
    const updated = { ...tokens, ...newTokens };
    fs.writeFileSync(TOKENS_PATH, JSON.stringify(updated, null, 2));
  });

  return oauth2Client;
}

async function saveTokens(code) {
  const oauth2Client = getOAuth2Client();
  const { tokens } = await oauth2Client.getToken(code);
  fs.mkdirSync(path.dirname(TOKENS_PATH), { recursive: true });
  fs.writeFileSync(TOKENS_PATH, JSON.stringify(tokens, null, 2));
  return tokens;
}

/**
 * Initialisiert die Google Sheets Tabelle mit den zwei Tabs.
 */
async function initializeSpreadsheet() {
  const auth = await getAuthenticatedClient();
  const sheets = google.sheets({ version: "v4", auth });
  const spreadsheetId = process.env.GOOGLE_SHEETS_ID;

  // Prüfe ob Tabs existieren
  const spreadsheet = await sheets.spreadsheets.get({ spreadsheetId });
  const existingSheets = spreadsheet.data.sheets.map(
    (s) => s.properties.title
  );

  const requests = [];

  if (!existingSheets.includes("Transaktionen")) {
    requests.push({
      addSheet: { properties: { title: "Transaktionen" } },
    });
  }

  if (!existingSheets.includes("Zusammenfassung")) {
    requests.push({
      addSheet: { properties: { title: "Zusammenfassung" } },
    });
  }

  if (requests.length > 0) {
    await sheets.spreadsheets.batchUpdate({
      spreadsheetId,
      resource: { requests },
    });
  }

  // Header für Transaktionen setzen
  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range: "Transaktionen!A1:J1",
    valueInputOption: "RAW",
    resource: {
      values: [
        [
          "Datum",
          "Betrag Brutto",
          "Netto",
          "MwSt",
          "MwSt-Satz",
          "Händler",
          "Kategorie",
          "Typ",
          "Beleg-Status",
          "Beschreibung",
        ],
      ],
    },
  });

  // Zusammenfassung-Header und Formeln
  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range: "Zusammenfassung!A1:F1",
    valueInputOption: "RAW",
    resource: {
      values: [
        [
          "Monat",
          "Einnahmen Brutto",
          "Ausgaben Brutto",
          "Netto Einnahmen",
          "Netto Ausgaben",
          "MwSt Zahllast",
        ],
      ],
    },
  });

  // Monatszeilen mit Formeln
  const months = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
  ];
  const year = new Date().getFullYear();
  const monthRows = months.map((name, i) => {
    const m = String(i + 1).padStart(2, "0");
    const startDate = `${year}-${m}-01`;
    const endDate = i < 11 ? `${year}-${String(i + 2).padStart(2, "0")}-01` : `${year + 1}-01-01`;
    return [
      `${name} ${year}`,
      `=SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Einnahme")*Transaktionen!B2:B10000)`,
      `=SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Ausgabe")*Transaktionen!B2:B10000)`,
      `=SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Einnahme")*Transaktionen!C2:C10000)`,
      `=SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Ausgabe")*Transaktionen!C2:C10000)`,
      `=SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Einnahme")*Transaktionen!D2:D10000)-SUMPRODUCT((Transaktionen!A2:A10000>="${startDate}")*(Transaktionen!A2:A10000<"${endDate}")*(Transaktionen!H2:H10000="Ausgabe")*Transaktionen!D2:D10000)`,
    ];
  });

  await sheets.spreadsheets.values.update({
    spreadsheetId,
    range: "Zusammenfassung!A2:F13",
    valueInputOption: "USER_ENTERED",
    resource: { values: monthRows },
  });

  console.log("Google Sheets initialisiert.");
}

/**
 * Fügt eine Transaktion zum Transaktionen-Tab hinzu.
 */
async function addTransaction(data) {
  const auth = await getAuthenticatedClient();
  const sheets = google.sheets({ version: "v4", auth });

  await sheets.spreadsheets.values.append({
    spreadsheetId: process.env.GOOGLE_SHEETS_ID,
    range: "Transaktionen!A:J",
    valueInputOption: "USER_ENTERED",
    resource: {
      values: [
        [
          data.datum || new Date().toISOString().split("T")[0],
          data.betrag_brutto || 0,
          data.betrag_netto || 0,
          data.mwst_betrag || 0,
          data.mwst_satz || 19,
          data.haendler || "Unbekannt",
          data.kategorie || "Sonstiges",
          data.typ || "Ausgabe",
          data.beleg_status || "Beleg vorhanden",
          data.beschreibung || "",
        ],
      ],
    },
  });
}

/**
 * Holt die letzten N Transaktionen.
 */
async function getRecentTransactions(count = 10) {
  const auth = await getAuthenticatedClient();
  const sheets = google.sheets({ version: "v4", auth });

  const response = await sheets.spreadsheets.values.get({
    spreadsheetId: process.env.GOOGLE_SHEETS_ID,
    range: "Transaktionen!A:J",
  });

  const rows = response.data.values || [];
  if (rows.length <= 1) return []; // Nur Header

  const headers = rows[0];
  const dataRows = rows.slice(1).slice(-count);

  return dataRows.map((row) => {
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = row[i] || "";
    });
    return obj;
  });
}

/**
 * Holt alle Transaktionen (für Matching).
 */
async function getAllTransactions() {
  const auth = await getAuthenticatedClient();
  const sheets = google.sheets({ version: "v4", auth });

  const response = await sheets.spreadsheets.values.get({
    spreadsheetId: process.env.GOOGLE_SHEETS_ID,
    range: "Transaktionen!A:J",
  });

  const rows = response.data.values || [];
  if (rows.length <= 1) return [];

  const headers = rows[0];
  return rows.slice(1).map((row, index) => {
    const obj = { _rowIndex: index + 2 }; // 1-indexed + header
    headers.forEach((h, i) => {
      obj[h] = row[i] || "";
    });
    return obj;
  });
}

/**
 * Aktualisiert den Beleg-Status einer Transaktion.
 */
async function updateTransactionStatus(rowIndex, status) {
  const auth = await getAuthenticatedClient();
  const sheets = google.sheets({ version: "v4", auth });

  await sheets.spreadsheets.values.update({
    spreadsheetId: process.env.GOOGLE_SHEETS_ID,
    range: `Transaktionen!I${rowIndex}`,
    valueInputOption: "RAW",
    resource: { values: [[status]] },
  });
}

module.exports = {
  getOAuth2Client,
  getAuthUrl,
  getAuthenticatedClient,
  saveTokens,
  initializeSpreadsheet,
  addTransaction,
  getRecentTransactions,
  getAllTransactions,
  updateTransactionStatus,
  TOKENS_PATH,
};
