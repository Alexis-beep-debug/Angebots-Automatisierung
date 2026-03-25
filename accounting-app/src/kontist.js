const fs = require("fs");
const path = require("path");
const { addTransaction } = require("./google-sheets");

const TOKENS_PATH = path.join(__dirname, "..", "tokens", "kontist-tokens.json");
const STATE_PATH = path.join(__dirname, "..", "tokens", "kontist-state.json");

function getAuthUrl() {
  const params = new URLSearchParams({
    client_id: process.env.KONTIST_CLIENT_ID,
    redirect_uri: process.env.KONTIST_REDIRECT_URI,
    response_type: "code",
    scope: "transactions",
  });
  return `https://api.kontist.com/api/oauth/authorize?${params}`;
}

async function saveTokens(code) {
  const response = await fetch("https://api.kontist.com/api/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "authorization_code",
      code,
      client_id: process.env.KONTIST_CLIENT_ID,
      client_secret: process.env.KONTIST_CLIENT_SECRET,
      redirect_uri: process.env.KONTIST_REDIRECT_URI,
    }),
  });

  if (!response.ok) {
    throw new Error(`Kontist Token-Fehler: ${await response.text()}`);
  }

  const tokens = await response.json();
  fs.mkdirSync(path.dirname(TOKENS_PATH), { recursive: true });
  fs.writeFileSync(TOKENS_PATH, JSON.stringify(tokens, null, 2));
  return tokens;
}

async function getAccessToken() {
  if (!fs.existsSync(TOKENS_PATH)) {
    throw new Error("Kontist nicht autorisiert. Bitte /auth/kontist aufrufen.");
  }

  let tokens = JSON.parse(fs.readFileSync(TOKENS_PATH, "utf8"));

  // Token refresh falls nötig
  if (tokens.refresh_token) {
    const response = await fetch("https://api.kontist.com/api/oauth/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grant_type: "refresh_token",
        refresh_token: tokens.refresh_token,
        client_id: process.env.KONTIST_CLIENT_ID,
        client_secret: process.env.KONTIST_CLIENT_SECRET,
      }),
    });

    if (response.ok) {
      const newTokens = await response.json();
      tokens = { ...tokens, ...newTokens };
      fs.writeFileSync(TOKENS_PATH, JSON.stringify(tokens, null, 2));
    }
  }

  return tokens.access_token;
}

function getLastFetchDate() {
  if (fs.existsSync(STATE_PATH)) {
    const state = JSON.parse(fs.readFileSync(STATE_PATH, "utf8"));
    return state.lastFetch || null;
  }
  return null;
}

function saveLastFetchDate(date) {
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true });
  fs.writeFileSync(STATE_PATH, JSON.stringify({ lastFetch: date }, null, 2));
}

/**
 * Holt neue Transaktionen von Kontist via GraphQL.
 */
async function fetchTransactions() {
  console.log("[Kontist] Starte Transaktions-Import...");

  let accessToken;
  try {
    accessToken = await getAccessToken();
  } catch {
    console.log("[Kontist] Nicht autorisiert, überspringe Import.");
    return { imported: 0, errors: [] };
  }

  const lastFetch = getLastFetchDate();
  const fromDate = lastFetch || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();

  const query = `
    query {
      viewer {
        mainAccount {
          transactions(filter: { from: "${fromDate}" }) {
            edges {
              node {
                id
                amount
                name
                purpose
                bookingDate
                valutaDate
                type
              }
            }
          }
        }
      }
    }
  `;

  const response = await fetch("https://api.kontist.com/api/graphql", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    throw new Error(`Kontist API Fehler: ${response.status}`);
  }

  const data = await response.json();

  if (data.errors) {
    throw new Error(`Kontist GraphQL Fehler: ${JSON.stringify(data.errors)}`);
  }

  const edges = data.data?.viewer?.mainAccount?.transactions?.edges || [];
  const results = { imported: 0, errors: [] };

  for (const { node } of edges) {
    try {
      // Kontist gibt Beträge in Cent zurück
      const amountEuro = node.amount / 100;
      const isIncome = amountEuro > 0;
      const absAmount = Math.abs(amountEuro);

      await addTransaction({
        datum: node.bookingDate?.split("T")[0] || node.valutaDate?.split("T")[0],
        betrag_brutto: absAmount,
        betrag_netto: Math.round((absAmount / 1.19) * 100) / 100,
        mwst_betrag: Math.round((absAmount - absAmount / 1.19) * 100) / 100,
        mwst_satz: 19,
        haendler: node.name || "Unbekannt",
        kategorie: "Sonstiges",
        typ: isIncome ? "Einnahme" : "Ausgabe",
        beleg_status: "Offen - kein Beleg",
        beschreibung: node.purpose || "",
      });

      results.imported++;
    } catch (error) {
      results.errors.push({ id: node.id, error: error.message });
    }
  }

  saveLastFetchDate(new Date().toISOString());

  console.log(
    `[Kontist] Import abgeschlossen: ${results.imported} Transaktionen, ${results.errors.length} Fehler.`
  );
  return results;
}

module.exports = { getAuthUrl, saveTokens, fetchTransactions, TOKENS_PATH };
