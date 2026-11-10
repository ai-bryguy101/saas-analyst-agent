"""Integration payloads and configuration files.

Renders:
  integrations/meridian_soap/*.xml          SOAP 1.1 request/response pairs (2016-2019), one fault, one with a BOM
  integrations/tallyflow_webhooks/*.json    webhook payloads with schema drift
  config/pricing.yaml                       price book as configured (disagrees with contracts on purpose)
  config/legacy/brix_batch.ini              INI with Windows line endings
  config/feature_flags.properties
  integrations/edi/850_*.edi                X12 850 purchase orders from two government customers
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from ..util import AS_OF, rand_date, rng_for, write_text, uuid_like
from ..world import ADDON_PRICE, PRICE_BOOK

SOAP_ENV = '<?xml version="1.0" encoding="utf-8"?>\n<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:md="urn:meridiandispatch:partner:v2">\n<soap:Header><md:Auth><md:ApiKey>REDACTED</md:ApiKey></md:Auth></soap:Header>\n<soap:Body>\n{body}\n</soap:Body>\n</soap:Envelope>\n'

PARTNERS = [("PLC-001", "Prairie Line Couriers", 4.75), ("NWH-014", "Northwoods Haulage", 5.10), ("RRX-022", "Red River Express", 4.40),
            ("KSV-031", "Keewatin Service Vans", 6.25), ("ASP-040", "Assiniboine Parts Runners", 3.95)]


def render(world, out, seed):
    r = rng_for(seed, "integrations")
    soap = out / "integrations" / "meridian_soap"
    # rate card response holding GF09
    d = date(2017, 10, 2)
    body = "<md:GetPartnerRateCardResponse>\n  <md:EffectiveDate>2017-10-01</md:EffectiveDate>\n  <md:Currency>CAD</md:Currency>\n  <md:Partners>\n"
    for pid, name, rate in PARTNERS:
        body += (f"    <md:Partner id=\"{pid}\">\n      <md:Name>{name}</md:Name>\n      <md:RatePerJob>{rate:.2f}</md:RatePerJob>\n"
                 f"      <md:FuelSurchargePct>{r.choice([0, 2.5, 3, 4])}</md:FuelSurchargePct>\n    </md:Partner>\n")
    body += "  </md:Partners>\n</md:GetPartnerRateCardResponse>"
    write_text(soap / f"{d}_GetPartnerRateCard_response.xml", SOAP_ENV.format(body=body))
    write_text(soap / f"{d}_GetPartnerRateCard_request.xml", SOAP_ENV.format(body="<md:GetPartnerRateCard><md:Region>MB</md:Region></md:GetPartnerRateCard>"))
    mer = [c for c in world.customers if c.origin == "meridian"]
    for k in range(220):
        d = rand_date(r, date(2016, 1, 1), date(2019, 6, 30))
        c = r.choice(mer)
        pid, name, rate = r.choice(PARTNERS)
        job = f"J{r.randint(100000, 999999)}"
        if r.random() < 0.03:
            body = ("<soap:Fault><faultcode>soap:Server</faultcode><faultstring>Object reference not set to an instance of an object.</faultstring>"
                    "<detail><md:Trace>at Meridian.Dispatch.JobService.Create(JobRequest req) in C:\\build\\src\\JobService.cs:line 212</md:Trace></detail></soap:Fault>")
        else:
            body = (f"<md:CreateDispatchJob>\n  <md:CustomerCode>{c.ids['meridian']}</md:CustomerCode>\n  <md:CustomerName>{c.name.replace('&', '&amp;')}</md:CustomerName>\n"
                    f"  <md:JobId>{job}</md:JobId>\n  <md:Partner id=\"{pid}\">{name}</md:Partner>\n"
                    f"  <md:Requested>{d}T{r.randint(6, 20):02d}:{r.randint(0, 59):02d}:00</md:Requested>\n"
                    f"  <md:Address><md:City>{c.city}</md:City><md:Province>{c.region}</md:Province></md:Address>\n"
                    f"  <md:Notes><![CDATA[{r.choice(['Back door, ring bell', 'Livraison avant 10h SVP', 'Call on arrival', '', 'Fragile - <glass> panels'])}]]></md:Notes>\n"
                    f"</md:CreateDispatchJob>")
        xml = SOAP_ENV.format(body=body)
        name_ = f"{d}_CreateDispatchJob_{job}.xml"
        if r.random() < 0.05:
            (soap).mkdir(parents=True, exist_ok=True)
            (soap / name_).write_bytes(b"\xef\xbb\xbf" + xml.encode("utf-8"))
        else:
            write_text(soap / name_, xml)

    # ---------------------------------------------------------------- TallyFlow webhooks (schema drift)
    wh = out / "integrations" / "tallyflow_webhooks"
    tf = [c for c in world.customers if c.origin == "tallyflow"]
    for k in range(120):
        d = rand_date(r, date(2013, 1, 1), date(2019, 12, 31))
        c = r.choice(tf)
        if d < date(2015, 6, 1):
            payload = {"event": "invoice.paid", "account": c.ids["tallyflow"], "amount": f"{r.randint(100, 9000)}.{r.randint(0, 99):02d}", "ts": d.strftime("%m/%d/%Y %H:%M")}
        elif d < date(2017, 4, 1):
            payload = {"type": "invoice.paid", "data": {"account_ref": c.ids["tallyflow"], "amount_cents": r.randint(10000, 900000), "currency": "usd"},
                       "created_at": f"{d}T{r.randint(0, 23):02d}:00:00-06:00"}
        else:
            payload = {"id": "evt_" + uuid_like(r)[:13], "type": "tallyflow.invoice.paid", "version": "2017-04",
                       "data": {"object": {"customer": c.ids.get("billing", ""), "legacy_ref": c.ids["tallyflow"], "total": r.randint(10000, 900000)}},
                       "created": int(datetime(d.year, d.month, d.day).timestamp())}
        write_text(wh / f"{d}_{k:03d}.json", json.dumps(payload, indent=2))

    # ---------------------------------------------------------------- configs
    cfg = out / "config"
    latest = PRICE_BOOK[-1][1]
    write_text(cfg / "pricing.yaml", f"""# Price book as deployed to billing v3. Owner: RevOps.
