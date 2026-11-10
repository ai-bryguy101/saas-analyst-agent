"""CRM lineage: dBase contact file (2003) -> Sugar-style CRM (2006-2016) -> Salesforce-style CRM (2016-now).

Renders:
  sales_dbase_2003/CONTACTS.DBF                dBase III, cp437, includes rows flagged deleted ('*')
  crm_sugar_export_2016/*.csv                  cp1252, ';' delimited, m/d/Y h:i a dates, test rows, dupes
  crm_salesforce_export_2026-10/*.csv          UTF-8 with BOM, all-quoted, 18-char ids, IsDeleted soft deletes
  crm_migration_2016/Sugar_to_SFDC_crosswalk_FINAL_v3.xlsx   the crosswalk (one row knowingly wrong)
"""
from __future__ import annotations

import struct
from datetime import date, datetime, timedelta

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..util import b62, csv_line, fmt_date, maybe_null, rand_date, rng_for, typo, uuid_like, write_bytes, write_text, AS_OF
from ..world import COMPETITORS, ERA, first_year_arr_local

GENERIC_CALL_NOTES = [
    "Quarterly check-in. {contact} says techs like the mobile app. Asked about bulk import of assets again.",
    "Spoke w/ {contact}. Renewal looks fine, budget approved for FY. wants training for 3 new dispatchers",
    "Left VM for {contact}. 2nd attempt. Will try email.",
    "{contact} raised concern re: invoice timing (they pay net-60, we bill net-30). Told them I'd check w/ finance.",
    "Demo of PM scheduling for {contact} + 2 building engineers. Good reception. Possible expansion +{n} seats Q{q}.",
    "Customer asked if we integrate with their ERP. Said not today, roadmap maybe. Logged feature req.",
    "EBR deck reviewed. Work order volume up {pct}% YoY. {contact} happy w/ support response times.",
    "Pricing convo - {contact} pushed back on increase. Offered to hold price if they sign 2yr. Pending.",
    "Onsite visit. Toured 2 facilities. Lots of paper work orders still in use at the second site.",
    "{contact} out on leave, covering contact is the controller. No action.",
    "Escalation call re: sync issues w/ offline mode. Looped in support (ticket ref in helpdesk).",
    "Champion {contact} mentioned they are evaluating {comp}. Not urgent per them.",
]


# ----------------------------------------------------------------------------- dBase III writer
def write_dbf(path, fields, rows, deleted, encoding="cp437"):
    """Minimal dBase III (.dbf) writer. fields: [(name, type, length, decimals)]."""
    now = date(2003, 11, 21)
    rec_len = 1 + sum(f[2] for f in fields)
    header_len = 32 + 32 * len(fields) + 1
    out = bytearray()
    out += struct.pack("<BBBBIHH20x", 0x03, now.year - 1900, now.month, now.day, len(rows), header_len, rec_len)
    for name, typ, length, dec in fields:
        out += struct.pack("<11sc4xBB14x", name.encode("ascii"), typ.encode("ascii"), length, dec)
    out += b"\x0d"
    for row, is_del in zip(rows, deleted):
        out += b"*" if is_del else b" "
        for (name, typ, length, dec), val in zip(fields, row):
            if typ == "D":
                s = val.strftime("%Y%m%d") if val else " " * 8
            elif typ == "L":
                s = "T" if val else ("F" if val is False else "?")
            elif typ == "N":
                s = ("" if val is None else f"{val:.{dec}f}").rjust(length)
            else:
                s = ("" if val is None else str(val)).ljust(length)
            out += s.encode(encoding, errors="replace")[:length].ljust(length, b" ")
    out += b"\x1a"
    write_bytes(path, bytes(out))


