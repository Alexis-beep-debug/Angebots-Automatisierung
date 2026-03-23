import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import GOOGLE_SLIDES_TEMPLATE_ID, GOOGLE_DRIVE_PARENT_FOLDER_ID

def _drive():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

def _slides():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token"
    )
    creds.refresh(Request())
    return build("slides", "v1", credentials=creds)

def create_folder(name):
    drive = _drive()
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if GOOGLE_DRIVE_PARENT_FOLDER_ID:
        body["parents"] = [GOOGLE_DRIVE_PARENT_FOLDER_ID]
    folder = drive.files().create(body=body, fields="id").execute()
    return folder["id"]

def copy_template(folder_id, name):
    drive = _drive()
    file_id = drive.files().copy(
        fileId=GOOGLE_SLIDES_TEMPLATE_ID,
        body={"name": name, "parents": [folder_id]},
        fields="id"
    ).execute()["id"]
    return file_id

def fill_presentation(presentation_id, replacements):
    slides = _slides()
    requests = [
        {"replaceAllText": {"containsText": {"text": k, "matchCase": True}, "replaceText": v}}
        for k, v in replacements.items()
    ]
    slides.presentations().batchUpdate(presentationId=presentation_id, body={"requests": requests}).execute()

def get_presentation_url(presentation_id):
    return f"https://docs.google.com/presentation/d/{presentation_id}/edit"


PROBLEM_MAP = {
    "fehlende Kontrolle": ("Fehlende Kontrolle", "Mangelnde Transparenz fuehrt zu Qualitaetsproblemen und Vertrauensverlust."),
    "Schlechtes Beschwerdemanagement": ("Schlechtes Beschwerdemanagement", "Reklamationen werden nicht zeitnah bearbeitet - Unzufriedenheit steigt."),
    "Mangelnde Zuverlaessigkeit": ("Mangelnde Zuverlaessigkeit", "Unregelmaessige Leistungserbringung schafft Unsicherheit."),
    "Hohe Kosten": ("Hohe und versteckte Kosten", "Unuebersichtliche Abrechnungen belasten das Budget."),
    "Personalprobleme": ("Personalprobleme", "Haeufiger Personalwechsel fuehrt zu inkonstanter Qualitaet."),
    "Qualitaetsprobleme": ("Qualitaetsprobleme", "Unregelmaessige Reinigungsqualitaet entspricht nicht den Anforderungen."),
    "Hygienemangel": ("Hygienemangel", "Unzureichende Hygiene gefaehrdet Gesundheit und Image."),
    "Schlechte Kommunikation": ("Schlechte Kommunikation", "Fehlende Abstimmung fuehrt zu Missverstaendnissen."),
}

LOESUNG_MAP = {
    "Alles aus einer Hand": ("Alles aus einer Hand", "Ein Ansprechpartner fuer alle Facility-Leistungen - einfach und effizient."),
    "Digitale Nachweis": ("Digitale Kontrollsysteme", "Transparente Echtzeit-Dokumentation aller Leistungen per App."),
    "Persoenlicher Ansprechpartner": ("Persoenlicher Ansprechpartner", "Direkter Kontakt - immer erreichbar."),
    "Qualitaetsmanagement": ("Qualitaetsmanagement", "Regelmaessige Qualitaetskontrollen und sofortige Nachbesserung."),
    "Flexible Vertraege": ("Flexible Vertraege", "Individuelle Vertragsgestaltung ohne versteckte Kosten."),
    "Geschultes Personal": ("Geschultes Fachpersonal", "Festangestelltes geschultes Personal fuer konstante Qualitaet."),
}


def _match_map(text, mapping):
    if text in mapping:
        return mapping[text]
    text_l = text.lower()
    for key, val in mapping.items():
        if key.lower() in text_l or text_l in key.lower():
            return val
    return (text, "")


def find_problem_slide(presentation_id, marker="{{Problem_Titel}}"):
    service = _get_slides_service()
    prs = service.presentations().get(presentationId=presentation_id).execute()
    for slide in prs.get("slides", []):
        for el in slide.get("pageElements", []):
            for te in el.get("shape", {}).get("text", {}).get("textElements", []):
                if marker in te.get("textRun", {}).get("content", ""):
                    return slide["objectId"]
    return None


def duplicate_slide(presentation_id, slide_id):
    service = _get_slides_service()
    resp = service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": [{"duplicateObject": {"objectId": slide_id}}]}
    ).execute()
    return resp["replies"][0]["duplicateObject"]["objectId"]


def fill_slide_placeholders(presentation_id, slide_id, mapping):
    service = _get_slides_service()
    requests = [
        {"replaceAllText": {
            "containsText": {"text": k, "matchCase": True},
            "replaceText": v,
            "pageObjectIds": [slide_id],
        }}
        for k, v in mapping.items()
    ]
    if requests:
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={"requests": requests}
        ).execute()


def delete_slide(presentation_id, slide_id):
    service = _get_slides_service()
    service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": [{"deleteObject": {"objectId": slide_id}}]}
    ).execute()


def fill_presentation_dynamic(presentation_id, data, replacements):
    import logging as _log
    log = _log.getLogger("main")

    prob_raw = ""
    for k, v in data.items():
        if "glichkeit_2_2" in k:
            prob_raw = v.get("value", "") if isinstance(v, dict) else str(v)
            break
    loes_raw = data.get("field_cCLhd", "")
    if isinstance(loes_raw, dict):
        loes_raw = loes_raw.get("value", "")

    problems = [p.strip() for p in prob_raw.split(",") if p.strip()]
    loesungen = [l.strip() for l in loes_raw.split(",") if l.strip()]

    log.info("Probleme: %s", problems)
    log.info("Loesungen: %s", loesungen)

    tmpl_id = find_problem_slide(presentation_id)

    if not problems or tmpl_id is None:
        log.warning("Kein Template oder keine Probleme - fallback")
        fill_presentation(presentation_id, replacements)
        return

    new_ids = []
    for _ in problems:
        nid = duplicate_slide(presentation_id, tmpl_id)
        new_ids.append(nid)

    for i, (nid, prob) in enumerate(zip(new_ids, problems)):
        loes = loesungen[i] if i < len(loesungen) else (loesungen[0] if loesungen else "")
        p_t, p_b = _match_map(prob, PROBLEM_MAP)
        l_t, l_b = _match_map(loes, LOESUNG_MAP)
        fill_slide_placeholders(presentation_id, nid, {
            "{{Problem_Titel}}": p_t,
            "{{Problem_Beschreibung}}": p_b,
            "{{Loesung_Titel}}": l_t,
            "{{Loesung_Beschreibung}}": l_b,
        })
        log.info("Slide %d: %s / %s", i + 1, p_t, l_t)

    delete_slide(presentation_id, tmpl_id)
    fill_presentation(presentation_id, replacements)
