"""Golden facts: planted answers that need one odd document or a cross-source join.

`compute(world)` derives every number from the world model (never hand-typed),
and the document renderers call it too, so the docs and the answer key can't drift.
`write_golden` writes data/GOLDEN_FACTS.yaml for agent evaluation.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from .world import FX_TO_USD, PRICE_BOOK, arr_at, first_year_arr_local

RAW = "data/raw"


def compute(world):
    if getattr(world, "_facts", None):
        return world._facts
    g = world.golden
    f = {}
    q4 = date(2019, 12, 31)
    f["arr_finance_2019"] = arr_at(world, q4)
    sns = [c for c in world.customers if c.cloud_start and c.signed and c.signed <= q4 < c.cloud_start]
    f["sns_count"] = len(sns)
    f["sns_arr"] = round(sum(first_year_arr_local(c) * FX_TO_USD[c.currency] for c in sns), 2)
    f["arr_board_2019"] = round(f["arr_finance_2019"] + f["sns_arr"], 2)

    cal = g["calloway"]
    f["calloway_list"] = PRICE_BOOK[0][1]["Enterprise"]
    f["calloway_net"] = round(f["calloway_list"] * (1 - cal.discount), 2)
    f["calloway_discount_pct"] = int(round(cal.discount * 100))

    ost = g["ostrander"]
    o99 = [i for i in world.invoices if i.cust is ost and i.system == "brix" and i.issued.year == 1999]
    f["ostrander_1999_amount"] = round(sum(i.total for i in o99), 2)
    f["ostrander_1999_count"] = len(o99)

    def total(c, y, statuses=("paid", "open", "uncollectible", "refunded")):
        return round(sum(i.total for i in world.invoices if i.cust is c and i.issued.year == y and i.status in statuses), 2)

    f["brigid_2022_usd"] = total(g["brigid_us"], 2022)
    f["brigid_2022_cad"] = total(g["brigid_ca"], 2022)

    leaks = []
    for c in world.customers:
        if c.deleted_in_crm:
            after = [i for i in world.invoices if i.cust is c and i.issued > c.deleted_in_crm and i.status != "void"]
            if after:
                leaks.append({"name": c.name, "crm_id": c.ids.get("sfdc"), "billing_id": c.ids.get("billing"),
                              "deleted_on": str(c.deleted_in_crm), "invoices_after": len(after),
                              "billed_after": round(sum(i.total for i in after), 2), "currency": c.currency})
    leaks.sort(key=lambda x: (-x["invoices_after"], x["name"]))
    f["soft_delete_leaks"] = leaks

    sev1_22 = [i for i in getattr(world, "incidents", []) if i["sev"] == "Sev1" and i["date"].year == 2022]
    cnt = Counter(i["root"] for i in sev1_22)
    f["sev1_2022"] = {"count": len(sev1_22), "by_root": dict(cnt.most_common()), "top": cnt.most_common(1)[0][0] if cnt else None}

    wo = getattr(world, "wo_2024", Counter())
    if wo:
        k, n = wo.most_common(1)[0]
        c = next(c for c in world.customers if c.key == k)
        f["wo_2024_top"] = {"name": c.name, "tenant_id": world.tenants[k], "events": n}
    world._facts = f
    return f


def write_golden(world, out_root: Path, path: Path):
    f = compute(world)
    g = world.golden
    hb, cal, ost = g["harbortown"], g["calloway"], g["ostrander"]
    t, w = g["xwalk_true"], g["xwalk_wrong"]
    facts = [
        {"id": "GF01", "difficulty": "hard", "kind": "buried-in-email",
         "question": "Why did Harbortown Property Group cancel in 2016?",
         "answer": "Two outages in March 2016 (Mar 8 and Mar 22) plus a competitor (Plinthwise) quoting ~30% under the renewal. "
                   "The CRM churn reason says 'Other' because the VP Sales asked for it to be logged that way.",
         "trail": [f"{RAW}/email_archive/sales_bkittredge_2014-2017.mbox (thread 'Notice of non-renewal - Harbortown', Aug 1 2016)",
                   f"{RAW}/crm_salesforce_export_2026-10/Account.csv (Churn_Reason__c = Other)",
                   f"{RAW}/support_helpdesk_2011-2019/tickets_export.json.gz (urgent outage tickets, March 2016)",
                   f"{RAW}/crm_salesforce_export_2026-10/Task.csv (June 2016 call note says 'all good' - misleading)"],
         "traps": ["CRM reason is 'Other'", "call notes say renewal looked routine"]},
        {"id": "GF02", "difficulty": "hard", "kind": "scanned-document",
         "question": "Why does Calloway Facilities Management pay less per seat than list price?",
         "answer": f"Their June 2013 MSA grants a {f['calloway_discount_pct']}% discount off list for as long as they keep 150+ seats: "
                   f"${f['calloway_net']:.2f} per Enterprise seat vs ${f['calloway_list']:.2f} list at the time. It is baked into the seat price, "
                   "so Ledger shows discount_pct 0.00.",
         "trail": [f"{RAW}/legal_contracts/scanned/Calloway_MSA_2013_signed.pdf (image-only scan, page 2)",
                   f"{RAW}/legal_contracts/scanned/Calloway_MSA_2013_signed.ocr.txt (OCR text with errors)",
                   f"{RAW}/email_archive/finance_idelacroix_2013-2026.mbox ('Calloway - billing setup for cloud')",
                   f"{RAW}/billing_ledger_mysql_2011-2017/ledger_dump_2017-03-31.sql (seat_price 27.9, discount_pct 0.00)",
                   f"{RAW}/wiki_confluence_export/SALES/Pricing-and-Discount-Policy_2012.html (says max discount 20% - stale)"],
         "traps": ["policy page says discounts cap at 20%", "Ledger shows no discount"]},
        {"id": "GF03", "difficulty": "medium", "kind": "migration-error",
         "question": "Which CRM account is legacy BRIX customer 004417?",
         "answer": f"{t.name} (Salesforce {t.ids['sfdc']}). The 2016 crosswalk wrongly maps 004417 to {w.name} ({w.ids['sfdc']}); "
                   "the wiki errata page and the Salesforce BRIX_Cust_No__c field have it right. Note 004471 (transposed digits) is the other Riverbend.",
         "trail": [f"{RAW}/crm_migration_2016/Sugar_to_SFDC_crosswalk_FINAL_v3.xlsx (yellow row, wrong)",
                   f"{RAW}/wiki_confluence_export/DATA/CRM-Migration-Known-Issues.html",
                   f"{RAW}/brix_mainframe/BRXCUST.TXT", f"{RAW}/crm_salesforce_export_2026-10/Account.csv"]},
        {"id": "GF04", "difficulty": "hard", "kind": "conflicting-numbers",
         "question": "Why does the Q4 2019 board deck ARR differ from finance's year-end ARR?",
         "answer": f"Board deck uses contracted ARR ${f['arr_board_2019']:,.0f}; finance live ARR is ${f['arr_finance_2019']:,.0f}. "
                   f"The ${f['sns_arr']:,.0f} gap is {f['sns_count']} contracts signed on or before Dec 31 2019 whose subscriptions start in 2020.",
         "trail": [f"{RAW}/board_and_finance/Board_Deck_Q4_2019_FINAL.pptx",
                   f"{RAW}/board_and_finance/FY2019_ARR_close_finance.xlsx",
                   f"{RAW}/wiki_confluence_export/FIN/ARR-Definitions.html",
                   f"{RAW}/crm_salesforce_export_2026-10/Opportunity.csv (CloseDate <= 2019-12-31, Contract_Start__c in 2020)"],
         "values": {"board": f["arr_board_2019"], "finance": f["arr_finance_2019"], "gap": f["sns_arr"], "contracts": f["sns_count"]}},
        {"id": "GF05", "difficulty": "medium", "kind": "units-trap",
         "question": "What unit are billing v3 invoice amounts in?",
         "answer": "Cents (integers) for everything created in billing v3, but rows with metadata.source = ledger_import_2017 are in dollars "
                   f"({getattr(world, 'legacy_import_count', 0)} rows, Jan 2016 - Mar 2017). Those invoices also exist in the Ledger dump, so don't double count.",
         "trail": [f"{RAW}/jira_export_2026-10/DATA.json (DATA-212 comments)", f"{RAW}/billing_v3_2017-now/invoices.csv",
                   f"{RAW}/wiki_confluence_export/DATA/Data-Dictionary-Billing.html (says cents for all rows - wrong)"]},
        {"id": "GF06", "difficulty": "hard", "kind": "timezone-dst",
         "question": "How long was the November 5, 2017 outage?",
         "answer": "About 100 minutes (06:20-08:00 UTC; 01:20 CDT to 02:00 CST). The logs are in local Dallas time with no offset and the 1 AM hour repeats "
                   "at the DST change, so a naive read (and the postmortem) says 40 minutes.",
         "trail": [f"{RAW}/app_logs/app-2017-11-04_05.dal-app03.log (req= sequence numbers keep increasing through the repeated hour)",
                   f"{RAW}/wiki_confluence_export/ENG/Postmortem-2017-11-05-DB-pool-exhaustion.html (says ~40 min)",
                   f"{RAW}/jira_export_2026-10/ENG.json (ENG-1180: logs were local time until 2018-03-12)"]},
        {"id": "GF07", "difficulty": "easy", "kind": "codename",
         "question": "What is Project Lantern?",
         "answer": "The internal codename for Brindle Insights, the analytics add-on built from the Kestrel Analytics acquisition (2021).",
         "trail": [f"{RAW}/board_and_finance/Kestrel_Integration_Plan_2021.pptx (slide 3)"]},
        {"id": "GF08", "difficulty": "medium", "kind": "draft-vs-final",
         "question": "When did Brindle Classic reach end of life, and what migration incentive was offered?",
         "answer": "June 30, 2020. Classic customers who moved to Ops Cloud before then got a 25% credit on subscription fees for their first 12 months. "
                   "(A 2019 draft memo says 20%; the final announcement and the staff meeting transcript say 25%.)",
         "trail": [f"{RAW}/meetings/2019-11-14_exec-staff.vtt", f"{RAW}/email_archive/exec_announcements_2012-2026.mbox ('Classic end of life - FINAL')",
                   f"{RAW}/memos/Classic_EOL_memo_DRAFT_v2.rtf (20%, superseded)"]},
        {"id": "GF09", "difficulty": "easy", "kind": "xml-payload",
         "question": "What per-job rate did Meridian Dispatch pay Prairie Line Couriers?",
         "answer": "CAD 4.75 per dispatched job (contract rate in the 2017 SOAP rate-card response).",
         "trail": [f"{RAW}/integrations/meridian_soap/2017-10-02_GetPartnerRateCard_response.xml"]},
        {"id": "GF10", "difficulty": "hard", "kind": "binary-legacy",
         "question": "How much did BRIX bill Ostrander Mills in 1999?",
         "answer": f"${f['ostrander_1999_amount']:,.2f} across {f['ostrander_1999_count']} invoices (packed-decimal amounts in BRXINV.Y1999, customer 001207; no Ohio license tax that year).",
         "trail": [f"{RAW}/brix_mainframe/BRXINV.Y1999", f"{RAW}/brix_mainframe/BRXINV.CPY", f"{RAW}/brix_mainframe/BRXCUST.TXT"]},
        {"id": "GF11", "difficulty": "medium", "kind": "undocumented-code",
         "question": "What does status 'X' mean in the BRIX customer master?",
         "answer": "Migrated to Ledger (cloud billing). It is not in the copybook's 88-levels or the README; it is only explained in the 2012 status-code spreadsheet.",
         "trail": [f"{RAW}/brix_mainframe/BRXCUST.TXT", f"{RAW}/brix_mainframe/BRXCUST.CPY", f"{RAW}/spreadsheets/BRIX_status_codes_2012.xls"]},
        {"id": "GF12", "difficulty": "hard", "kind": "entity-resolution",
         "question": "What did St. Brigid's Health System pay Brindlecove in 2022, across all its accounts?",
         "answer": f"USD {f['brigid_2022_usd']:,.2f} (Detroit, Ops Cloud) plus CAD {f['brigid_2022_cad']:,.2f} (Windsor campus, came in via Meridian Dispatch). "
                   "Same health system under different names and two CRM accounts.",
         "trail": [f"{RAW}/billing_v3_2017-now/invoices.csv", f"{RAW}/billing_v3_2017-now/customers.csv",
                   f"{RAW}/crm_salesforce_export_2026-10/Account.csv (duplicate accounts)", f"{RAW}/billing_meridian_2015-2019/"],
         "values": {"USD": f["brigid_2022_usd"], "CAD": f["brigid_2022_cad"]}},
        {"id": "GF13", "difficulty": "hard", "kind": "soft-delete",
         "question": "Which customers were deleted in the CRM but kept being invoiced afterward?",
         "answer": f"{len(f['soft_delete_leaks'])} accounts. Most invoices after deletion: " + "; ".join(f"{x['name']} ({x['invoices_after']} invoices after {x['deleted_on']})" for x in f["soft_delete_leaks"][:3]),
         "trail": [f"{RAW}/crm_salesforce_export_2026-10/Account.csv (IsDeleted = true)", f"{RAW}/billing_v3_2017-now/invoices.csv",
                   f"{RAW}/billing_v3_2017-now/customers.csv (metadata.sfdc_id)"],
         "values": f["soft_delete_leaks"]},
        {"id": "GF14", "difficulty": "medium", "kind": "dirty-categories",
         "question": "What was the most common root cause of Sev1 incidents in 2022?",
         "answer": f"{f['sev1_2022']['top']} ({f['sev1_2022']['by_root'].get(f['sev1_2022']['top'], 0)} of {f['sev1_2022']['count']} Sev1s), "
                   "after normalizing the free-text root cause field.",
         "trail": [f"{RAW}/jira_export_2026-10/INC.json (customfield_10101 = Root Cause, customfield_10100 = Severity)"],
         "values": f["sev1_2022"]},
    ]
    if "wo_2024_top" in f:
        facts.append({"id": "GF15", "difficulty": "medium", "kind": "event-logs",
                      "question": "Which customer created the most work orders in 2024 (per product telemetry)?",
                      "answer": f"{f['wo_2024_top']['name']} (tenant {f['wo_2024_top']['tenant_id']}, {f['wo_2024_top']['events']} wo_created events in the sample, before de-duplicating repeated deliveries).",
                      "trail": [f"{RAW}/product_events/events_2024-*.jsonl.gz", f"{RAW}/product_events/tenants.csv"],
                      "notes": "Event files include duplicated deliveries; the count above is raw. De-duplicated counts may differ slightly."})
    facts += sorted(getattr(world, "extra_facts", []), key=lambda x: int(x["id"][2:]))
    doc = {"description": "Answer key for agent evaluation. Every value is computed by generator/golden.py from the same seeded world that produced data/raw.",
           "seed": world.seed, "facts": facts}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# ALL DATA IS SYNTHETIC. Brindlecove Software and everything in it is invented.\n" +
                    yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120))