def render_dbf(world, out, r):
    fields = [("CUSTNO", "C", 6, 0), ("COMPANY", "C", 40, 0), ("CONTACT", "C", 30, 0), ("TITLE", "C", 25, 0),
              ("PHONE", "C", 14, 0), ("LASTCALL", "D", 8, 0), ("POTENTIAL", "N", 10, 2), ("NOTES", "C", 60, 0),
              ("ACTIVE", "L", 1, 0)]
    rows, deleted = [], []
    for c in world.customers:
        if "brix" not in c.ids or c.first_seen > date(2003, 11, 1):
            continue
        for i, ct in enumerate(c.contacts[: r.randint(1, 3)]):
            notes = r.choice(["", "", "PREFERS FAX", "CALL AFTER 2PM", "DO NOT CALL - GOES THRU PURCHASING",
                              "SENT XMAS CARD 2002", "BIG ACCT - BRYCE HANDLES", "ASKED ABOUT Y2K COMPLIANCE LETTER",
                              "MOVED TO NEW BLDG, ADDR CHG PENDING"])
            rows.append([c.ids["brix"] if r.random() > 0.08 else "", c.name.upper()[:40] if r.random() > 0.3 else c.name[:40],
                         ct.name.upper(), ct.title.upper(), ct.phone, rand_date(r, date(1998, 1, 1), date(2003, 11, 1)) if r.random() > 0.1 else None,
                         round(c.classic_license * r.uniform(0.1, 0.6), 2) if r.random() > 0.2 else None, notes,
                         None if r.random() < 0.05 else (c.end is None or c.end > date(2003, 11, 1))])
            deleted.append(r.random() < 0.04)
    cal = world.golden["calloway"]
    rows.append([cal.ids["brix"], "CALLOWAY FACILITIES MGMT", "THEODORA VANCE", "FACILITIES DIRECTOR", "(513) 555-0142",
                 date(2003, 10, 6), 120000.0, "CHAMPION. WANTS MULTI-SITE. DISCOUNT ASKED - SEE DESMOND", True])
    deleted.append(False)
    write_dbf(out / "sales_dbase_2003" / "CONTACTS.DBF", fields, rows, deleted)


# ----------------------------------------------------------------------------- Sugar export (2016)
def sugar_dt(d: date, r) -> str:
    dt = datetime(d.year, d.month, d.day, r.randint(7, 18), r.randint(0, 59))
    return dt.strftime("%m/%d/%Y %I:%M %p").lower().replace(" am", "am").replace(" pm", "pm")


