
PREISE = {"buero":1.89,"meeting":1.89,"kueche":2.20,"sanitaer":2.50,"weitere":1.89}
FREQUENZ = {"1x Woche":4.33,"2x Woche":8.66,"3x Woche":13.0,"täglich":21.5,"14-tägig":2.17,"1x Monat":1.0}

def _val(data,key):
    e = data.get(key,{})
    return str(e.get("value","")).strip() if isinstance(e,dict) else ""

def _num(val):
    try: return float(str(val).replace(",","."))
    except: return 0.0

def _freq(data,key): return FREQUENZ.get(_val(data,key),4.33)

def calculate(payload):
    if isinstance(payload,list): data = payload[0].get("data",{})
    elif isinstance(payload,dict) and "data" in payload: data = payload["data"]
    else: data = payload
    items = []
    freq = _freq(data,"field_LOxcA")
    for key,pkey,label,rtype in [
        ("Menge_2_2","Menge_2_3","Büroreinigung","buero"),
        ("field_LzyvM","Menge_2uu","Meetingraumreinigung","meeting"),
        ("field_fCOgh","Menge_2_3hgt","Küchenreinigung","kueche"),
        ("field_sWVLz","Menge_2rr","Sanitärreinigung","sanitaer"),
        ("field_wZosx",None,"Weitere Flächen","weitere"),
    ]:
        m2 = _num(_val(data,key))
        if m2:
            p = round(PREISE[rtype]*freq,2)
            items.append({"name":label,"quantity":m2,"unit":"m²","price":p,"total":round(m2*p,2)})
    if _val(data,"Menge_2_2_2") not in ("off","","0"):
        items.append({"name":"Fensterreinigung","quantity":1,"unit":"Pauschal","price":89.0,"total":89.0})
    for fk,lb,pr in [
        ("field_MCsHM","Kühlschrank reinigen",15.0),
        ("Menge_2_2gff","Mikrowelle reinigen",8.0),
        ("field_kwRxo","Kaffeemaschinenpflege",12.0),
        ("field_QPFfk","Spülmaschine/Gläser",10.0),
        ("field_cPdkX","Papier & Seife",9.0),
        ("field_FEykX","Pflanzenpflege",15.0),
        ("field_GtKat","Duftservice",20.0),
        ("field_cHHIL","Ordnungsservice",25.0),
    ]:
        if _val(data,fk) not in ("off","","0"):
            items.append({"name":lb,"quantity":1,"unit":"Pauschal/Monat","price":pr,"total":pr})
    return items

def total_net(items): return round(sum(i["total"] for i in items),2)

def build_summary(data,items):
    if isinstance(data,list): data = data[0].get("data",{})
    freq_label = _val(data,"field_LOxcA") or "1x Woche"
    lines = [f"Reinigungsfrequenz: {freq_label}\n"]
    for i in items:
        lines.append(f"• {i['name']}: {i['quantity']} {i['unit']} x {i['price']:.2f}€ = {i['total']:.2f}€")
    lines.append(f"\nNetto gesamt/Monat: {total_net(items):.2f}€")
    return "\n".join(lines)
