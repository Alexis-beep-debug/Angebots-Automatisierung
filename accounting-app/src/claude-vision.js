const Anthropic = require("@anthropic-ai/sdk");

const client = new Anthropic();

const CATEGORIES = [
  "Büromaterial",
  "Reise",
  "Software",
  "Hardware",
  "Bewirtung",
  "Sonstiges",
];

/**
 * Analysiert ein Belegfoto mit Claude Vision und extrahiert strukturierte Daten.
 * @param {Buffer} imageBuffer - Das Bild als Buffer
 * @param {string} mimeType - z.B. "image/jpeg" oder "image/png"
 * @returns {Promise<Object>} Erkannte Belegdaten
 */
async function analyzeReceipt(imageBuffer, mimeType) {
  const base64Image = imageBuffer.toString("base64");

  const response = await client.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    messages: [
      {
        role: "user",
        content: [
          {
            type: "image",
            source: {
              type: "base64",
              media_type: mimeType,
              data: base64Image,
            },
          },
          {
            type: "text",
            text: `Analysiere diesen Beleg/Rechnung und extrahiere die folgenden Informationen.
Antworte NUR mit validem JSON, kein anderer Text.

{
  "betrag_netto": <number - Nettobetrag in Euro>,
  "mwst_betrag": <number - MwSt-Betrag in Euro>,
  "betrag_brutto": <number - Bruttobetrag in Euro>,
  "mwst_satz": <number - MwSt-Satz in Prozent, z.B. 19 oder 7>,
  "datum": "<string - Datum im Format YYYY-MM-DD>",
  "haendler": "<string - Name des Händlers/Dienstleisters>",
  "kategorie": "<string - Eine der folgenden: ${CATEGORIES.join(", ")}>",
  "beschreibung": "<string - Kurze Beschreibung des Kaufs>"
}

Wenn ein Wert nicht erkennbar ist, setze null.
Wenn nur der Bruttobetrag sichtbar ist, berechne Netto und MwSt mit 19%.
Wähle die passendste Kategorie basierend auf dem Händler und den Artikeln.`,
          },
        ],
      },
    ],
  });

  const text = response.content[0].text;

  // Extrahiere JSON aus der Antwort (falls Claude es in Markdown-Codeblöcke packt)
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error("Claude hat kein valides JSON zurückgegeben: " + text);
  }

  const data = JSON.parse(jsonMatch[0]);

  // Validierung und Defaults
  if (data.betrag_brutto && !data.betrag_netto) {
    data.betrag_netto = Math.round((data.betrag_brutto / 1.19) * 100) / 100;
    data.mwst_betrag =
      Math.round((data.betrag_brutto - data.betrag_netto) * 100) / 100;
    data.mwst_satz = 19;
  }

  if (!CATEGORIES.includes(data.kategorie)) {
    data.kategorie = "Sonstiges";
  }

  return data;
}

/**
 * Analysiert ein PDF-Dokument (als Buffer) mit Claude Vision.
 */
async function analyzePDF(pdfBuffer) {
  const base64PDF = pdfBuffer.toString("base64");

  const response = await client.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    messages: [
      {
        role: "user",
        content: [
          {
            type: "document",
            source: {
              type: "base64",
              media_type: "application/pdf",
              data: base64PDF,
            },
          },
          {
            type: "text",
            text: `Analysiere diese Rechnung/Beleg und extrahiere die folgenden Informationen.
Antworte NUR mit validem JSON, kein anderer Text.

{
  "betrag_netto": <number - Nettobetrag in Euro>,
  "mwst_betrag": <number - MwSt-Betrag in Euro>,
  "betrag_brutto": <number - Bruttobetrag in Euro>,
  "mwst_satz": <number - MwSt-Satz in Prozent, z.B. 19 oder 7>,
  "datum": "<string - Datum im Format YYYY-MM-DD>",
  "haendler": "<string - Name des Händlers/Dienstleisters>",
  "kategorie": "<string - Eine der folgenden: ${CATEGORIES.join(", ")}>",
  "beschreibung": "<string - Kurze Beschreibung des Kaufs>"
}

Wenn ein Wert nicht erkennbar ist, setze null.
Wenn nur der Bruttobetrag sichtbar ist, berechne Netto und MwSt mit 19%.
Wähle die passendste Kategorie basierend auf dem Händler und den Artikeln.`,
          },
        ],
      },
    ],
  });

  const text = response.content[0].text;
  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error("Claude hat kein valides JSON zurückgegeben: " + text);
  }

  const data = JSON.parse(jsonMatch[0]);

  if (data.betrag_brutto && !data.betrag_netto) {
    data.betrag_netto = Math.round((data.betrag_brutto / 1.19) * 100) / 100;
    data.mwst_betrag =
      Math.round((data.betrag_brutto - data.betrag_netto) * 100) / 100;
    data.mwst_satz = 19;
  }

  if (!CATEGORIES.includes(data.kategorie)) {
    data.kategorie = "Sonstiges";
  }

  return data;
}

module.exports = { analyzeReceipt, analyzePDF, CATEGORIES };
