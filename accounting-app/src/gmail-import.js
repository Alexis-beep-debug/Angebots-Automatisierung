const { google } = require("googleapis");
const { getAuthenticatedClient } = require("./google-sheets");
const { analyzeReceipt, analyzePDF } = require("./claude-vision");
const { addTransaction } = require("./google-sheets");

const LABEL_NAME = "Verarbeitet";

/**
 * Findet oder erstellt das "Verarbeitet" Label in Gmail.
 */
async function getOrCreateLabel(gmail) {
  const labels = await gmail.users.labels.list({ userId: "me" });
  const existing = labels.data.labels.find((l) => l.name === LABEL_NAME);
  if (existing) return existing.id;

  const created = await gmail.users.labels.create({
    userId: "me",
    resource: {
      name: LABEL_NAME,
      labelListVisibility: "labelShow",
      messageListVisibility: "show",
    },
  });
  return created.data.id;
}

/**
 * Sucht nach Rechnungs-Emails und verarbeitet Anhänge.
 */
async function importFromGmail() {
  console.log("[Gmail] Starte Email-Import...");

  let auth;
  try {
    auth = await getAuthenticatedClient();
  } catch {
    console.log("[Gmail] Google nicht autorisiert, überspringe Import.");
    return { processed: 0, errors: [] };
  }

  const gmail = google.gmail({ version: "v1", auth });
  const labelId = await getOrCreateLabel(gmail);

  // Suche nach relevanten Emails ohne "Verarbeitet" Label
  const query =
    '(subject:Rechnung OR subject:Invoice OR subject:Beleg) has:attachment -label:Verarbeitet';
  const messages = await gmail.users.messages.list({
    userId: "me",
    q: query,
    maxResults: 20,
  });

  if (!messages.data.messages || messages.data.messages.length === 0) {
    console.log("[Gmail] Keine neuen Rechnungs-Emails gefunden.");
    return { processed: 0, errors: [] };
  }

  const results = { processed: 0, errors: [] };

  for (const msg of messages.data.messages) {
    try {
      const message = await gmail.users.messages.get({
        userId: "me",
        id: msg.id,
      });

      const parts = message.data.payload.parts || [];
      for (const part of parts) {
        if (!part.filename || part.filename.length === 0) continue;

        const isImage = part.mimeType?.startsWith("image/");
        const isPDF = part.mimeType === "application/pdf";

        if (!isImage && !isPDF) continue;

        // Anhang herunterladen
        const attachment = await gmail.users.messages.attachments.get({
          userId: "me",
          messageId: msg.id,
          id: part.body.attachmentId,
        });

        const buffer = Buffer.from(attachment.data.data, "base64");

        // Mit Claude analysieren
        let receiptData;
        if (isPDF) {
          receiptData = await analyzePDF(buffer);
        } else {
          receiptData = await analyzeReceipt(buffer, part.mimeType);
        }

        // In Google Sheets speichern
        await addTransaction({
          ...receiptData,
          typ: "Ausgabe",
          beleg_status: "Beleg vorhanden (Email-Import)",
        });

        results.processed++;
        console.log(
          `[Gmail] Beleg verarbeitet: ${receiptData.haendler} - ${receiptData.betrag_brutto}€`
        );
      }

      // Email als verarbeitet markieren
      await gmail.users.messages.modify({
        userId: "me",
        id: msg.id,
        resource: {
          addLabelIds: [labelId],
        },
      });
    } catch (error) {
      console.error(`[Gmail] Fehler bei Nachricht ${msg.id}:`, error.message);
      results.errors.push({ messageId: msg.id, error: error.message });
    }
  }

  console.log(
    `[Gmail] Import abgeschlossen: ${results.processed} Belege verarbeitet, ${results.errors.length} Fehler.`
  );
  return results;
}

module.exports = { importFromGmail };
