"""
Angebotsautomatisierung - G+C Facility GmbH
Webhook-Endpunkt für SuperForms → Pipedrive + Lexoffice + Google Slides
"""

import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

import pipedrive_client as pd
import lexoffice_client as lx
import google_client as gc
import price_calculator as calc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Angebotsautomatisierung")


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}


@app.post("/webhook/angebot")
async def handle_angebot(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    log.info("Angebot-Webhook empfangen, starte Hintergrundverarbeitung")
    background_tasks.add_task(_process_angebot, body)
    return JSONResponse({"status": "accepted"})


async def _process_angebot(body):
    try:
        if isinstance(body, list):
            data = body[0].get("data", {})
        else:
            data = body.get("data", body)

        def _v(key): return (data.get(key) or {}).get("value", "") if isinstance(data.get(key), dict) else ""

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
            log.error("E-Mail fehlt im Formular")
            return

        line_items = calc.calculate(body)
        netto_gesamt = calc.total_net(line_items)
        log.info("Preisberechnung: %s Positionen, Netto: %.2f EUR", len(line_items), netto_gesamt)

        person = await pd.find_person_by_email(email)
        if person:
            person_id = person["id"]
            log.info("Pipedrive Person gefunden: %s (ID %s)", name, person_id)
        else:
            person = await pd.create_person(name=name, email=email, phone=phone, company=company)
            person_id = person["id"]
            log.info("Pipedrive Person angelegt: %s (ID %s)", name, person_id)

        existing_deal = await pd.find_open_deal_by_person(person_id)
        if existing_deal:
            deal_id = existing_deal["id"]
            log.info("Pipedrive Deal bereits vorhanden (ID %s)", deal_id)
        else:
            deal_title = f"Angebot {company or name} – {datetime.now().strftime('%d.%m.%Y')}"
            deal = await pd.create_deal(person_id=person_id, title=deal_title, value=netto_gesamt)
            deal_id = deal["id"]
            log.info("Pipedrive Deal angelegt: %s (ID %s)", deal_title, deal_id)

        lx_deeplink = ""
        try:
            lx_contact_id = await lx.find_or_create_contact(name=name, email=email, phone=phone, company=company)
            lx_line_items = [{"name": i["name"], "quantity": i["quantity"], "unit": i["unit"], "price": i["price"]} for i in line_items]
            lx_quote = await lx.create_quote(contact_id=lx_contact_id, line_items=lx_line_items, title=f"Angebot für {company or name}")
            lx_deeplink = lx_quote["deeplink"]
            log.info("Lexoffice Angebot: %s", lx_deeplink)
        except Exception as e:
            log.warning("Lexoffice fehlgeschlagen: %s", e)

        slides_url = ""
        folder_url = ""
        try:
            folder_name = f"Angebot_{(company or name).replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
            folder_id = gc.create_folder(folder_name)
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            log.info("Google Drive Ordner: %s", folder_id)

            slides_name = f"Angebot {company or name} {datetime.now().strftime('%d.%m.%Y')}"
            presentation_id = gc.copy_template(folder_id=folder_id, name=slides_name)
            positionen_text = "\n".join(
                f"• {i['name']}: {i['quantity']} {i['unit']} × {i['price']:.2f} € = {i['total']:.2f} €"
                for i in line_items
            )
            replacements = {
                "{{KUNDENNAME}}":   name,
                "{{FIRMA}}":        company,
                "{{EMAIL}}":        email,
                "{{TELEFON}}":      phone,
                "{{DATUM}}":        datetime.now().strftime("%d.%m.%Y"),
                "{{POSITIONEN}}":   positionen_text,
                "{{NETTO_GESAMT}}": f"{netto_gesamt:.2f} €",
                "{{ANGEBOT_LINK}}": lx_deeplink,
            }
            gc.fill_presentation(presentation_id, replacements)
            slides_url = gc.get_presentation_url(presentation_id)
            log.info("Google Slides befüllt: %s", slides_url)
        except Exception as e:
            log.warning("Google Drive/Slides fehlgeschlagen: %s", e)

        summary = calc.build_summary(data, line_items)
        note_lines = ["📋 Angebot automatisch erstellt", "", f"🏢 {company} | {street}, {plz} {city}", "", summary]
        if lx_deeplink:
            note_lines += ["", f"📄 Lexoffice Angebot: {lx_deeplink}"]
        if slides_url:
            note_lines += ["", f"📊 Google Slides: {slides_url}"]
        if folder_url:
            note_lines += ["", f"📁 Google Drive Ordner: {folder_url}"]
        await pd.add_note(deal_id=deal_id, content="\n".join(note_lines))

        activity_note = f"Angebot über {netto_gesamt:.2f} € netto wurde erstellt."
        if lx_deeplink:
            activity_note += f"\nLexoffice: {lx_deeplink}"
        if slides_url:
            activity_note += f"\nSlides: {slides_url}"
        if folder_url:
            activity_note += f"\nOrdner: {folder_url}"
        await pd.add_activity(
            person_id=person_id,
            deal_id=deal_id,
            subject=f"Angebot fertig erstellt: {company or name}",
            note=activity_note,
        )
        log.info("Pipedrive Notiz und Aufgabe erstellt")

    except Exception as e:
        log.error("Fehler in Hintergrundverarbeitung: %s", e, exc_info=True)
