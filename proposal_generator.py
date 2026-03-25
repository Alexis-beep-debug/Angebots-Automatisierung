"""
Proposal PDF Generator – HTML/Jinja2 + WeasyPrint.

Replaces the previous Google Slides approach.
Maps Superforms webhook data to the Jinja2 template and renders a PDF.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_OUTPUT_DIR = Path(__file__).parent / "output"
_OUTPUT_DIR.mkdir(exist_ok=True)

# ── Problem → Kategorie + Lösung Mapping ──
# Maps the Superforms checkbox labels to grouped categories with GC solutions
PROBLEM_SOLUTION_MAP = {
    "Ineffektive und Inkonsistente Reinigungsqualität": {
        "kategorie": "QUALITÄT & ZUVERLÄSSIGKEIT",
        "herausforderung": "Ineffektive und inkonsistente Reinigungsqualität sowie mangelnde Zuverlässigkeit in der Ausführung.",
        "loesung": 'Als Fach- und Meisterbetrieb erhalten Sie "Alles aus einer Hand". Wir setzen auf geschultes Personal und feste Revierpläne für konstante Ergebnisse.',
    },
    "Mangelnde Zuverlässigkeit (Reliabilität)": {
        "kategorie": "QUALITÄT & ZUVERLÄSSIGKEIT",
        "herausforderung": "Ineffektive und inkonsistente Reinigungsqualität sowie mangelnde Zuverlässigkeit in der Ausführung.",
        "loesung": 'Als Fach- und Meisterbetrieb erhalten Sie "Alles aus einer Hand". Wir setzen auf geschultes Personal und feste Revierpläne für konstante Ergebnisse.',
    },
    "fehlende Kontrolle": {
        "kategorie": "TRANSPARENZ & KONTROLLE",
        "herausforderung": "Fehlende Kontrolle, Intransparenz bei Leistung und Kosten sowie Zeitverlust durch eigenes Nachsteuern.",
        "loesung": "Digitale Nachweis- und Kontrollsysteme schaffen volle Transparenz. Sie haben jederzeit Einblick, ohne selbst Zeit für ständige Kontrollen aufwenden zu müssen.",
    },
    "Intransparenz bei Leistung, Kosten und Prozessen": {
        "kategorie": "TRANSPARENZ & KONTROLLE",
        "herausforderung": "Fehlende Kontrolle, Intransparenz bei Leistung und Kosten sowie Zeitverlust durch eigenes Nachsteuern.",
        "loesung": "Digitale Nachweis- und Kontrollsysteme schaffen volle Transparenz. Sie haben jederzeit Einblick, ohne selbst Zeit für ständige Kontrollen aufwenden zu müssen.",
    },
    "Schlechte Urlaubs/ und Krankheitsvertretung": {
        "kategorie": "SERVICE & NACHHALTIGKEIT",
        "herausforderung": "Schlechte Urlaubs- und Krankheitsvertretung, mangelhaftes Beschwerdemanagement.",
        "loesung": "Wir garantieren Proaktivität in Beratung und Ausführung. Zudem sichern wir Nachhaltigkeit und Compliance, inklusive verlässlicher Vertretungsregelungen.",
    },
    "Schlechtes Beschwerdemanagement": {
        "kategorie": "SERVICE & NACHHALTIGKEIT",
        "herausforderung": "Schlechte Urlaubs- und Krankheitsvertretung, mangelhaftes Beschwerdemanagement.",
        "loesung": "Wir garantieren Proaktivität in Beratung und Ausführung. Zudem sichern wir Nachhaltigkeit und Compliance, inklusive verlässlicher Vertretungsregelungen.",
    },
}


def _build_probleme_loesungen(selected_problems: list[str]) -> list[dict]:
    """Group selected problems into unique categories with solutions."""
    seen_categories: set[str] = set()
    result: list[dict] = []

    for problem in selected_problems:
        mapping = PROBLEM_SOLUTION_MAP.get(problem)
        if mapping and mapping["kategorie"] not in seen_categories:
            seen_categories.add(mapping["kategorie"])
            result.append(mapping)

    # If no problems selected, provide a default entry
    if not result:
        result.append({
            "kategorie": "QUALITÄT & ZUVERLÄSSIGKEIT",
            "herausforderung": "Wir haben Ihre aktuelle Situation analysiert und Optimierungspotenzial identifiziert.",
            "loesung": "Mit dem G+C-Konzept bieten wir Ihnen eine maßgeschneiderte Reinigungslösung auf Meisterbetrieb-Niveau.",
        })

    return result


def map_superforms_to_template(data: dict) -> dict:
    """
    Map raw Superforms webhook payload to template variables.

    Superforms field names (from the form config) → template variables.
    """
    # ── Kontaktdaten ──
    firma = data.get("Firmenname", "")
    strasse = data.get("Anschrift", "")
    plz = data.get("field_YSXLd", "")
    stadt = data.get("field_ayedY", "")
    vorname = data.get("first_name", "")
    nachname = data.get("last_name", "")
    telefon = data.get("Telefonnummer", "")
    email = data.get("Email", "")

    kontaktperson = f"{vorname} {nachname}".strip()
    objekt_adresse = f"{strasse}, {plz} {stadt}".strip(", ")

    # ── Rechnungsadresse ──
    andere_rechnung = data.get("Rechnungsadresse", "") == "on"
    if andere_rechnung:
        rech_strasse = data.get("Rechnungsadresse1", strasse)
        rech_plz = data.get("Rechnungsadresse2", plz)
        rech_stadt = data.get("Rechnungsadresse3", stadt)
    else:
        rech_strasse, rech_plz, rech_stadt = strasse, plz, stadt

    # ── Räume: Büro ──
    buero_raeume = _int(data.get("Menge_2_3", 0))
    buero_tische = _int(data.get("Menge_27o7", 0))
    buero_stuehle = _int(data.get("Menge_2oipp", 0))
    schraenke = _int(data.get("field_rtCTb", 0))
    buero_qm = _float(data.get("Menge_2_2", 0))

    # ── Räume: Meeting ──
    meeting_raeume = _int(data.get("Menge_2uu", 0))
    meeting_tische = _int(data.get("Menge_2_37o7_2", 0))
    meeting_stuehle = _int(data.get("Menge_2ioup", 0))
    meeting_qm = _float(data.get("field_LzyvM", 0))

    # ── Räume: Küche ──
    kueche_raeume = _int(data.get("Menge_2_3hgt", 0))
    kueche_spuele = _int(data.get("field_AJctI", 0))
    kueche_zeile = _int(data.get("Menge_2_37o7", 0))
    kueche_spuelmaschine = _int(data.get("Menge_2u55", 0))
    kueche_kaffeemaschine = _int(data.get("field_cHSyM", 0))
    kueche_qm = _float(data.get("field_fCOgh", 0))

    # ── Räume: Sanitär ──
    sanitaer_raeume = _int(data.get("Menge_2rr", 0))
    sanitaer_wc = _int(data.get("Menge_2_3t7t7", 0))
    sanitaer_waschbecken = _int(data.get("Menge_2", 0))
    sanitaer_spiegel = _int(data.get("Menge_2_267i67i", 0))
    sanitaer_duschen = _int(data.get("field_Nsaox", 0))
    sanitaer_pissoir = _int(data.get("field_TgHWm", 0))
    sanitaer_qm = _float(data.get("field_sWVLz", 0))

    # ── Räume: Weitere ──
    weitere = _int(data.get("Menge", 0))
    muelleimer = _int(data.get("Menge_2uzkiz", 0))
    tueren = _int(data.get("field_LZShT", 0))
    glastueren = _int(data.get("field_FjaFR", 0))
    weitere_qm = _float(data.get("field_wZosx", 0))

    # ── Gesamt ──
    gesamt_qm = buero_qm + meeting_qm + kueche_qm + sanitaer_qm + weitere_qm
    anzahl_raeume_gesamt = buero_raeume + meeting_raeume + kueche_raeume + sanitaer_raeume + weitere
    anzahl_arbeitsplaetze = buero_tische  # Schreibtische ≈ Arbeitsplätze

    # ── Reinigungsintervalle ──
    intervall_muell = data.get("Möglichkeit", "")
    intervall_tische = data.get("field_yhSgD", "")
    intervall_kueche = data.get("field_zHLCn", "")
    intervall_sanitaer = data.get("field_IsCve", "")
    intervall_boden = data.get("field_LOxcA", "")
    intervall_schraenke = data.get("field_pdGkr", "")
    intervall_griffspuren = data.get("field_khHLN", "")

    # ── Services (Toggles) ──
    service_kuehlschrank = data.get("field_MCsHM", "") == "on"
    service_mikrowelle = data.get("Menge_2_2gff", "") == "on"
    service_kaffeepflege = data.get("field_kwRxo", "") == "on"
    service_spuelmaschine = data.get("field_QPFfk", "") == "on"
    service_papier_seife = data.get("field_cPdkX", "") == "on"
    service_pflanzenpflege = data.get("field_FEykX", "") == "on"
    service_duftservice = data.get("field_GtKat", "") == "on"
    service_kabelmanagement = data.get("field_cHHIL", "") == "on"
    service_fenster = data.get("Menge_2_2_2", "") == "on"

    # ── Probleme & Wünsche (Checkboxen) ──
    selected_problems = _parse_checkboxes(data.get("Möglichkeit_2_2", ""))
    selected_wishes = _parse_checkboxes(data.get("field_cCLhd", ""))

    # ── Problem → Lösung Mapping ──
    probleme_loesungen = _build_probleme_loesungen(selected_problems)

    # ── Datum ──
    heute = datetime.now(timezone.utc).strftime("%d.%m.%Y")

    return {
        # Cover
        "firma_name": firma,
        "kontaktperson_name": kontaktperson,
        "objekt_adresse": objekt_adresse,
        "datum": heute,
        "datum_begehung": data.get("datum_begehung", heute),
        "angebots_id": data.get("angebots_id", f"GC-{datetime.now(timezone.utc).strftime('%Y%m%d')}"),
        "email": email,
        "telefon": telefon,
        # Rechnungsadresse (für Lexoffice)
        "rech_strasse": rech_strasse,
        "rech_plz": rech_plz,
        "rech_stadt": rech_stadt,
        # Optimierungspotenzial
        "probleme_loesungen": probleme_loesungen,
        "selected_problems": selected_problems,
        "selected_wishes": selected_wishes,
        # Daten & Fakten
        "gesamt_qm": gesamt_qm,
        "buero_qm": buero_qm,
        "meeting_qm": meeting_qm,
        "kueche_qm": kueche_qm,
        "sanitaer_qm": sanitaer_qm,
        "weitere_qm": weitere_qm,
        "anzahl_raeume_gesamt": anzahl_raeume_gesamt,
        "buero_raeume": buero_raeume,
        "meeting_raeume": meeting_raeume,
        "kueche_raeume": kueche_raeume,
        "sanitaer_raeume": sanitaer_raeume,
        "anzahl_arbeitsplaetze": anzahl_arbeitsplaetze,
        # Ausstattung Details
        "buero_tische": buero_tische,
        "buero_stuehle": buero_stuehle,
        "schraenke": schraenke,
        "meeting_tische": meeting_tische,
        "meeting_stuehle": meeting_stuehle,
        "muelleimer": muelleimer,
        "tueren": tueren,
        "glastueren": glastueren,
        # Sanitär
        "sanitaer_wc": sanitaer_wc,
        "sanitaer_waschbecken": sanitaer_waschbecken,
        "sanitaer_spiegel": sanitaer_spiegel,
        "sanitaer_duschen": sanitaer_duschen,
        "sanitaer_pissoir": sanitaer_pissoir,
        # Küche
        "kueche_spuele": kueche_spuele,
        "kueche_zeile": kueche_zeile,
        "kueche_spuelmaschine": kueche_spuelmaschine,
        "kueche_kaffeemaschine": kueche_kaffeemaschine,
        # Intervalle
        "intervall_muell": intervall_muell,
        "intervall_tische": intervall_tische,
        "intervall_kueche": intervall_kueche,
        "intervall_sanitaer": intervall_sanitaer,
        "intervall_boden": intervall_boden,
        "intervall_schraenke": intervall_schraenke,
        "intervall_griffspuren": intervall_griffspuren,
        # Services
        "service_glasreinigung": service_fenster,
        "service_teppichreinigung": buero_qm > 0,
        "service_kabelmanagement": service_kabelmanagement,
        "service_waescheservice": service_papier_seife,
        "service_pflanzenpflege": service_pflanzenpflege,
        "service_duftservice": service_duftservice,
        "intervall_pflanzenpflege": data.get("field_BsHRM", "1x Woche"),
        # Preise – werden extern berechnet oder manuell eingetragen
        "gesamtpreis_netto": data.get("gesamtpreis_netto", "–"),
        "preis_schreibtische": data.get("preis_schreibtische", "–"),
        "preis_buerostuehle": data.get("preis_buerostuehle", "–"),
        "preis_muelleimer": data.get("preis_muelleimer", "–"),
        "preis_schraenke": data.get("preis_schraenke", "–"),
        "preis_buero_boden": data.get("preis_buero_boden", "–"),
        "preis_meeting_boden": data.get("preis_meeting_boden", "–"),
        "preis_weitere_boden": data.get("preis_weitere_boden", "–"),
        "preis_wc": data.get("preis_wc", "–"),
        "preis_waschbecken": data.get("preis_waschbecken", "–"),
        "preis_duschen": data.get("preis_duschen", "–"),
        "preis_kueche": data.get("preis_kueche", "–"),
        # Objektbeschreibung (optional, manuell)
        "objektbeschreibung": data.get("objektbeschreibung", ""),
        # Page count
        "total_pages": 6,
        # GC contact
        "gc_telefon": data.get("gc_telefon", ""),
        "gc_email": data.get("gc_email", "info@gc-facility.de"),
    }


def generate_pdf(data: dict) -> bytes:
    """
    Generate a proposal PDF from Superforms data.

    Args:
        data: Raw webhook payload from Superforms

    Returns:
        PDF file as bytes
    """
    template_vars = map_superforms_to_template(data)

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("angebot.html")
    html_content = template.render(**template_vars)

    pdf_bytes = HTML(string=html_content).write_pdf()
    logger.info(
        "Generated PDF for '%s' (%d bytes)",
        template_vars["firma_name"],
        len(pdf_bytes),
    )
    return pdf_bytes


def generate_and_save(data: dict, filename: str | None = None) -> Path:
    """Generate PDF and save to output directory. Returns file path."""
    template_vars = map_superforms_to_template(data)
    firma = template_vars["firma_name"] or "Unbekannt"

    if not filename:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        filename = f"Angebot_{firma.replace(' ', '_')}_{ts}.pdf"

    pdf_bytes = generate_pdf(data)
    path = _OUTPUT_DIR / filename
    path.write_bytes(pdf_bytes)
    logger.info("Saved PDF to %s", path)
    return path


# ── Helpers ──

def _int(val) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0


def _float(val) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _parse_checkboxes(val) -> list[str]:
    """Parse checkbox values – can be a list or comma-separated string."""
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [v.strip() for v in val.split(",") if v.strip()]
    return []