# NOTE: contract-specific prices (see legal) are NOT represented here.
version: 2023-01
currency_defaults:
  USD: {{symbol: "$", planning_fx: 1.0}}
  CAD: {{symbol: "C$", planning_fx: 0.75}}
  GBP: {{symbol: "£", planning_fx: 1.27}}
plans:
  starter:    {{per_seat_monthly: {latest['Starter']}, min_seats: 1}}
  pro:        {{per_seat_monthly: {latest['Pro']}, min_seats: 5}}
  enterprise: {{per_seat_monthly: {latest['Enterprise']}, min_seats: 50, annual_only: false}}
addons:
  invoicing:  {{per_seat_monthly: {ADDON_PRICE['Invoicing']}}}
  dispatch:   {{per_seat_monthly: {ADDON_PRICE['Dispatch']}}}
  insights:   {{flat_monthly: {ADDON_PRICE['Insights']}}}   # Project Lantern
discounts:
  max_without_approval: 0.10
  max_with_vp: 0.20
grandfathering: true
legacy_price_books:
""" + "".join(f"  - effective: {eff}\n    plans: {{starter: {p['Starter']}, pro: {p['Pro']}, enterprise: {p['Enterprise']}}}\n" for eff, p in PRICE_BOOK[:-1]))
    write_text(cfg / "legacy" / "brix_batch.ini", """; BRIX batch scheduler - copied off the ops share 2011
[general]
system=BRIX
operator=HPENHALLOW
tz=EST5EDT
date_format=CYYMMDD

[jobs]
BRXX010=NIGHTLY 23:30
BRXL020=LATEFEE 1ST 02:00   ; Y2K patched 01/04/2000
BRXM030=MAINT_INVOICE QTR 1ST 04:00

[late_fee]
rate=1.5            ; percent per month
grace_days=10
min_fee=15.00
""", newline="\r\n", encoding="cp1252")
    write_text(cfg / "feature_flags.properties", """# ops-api feature flags (exported 2026-10-31)
sync.offline_v2.enabled=true
billing.ledger_import.cents_fix=false
insights.lantern_ui=true
dispatch.partner_ratecard.source=meridian_soap
logs.timezone=UTC
classic.license_server.enabled=false
""")

    # ---------------------------------------------------------------- X12 EDI 850 purchase orders
    gov = [c for c in world.customers if c.industry == "Government" and c.cloud_start][:2]
    for c in gov:
        d = c.cloud_start - timedelta(days=20)
        seats = c.seats(c.cloud_start)
        price = c.unit_price(c.cloud_start)
        edi = (f"ISA*00*          *00*          *ZZ*{c.ids.get('netsuite', '000'):<15}*ZZ*BRINDLECOVE    *{d:%y%m%d}*1200*U*00401*000000{r.randint(100, 999)}*0*P*>~"
               f"GS*PO*{c.ids.get('netsuite', '000')}*BRINDLECOVE*{d:%Y%m%d}*1200*1*X*004010~ST*850*0001~"
               f"BEG*00*SA*PO{r.randint(100000, 999999)}**{d:%Y%m%d}~N1*BY*{c.name.upper()[:35]}~"
               f"PO1*1*{seats}*EA*{price:.2f}**VP*OPS-CLOUD-{c.plan.upper()}~CTT*1~SE*6*0001~GE*1*1~IEA*1*000000001~")
        write_text(out / "integrations" / "edi" / f"850_{c.ids.get('netsuite', 'x')}_{d:%Y%m%d}.edi", edi)
    return {}
