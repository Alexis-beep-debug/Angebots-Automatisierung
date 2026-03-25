const {
  getAllTransactions,
  updateTransactionStatus,
} = require("./google-sheets");

/**
 * Matching-Logik: Verbindet Belege/Rechnungen mit Bank-Transaktionen.
 *
 * Match-Kriterien: Betrag (±1€ Toleranz) + Datum (±3 Tage)
 *
 * Zwei Richtungen:
 * 1. Ausgaben: Eingescannte Belege ↔ Kontist-Abbuchungen
 * 2. Einnahmen: Ausgehende Rechnungen ↔ Kontist-Geldeingänge
 */
async function runMatching() {
  console.log("[Matching] Starte Matching-Prozess...");

  const transactions = await getAllTransactions();

  // Belege/Rechnungen die wir eingescannt haben (Ausgaben)
  const expenseReceipts = transactions.filter(
    (t) =>
      t["Typ"] === "Ausgabe" &&
      (t["Beleg-Status"] === "Beleg vorhanden" ||
        t["Beleg-Status"] === "Beleg vorhanden (Email-Import)")
  );

  // Ausgehende Rechnungen (Einnahmen mit Beleg)
  const outgoingInvoices = transactions.filter(
    (t) =>
      t["Typ"] === "Einnahme" &&
      (t["Beleg-Status"] === "Beleg vorhanden" ||
        t["Beleg-Status"] === "Beleg vorhanden (Email-Import)" ||
        t["Beleg-Status"] === "Rechnung gestellt")
  );

  // Bank-Transaktionen ohne Beleg (Ausgaben von Kontist)
  const bankExpenses = transactions.filter(
    (t) =>
      t["Typ"] === "Ausgabe" && t["Beleg-Status"] === "Offen - kein Beleg"
  );

  // Bank-Eingänge ohne Zuordnung (Einnahmen von Kontist)
  const bankIncome = transactions.filter(
    (t) =>
      t["Typ"] === "Einnahme" && t["Beleg-Status"] === "Offen - kein Beleg"
  );

  let matchCount = 0;

  // 1. Ausgaben matchen: Belege ↔ Bank-Abbuchungen
  for (const receipt of expenseReceipts) {
    if (receipt["Beleg-Status"] === "Gematcht") continue;

    const match = findMatch(receipt, bankExpenses);
    if (match) {
      await updateTransactionStatus(receipt._rowIndex, "Gematcht");
      await updateTransactionStatus(match._rowIndex, "Gematcht");
      match["Beleg-Status"] = "Gematcht";
      matchCount++;
      console.log(
        `[Matching] Ausgabe: ${receipt["Händler"]} ${receipt["Betrag Brutto"]}€ ↔ Bank ${match["Betrag Brutto"]}€`
      );
    }
  }

  // 2. Einnahmen matchen: Ausgehende Rechnungen ↔ Bank-Eingänge
  for (const invoice of outgoingInvoices) {
    if (invoice["Beleg-Status"] === "Gematcht") continue;

    const match = findMatch(invoice, bankIncome);
    if (match) {
      await updateTransactionStatus(invoice._rowIndex, "Gematcht");
      await updateTransactionStatus(match._rowIndex, "Gematcht");
      match["Beleg-Status"] = "Gematcht";
      matchCount++;
      console.log(
        `[Matching] Einnahme: ${invoice["Händler"]} ${invoice["Betrag Brutto"]}€ ↔ Bank ${match["Betrag Brutto"]}€`
      );
    }
  }

  // Markiere unbezahlte ausgehende Rechnungen
  for (const invoice of outgoingInvoices) {
    if (
      invoice["Beleg-Status"] !== "Gematcht" &&
      invoice["Beleg-Status"] !== "Offen - keine Transaktion"
    ) {
      await updateTransactionStatus(
        invoice._rowIndex,
        "Offen - keine Transaktion"
      );
    }
  }

  console.log(`[Matching] Abgeschlossen: ${matchCount} Matches gefunden.`);
  return { matchCount, total: transactions.length };
}

/**
 * Sucht einen passenden Match anhand Betrag (±1€) und Datum (±3 Tage).
 */
function findMatch(source, candidates) {
  const sourceAmount = parseFloat(source["Betrag Brutto"]) || 0;
  const sourceDate = new Date(source["Datum"]);

  for (const candidate of candidates) {
    if (candidate["Beleg-Status"] === "Gematcht") continue;

    const candidateAmount = parseFloat(candidate["Betrag Brutto"]) || 0;
    const candidateDate = new Date(candidate["Datum"]);

    // Betrag-Toleranz: ±1€
    if (Math.abs(sourceAmount - candidateAmount) > 1) continue;

    // Datum-Toleranz: ±3 Tage
    const daysDiff =
      Math.abs(sourceDate - candidateDate) / (1000 * 60 * 60 * 24);
    if (daysDiff > 3) continue;

    return candidate;
  }

  return null;
}

module.exports = { runMatching };
