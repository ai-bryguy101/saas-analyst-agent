"""Round 3: cross-source patterns and trends, plus the sources that carry them.

Nothing here is a single planted answer. Each pattern is a tendency spread thinly
across several systems, with noise around it, that an analyst only sees by
aggregating or joining. The answer key records each one (what, where, how strong).

Renders:
  support_zendesk_2020-2026/organizations.json         org -> tenant / billing id (incomplete, name variants)
  support_zendesk_2020-2026/tickets_<year>.jsonl.gz     2020-2023, 2025, 2026
  support_zendesk_2020-2026/tickets_2024_part1.jsonl    \
  support_zendesk_2020-2026/tickets_2024_part2.jsonl     > 2024 export: part2 is cut off mid-record,
  support_zendesk_2020-2026/tickets_2024_part2_retry.jsonl/  the retry overlaps it and has newer edits
  product_usage_exports/usage_<YYYY-MM>.csv            monthly tenant usage, schema drifts three times
  product_changelog/CHANGELOG.md                       release notes (the only explicit hint for P01 / P03)
  app_store_reviews/ios_reviews_2024-2025.csv          App Store Connect export
  app_store_reviews/google_play_reviews_2024-2025.csv  Play Console export (UTF-16LE)
  lms_training/Brindle_Academy_completions_2019-2026.csv  learner emails only, no customer names
  sales_calls_gong/cs_*.json                           customer success check-in calls (Gong format)
  phone_backups/sms_csm_<name>_2025.xml                a CSM's text messages

Patterns:
  P01 churn driver     QuickBooks connector v2 sync failures -> churn (tickets, usage, calls, texts; CRM reasons disagree)
  P02 seasonal/region  Southern facilities and hospitality customers spike every summer (work orders and scheduling tickets)
  P03 release -> pain  Mobile 5.0 (2025-02-10) removed the offline photo queue: mobile tickets and store ratings, until 5.0.3
  P04 hidden join      Customers whose admin finished Academy training in the first 30 days churn far less

Planted facts:
  GF44  Q1 2024 escalations (truncated export, overlapping retry, edits)
  GF46  storage footprint Dec 2022 vs Dec 2023 (column renamed and unit changed MB -> GB)
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from ..util import AS_OF, add_fact, add_pattern, b62, csv_line, month_iter, rng_for, uuid_like, write_gz, write_text

RAW = "data/raw"
SOUTH = {"TX", "FL", "AZ", "GA", "LA", "AL", "MS", "SC", "NV", "OK", "NM"}
SEASONAL_IND = {"Facilities Services", "Property Management", "Hospitality"}
SYNC_V2 = date(2024, 6, 11)
MOBILE5 = date(2025, 2, 10)
MOBILE503 = date(2025, 3, 24)
ESC_FIELD = 360004417231

CATS = {
    "how-to": (["How do I {x}?", "Question about {x}", "Can't figure out {x}"],
               ["set up recurring jobs", "export a report", "add a technician", "change the invoice template", "merge two sites"]),
    "billing": (["Invoice question", "Charged for too many seats?", "Need a W-9", "Update card on file"], []),
    "bug": (["Error when saving a work order", "Report shows wrong totals", "Page won't load", "Duplicate jobs created"], []),
    "access": (["Locked out", "SSO not working", "Reset 2FA for a tech", "Add admin"], []),
    "reports": (["Report is slow", "Need a custom report", "Dashboard missing data"], []),
    "scheduling": (["Dispatch board can't keep up", "Too many jobs to schedule this week", "Need more capacity on the schedule",
                    "Techs double booked", "Calendar view is overloaded"], []),
    "mobile": (["App crashes on Android", "Login on iPad", "Push notifications not arriving"], []),
    "mobile-offline": (["Photos lost when offline", "App lost my photos", "Offline mode broken after update",
                        "Techs losing photos in basements", "Pictures not uploading after update"], []),
    "integration-sync": (["QuickBooks sync failed", "Invoices not syncing to QuickBooks", "Duplicate invoices in QBO",
                          "Sync error 409", "QuickBooks connector disconnected again", "Payments not syncing back"], []),
}
BODY = {
    "integration-sync": ["Since the connector update our invoices are not showing in QuickBooks.", "Getting 'webhook signature mismatch' on every sync.",
                         "Our bookkeeper had to re-key 40 invoices by hand this week.", "The sync created duplicates again. This is the third time.",
                         "QBO says the customer already exists and stops the sync."],
    "mobile-offline": ["Since the update, photos taken without signal never upload.", "Our techs work in basements. The new version drops the photos.",
                       "We lost before/after photos for a whole job.", "Version 5.0 removed the offline queue?"],
    "scheduling": ["Summer rush, we have twice the calls and the board is a mess.", "AC calls are through the roof and we can't fit them in.",
                   "Can we get help setting up a second dispatch board for the season?"],
}


def _ts(d: date, r) -> datetime:
    return datetime(d.year, d.month, d.day, r.randint(12, 23), r.randint(0, 59), r.randint(0, 59), tzinfo=timezone.utc)


def render(world, out, seed):
    r = rng_for(seed, "patterns")
    tenants = getattr(world, "tenants", {})
    cloud = [c for c in world.customers if c.cloud_start and c.key in tenants]

    # ------------------------------------------------------------------ who carries which pattern
    pop1 = [c for c in cloud if c.cloud_start < SYNC_V2 and (not c.end or c.end >= SYNC_V2) and c.country == "US"]
    churn1 = {c.key for c in pop1 if c.end and date(2024, 9, 1) <= c.end <= AS_OF}
    users = {c.key for c in pop1 if r.random() < (0.55 if c.key in churn1 else 0.18)}
    seasonal = {c.key for c in cloud if c.region in SOUTH and c.industry in SEASONAL_IND}
    cohort = [c for c in cloud if date(2019, 1, 1) <= c.cloud_start <= date(2024, 6, 30) and c.contacts]

    def churn24(c):
        return bool(c.end and c.end <= c.cloud_start + timedelta(days=730))
    trained = {c.key for c in cohort if r.random() < (0.30 if churn24(c) else 0.60)}

    # ------------------------------------------------------------------ zendesk organizations
    orgs, org_of = [], {}
    for i, c in enumerate(sorted(cloud, key=lambda c: c.cloud_start)):
        oid = 360000100000 + i * 7 + r.randint(0, 6)
        org_of[c.key] = oid
        name = r.choice(c.variants) if c.variants and r.random() < 0.3 else c.name
        fields = {"ops_tenant": tenants[c.key] if r.random() < 0.9 else None,
                  "billing_customer": c.ids.get("billing") if r.random() < 0.7 else None}
        dom = c.contacts[0].email_domain if c.contacts else None
        orgs.append({"url": f"https://brindlecove.zendesk.example/api/v2/organizations/{oid}.json", "id": oid, "name": name,
                     "domain_names": [dom] if dom else [], "created_at": f"{_ts(c.cloud_start, r):%Y-%m-%dT%H:%M:%SZ}",
                     "tags": [c.plan.lower()], "organization_fields": fields})
    zd = out / "support_zendesk_2020-2026"
    write_text(zd / "organizations.json", json.dumps({"organizations": orgs, "count": len(orgs)}, indent=1))

    # ------------------------------------------------------------------ tickets
    tickets = []
    tid = [410000]

    def ticket(c, created: date, cat: str, escal_p=None):
        tid[0] += r.randint(1, 3)
        subj_t, xs = CATS[cat]
        subj = r.choice(subj_t).format(x=r.choice(xs) if xs else "")
        ct = r.choice(c.contacts) if c.contacts else None
        t0 = _ts(created, r)
        esc = r.random() < (escal_p if escal_p is not None else {"bug": 0.22, "integration-sync": 0.15, "mobile-offline": 0.12}.get(cat, 0.02))
        upd = t0 + timedelta(hours=r.randint(1, 400))
        status = "closed" if upd.date() < AS_OF - timedelta(days=30) else r.choice(["open", "pending", "solved"])
        tags = [cat] + ([c.plan.lower()] if r.random() < 0.5 else [])
        if cat == "mobile-offline":
            tags += ["mobile", "offline"]
        tickets.append({"id": tid[0], "created_at": t0, "updated_at": upd, "type": r.choice(["question", "problem", "incident", None]),
                        "subject": subj, "description": r.choice(BODY.get(cat, ["See subject.", "Please help.", "Thanks in advance."])),
                        "priority": r.choice(["low", "normal", "normal", "high", "urgent"] if cat != "how-to" else ["low", "normal"]),
                        "status": status, "requester_email": ct.email if ct else None, "organization_id": org_of[c.key],
                        "tags": tags, "custom_fields": [{"id": ESC_FIELD, "value": esc}, {"id": 360004417232, "value": cat}],
                        "via": {"channel": r.choice(["email", "web", "web", "api", "voice"])}})

    weekly_mobile = Counter()
    for c in cloud:
        start = max(c.cloud_start, date(2020, 1, 1))
        end = min(c.end or AS_OF, AS_OF)
        for m in month_iter(start, end):
            summer = m.month in (6, 7, 8)
            lam = 0.30 + c.seats(m) / 400
            n = sum(r.random() < lam / 3 for _ in range(3))
            for _ in range(n):
                cat = r.choices(["how-to", "billing", "bug", "access", "reports", "scheduling", "mobile", "integration-sync"],
                                [30, 16, 18, 10, 9, 6, 9, 2])[0]
                ticket(c, m + timedelta(days=r.randint(0, 27)), cat)
            if c.key in seasonal and summer and r.random() < 0.55:          # P02
                for _ in range(r.randint(1, 2)):
                    ticket(c, m + timedelta(days=r.randint(0, 27)), "scheduling")
        # P01: sync failures after the v2 connector
        if c.key in users:
            last = (c.end - timedelta(days=30)) if c.key in churn1 else min(end, date(2025, 6, 30))
            k = r.randint(3, 7) if c.key in churn1 else r.randint(0, 2)
            for _ in range(k):
                if last > SYNC_V2 + timedelta(days=5):
                    ticket(c, SYNC_V2 + timedelta(days=r.randint(5, (last - SYNC_V2).days)), "integration-sync")
        elif c.key in {x.key for x in pop1} and r.random() < 0.04:
            ticket(c, SYNC_V2 + timedelta(days=r.randint(5, 400)), "integration-sync")
        # P03: mobile 5.0 offline regression
        if start <= MOBILE5 <= end:
            if r.random() < 0.11:
                ticket(c, MOBILE5 + timedelta(days=r.randint(0, (MOBILE503 - MOBILE5).days + 6)), "mobile-offline")
            if r.random() < 0.04:
                ticket(c, MOBILE5 + timedelta(days=r.randint(-200, 200)), "mobile-offline")
    tickets.sort(key=lambda t: (t["created_at"], t["id"]))
    for t in tickets:
        if "mobile-offline" in t["tags"]:
            weekly_mobile[(t["created_at"].date() - MOBILE5).days // 7] += 1

    def ser(t):
        x = dict(t)
        x["created_at"] = f"{t['created_at']:%Y-%m-%dT%H:%M:%SZ}"
        x["updated_at"] = f"{t['updated_at']:%Y-%m-%dT%H:%M:%SZ}"
        return json.dumps(x, separators=(",", ":"))

    by_year = defaultdict(list)
    for t in tickets:
        by_year[t["created_at"].year].append(t)
    for y, ts in by_year.items():
        if y != 2024:
            write_gz(zd / f"tickets_{y}.jsonl.gz", "\n".join(ser(t) for t in ts) + "\n")

    # GF44: the 2024 export failed half way and was re-run
    t24 = by_year[2024]
    cut = len(t24) // 2
    p1, p2 = t24[:cut], t24[cut:]
    write_text(zd / "tickets_2024_part1.jsonl", "\n".join(ser(t) for t in p1) + "\n")
    trunc = p2[: len(p2) * 2 // 3]
    lines = [ser(t) for t in trunc]
    lines[-1] = lines[-1][: len(lines[-1]) // 2]                       # cut mid-record
    write_text(zd / "tickets_2024_part2.jsonl", "\n".join(lines))
    # retry: an incremental export by updated_at, started 300 tickets before the cut (so it overlaps part1). Tickets that
    # were escalated after the first run (including Q1 ones) come back with a newer updated_at.
    edited = []
    for t in t24[:cut]:
        if t["created_at"].month <= 3 and not t["custom_fields"][0]["value"] and r.random() < 0.03:
            t2 = dict(t)
            t2["custom_fields"] = [{"id": ESC_FIELD, "value": True}, t["custom_fields"][1]]
            t2["updated_at"] = datetime(2024, 7, 1, tzinfo=timezone.utc) + timedelta(hours=r.randint(1, 900))
            edited.append(t2)
    edited_ids = {t["id"]: t for t in edited}
    retry = sorted(t24[cut - 300:] + edited, key=lambda t: (t["updated_at"], t["id"]))
    write_text(zd / "tickets_2024_part2_retry.jsonl", "\n".join(ser(t) for t in retry) + "\n")
    final = {t["id"]: edited_ids.get(t["id"], t) for t in t24}
    q1 = [t for t in final.values() if t["created_at"] < datetime(2024, 4, 1, tzinfo=timezone.utc) and t["custom_fields"][0]["value"]]
    naive_p1 = sum(1 for t in p1 if t["created_at"].month <= 3 and t["custom_fields"][0]["value"])
    add_fact(world, {"id": "GF44", "difficulty": "hard", "kind": "partial and overlapping export",
                     "question": "How many support tickets were escalated to engineering in Q1 2024?",
                     "answer": f"{len(q1)}. Read all three 2024 files, skip the cut-off last line of part2, de-duplicate by ticket id and keep the "
                               f"version with the latest updated_at ({len(edited)} tickets were escalated after the first export ran). "
                               f"Escalation is custom field {ESC_FIELD}.",
                     "trail": [f"{RAW}/support_zendesk_2020-2026/tickets_2024_part1.jsonl",
                               f"{RAW}/support_zendesk_2020-2026/tickets_2024_part2.jsonl (last line truncated)",
                               f"{RAW}/support_zendesk_2020-2026/tickets_2024_part2_retry.jsonl (incremental by updated_at; overlaps part1)"],
                     "traps": ["part2 ends mid-record", "the retry file overlaps part1, so a plain concat double counts",
                               "some tickets changed between the two runs: keep the latest updated_at",
                               "escalation lives in custom_fields by numeric id, not in tags"],
                     "values": {"escalated_q1_2024": len(q1), "edited_between_runs": len(edited), "part1_only_naive": naive_p1}})

    # ------------------------------------------------------------------ usage exports (schema drift + P01/P02 signal)
    ue = out / "product_usage_exports"
    util = {c.key: r.uniform(0.55, 0.95) for c in cloud}
    wo_rate = {c.key: r.uniform(6, 14) for c in cloud}
    storage_mb = {}
    totals = {}
    summer_ratio = defaultdict(lambda: [0, 0])          # seasonal flag -> [summer wo, winter wo]
    for m in month_iter(date(2022, 1, 1), date(2026, 10, 1)):
        rows = []
        for c in cloud:
            if not c.active(m) or m < date(c.cloud_start.year, c.cloud_start.month, 1):
                continue
            seats = c.seats(m)
            au = seats * util[c.key] * r.uniform(0.93, 1.05)
            if c.end and (c.end - m).days < 150:                               # pre-churn decline
                frac = 1 - max(0, (c.end - m).days) / 150
                au *= 1 - (0.5 if c.key in users and c.key in churn1 else 0.25) * frac
            au = max(1, round(min(au, seats)))
            season = 1.0
            if c.key in seasonal:
                season = {6: 1.65, 7: 1.85, 8: 1.7, 5: 1.2, 9: 1.15}.get(m.month, 1.0)
            else:
                season = {12: 0.9, 1: 0.95}.get(m.month, 1.0)
            wo = round(au * wo_rate[c.key] * season * r.uniform(0.85, 1.15))
            if m.year in (2022, 2023, 2024, 2025):
                bucket = "summer" if m.month in (6, 7, 8) else ("winter" if m.month in (12, 1, 2) else None)
                if bucket:
                    summer_ratio[c.key in seasonal][0 if bucket == "summer" else 1] += wo
            storage_mb[c.key] = storage_mb.get(c.key, seats * r.uniform(40, 120)) + wo * r.uniform(1.6, 2.6)
            st = storage_mb[c.key]
            api = int(au * r.uniform(800, 3000))
            name = r.choice(c.variants) if c.variants and r.random() < 0.15 else c.name
            rows.append((c, seats, au, wo, st, api, name))
        if m in (date(2022, 12, 1), date(2023, 12, 1)):
            totals[m.year] = sum(x[4] for x in rows)
        if m < date(2023, 1, 1):
            hdr = ["tenant_id", "account", "month", "seats", "active_users", "work_orders", "storage_mb"]
            body = [[tenants[c.key], nm, f"{m:%Y-%m}", s, a, w, f"{st:.1f}"] for c, s, a, w, st, api, nm in rows]
            text = "\n".join(csv_line(x) for x in [hdr] + body) + "\n"
        elif m < date(2023, 7, 1):
            hdr = ["tenant_id", "account_name", "period", "licensed_users", "active_users", "work_orders", "storage_mb", "api_calls"]
            body = [[tenants[c.key], nm, f"{m:%Y-%m-01}", s, a, w, f"{st:.1f}", api] for c, s, a, w, st, api, nm in rows]
            text = "\n".join(csv_line(x) for x in [hdr] + body) + "\n"
        elif m < date(2025, 3, 1):
            hdr = ["tenant", "account_name", "period", "seat_count", "mau", "work_orders_created", "storage_gb", "api_calls"]
            body = [[tenants[c.key], nm, f"{m:%Y-%m-01}", s, a, w, f"{st / 1024:.3f}", api] for c, s, a, w, st, api, nm in rows]
            text = "\n".join(csv_line(x) for x in [hdr] + body) + "\n"
        else:   # new warehouse job: semicolon delimited, columns reordered
            hdr = ["period", "tenant", "mau", "seat_count", "work_orders_created", "api_calls", "storage_gb", "account_name"]
            body = [[f"{m:%Y-%m-01}", tenants[c.key], a, s, w, api, f"{st / 1024:.3f}", nm] for c, s, a, w, st, api, nm in rows]
            text = "\n".join(csv_line(x, delim=";") for x in [hdr] + body) + "\n"
        write_text(ue / f"usage_{m:%Y-%m}.csv", text)
    tb22, tb23 = totals[2022] / 1024 / 1024, totals[2023] / 1024 / 1024
    add_fact(world, {"id": "GF46", "difficulty": "medium", "kind": "schema drift",
                     "question": "How much data were customers storing at the end of 2023 compared with the end of 2022?",
                     "answer": f"{tb23:.2f} TB in December 2023 versus {tb22:.2f} TB in December 2022 (up {(tb23 / tb22 - 1) * 100:.0f}%). "
                               "The column is storage_mb until June 2023 and storage_gb from July 2023, so adding the raw numbers "
                               "makes storage look like it fell by about 99.9%.",
                     "trail": [f"{RAW}/product_usage_exports/usage_2022-12.csv (storage_mb)", f"{RAW}/product_usage_exports/usage_2023-12.csv (storage_gb)"],
                     "traps": ["storage_mb became storage_gb in July 2023", "tenant_id became tenant, seats became licensed_users then seat_count",
                               "from March 2025 the files are semicolon delimited with reordered columns"],
                     "values": {"tb_2022_12": round(tb22, 2), "tb_2023_12": round(tb23, 2)}})

    # ------------------------------------------------------------------ changelog
    log = ["# Brindle Ops Cloud changelog", "", "Internal. Customer-facing notes are on the status page.", ""]
    rel = [(date(2023, 3, 14), "4.2.0", ["Faster dispatch board", "CSV import for assets"]),
           (date(2023, 9, 5), "4.4.0", ["Recurring jobs editor", "Fix: report totals with credit notes"]),
           (date(2024, 2, 20), "4.6.0", ["SSO for Pro plan", "New invoice templates"]),
           (SYNC_V2, "4.7.0", ["QuickBooks Online connector v2: moved from polling to webhooks; v1 retired on 2024-07-31",
                               "Minor: dark mode for the web app"]),
           (date(2024, 10, 2), "4.8.1", ["Fix: some QBO webhooks rejected after token refresh (partial)", "Bulk edit for sites"]),
           (MOBILE5, "mobile 5.0.0", ["Rebuilt mobile app on the new framework", "Photos now upload directly; the separate offline photo queue was removed",
                                      "New job timeline"]),
           (date(2025, 2, 27), "mobile 5.0.2", ["Crash fix on older Android devices"]),
           (MOBILE503, "mobile 5.0.3", ["Restored offline photo queue: photos taken without signal upload when the device reconnects"]),
           (date(2025, 6, 18), "4.11.0", ["Usage export moved to the new warehouse job (semicolon delimited)", "Technician skills matching"]),
           (date(2026, 4, 9), "4.14.0", ["Insights dashboards v2"])]
    for d, v, items in sorted(rel, reverse=True):
        log += [f"## {v} ({d:%Y-%m-%d})", ""] + [f"- {x}" for x in items] + [""]
    write_text(out / "product_changelog" / "CHANGELOG.md", "\n".join(log))

    # ------------------------------------------------------------------ app store reviews (P03)
    ios = [["App Name", "App Apple ID", "Review Date", "Rating", "Title", "Review", "Version", "Territory", "Nickname"]]
    play = [["Package Name", "App Version Code", "App Version Name", "Reviewer Language", "Device", "Review Submit Date and Time",
             "Review Submit Millis Since Epoch", "Review Last Update Date and Time", "Review Last Update Millis Since Epoch",
             "Star Rating", "Review Title", "Review Text", "Developer Reply Date and Time", "Developer Reply Millis Since Epoch",
             "Developer Reply Text", "Review Link"]]
    good = ["Works great for our techs", "Easy to use", "Love the job timeline", "Solid app", "Does what we need"]
    bad = ["Lost all my photos", "Offline mode is gone??", "Update broke photo uploads", "Photos vanish without signal", "Worst update ever"]
    rating_by_phase = defaultdict(list)
    d = date(2024, 1, 2)
    while d <= date(2025, 12, 31):
        phase = "before" if d < MOBILE5 else ("broken" if d < MOBILE503 else "after")
        for _ in range(r.choice([0, 1, 1, 2, 3] if phase != "broken" else [3, 4, 5, 6])):
            if phase == "broken":
                stars = r.choices([1, 2, 3, 4, 5], [44, 20, 12, 10, 14])[0]
            else:
                stars = r.choices([1, 2, 3, 4, 5], [5, 4, 8, 28, 55] if phase == "before" else [7, 5, 10, 30, 48])[0]
            rating_by_phase[phase].append(stars)
            ver = ("4." + str(r.randint(6, 9)) + ".0") if phase == "before" else ("5.0.0" if phase == "broken" else "5." + str(r.randint(0, 3)) + ".3")
            txt = r.choice(bad if stars <= 2 and phase == "broken" else (good if stars >= 4 else ["It's ok", "Sync is slow", "Needs a dark mode"]))
            if r.random() < 0.5:
                ios.append(["Brindle Ops", "1458823019", f"{d:%Y-%m-%d}", stars, txt[:30], txt, ver, r.choice(["USA", "CAN", "GBR"]), "user" + b62(r, 6)])
            else:
                ts = datetime(d.year, d.month, d.day, r.randint(0, 23), r.randint(0, 59), r.randint(0, 59), tzinfo=timezone.utc)
                ms = int(ts.timestamp() * 1000)
                play.append(["com.brindlecove.ops", str(500 + r.randint(0, 40)), ver, "en", r.choice(["a52", "redfin", "SM-G991U", "Pixel 6"]),
                             f"{ts:%Y-%m-%dT%H:%M:%SZ}", ms, f"{ts:%Y-%m-%dT%H:%M:%SZ}", ms, stars, "", txt, "", "", "", ""])
        d += timedelta(days=1)
    write_text(out / "app_store_reviews" / "ios_reviews_2024-2025.csv", "\n".join(csv_line(x) for x in ios) + "\n")
    write_text(out / "app_store_reviews" / "google_play_reviews_2024-2025.csv", "\n".join(csv_line(x) for x in play) + "\n",
               encoding="utf-16-le", bom=True)

    # ------------------------------------------------------------------ LMS (P04)
    lms = [["learner_email", "learner_name", "course_code", "course_title", "enrolled_at", "completed_at", "score_pct", "certificate_id"]]
    courses = [("OCA-101", "Ops Cloud Admin Essentials"), ("DSP-110", "Dispatch Board Basics"), ("INV-120", "Invoicing in Ops Cloud"),
               ("MOB-130", "Mobile App for Technicians"), ("RPT-210", "Reporting and Insights")]
    for c in sorted(cohort, key=lambda c: c.cloud_start):
        admin = c.contacts[0]
        enrol = c.cloud_start + timedelta(days=r.randint(0, 6))
        if c.key in trained:
            done = enrol + timedelta(days=r.randint(2, 26))
            lms.append([admin.email, admin.name, "OCA-101", courses[0][1], f"{enrol:%Y-%m-%d}", f"{done:%Y-%m-%d}", r.randint(72, 100), "CERT-" + b62(r, 8)])
        elif r.random() < 0.35:     # enrolled, finished late or never
            late = r.random() < 0.5 and not (c.end and c.end < enrol + timedelta(days=120))
            done = enrol + timedelta(days=r.randint(45, 200)) if late else None
            lms.append([admin.email, admin.name, "OCA-101", courses[0][1], f"{enrol:%Y-%m-%d}", f"{done:%Y-%m-%d}" if done else "",
                        r.randint(60, 95) if done else "", "CERT-" + b62(r, 8) if done else ""])
        for ct in c.contacts[1:]:
            if r.random() < 0.4:
                code, title = r.choice(courses[1:])
                e = enrol + timedelta(days=r.randint(0, 300))
                fin = r.random() < 0.7
                lms.append([ct.email.upper() if r.random() < 0.1 else ct.email, ct.name, code, title, f"{e:%Y-%m-%d}",
                            f"{e + timedelta(days=r.randint(1, 40)):%Y-%m-%d}" if fin else "", r.randint(55, 100) if fin else "", ""])
    write_text(out / "lms_training" / "Brindle_Academy_completions_2019-2026.csv", "\n".join(csv_line(x) for x in lms) + "\n")

    # ------------------------------------------------------------------ CS calls (Gong) and CSM texts
    csm = next(p for p in world.people if p.dept == "Customer Success" and not p.left and "Customer Success Manager" in p.title)
    gong = out / "sales_calls_gong"
    sync_lines = ["Honestly the QuickBooks sync has been a nightmare since the summer.", "Our bookkeeper is re-keying invoices by hand.",
                  "Every time it disconnects we lose a day.", "We're looking at options that just work with QuickBooks.",
                  "If this isn't fixed by renewal I can't defend it to our owner."]
    calm = ["Things are going well overall.", "The team likes the dispatch board.", "We might add a few seats next quarter."]
    rep = ["I hear you. Engineering has a fix in progress.", "Let me get you on a call with our integrations team.", "Can I share a workaround?",
           "Thanks, that's helpful context for the renewal."]
    calls = 0
    cands = sorted([c for c in pop1 if c.key in users and c.key in churn1], key=lambda c: c.end)
    others = sorted([c for c in pop1 if c.key not in churn1], key=lambda c: c.key)
    plan = [(c, True) for c in cands[:24]] + [(c, False) for c in r.sample(others, 30)]
    for c, sync in plan:
        when = (c.end - timedelta(days=r.randint(30, 90))) if c.end else date(2024, 9, 1) + timedelta(days=r.randint(0, 600))
        if when < SYNC_V2 + timedelta(days=20):
            when = SYNC_V2 + timedelta(days=r.randint(20, 60))
        cid = uuid_like(r)
        start = datetime(when.year, when.month, when.day, r.randint(13, 21), 0, tzinfo=timezone.utc)
        ext = c.contacts[0] if c.contacts else None
        lines = ([r.choice(calm)] + r.sample(sync_lines, 3)) if sync else (r.sample(calm, 2) + ([r.choice(sync_lines[:2])] if c.key in users and r.random() < 0.5 else []))
        tr, t = [], 0
        for i, ln in enumerate(lines):
            for who, text in (("s1", ln), ("s0", r.choice(rep))):
                dur = 1500 + len(text) * 55
                tr.append({"speakerId": who, "topic": None, "sentences": [{"start": t, "end": t + dur, "text": text}]})
                t += dur + r.randint(400, 2500)
        doc = {"metaData": {"id": cid, "url": f"https://app.gong.example/call?id={cid}", "title": f"{c.name} | Quarterly check-in",
                            "scheduled": f"{start:%Y-%m-%dT%H:%M:%SZ}", "started": f"{start + timedelta(seconds=r.randint(20, 400)):%Y-%m-%dT%H:%M:%SZ}",
                            "duration": t // 1000, "primaryUserId": csm.pid, "direction": "Conference", "system": "Zoom", "scope": "External",
                            "media": "Video", "language": "eng"},
               "parties": [{"id": "s0", "name": csm.name, "affiliation": "Internal", "emailAddress": csm.email(when)},
                           {"id": "s1", "name": ext.name if ext else None, "affiliation": "External", "emailAddress": ext.email if ext else None}],
               "transcript": tr}
        write_text(gong / f"cs_{when:%Y-%m-%d}_{cid[:8]}.json", json.dumps(doc, indent=1))
        calls += 1
    sms = []
    for c in cands[24:36]:
        d = c.end - timedelta(days=r.randint(20, 70))
        sms.append((d, f"Heads up: {c.name.split()[0]} is talking about leaving over the QuickBooks sync again"))
    for c in r.sample(others, 8):
        sms.append((date(2025, 1, 6) + timedelta(days=r.randint(0, 280)), r.choice(["Can you join the {n} QBR Thursday?", "{n} renewed!"]).format(n=c.name.split()[0])))
    sms.sort()
    smsx = ["<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>",
            f"<!--File Created By SMS Backup &amp; Restore v10.18.002 on 03/11/2025 09:12:40-->",
            f'<smses count="{len(sms)}" backup_set="{uuid_like(r)}" backup_date="1762161160000" type="full">']
    for d, body in sms:
        ts = datetime(d.year, d.month, d.day, r.randint(13, 23), r.randint(0, 59), r.randint(0, 59), tzinfo=timezone.utc)
        ms = int(ts.timestamp() * 1000)
        body = body.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&apos;")
        smsx.append(f'  <sms protocol="0" address="+1614555{r.randint(100, 199):04d}" date="{ms}" type="{r.choice([1, 2])}" subject="null" '
                    f'body="{body}" toa="null" sc_toa="null" service_center="null" read="1" status="-1" locked="0" date_sent="{ms - 2000}" '
                    f'sub_id="1" readable_date="{ts:%b %d, %Y %I:%M:%S %p}" contact_name="(Unknown)" />')
    smsx.append("</smses>")
    write_text(out / "phone_backups" / f"sms_csm_{csm.first.lower()}_{csm.last.lower()}_2025.xml", "\n".join(smsx) + "\n")

    # ------------------------------------------------------------------ pattern answer key
    pk = {c.key for c in pop1}
    n_u = len(users & pk)
    ch_u = len(users & churn1)
    ch_n = len(churn1 - users)
    rate_u = ch_u / n_u
    rate_n = ch_n / (len(pk) - n_u)
    crm_integr = sum(1 for c in pop1 if c.key in users & churn1 and c.churn_reason in ("Product gaps", "Outage / reliability"))
    add_pattern(world, {
        "id": "P01", "kind": "churn driver", "strength": "strong",
        "summary": "US cloud customers who used the QuickBooks Online connector after v2 shipped (2024-06-11) and hit repeated sync "
                   f"failures churned at {rate_u * 100:.0f}% (Sep 2024 to Oct 2026) versus {rate_n * 100:.0f}% for everyone else.",
        "how_to_find": "Join Zendesk tickets tagged integration-sync (organization -> ops_tenant) to usage exports (tenant disappears "
                       "after churn). Churners with 3+ sync tickets show a 40-50% drop in mau over their last five months.",
        "sources": [f"{RAW}/support_zendesk_2020-2026/", f"{RAW}/product_usage_exports/", f"{RAW}/product_changelog/CHANGELOG.md (4.7.0, 4.8.1)",
                    f"{RAW}/sales_calls_gong/cs_*.json", f"{RAW}/phone_backups/sms_csm_*_2025.xml", f"{RAW}/billing_v3_2017-now/subscriptions.csv"],
        "noise": "About 4% of non-connector customers file a sync ticket too; most churners also have ordinary tickets; "
                 f"only {crm_integr} of the {ch_u} connector churners have a CRM churn reason that points at product or reliability.",
        "values": {"connector_customers": n_u, "population": len(pk), "churned_connector": ch_u, "churned_other": ch_n,
                   "churn_rate_connector": round(rate_u, 3), "churn_rate_other": round(rate_n, 3), "gong_calls": calls}})
    s_ratio = summer_ratio[True][0] / summer_ratio[True][1]
    o_ratio = summer_ratio[False][0] / summer_ratio[False][1]
    add_pattern(world, {
        "id": "P02", "kind": "seasonal and regional trend", "strength": "moderate",
        "summary": f"Facilities, property management and hospitality customers in southern states run {s_ratio:.2f}x as many work orders "
                   f"in June to August as in December to February; everyone else runs {o_ratio:.2f}x. They also file extra scheduling tickets each summer.",
        "how_to_find": "Group usage exports by month and by the customer's state and industry (state and industry live in the CRM, "
                       "not in the usage files), then compare summer and winter.",
        "sources": [f"{RAW}/product_usage_exports/", f"{RAW}/crm_salesforce_export_2026-10/Account.csv", f"{RAW}/support_zendesk_2020-2026/"],
        "noise": "Per-customer work order rates vary 2x and every month has +/-15% noise; the column name changes in 2023.",
        "values": {"segment_customers": len(seasonal), "summer_winter_ratio_segment": round(s_ratio, 2), "summer_winter_ratio_rest": round(o_ratio, 2)}})
    before = sum(weekly_mobile[w] for w in range(-6, 0)) / 6
    during = sum(weekly_mobile[w] for w in range(0, 6)) / 6
    rb = sum(rating_by_phase["before"]) / len(rating_by_phase["before"])
    rd = sum(rating_by_phase["broken"]) / len(rating_by_phase["broken"])
    ra = sum(rating_by_phase["after"]) / len(rating_by_phase["after"])
    add_pattern(world, {
        "id": "P03", "kind": "product change -> complaints", "strength": "strong",
        "summary": f"Mobile 5.0.0 (2025-02-10) removed the offline photo queue. Offline-photo tickets went from {before:.1f} a week to "
                   f"{during:.1f} a week and the average store rating fell from {rb:.2f} to {rd:.2f}, recovering to {ra:.2f} after 5.0.3 (2025-03-24).",
        "how_to_find": "Weekly counts of tickets tagged offline or mentioning photos, lined up against the changelog and the two store exports.",
        "sources": [f"{RAW}/product_changelog/CHANGELOG.md", f"{RAW}/support_zendesk_2020-2026/tickets_2025.jsonl.gz",
                    f"{RAW}/app_store_reviews/ios_reviews_2024-2025.csv", f"{RAW}/app_store_reviews/google_play_reviews_2024-2025.csv (UTF-16)"],
        "noise": "A few offline tickets appear months before and after; Android 5.0.2 was a separate crash fix, not the cause.",
        "values": {"weekly_before": round(before, 1), "weekly_during": round(during, 1), "rating_before": round(rb, 2),
                   "rating_during": round(rd, 2), "rating_after": round(ra, 2)}})
    tr_c = [c for c in cohort if c.key in trained]
    un_c = [c for c in cohort if c.key not in trained]
    rt = sum(churn24(c) for c in tr_c) / len(tr_c)
    ru = sum(churn24(c) for c in un_c) / len(un_c)
    add_pattern(world, {
        "id": "P04", "kind": "hidden correlation (needs a join)", "strength": "strong",
        "summary": f"Customers whose admin completed 'Ops Cloud Admin Essentials' within 30 days of going live churned within two years "
                   f"{rt * 100:.0f}% of the time, versus {ru * 100:.0f}% for customers whose admin didn't (cohort: went live 2019 to mid-2024).",
        "how_to_find": "The LMS export has learner emails only. Match the email domain to CRM contacts or Account websites to get the "
                       "customer, then take go-live and churn dates from billing.",
        "sources": [f"{RAW}/lms_training/Brindle_Academy_completions_2019-2026.csv", f"{RAW}/crm_salesforce_export_2026-10/Contact.csv",
                    f"{RAW}/billing_v3_2017-now/subscriptions.csv"],
        "noise": "Late completions (after 30 days) don't count and look similar; other courses are taken by non-admins; ~10% of emails are upper case.",
        "values": {"cohort": len(cohort), "trained": len(tr_c), "churn24_trained": round(rt, 3), "churn24_untrained": round(ru, 3)}})
    return {}
