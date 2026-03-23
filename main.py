"""
Angebotsautomatisierung - G+C Facility GmbH
Webhook-Endpunkt fuer SuperForms -> Pipedrive + Lexoffice + Google Slides/Drive
"""

import logging
import random
import string
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

import pipedrive_client as pd
import lexoffice_client as lx
import google_client as gc
import price_calculator as calc
from config import EWGENI_TELEFON, EWGENI_EMAIL

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Angebotsautomatisierung")

CONTENT_MAP = {
    "Ineffektive und Inkonsistente Reinigungsqualität": (
        "Schwankende Reinigungsergebnisse hinterlassen einen unprofessionellen Eindruck und führen zu Unzufriedenheit bei Mitarbeitenden und Gästen.",
        "Feste Reinigungsteams mit definierten Revierplänen und regelmäßigen Qualitätschecks sorgen für gleichbleibend hohe Standards – messbar und nachvollziehbar.",
    ),
    "Schlechte Urlaubs/ und Krankheitsvertretung": (
        "Fällt Personal aus, bleibt die Reinigung aus oder wird reduziert – ohne Vorwarnung, ohne Lösung, auf Kosten Ihrer Hygiene.",
        "Unser eingespielter Personalpool garantiert lückenlose Vertretung. Ausfälle werden intern abgefangen – Sie merken nichts davon, die Leistung bleibt konstant.",
    ),
    "fehlende Kontrolle": (
        "Ohne strukturierte Nachweise wissen Verantwortliche nicht, ob und was tatsächlich gereinigt wurde. Vertrauen ersetzt keine Transparenz.",
        "Digitale Leistungsprotokolle dokumentieren jeden Einsatz in Echtzeit. Sie haben jederzeit Überblick – ohne selbst nachkontrollieren zu müssen.",
    ),
    "Intransparenz bei Leistung, Kosten und Prozessen": (
        "Unklare Vertragsstrukturen und versteckte Kosten erschweren die Planung und erzeugen unnötigen Verwaltungsaufwand.",
        "Transparente Festpreise, klar definierte Leistungspakete und offene Kommunikation – Sie wissen immer genau, was Sie bekommen und was es kostet.",
    ),
    "Mangelnde Zuverlässigkeit (Reliabilität)": (
        "Unzuverlässige Dienstleister zwingen zur ständigen Nachkontrolle und binden wertvolle Zeit, die Ihr Team anderweitig dringend benötigt.",
        "Verbindliche Servicevereinbarungen und ein festes Ansprechpartnermodell stellen sicher, dass Zusagen eingehalten werden – oder wir reagieren sofort.",
    ),
    "Schlechtes Beschwerdemanagement": (
        "Beschwerden versickern, Ansprechpartner sind nicht erreichbar, Probleme wiederholen sich – das kostet Zeit, Geld und Nerven.",
        "Ihr persönlicher Ansprechpartner ist direkt erreichbar und löst Probleme schnell und verbindlich. Jede Rückmeldung wird dokumentiert und nachverfolgt.",
    ),
    "Fachbetrieb / Meisterbetrieb": (
        "Viele Dienstleister arbeiten ohne Qualifikationsnachweis – das Risiko: mangelnde Fachkenntnis bei Spezialreinigungen und fehlende Haftungsabsicherung.",
        "Als zertifizierter Fach- und Meisterbetrieb garantieren wir qualifizierte Ausführung, geprüfte Standards und volle Versicherung – für Ihre Sicherheit.",
    ),
    "Nachhaltigkeit und Compliance": (
        "Steigende Anforderungen an Umweltstandards und gesetzliche Compliance-Pflichten stellen Unternehmen vor wachsende Herausforderungen.",
        "Wir setzen auf zertifizierte, umweltfreundliche Reinigungsmittel und -verfahren – vollständig dokumentiert für Ihre Compliance-Nachweise.",
    ),
    "Proaktivität in Beratung und Ausführung": (
        "Reaktive Dienstleister warten auf Anweisung. Verbesserungspotenziale bleiben ungenutzt, Probleme entstehen, bevor sie angesprochen werden.",
        "Wir kommen mit Ideen, nicht nur mit Reinigungswagen. Regelmäßige Beratungsgespräche und proaktive Vorschläge halten Ihr Objekt dauerhaft auf Top-Niveau.",
    ),
    "Digitale Nachweis- und Kontrollsysteme": (
        "Ohne digitale Dokumentation sind Leistungsnachweise lückenhaft, Eskalationen schwer nachvollziehbar und Audits aufwändig.",
        "Unser digitales Kontrollsystem liefert Echtzeit-Nachweise für jeden Reinigungsvorgang – jederzeit abrufbar, revisionssicher und auditkonform.",
    ),
    "Kein Zeitverlust durch ständiges kontrollieren": (
        "Selbst kontrollieren zu müssen bindet Ressourcen, die im Kerngeschäft fehlen – und ist kein Zeichen eines wirklich zuverlässigen Dienstleisters.",
        "Unsere eigene Qualitätssicherung macht Ihre Kontrolle überflüssig. Sie erhalten regelmäßige Berichte, ohne selbst suchen oder nachhaken zu müssen.",
    ),
    "Alles aus einer Hand": (
        "Mehrere Dienstleister bedeuten mehrere Schnittstellen, Koordinationsaufwand und erhöhtes Fehlerrisiko bei der Abstimmung.",
        "Von der Unterhaltsreinigung über Fenster bis zum Spezialservice – ein Ansprechpartner koordiniert alles. Einfach, effizient, zuverlässig.",
    ),
}