def render_sugar(world, out, r):
    base = out / "crm_sugar_export_2016"
    users = {p.pid: uuid_like(r) for p in world.people}
    acc_rows = [["id", "name", "account_type", "industry", "billing_address_city", "billing_address_state",
                 "billing_address_country", "phone_office", "assigned_user_id", "date_entered", "date_modified",
                 "deleted", "brix_custno_c", "annual_revenue", "description"]]
    con_rows = [["id", "first_name", "last_name", "title", "email1", "phone_work", "account_id", "date_entered", "deleted"]]
    opp_rows = [["id", "name", "account_id", "sales_stage", "amount", "currency_id", "date_closed", "lead_source",
                 "assigned_user_id", "deleted"]]
    sugar_accounts = [c for c in world.customers if "sugar" in c.ids]
    for c in sugar_accounts:
        if c.end and c.end < ERA["sugar_to_sfdc"]:
            acct_type = "Former Customer" if r.random() > 0.3 else "Customer"   # stale status
        else:
            acct_type = "Customer"
        created = max(c.first_seen, ERA["sugar_start"]) if c.first_seen > ERA["sugar_start"] else rand_date(r, ERA["sugar_start"], date(2007, 6, 1))
        name = c.name.replace("’", "'")
        if r.random() < 0.1:
            name = typo(r, name)
        desc = ""
        if c.origin == "classic":
            desc = r.choice(["Classic customer (imported from ACT! 2006)", "on-prem", "Classic - maint thru BRIX", ""])
        if c is world.golden["calloway"]:
            desc = "Classic since 2001. Moving to cloud 2013 w/ special pricing - contract in legal share (scanned)."
        acc_rows.append([c.ids["sugar"], name, acct_type, c.industry, c.city, c.region,
                         r.choice(["USA", "US", "United States", "U.S.A.", ""]) if c.country == "US" else c.country,
                         c.contacts[0].phone, users.get(c.owner, ""), sugar_dt(created, r), sugar_dt(rand_date(r, created, ERA["sugar_to_sfdc"]), r),
                         "0", (c.ids.get("brix") or "") if r.random() > 0.15 else "", "", desc])
        # duplicate accounts created by reps who did not search first
        if r.random() < 0.07:
            dup_id = uuid_like(r)
            c.ids.setdefault("sugar_dupes", []).append(dup_id)
            acc_rows.append([dup_id, r.choice(c.variants), "Customer", r.choice([c.industry, "", "Other"]), c.city, c.region,
                             "USA", "", users.get(c.owner, ""), sugar_dt(rand_date(r, created, ERA["sugar_to_sfdc"]), r),
                             sugar_dt(ERA["sugar_to_sfdc"] - timedelta(days=3), r), "0", "", "", "dup?"])
        for ct in c.contacts:
            con_rows.append([uuid_like(r), ct.first, ct.last, ct.title, ct.email if r.random() > 0.1 else "",
                             ct.phone, c.ids["sugar"], sugar_dt(created, r), "1" if r.random() < 0.03 else "0"])
        if c.signed and c.signed >= ERA["sugar_start"] and c.signed < ERA["sugar_to_sfdc"]:
            amt = first_year_arr_local(c) if c.cloud_start else c.classic_license
            opp_rows.append([uuid_like(r), f"{c.name.split()[0]} - New", c.ids["sugar"], "Closed Won", f"{amt:.2f}",
                             "-99", c.signed.strftime("%Y-%m-%d"), r.choice(["Web Site", "Trade Show", "Cold Call", "Partner", ""]),
                             users.get(c.owner, ""), "0"])
    for i in range(4):
        acc_rows.append([uuid_like(r), f"TEST ACCOUNT {i} DO NOT USE", "Other", "", "Dayton", "OH", "USA", "", "", sugar_dt(date(2009, 3, 3), r),
                         sugar_dt(date(2014, 1, 6), r), "0", "999999", "", "qa"])
    for p in world.prospects:
        if ERA["sugar_start"] <= p["created"] < ERA["sugar_to_sfdc"]:
            sid = uuid_like(r)
            p["sugar"] = sid
            acc_rows.append([sid, p["name"], "Prospect", p["industry"], p["city"], p["region"], "USA", "",
                             users.get(p["owner"], ""), sugar_dt(p["created"], r), sugar_dt(p["created"], r), "0", "", "", ""])
            if r.random() < 0.5:
                opp_rows.append([uuid_like(r), f"{p['name'].split()[0]} - New", sid, r.choice(["Closed Lost", "Closed Lost", "Prospecting", "Proposal/Price Quote"]),
                                 f"{p['seats'] * 29 * 12:.2f}", "-99", rand_date(r, p["created"], p["created"] + timedelta(days=200)).strftime("%Y-%m-%d"),
                                 "Web Site", users.get(p["owner"], ""), "0"])
    usr = [["id", "user_name", "first_name", "last_name", "status", "department"]]
    for p in world.people:
        usr.append([users[p.pid], (p.first[0] + p.last).lower().replace("'", ""), p.first, p.last,
                    "Inactive" if p.left and p.left < ERA["sugar_to_sfdc"] else "Active", p.dept])
    for fname, rows in [("accounts.csv", acc_rows), ("contacts.csv", con_rows), ("opportunities.csv", opp_rows), ("users.csv", usr)]:
        write_text(base / fname, "\n".join(csv_line(row, ";") for row in rows) + "\n", encoding="cp1252", newline="\r\n")
    return users


