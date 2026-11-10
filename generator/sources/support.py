"""Support history: a Zendesk-style helpdesk (2011-2019) then Jira (2019-now).

Renders:
  support_helpdesk_2011-2019/tickets_export.json.gz      one JSON array, HTML bodies, org names free-typed
  support_helpdesk_2011-2019/users_export.csv
  jira_export_2026-10/SUP-*.json                         Jira REST-style issues by year (SUP project)
  jira_export_2026-10/INC.json, DATA.json, ENG.json      incidents, data-team and engineering tickets
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from ..util import AS_OF, csv_line, hexid, rand_date, rng_for, typo, write_gz, write_text
from ..world import ERA

TOPICS = [
    ("Login", ["Can't log in", "Password reset not arriving", "SSO error after IdP change", "Locked out after 5 attempts", "2FA codes not accepted"]),
    ("Work Orders", ["Work orders not syncing to mobile", "Duplicate work orders created", "Can't close WO - spinner", "Recurring PM not generating", "Wrong technician assigned"]),
    ("Billing", ["Question about invoice", "Charged twice this month", "Need W-9", "Update billing contact", "Seat count wrong on invoice", "Request PO on invoice"]),
    ("Reports", ["Export to Excel broken", "Report totals don't match", "Scheduled report not emailed", "Custom field missing in report"]),
    ("Mobile", ["App crashes on Android 9", "Offline mode loses photos", "iOS app stuck on splash", "GPS check-in wrong"]),
    ("Integrations", ["API returning 500", "Webhook not firing", "TallyFlow sync stuck", "Dispatch feed delayed", "CSV import fails with encoding error"]),
    ("Account", ["Add users", "Remove ex-employee", "Change account owner", "Cancel subscription", "Data export request"]),
    ("Performance", ["Very slow today", "Timeouts on dashboard", "Search takes 30s+"]),
]

BODY = [
    "Hi team,\n\n{issue} since this morning. {who} tried clearing cache and it still happens.\n\nThanks,\n{name}",
    "{issue}. This is impacting our techs in the field. Please call me at {phone}.\n\n{name}\n{title}",
    "hello - {issue_l}?? we have an audit next week. pls advise",
    "{issue}. Screenshot attached. Account: {org}. Steps: 1) open app 2) tap sync 3) error 0x80{hex}",
    "Following up on my previous ticket. {issue_l} again. This is the third time this month.",
    "{issue}. Our card ending 4{last4} was charged. Can someone look? [card number redacted by system]",
    "Hi,\nWe need help: {issue_l}.\n\nSent from my iPhone",
]

SUPPORT_REPLIES = [
    "Thanks for reaching out! I've escalated this to our engineering team and will update you shortly.",
    "Could you send us a HAR file and the exact time (with time zone) this happened?",
    "This was caused by a known issue that has now been resolved. Please let us know if you still see it.",
    "I've reset the sync token for your account. Please log out and back in on the device.",
    "Our billing team has issued a credit for the duplicate charge; it will appear on your next invoice.",
    "Closing this ticket due to inactivity. Reply to reopen.",
    "Workaround: export as CSV (UTF-8) instead of XLS for now.",
]

INC_ROOT = ["Database", "Deploy / bad release", "Third-party provider", "Capacity", "Network", "Certificate expiry", "Config change"]
INC_ROOT_SPELLINGS = {
    "Database": ["Database", "database", "DB", "Database - connection pool", "Postgres", "db (replica lag)"],
    "Deploy / bad release": ["Deploy / bad release", "Bad deploy", "deploy", "Release regression", "Code change"],
    "Third-party provider": ["Third-party provider", "3rd party", "Vendor", "Third party (SMS)", "AWS"],
    "Capacity": ["Capacity", "capacity", "Load spike", "Resource exhaustion"],
    "Network": ["Network", "network", "DNS", "Networking/LB"],
    "Certificate expiry": ["Certificate expiry", "Cert expired", "TLS cert"],
    "Config change": ["Config change", "config", "Misconfiguration", "Feature flag"],
}


def html(s):
    return "<p>" + s.replace("&", "&amp;").replace("<", "&lt;").replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>"


def render(world, out, seed):
    r = rng_for(seed, "support")
    agents = [p for p in world.people if p.dept == "Support"]
    tickets_hd, users = [], {}
    sup_by_year = defaultdict(list)
    jid = Counter()
    hd_id = 1000

    def ticket_count(c, d):
        return c.seats(d) / 40.0

    def make_text(c, ct, topic, subj):
        tmpl = r.choice(BODY)
        return tmpl.format(issue=subj, issue_l=subj.lower(), who=r.choice(["Our tech", "I", "Our IT guy", "Dispatcher"]),
                           name=ct.first, phone=ct.phone, title=ct.title, org=r.choice(c.variants), hex=hexid(r, 4).upper(),
                           last4=f"{r.randint(0, 999):03d}")

    for c in world.customers:
        if not c.cloud_start:
            continue
        start = max(c.cloud_start, date(2011, 9, 1))
        end = min(c.end or AS_OF, AS_OF)
        months = max(0, (end.year - start.year) * 12 + end.month - start.month)
        n = int(ticket_count(c, start) * months / 12 * r.uniform(0.5, 1.5))
        if c is world.golden["harbortown"]:
            n = max(n, 25)
        for _ in range(min(n, 400)):
            created = rand_date(r, start, end)
            topic, subjects = r.choice(TOPICS)
            subj = r.choice(subjects)
            ct = r.choice(c.contacts)
            prio = r.choices(["low", "normal", "high", "urgent"], [20, 55, 20, 5])[0]
            agent = r.choice([a for a in agents if a.hired <= created and (not a.left or a.left >= created)] or agents)
            solved = created + timedelta(hours=r.randint(1, 24 * 14))
            body = make_text(c, ct, topic, subj)
            if created < ERA["helpdesk_to_jira"]:
                hd_id += 1
                comments = [{"author": ct.email, "public": True, "created_at": f"{created}T{r.randint(10, 23):02d}:{r.randint(0, 59):02d}:00Z", "html_body": html(body)}]
                for k in range(r.randint(0, 4)):
                    comments.append({"author": agent.email(created), "public": r.random() > 0.15,
                                     "created_at": f"{created + timedelta(hours=k * 5 + 2)}T12:00:00Z".replace(" ", "T", 0),
                                     "html_body": html(r.choice(SUPPORT_REPLIES))})
                users[ct.email] = (ct.name, r.choice(c.variants))
                tickets_hd.append({"id": hd_id, "subject": subj if r.random() > 0.05 else typo(r, subj),
                                   "status": "closed" if solved < ERA["helpdesk_to_jira"] else r.choice(["open", "pending", "solved"]),
                                   "priority": prio if r.random() > 0.1 else None, "type": r.choice(["question", "incident", "problem", "task", None]),
                                   "requester": ct.email, "organization_name": r.choice(c.variants),
                                   "assignee": agent.email(created), "created_at": f"{created}T{r.randint(10, 23):02d}:{r.randint(0, 59):02d}:00Z",
                                   "updated_at": f"{solved.date() if hasattr(solved, 'date') else solved}T09:00:00Z",
                                   "tags": [topic.lower().replace(" ", "_")] + r.sample(["vip", "classic_migrated", "billing", "android", "ios", "escalated", "sla_breach"], r.randint(0, 2)),
                                   "custom_fields": {"product_area": topic if r.random() > 0.2 else "", "brix_no": c.ids.get("brix", "")},
                                   "comments": comments, "satisfaction_rating": r.choice([None, None, "good", "good", "bad"])})
            else:
                year = created.year
                jid["SUP"] += 1
                key = f"SUP-{jid['SUP']}"
                created_s = f"{created}T{r.randint(10, 23):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}.000+0000"
                status = "Done" if solved < AS_OF - timedelta(days=10) else r.choice(["Open", "In Progress", "Waiting for customer", "Done"])
                issue = {"key": key, "fields": {
                    "summary": subj, "issuetype": {"name": r.choice(["Service Request", "Incident", "Question", "Problem"])},
                    "status": {"name": status}, "priority": {"name": {"low": "Low", "normal": "Medium", "high": "High", "urgent": "Highest"}[prio]},
                    "created": created_s, "resolutiondate": (f"{solved}T17:00:00.000+0000" if status == "Done" else None),
                    "reporter": {"displayName": ct.name, "emailAddress": ct.email if r.random() > 0.05 else None},
                    "assignee": {"displayName": agent.name} if r.random() > 0.08 else None,
                    "customfield_10010": {"value": r.choice(c.variants)},         # Organization (free text before 2021)
                    "customfield_10042": c.ids.get("sfdc") if created > date(2021, 3, 1) and r.random() > 0.2 else None,   # SFDC Account Id
                    "customfield_10050": topic if r.random() > 0.15 else None,      # Product area
                    "labels": r.sample(["billing", "mobile", "escalated", "vip", "kestrel", "dispatch", "bug", "fr"], r.randint(0, 2)),
                    "description": body.replace("\n\n", "\n\n").replace("Hi team,", "h3. Hi team,") if r.random() < 0.2 else body,
                    "comment": {"comments": [{"author": {"displayName": agent.name}, "created": created_s, "body": r.choice(SUPPORT_REPLIES)}
                                             for _ in range(r.randint(0, 3))]},
                }}
                sup_by_year[year].append(issue)

    # Harbortown's outage tickets in March 2016 (corroborates GF01)
    hb = world.golden["harbortown"]
    for d in [date(2016, 3, 8), date(2016, 3, 8), date(2016, 3, 9), date(2016, 3, 22)]:
        hd_id += 1
        tickets_hd.append({"id": hd_id, "subject": "URGENT system down - techs cannot see work orders", "status": "closed",
                           "priority": "urgent", "type": "incident", "requester": hb.contacts[0].email,
                           "organization_name": "Harbortown Property Grp", "assignee": "jpark@brindlecove.com",
                           "created_at": f"{d}T13:{r.randint(10, 59)}:00Z", "updated_at": f"{d + timedelta(days=2)}T09:00:00Z",
                           "tags": ["outage", "escalated", "vip"], "custom_fields": {"product_area": "Performance", "brix_no": ""},
                           "comments": [{"author": hb.contacts[0].email, "public": True, "created_at": f"{d}T13:20:00Z",
                                         "html_body": html("Nothing loads. 140 techs idle. This is the 2nd time this month. Lionel")}],
                           "satisfaction_rating": "bad"})
    tickets_hd.sort(key=lambda t: t["id"])
    write_gz(out / "support_helpdesk_2011-2019" / "tickets_export.json.gz", json.dumps(tickets_hd, ensure_ascii=False, indent=None))
    urows = [["email", "name", "organization", "role"]] + [[e, n, o, "end-user"] for e, (n, o) in sorted(users.items())]
    urows += [[a.email(date(2018, 1, 1)), a.name, "Brindlecove", "agent"] for a in agents]
    write_text(out / "support_helpdesk_2011-2019" / "users_export.csv", "\n".join(csv_line(x) for x in urows) + "\n")

    base = out / "jira_export_2026-10"
    for y, issues in sorted(sup_by_year.items()):
        write_text(base / f"SUP-{y}.json", json.dumps({"expand": "schema,names", "startAt": 0, "maxResults": len(issues),
                                                     "total": len(issues), "issues": issues}, ensure_ascii=False))

    # ---- incidents
    inc = []
    world.incidents = []
    d = date(2019, 7, 3)
    k = 0
    while d < AS_OF:
        d += timedelta(days=r.randint(3, 14))
        if d > AS_OF:
            break
        k += 1
        sev = r.choices(["Sev1", "Sev2", "Sev3"], [16, 34, 50])[0]
        root = r.choices(INC_ROOT, [30, 25, 15, 10, 8, 4, 8] if d.year != 2022 else [18, 34, 15, 10, 8, 5, 10])[0]
        dur = r.randint(8, 240) if sev != "Sev1" else r.randint(25, 300)
        world.incidents.append({"key": f"INC-{k}", "date": d, "sev": sev, "root": root, "minutes": dur})
        inc.append({"key": f"INC-{k}", "fields": {
            "summary": r.choice(["Elevated 5xx on API", "Mobile sync degraded", "Login failures", "Dashboard timeouts", "Email notifications delayed",
                                  "Invoices not generating", "Dispatch feed stalled", "Insights reports stale"]),
            "issuetype": {"name": "Incident"}, "status": {"name": "Resolved"},
            "priority": {"name": {"Sev1": "Highest", "Sev2": "High", "Sev3": "Medium"}[sev]},
            "customfield_10100": sev if r.random() > 0.05 else sev.upper(),
            "customfield_10101": r.choice(INC_ROOT_SPELLINGS[root]),      # Root Cause (free text!)
            "customfield_10102": dur,                                    # Customer impact minutes
            "created": f"{d}T{r.randint(0, 23):02d}:{r.randint(0, 59):02d}:00.000+0000",
            "description": f"Impact: {dur} min. See postmortem in Confluence (ENG space) if Sev1.",
        }})
    # keep the 2022 Sev1 answer unambiguous: break any tie with one more incident
    c22 = Counter(i["root"] for i in world.incidents if i["sev"] == "Sev1" and i["date"].year == 2022).most_common()
    if len(c22) > 1 and c22[0][1] == c22[1][1]:
        k += 1
        world.incidents.append({"key": f"INC-{k}", "date": date(2022, 12, 28), "sev": "Sev1", "root": c22[0][0], "minutes": 61})
        inc.append({"key": f"INC-{k}", "fields": {"summary": "Elevated 5xx on API", "issuetype": {"name": "Incident"}, "status": {"name": "Resolved"},
                    "priority": {"name": "Highest"}, "customfield_10100": "Sev1", "customfield_10101": INC_ROOT_SPELLINGS[c22[0][0]][-1],
                    "customfield_10102": 61, "created": "2022-12-28T03:12:00.000+0000", "description": "Impact: 61 min."}})
    write_text(base / "INC.json", json.dumps({"total": len(inc), "issues": inc}, ensure_ascii=False, indent=1))

    # ---- data team tickets incl. DATA-212 (the cents/dollars note)
    data = []
    for n in range(150, 320):
        created = rand_date(r, date(2017, 1, 1), AS_OF)
        data.append({"key": f"DATA-{n}", "fields": {"summary": r.choice(["Dashboard ARR off vs finance", "Dedupe accounts", "Backfill SFDC ids",
                                                                          "Add Kestrel to warehouse", "Fix churn report", "CSV import encoding",
                                                                          "Timezone of event timestamps", "Remove test accounts from metrics"]),
                                                    "status": {"name": r.choice(["Done", "Done", "Won't Do", "Backlog"])},
                                                    "created": f"{created}T15:00:00.000+0000", "comment": {"comments": []}}})
    data[62] = {"key": "DATA-212", "fields": {
        "summary": "Billing v3 invoice amounts look 100x too small for 2016 - Q1 2017",
        "status": {"name": "Won't Do"}, "created": "2017-06-02T14:11:09.000+0000",
        "description": "Revenue dashboard shows Jan 2016 at ~1% of what finance has. Investigating.",
        "comment": {"comments": [
            {"author": {"displayName": "Yuki Tanaka"}, "created": "2017-06-05T10:02:44.000+0000",
             "body": "Root cause: the ledger import (metadata.source = ledger_import_2017) wrote subtotal/amount_due in DOLLARS with 2 decimals. "
                     "Everything created natively in billing v3 is in CENTS (integer). Data dictionary says cents for all rows - it is wrong for the imported ones."},
            {"author": {"displayName": "Femi Adeyemi"}, "created": "2017-06-05T16:40:00.000+0000",
             "body": "Can we just rewrite them? Finance doesn't want history touched after close."},
            {"author": {"displayName": "Ines Delacroix"}, "created": "2017-06-06T09:15:12.000+0000",
             "body": "Correct - do not modify. Downstream: if source = ledger_import_2017 treat as dollars. Also note those invoices ALSO exist in the Ledger dump, don't double count."},
        ]}}}
    write_text(base / "DATA.json", json.dumps({"total": len(data), "issues": data}, ensure_ascii=False, indent=1))
    eng = [{"key": "ENG-1180", "fields": {"summary": "Switch app server log timestamps to UTC", "status": {"name": "Done"},
                                          "created": "2018-02-20T18:00:00.000+0000", "resolutiondate": "2018-03-12T14:30:00.000+0000",
                                          "description": "Logs are currently written in server local time (America/Chicago, Dallas colo) without an offset. "
                                                         "DST transitions produce duplicate/missing hours. Switching log4j pattern to ISO8601 UTC with 'Z'."}}]
    write_text(base / "ENG.json", json.dumps({"total": len(eng), "issues": eng}, ensure_ascii=False, indent=1))
    return {}
