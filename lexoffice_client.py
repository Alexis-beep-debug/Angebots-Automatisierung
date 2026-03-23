import httpx
from datetime import datetime
from config import LEXOFFICE_BASE, LEXOFFICE_API_KEY

_TIMEOUT = 30.0

def _headers():
    return {"Authorization": f"Bearer {LEXOFFICE_API_KEY}", "Content-Type": "application/json", "Accept": "application/json"}

async def find_or_create_contact(name, email, phone="", company=""):
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.get(f"{LEXOFFICE_BASE}/contacts", headers=_headers(), params={"email": email})
        if r.status_code == 200:
            items = r.json().get("content", [])
            if items:
                return items[0]["id"]
        parts = name.strip().split(" ", 1)
        payload = {
            "version": 0,
            "roles": {"customer": {}},
            "person": {
                "salutation": "",
                "firstName": parts[0],
                "lastName": parts[1] if len(parts) > 1 else ""
            },
            "emailAddresses": {"business": [email]}
        }
        if phone:
            payload["phoneNumbers"] = {"business": [phone]}
        if company:
            payload["company"] = {"name": company}
        r = await c.post(f"{LEXOFFICE_BASE}/contacts", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()["id"]

async def create_quote(contact_id, line_items, title="Angebot"):
    items = [
        {
            "type": "custom",
            "name": li["name"],
            "quantity": float(li["quantity"]),
            "unitName": li.get("unit", "Stück"),
            "unitPrice": {
                "currency": "EUR",
                "netAmount": float(li["price"]),
                "taxRatePercentage": 19
            },
            "discountPercentage": 0
        }
        for li in line_items
    ]
    payload = {
        "voucherDate": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+01:00"),
        "address": {"contactId": contact_id},
        "lineItems": items,
        "totalPrice": {"currency": "EUR"},
        "taxConditions": {"taxType": "net"},
        "title": title,
        "introduction": "Vielen Dank für Ihr Interesse. Wir unterbreiten Ihnen folgendes Angebot:",
        "remark": "Bei Fragen stehen wir Ihnen gerne zur Verfügung."
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
        r = await c.post(f"{LEXOFFICE_BASE}/quotations", headers=_headers(), json=payload)
        r.raise_for_status()
        quote_id = r.json()["id"]
        return {"id": quote_id, "deeplink": f"https://app.lexoffice.de/vouchers#!/VoucherView/Offer/{quote_id}"}