def _generate_angebots_id():
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"GC-{datetime.now().strftime('%Y%m%d')}-{suffix}"


def _extract_checkbox_labels(data, field_id):
    entry = data.get(field_id, {})
    raw = entry.get("value", "") if isinstance(entry, dict) else str(entry)
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x]
    return [s.strip() for s in str(raw).split(",") if s.strip()]


def _build_probleme_slots(data):
    slots = []
    for field_id in ("Möglichkeit_2_2", "field_cCLhd"):
        for label in _extract_checkbox_labels(data, field_id):
            entry = CONTENT_MAP.get(label)
            if entry and len(slots) < 6:
                slots.append({"titel": label, "herausforderung": entry[0], "ansatz": entry[1]})
    return slots


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}


@app.post("/webhook/angebot")
async def handle_angebot(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    log.info("Angebot-Webhook empfangen")
    background_tasks.add_task(_process_angebot, body)
    return JSONResponse({"status": "accepted"})


async def _process_angebot(body):
    try:
        await _run_pipeline(body)
    except Exception as e:
        log.error("Pipeline-Fehler: %s", e, exc_info=True)


async def _run_pipeline(body):
    if isinstance(body, list):
        data = body[0].get("data", {})
    else:
        data = body.get("data", body)

    def _v(key):
        entry = data.get(key, {})
        return str(entry.get("value", "")).strip() if isinstance(entry, dict) else ""

    first_name = _v("first_name")
    last_name  = _v("last_name")
    name       = f"{first_name} {last_name}".strip() or "Unbekannt"
    email      = _v("Email")
    phone      = _v("Telefonnummer")
    company    = _v("Firmenname")
    city       = _v("field_ayedY")
    street     = _v("Anschrift")
    plz        = _v("field_YSXLd")

    if not email:
        log.error("E-Mail fehlt im Payload – Pipeline abgebrochen")
        return

    adresse = " ".join(filter(None, [street, plz, city]))

    line_items   = calc.calculate(body)
    netto_gesamt = calc.total_net(line_items)
    log.info("Preisberechnung: %s Positionen, Netto: %.2f EUR", len(line_items), netto_gesamt)

    angebots_id = _generate_angebots_id()
    log.info("Angebots-ID: %s", angebots_id)

    person = await pd.find_person_by_email(email)
    if person:
        person_id = person["id"]
    else:
        person    = await pd.create_person(name=name, email=email, phone=phone, company=company)
        person_id = person["id"]

    existing_deal = await pd.find_open_deal_by_person(person_id)
    if existing_deal:
        deal_id = existing_deal["id"]
    else:
        deal_title = f"Angebot {company or name} – {datetime.now().strftime('%d.%m.%Y')}"
        deal       = await pd.create_deal(person_id=person_id, title=deal_title, value=netto_gesamt)
        deal_id    = deal["id"]

    lx_quote_id = ""
    lx_deeplink = ""
    try:
        lx_contact_id = await lx.find_or_create_contact(name=name, email=email, phone=phone, company=company)
        lx_line_items = [{"name": i["name"], "quantity": i["quantity"], "unit": i["unit"], "price": i["price"]} for i in line_items]
        lx_result   = await lx.create_quote(contact_id=lx_contact_id, line_items=lx_line_items, title=f"Angebot {company or name}")
        lx_quote_id = lx_result["id"]
        lx_deeplink = lx_result["deeplink"]
    except Exception as e:
        log.warning("Lexoffice fehlgeschlagen: %s", e)

    slides_url     = ""
    folder_url     = ""
    slides_pdf_url = ""
    lx_pdf_url     = ""
    try:
        folder_name = f"Angebot_{(company or name).replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}_{angebots_id}"
        folder_id   = gc.create_folder(folder_name)
        folder_url  = f"https://drive.google.com/drive/folders/{folder_id}"

        slides_name     = f"Angebot {angebots_id} – {company or name}"
        presentation_id = gc.copy_template(folder_id=folder_id, name=slides_name)

        kalkulation_text = "\n".join(
            f"{i['name']}: {i['quantity']} {i['unit']} x {i['price']:.2f} EUR = {i['total']:.2f} EUR"
            for i in line_items
        )
        kalkulation_text += f"\n\nNetto gesamt/Monat: {netto_gesamt:.2f} EUR"

        extras = [i for i in line_items if i.get("unit") in ("Pauschal/Monat", "Pauschal")]
        zusatz_text = (
            "\n".join(f"- {i['name']}: {i['price']:.2f} EUR/Monat" for i in extras)
            if extras else "– keine Zusatzmodule gewählt –"
        )

        probleme_slots = _build_probleme_slots(data)

        replacements = {
            "{{Firma_Name}}":         company or name,
            "{{Kontaktperson_Name}}": name,
            "{{Objekt_Adresse}}":     adresse,
            "{{Datum}}":              datetime.now().strftime("%d.%m.%Y"),
            "{{Angebots_ID}}":        angebots_id,
            "{{Datum_Begehung}}":     "",
            "{{Telefon}}":            phone,
            "{{Email}}":              email,
            "{{Kalkulation_Detail}}": kalkulation_text,
            "{{Netto_Gesamt}}":       f"{netto_gesamt:.2f} EUR",
            "{{Zusatzmodule}}":       zusatz_text,
            "{{Ewgeni_Telefon}}":     EWGENI_TELEFON,
            "{{Ewgeni_Email}}":       EWGENI_EMAIL,
            "{{Angebot_Link}}":       lx_deeplink,
        }
        gc.fill_presentation(presentation_id, replacements)

        tmpl_slide_id = gc.find_problem_slide(presentation_id, marker="{{Probleme_Titel}}")
        if tmpl_slide_id:
            for slot in probleme_slots:
                new_id = gc.duplicate_slide(presentation_id, tmpl_slide_id)
                gc.fill_slide(presentation_id, new_id, {
                    "{{Probleme_Titel}}":          slot["titel"],
                    "{{Problem_Herausforderung}}": slot["herausforderung"],
                    "{{Problem_Ansatz}}":          slot["ansatz"],
                })
                log.info("Problem-Slide erstellt: %s", slot["titel"][:40])
            gc.delete_slide(presentation_id, tmpl_slide_id)

        slides_url = gc.get_presentation_url(presentation_id)

        try:
            pdf_bytes      = gc.export_as_pdf(presentation_id)
            pdf_file_id    = gc.upload_pdf(folder_id=folder_id, name=f"Angebot_{angebots_id}.pdf", pdf_bytes=pdf_bytes)
            slides_pdf_url = gc.get_drive_file_url(pdf_file_id)
        except Exception as e:
            log.warning("Slides-PDF-Export fehlgeschlagen: %s", e)

        if lx_quote_id:
            try:
                lx_pdf_bytes = await lx.download_pdf(lx_quote_id)
                lx_file_id   = gc.upload_pdf(folder_id=folder_id, name=f"Lexoffice_Angebot_{angebots_id}.pdf", pdf_bytes=lx_pdf_bytes)
                lx_pdf_url   = gc.get_drive_file_url(lx_file_id)
            except Exception as e:
                log.warning("Lexoffice-PDF-Download fehlgeschlagen: %s", e)

    except Exception as e:
        log.warning("Google Drive/Slides fehlgeschlagen: %s", e)

    summary = calc.build_summary(data, line_items)
    note_lines = [
        f"Angebot {angebots_id} automatisch erstellt", "",
        f"{company} | {adresse}",
        f"{name} | {email} | {phone}", "",
        summary,
    ]
    if lx_deeplink:   note_lines += ["", f"Lexoffice Angebot: {lx_deeplink}"]
    if lx_pdf_url:    note_lines += [f"Lexoffice PDF: {lx_pdf_url}"]
    if slides_url:    note_lines += ["", f"Google Slides: {slides_url}"]
    if slides_pdf_url: note_lines += [f"Slides PDF: {slides_pdf_url}"]
    if folder_url:    note_lines += ["", f"Google Drive Ordner: {folder_url}"]

    await pd.add_note(deal_id=deal_id, content="\n".join(note_lines))

    activity_note = f"Angebot {angebots_id} ueber {netto_gesamt:.2f} EUR netto wurde erstellt."
    if lx_deeplink: activity_note += f"\nLexoffice: {lx_deeplink}"
    if slides_url:  activity_note += f"\nSlides: {slides_url}"
    if folder_url:  activity_note += f"\nOrdner: {folder_url}"

    await pd.add_activity(
        person_id=person_id,
        deal_id=deal_id,
        subject=f"Angebot {angebots_id} fertig: {company or name}",
        note=activity_note,
    )
    log.info("Pipeline abgeschlossen: %s | Deal %s | Angebot %s", name, deal_id, angebots_id)