# ----------------------------------------------------------------------------- Salesforce export
def sf_dt(d, r) -> str:
    return datetime(d.year, d.month, d.day, r.randint(12, 23), r.randint(0, 59), r.randint(0, 59)).strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def render_salesforce(world, out, r, sugar_users):
    base = out / "crm_salesforce_export_2026-10"
    uid = {p.pid: "005" + b62(r, 15) for p in world.people}
    usr = [["Id", "Username", "Name", "Title", "Department", "IsActive"]]
    for p in world.people:
        usr.append([uid[p.pid], p.email(date(2016, 6, 1)).replace("@", ".sfdc@") if p.hired < ERA["sugar_to_sfdc"] else p.email(p.hired),
                    p.name, p.title, p.dept, "false" if p.left else "true"])
    acc = [["Id", "IsDeleted", "Name", "Type", "Industry", "BillingCity", "BillingState", "BillingCountry", "Phone",
            "OwnerId", "CreatedDate", "LastModifiedDate", "Legacy_Sugar_Id__c", "BRIX_Cust_No__c",
            "Billing_Customer_Id__c", "NetSuite_Internal_Id__c", "Customer_Since__c", "Churn_Date__c",
            "Churn_Reason__c", "ARR__c", "CurrencyIsoCode", "Products__c"]]
    con = [["Id", "IsDeleted", "AccountId", "FirstName", "LastName", "Title", "Email", "Phone", "CreatedDate", "HasOptedOutOfEmail"]]
    opp = [["Id", "IsDeleted", "AccountId", "Name", "Type", "StageName", "Amount", "CurrencyIsoCode", "CloseDate",
            "Contract_Start__c", "Seats__c", "OwnerId", "CreatedDate", "Loss_Reason__c"]]
    task = [["Id", "WhoId", "WhatId", "Subject", "ActivityDate", "Status", "OwnerId", "Type", "Description"]]

    def acc_row(c, name=None, sid=None, created=None, deleted=False):
        created = created or (ERA["sugar_to_sfdc"] if c.first_seen < ERA["sugar_to_sfdc"] else c.signed or c.first_seen)
        brix = c.ids.get("brix", "")
        if brix and r.random() < 0.45:
            brix = str(int(brix))     # Excel ate the leading zeros during the 2016 load
        typ = "Customer" if not c.end or c.end > AS_OF else r.choice(["Former Customer", "Former Customer", "Customer - Churned", "Customer"])
        churn_reason = ""
        if c.end:
            churn_reason = c.churn_reason if r.random() > 0.35 else r.choice(["", "Other", "other", "see notes"])
        if c is world.golden["harbortown"]:
            churn_reason = "Other"
        arr = first_year_arr_local(c) if c.cloud_start else ""
        if arr and r.random() < 0.6:
            arr = round(arr * r.uniform(0.85, 1.25), 2)  # rarely updated since the opp closed
        prods = ";".join(["Ops Cloud"] + c.addons) if c.cloud_start else "Classic"
        country = {"US": r.choice(["United States", "USA", "US", "United States", "U.S."]), "CA": r.choice(["Canada", "CA", "CAN"]),
                   "GB": r.choice(["United Kingdom", "UK", "GB", "England"])}[c.country]
        return [sid or c.ids["sfdc"], "true" if deleted else "false", name or c.name, typ, c.industry if r.random() > 0.05 else "",
                c.city, c.region, country, c.contacts[0].phone, uid[c.owner], sf_dt(created, r),
                sf_dt(rand_date(r, created, AS_OF), r), c.ids.get("sugar", ""), brix,
                c.ids.get("billing", "") if r.random() > 0.08 else "", c.ids.get("netsuite", ""),
                fmt_date(c.first_seen, "iso"), fmt_date(c.end, "iso") if c.end else "", churn_reason,
                arr, c.currency, prods]

    for c in world.customers:
        if "sfdc" not in c.ids:
            continue
        deleted = c.deleted_in_crm is not None
        acc.append(acc_row(c, deleted=deleted))
        # cross-system duplicate accounts (e.g. Meridian import created a second record)
        if c.origin in ("meridian", "kestrel") and r.random() < 0.12 or c is world.golden["brigid_us"]:
            dup_id = "001" + b62(r, 15)
            c.ids.setdefault("sfdc_dupes", []).append(dup_id)
            created = ERA["meridian_acq"] if c.origin == "meridian" else ERA["kestrel_acq"] if c.origin == "kestrel" else date(2019, 8, 2)
            acc.append(acc_row(c, name=r.choice(c.variants), sid=dup_id, created=created))
        for ct in c.contacts:
            cid = "003" + b62(r, 15)
            con.append([cid, "false", c.ids["sfdc"], ct.first, ct.last, ct.title, ct.email if r.random() > 0.06 else "",
                        ct.phone, sf_dt(max(ERA["sugar_to_sfdc"], c.first_seen), r), "true" if r.random() < 0.1 else "false"])
        # opportunities: new business + yearly renewals/expansions since 2016
        if c.signed and c.signed >= ERA["sugar_to_sfdc"] - timedelta(days=30):
            amt = first_year_arr_local(c) if c.cloud_start else 0
            opp.append(["006" + b62(r, 15), "false", c.ids["sfdc"], f"{c.name} - New Business", "New Business", "Closed Won",
                        f"{amt:.2f}", c.currency, fmt_date(c.signed), fmt_date(c.cloud_start), c.seats(c.cloud_start or c.first_seen),
                        uid[c.owner], sf_dt(c.signed - timedelta(days=r.randint(10, 120)), r), ""])
        if c.cloud_start:
            d = max(c.cloud_start, ERA["sugar_to_sfdc"])
            k = 1
            while True:
                d = c.cloud_start.replace(year=c.cloud_start.year + k) if c.cloud_start.month != 2 or c.cloud_start.day < 29 else c.cloud_start
                k += 1
                if d > AS_OF or (c.end and d > c.end + timedelta(days=1)):
                    break
                if d < ERA["sugar_to_sfdc"]:
                    continue
                won = not (c.end and (c.end - d).days < 365)
                amt = c.seats(d) * c.unit_price(d) * (1 - c.discount) * 12 * {"USD": 1, "CAD": 1.32, "GBP": 0.79}[c.currency]
                opp.append(["006" + b62(r, 15), "false", c.ids["sfdc"], f"{c.name} - Renewal {d.year}", "Renewal",
                            "Closed Won" if won else "Closed Lost", f"{amt:.2f}", c.currency, fmt_date(d - timedelta(days=r.randint(0, 20))),
                            fmt_date(d), c.seats(d), uid[c.owner], sf_dt(d - timedelta(days=90), r),
                            "" if won else (c.churn_reason or "")])
        # call notes (unstructured)
        for _ in range(r.randint(0, 5)):
            when = rand_date(r, max(ERA["sugar_to_sfdc"], c.first_seen), min(AS_OF, c.end or AS_OF))
            ct = r.choice(c.contacts)
            note = r.choice(GENERIC_CALL_NOTES).format(contact=ct.first, n=r.randint(5, 40), q=r.randint(1, 4),
                                                        pct=r.randint(5, 60), comp=r.choice(COMPETITORS))
            if r.random() < 0.3:
                note += "\n\n" + r.choice(["Next steps:\n- send pricing\n- loop CSM", "f/u in 2 wks", "--\nsent from my iPhone", "TODO update ARR field"])
            task.append(["00T" + b62(r, 15), "", c.ids["sfdc"], r.choice(["Call", "Check-in", "EBR", "Follow up", "Call w/ " + ct.first]),
                         fmt_date(when), "Completed", uid[c.owner], "Call", note])
    hb = world.golden["harbortown"]
    task.append(["00T" + b62(r, 15), "", hb.ids["sfdc"], "Check-in", "2016-06-21", "Completed", uid["E013"], "Call",
                 "Spoke w/ Lionel. All good, renewal in Aug should be routine. They liked the new work order templates."])
    for p in world.prospects:
        if p["created"] >= ERA["sugar_to_sfdc"] - timedelta(days=365) and r.random() < 0.8:
            pid = "001" + b62(r, 15)
            acc.append([pid, "false", p["name"], "Prospect", p["industry"], p["city"], p["region"], "United States", "",
                        uid[p["owner"]], sf_dt(max(p["created"], ERA["sugar_to_sfdc"]), r), sf_dt(AS_OF, r), p.get("sugar", ""),
                        "", "", "", "", "", "", "", "USD", ""])
            opp.append(["006" + b62(r, 15), "false", pid, f"{p['name']} - New Business", "New Business",
                        r.choice(["Closed Lost", "Closed Lost", "Closed Lost", "Qualification", "Proposal", "Negotiation"]),
                        f"{p['seats'] * 35 * 12:.2f}", "USD", fmt_date(rand_date(r, max(p["created"], ERA["sugar_to_sfdc"]), AS_OF + timedelta(days=90))),
                        "", p["seats"], uid[p["owner"]], sf_dt(max(p["created"], ERA["sugar_to_sfdc"]), r),
                        r.choice(["Price", "No decision", "Went with " + r.choice(COMPETITORS), "Timing", ""])])
    for fname, rows in [("User.csv", usr), ("Account.csv", acc), ("Contact.csv", con), ("Opportunity.csv", opp), ("Task.csv", task)]:
        write_text(base / fname, "\n".join(csv_line(row, ",", quote_all=True) for row in rows) + "\n", bom=True, newline="\r\n")
    return uid


