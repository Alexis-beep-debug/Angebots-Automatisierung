import logging
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
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
    return {"status":"ok","timestamp":datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

@app.post("/webhook/angebot")
async def handle_angebot(request: Request):
    try: body = await request.json()
    except: raise HTTPException(status_code=400,detail="Invalid JSON")
    log.info("Webhook empfangen")
    if isinstance(body,list): data = body[0].get("data",{})
    else: data = body.get("data",body)
    def _v(k): return (data.get(k) or {}).get("value","") if isinstance(data.get(k),dict) else ""
    first_name=_v("first_name"); last_name=_v("last_name")
    name=f"{first_name} {last_name}".strip() or "Unbekannt"
    email=_v("Email"); phone=_v("Telefonnummer"); company=_v("Firmenname")
    city=_v("field_ayedY"); street=_v("Anschrift"); plz=_v("field_YSXLd")
    if not email: raise HTTPException(status_code=422,detail="E-Mail fehlt")
    line_items=calc.calculate(body); netto=calc.total_net(line_items)
    log.info(f"Netto: {netto} EUR")
    person=await pd.find_person_by_email(email)
    if person: person_id=person["id"]
    else:
        person=await pd.create_person(name=name,email=email,phone=phone,company=company)
        person_id=person["id"]
    deal_title=f"Angebot {company or name} – {datetime.now().strftime('%d.%m.%Y')}"
    deal=await pd.create_deal(person_id=person_id,title=deal_title,value=netto)
    deal_id=deal["id"]
    lx_contact_id=await lx.find_or_create_contact(name=name,email=email,phone=phone,company=company)
    lx_items=[{"name":i["name"],"quantity":i["quantity"],"unit":i["unit"],"price":i["price"]} for i in line_items]
    lx_quote=await lx.create_quote(contact_id=lx_contact_id,line_items=lx_items,title=f"Angebot für {company or name}")
    folder_name=f"Angebot_{(company or name).replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}"
    folder_id=gc.create_folder(folder_name)
    slides_name=f"Angebot {company or name} {datetime.now().strftime('%d.%m.%Y')}"
    presentation_id=gc.copy_template(folder_id=folder_id,name=slides_name)
    summary=calc.build_summary(data,line_items)
    replacements={"{{KUNDENNAME}}":name,"{{FIRMA}}":company,"{{EMAIL}}":email,"{{TELEFON}}":phone,"{{DATUM}}":datetime.now().strftime("%d.%m.%Y"),"{{NETTO_GESAMT}}":f"{netto:.2f} €","{{ANGEBOT_LINK}}":lx_quote["deeplink"]}
    gc.fill_presentation(presentation_id,replacements)
    slides_url=gc.get_presentation_url(presentation_id)
    note=f"📋 Angebot automatisch erstellt\n\n🏢 {company} | {street}, {plz} {city}\n\n{summary}\n\n📄 Lexoffice: {lx_quote['deeplink']}\n\n📊 Slides: {slides_url}"
    await pd.add_note(deal_id=deal_id,content=note)
    await pd.add_activity(person_id=person_id,deal_id=deal_id,subject=f"Angebot nachfassen: {company or name}",note=f"Angebot über {netto:.2f}€ erstellt. Bitte nachfassen!\n{lx_quote['deeplink']}")
    return JSONResponse({"status":"ok","deal_id":deal_id,"lexoffice_quote":lx_quote["deeplink"],"slides_url":slides_url,"netto_gesamt":netto})
