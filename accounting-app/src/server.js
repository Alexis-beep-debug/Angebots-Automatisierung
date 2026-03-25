require("dotenv").config();
const express = require("express");
const multer = require("multer");
const path = require("path");
const cron = require("node-cron");

const { analyzeReceipt } = require("./claude-vision");
const sheets = require("./google-sheets");
const { importFromGmail } = require("./gmail-import");
const kontist = require("./kontist");
const { runMatching } = require("./matching");

const app = express();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, "..", "public")));

// ==================== AUTH ROUTES ====================

// Google OAuth2
app.get("/auth/google", (req, res) => {
  res.redirect(sheets.getAuthUrl());
});

app.get("/auth/google/callback", async (req, res) => {
  try {
    await sheets.saveTokens(req.query.code);
    // Initialisiere Sheets nach erfolgreicher Auth
    await sheets.initializeSpreadsheet();
    res.send("Google erfolgreich verbunden! Du kannst dieses Fenster schließen.");
  } catch (error) {
    res.status(500).send("Fehler bei Google Auth: " + error.message);
  }
});

// Kontist OAuth2
app.get("/auth/kontist", (req, res) => {
  res.redirect(kontist.getAuthUrl());
});

app.get("/auth/kontist/callback", async (req, res) => {
  try {
    await kontist.saveTokens(req.query.code);
    res.send("Kontist erfolgreich verbunden! Du kannst dieses Fenster schließen.");
  } catch (error) {
    res.status(500).send("Fehler bei Kontist Auth: " + error.message);
  }
});

// Auth-Status prüfen
app.get("/api/auth/status", (req, res) => {
  const fs = require("fs");
  res.json({
    google: fs.existsSync(sheets.TOKENS_PATH),
    kontist: fs.existsSync(kontist.TOKENS_PATH),
  });
});

// ==================== API ROUTES ====================

// Beleg hochladen und analysieren
app.post("/api/receipt/scan", upload.single("image"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "Kein Bild hochgeladen" });
    }

    const mimeType = req.file.mimetype;
    if (!mimeType.startsWith("image/")) {
      return res.status(400).json({ error: "Nur Bilder sind erlaubt" });
    }

    const data = await analyzeReceipt(req.file.buffer, mimeType);
    res.json({ success: true, data });
  } catch (error) {
    console.error("Fehler bei Beleg-Scan:", error);
    res.status(500).json({ error: error.message });
  }
});

// Erkannte Daten bestätigen und in Sheets speichern
app.post("/api/receipt/confirm", async (req, res) => {
  try {
    const data = req.body;
    await sheets.addTransaction({
      ...data,
      typ: data.typ || "Ausgabe",
      beleg_status: "Beleg vorhanden",
    });
    res.json({ success: true });
  } catch (error) {
    console.error("Fehler beim Speichern:", error);
    res.status(500).json({ error: error.message });
  }
});

// Ausgehende Rechnung manuell erfassen
app.post("/api/invoice/outgoing", async (req, res) => {
  try {
    const data = req.body;
    await sheets.addTransaction({
      ...data,
      typ: "Einnahme",
      beleg_status: "Rechnung gestellt",
    });
    res.json({ success: true });
  } catch (error) {
    console.error("Fehler beim Speichern:", error);
    res.status(500).json({ error: error.message });
  }
});

// Letzte Transaktionen
app.get("/api/transactions/recent", async (req, res) => {
  try {
    const count = parseInt(req.query.count) || 10;
    const transactions = await sheets.getRecentTransactions(count);
    res.json({ success: true, transactions });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Manueller Gmail-Import
app.post("/api/gmail/import", async (req, res) => {
  try {
    const result = await importFromGmail();
    res.json({ success: true, ...result });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Manueller Kontist-Import
app.post("/api/kontist/import", async (req, res) => {
  try {
    const result = await kontist.fetchTransactions();
    res.json({ success: true, ...result });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Manuelles Matching
app.post("/api/matching/run", async (req, res) => {
  try {
    const result = await runMatching();
    res.json({ success: true, ...result });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Health Check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// ==================== CRON JOBS ====================
// Alle 4 Stunden: Gmail Import + Kontist Import + Matching
cron.schedule("0 */4 * * *", async () => {
  console.log("[Cron] Starte automatische Importe...");
  try {
    await importFromGmail();
  } catch (error) {
    console.error("[Cron] Gmail Import Fehler:", error.message);
  }

  try {
    await kontist.fetchTransactions();
  } catch (error) {
    console.error("[Cron] Kontist Import Fehler:", error.message);
  }

  try {
    await runMatching();
  } catch (error) {
    console.error("[Cron] Matching Fehler:", error.message);
  }
  console.log("[Cron] Automatische Importe abgeschlossen.");
});

// ==================== START ====================
app.listen(PORT, () => {
  console.log(`Buchhaltungs-App läuft auf Port ${PORT}`);
  console.log(`PWA: http://localhost:${PORT}`);
  console.log(`Google Auth: http://localhost:${PORT}/auth/google`);
  console.log(`Kontist Auth: http://localhost:${PORT}/auth/kontist`);
});