# ----------------------------------------------------------------------------- crosswalk
def render_crosswalk(world, out, r):
    wb = Workbook()
    ws = wb.active
    ws.title = "Crosswalk"
    ws.append(["SUGAR -> SALESFORCE ACCOUNT CROSSWALK  (cutover wknd 5/14/2016)  ** FINAL v3 **"])
    ws.append(["prepared by RevOps (FA) + Data (YT). Use THIS version not v2. Rows highlighted yellow = manual match."])
    ws.append([])
    ws.append(["Sugar ID", "Sugar Account Name", "BRIX Cust #", "SFDC Account ID", "SFDC Account Name", "Match Method", "Confidence", "Notes"])
    for cell in ws[4]:
        cell.font = Font(bold=True)
    yellow = PatternFill("solid", fgColor="FFFF00")
    t, w = world.golden["xwalk_true"], world.golden["xwalk_wrong"]
    for c in world.customers:
        if "sugar" not in c.ids or "sfdc" not in c.ids:
            continue
        method = r.choices(["exact name", "fuzzy name", "BRIX #", "manual"], [60, 20, 12, 8])[0]
        sfdc = c.ids["sfdc"]
        brix = c.ids.get("brix", "")
        notes = ""
        if c is t:
            sfdc = w.ids["sfdc"]           # the planted error: BRIX 004417 -> the wrong Riverbend
            method, notes = "fuzzy name", "Riverbend x2 - picked the one w/ more contacts"
        conf = {"exact name": 1.0, "fuzzy name": round(r.uniform(0.78, 0.97), 2), "BRIX #": 1.0, "manual": ""}[method]
        ws.append([c.ids["sugar"], c.name, int(brix) if brix and r.random() < 0.5 else brix, sfdc,
                   c.name if c is not t else w.name, method, conf, notes])
        if method == "manual" or c is t:
            for cell in ws[ws.max_row]:
                cell.fill = yellow
        for dup in c.ids.get("sugar_dupes", []):
            ws.append([dup, r.choice(c.variants), "", c.ids["sfdc"], c.name, "merged dup", "", "merged into survivor"])
    ws2 = wb.create_sheet("Not migrated")
    ws2.append(["Sugar ID", "Name", "Reason"])
    for c in world.customers:
        if "sugar" in c.ids and "sfdc" not in c.ids:
            ws2.append([c.ids["sugar"], c.name, r.choice(["inactive > 2 yrs", "former customer", "no activity", "dupe"])])
    ws3 = wb.create_sheet("notes")
    ws3["A1"] = "Open issues as of Sunday night:"
    ws3["A2"] = "- ~40% of BRIX numbers lost leading zeros when FA pasted from Excel. Fix later (ticket?)"
    ws3["A3"] = "- Meridian / Canada not in scope"
    ws3["A4"] = "- currency field defaulted to USD for everyone"
    wb.properties.creator = "fadeyemi"
    wb.properties.created = datetime(2016, 5, 15, 2, 14)
    wb.properties.modified = datetime(2016, 5, 16, 9, 2)
    p = out / "crm_migration_2016" / "Sugar_to_SFDC_crosswalk_FINAL_v3.xlsx"
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(p)


def render(world, out, seed):
    r = rng_for(seed, "crm")
    render_dbf(world, out, r)
    su = render_sugar(world, out, r)
    uid = render_salesforce(world, out, r, su)
    render_crosswalk(world, out, r)
    world.sf_user_ids = uid
    return {}
