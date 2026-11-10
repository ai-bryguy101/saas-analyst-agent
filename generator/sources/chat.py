"""Chat and text messages.

Renders:
  slack_export_2019-2026/                 Slack workspace export: users.json, channels.json, <channel>/<YYYY-MM-DD>.json
  teams_export_kestrel_2021-2023/         Microsoft Teams channel messages (Graph API JSON, HTML bodies)
  phone_backups/sms_renata_esposito_2023-01.xml   Android "SMS Backup & Restore" XML (epoch-ms dates, MMS parts)
  phone_backups/imessage_bkittredge_2017.csv      iMessage export from a departing rep's phone

Planted:
  GF16  an emergency credit approved in a Slack thread by a user only identifiable through users.json
  GF17  a UK author writes "3/4" for the Brindle Insights GA date (3 April, not March 4)
  GF18  a 12% discount agreed only by text message
"""
from __future__ import annotations

import base64
import json
from datetime import date, datetime, time, timedelta, timezone

from ..util import AS_OF, add_fact, rand_date, rng_for, uuid_like, write_text

RAW = "data/raw"
SLACK_START = date(2019, 7, 1)
CHANNELS = [
    ("general", "Company-wide announcements and work-based matters", SLACK_START, 2.0),
    ("sales", "Deals, pricing questions, wins", SLACK_START, 3.0),
    ("cs-escalations", "Customer escalations. Tag the CSM and the account.", SLACK_START, 2.5),
    ("eng-oncall", "Pages, incidents, deploys", SLACK_START, 4.0),
    ("finance-ops", "AR, billing questions, month-end", SLACK_START, 1.6),
    ("random", "Non-work banter", SLACK_START, 1.2),
    ("kestrel-integration", "Kestrel / Project Lantern integration", date(2021, 6, 1), 2.2),
    ("data-team", "Data requests and dashboards", date(2020, 2, 1), 1.4),
]
EMOJI = ["+1", "white_check_mark", "eyes", "raised_hands", "pray", "fire", "100", "thinking_face", "joy", "rotating_light"]


def slack_id(r, prefix, n=10):
    return prefix + "".join(r.choice("0123456789ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(n))


def ts_of(r, d: date, hour_lo=8, hour_hi=19):
    dt = datetime.combine(d, time(r.randint(hour_lo, hour_hi), r.randint(0, 59), r.randint(0, 59)), tzinfo=timezone.utc) + timedelta(hours=5)
    return f"{int(dt.timestamp())}.{r.randint(0, 999999):06d}"


def render(world, out, seed):
    r = rng_for(seed, "chat")
    P = {p.pid: p for p in world.people}
    g = world.golden
    base = out / "slack_export_2019-2026"

    # ---------------------------------------------------------------- users
    staff = [p for p in world.people if p.left is None or p.left >= SLACK_START]
    users, uid = [], {}
    for p in staff:
        u = slack_id(r, "U")
        uid[p.pid] = u
        handle = (p.first[0] + p.last).lower().replace(" ", "").replace("'", "")
        deleted = bool(p.left and p.left <= AS_OF)
        users.append({"id": u, "team_id": "T02BRNDLCV", "name": handle, "deleted": deleted, "color": f"{r.randint(0, 0xffffff):06x}",
                      "real_name": p.name, "tz": "Europe/London" if p.origin == "kestrel" else ("America/Winnipeg" if p.origin == "meridian" else "America/New_York"),
                      "profile": {"title": "" if deleted else p.title, "real_name": p.name,
                                  "display_name": r.choice([p.first, handle, p.first.lower(), ""]),
                                  "email": "" if deleted else p.email(AS_OF), "image_72": "https://avatars.slack-edge.example/72.png"},
                      "is_admin": p.pid in ("E001", "E010"), "is_bot": False, "is_restricted": False, "updated": 1600000000 + r.randint(0, 10 ** 8)})
    bots = {"jira": slack_id(r, "B"), "pagerduty": slack_id(r, "B"), "salesforce": slack_id(r, "B")}
    for name, b in bots.items():
        users.append({"id": b, "team_id": "T02BRNDLCV", "name": name, "deleted": False, "real_name": name.title(), "is_bot": True,
                      "profile": {"real_name": name.title(), "display_name": name, "bot_id": b}})
    write_text(base / "users.json", json.dumps(users, indent=4, ensure_ascii=False))

    chans = []
    for name, purpose, start, _ in CHANNELS:
        chans.append({"id": slack_id(r, "C"), "name": name, "created": int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp()),
                      "creator": uid["E010"], "is_archived": name == "kestrel-integration", "is_general": name == "general",
                      "members": sorted(r.sample(list(uid.values()), min(len(uid), r.randint(20, 120)))),
                      "topic": {"value": "", "creator": "", "last_set": 0}, "purpose": {"value": purpose, "creator": uid["E010"], "last_set": 0}})
    write_text(base / "channels.json", json.dumps(chans, indent=4))
    cid = {c["name"]: c["id"] for c in chans}

    def active_staff(d, dept=None):
        pool = [p for p in staff if p.hired <= d and (p.left is None or p.left >= d) and (dept is None or p.dept in dept)]
        return pool or staff

    custs = [c for c in world.customers if c.cloud_start]
    T = {
        "general": ["Reminder: all-hands Thursday at 1pm ET", "Welcome {p} to the {dept} team!", "Office wifi is back up",
                    "Benefits enrollment closes Friday", "Who left a lasagna in the 3rd floor fridge", "Q{q} kickoff deck is in the drive"],
        "sales": ["Closed {c}! {n} seats, {plan}", "Anyone have a reference customer in {ind}?", "{c} wants a discount, how far can I go?",
                  "Pricing question: does {plan} include Dispatch?", "Pipeline review moved to 3pm", "Lost {c} to Plinthwise on price"],
        "cs-escalations": ["{c} reporting sync failures since this morning, CSM is {p}", "{c} wants an exec call about the outage",
                           "Renewal risk: {c} unhappy with mobile app", "{c} asking for an SLA credit", "Can someone check {c}'s invoice? They say they were double billed"],
        "eng-oncall": ["deploy {v} to prod :rocket:", "PagerDuty: high error rate on api-gw", "replica lag on db-03 again", "rolling back {v}",
                       "postmortem doc for yesterday is up", "who owns the cron for nightly exports?", "cert renewal for *.brindlecove.example done"],
        "finance-ops": ["Month-end close starts tomorrow", "AR aging is up, {c} is 90+ days", "Can someone explain why invoices.csv amounts look 100x too big for 2016?",
                        "FX rates loaded for {m}", "Reminder: ledger_import rows are in dollars, not cents", "{c} paid by wire, applying now"],
        "random": ["anyone want coffee", "the parking lot is flooded lol", "happy friday", "who's watching the game tonight", "new dog pics in thread"],
        "kestrel-integration": ["Kestrel SSO cutover tonight", "Lantern dashboards look great on the demo tenant", "GBP invoices migrating next sprint",
                                "Xero export is the source of truth until April", "Who owns Lantern pricing?"],
        "data-team": ["Can I get ARR by region for the board?", "Don't use ARR__c from Salesforce, it's stale", "Dashboard refresh failed overnight",
                      "Events schema changed again (tenant_id vs account_id)", "Need churn list for {y}"],
    }

    msgs_by_day = {}   # (channel, date) -> list

    def post(ch, d, user_pid, text, ts=None, **extra):
        m = {"client_msg_id": uuid_like(r), "type": "message", "text": text, "user": uid.get(user_pid, user_pid), "ts": ts or ts_of(r, d), "team": "T02BRNDLCV"}
        m.update(extra)
        msgs_by_day.setdefault((ch, d), []).append(m)
        return m

    for name, _, start, rate in CHANNELS:
        end = date(2022, 12, 15) if name == "kestrel-integration" else AS_OF
        d = start
        while d <= end:
            if (d.weekday() < 5 and r.random() < 0.4) or r.random() < 0.02:
                for _ in range(1 + int(r.expovariate(1 / (rate * 1.5)))):
                    p = r.choice(active_staff(d))
                    c = r.choice(custs)
                    text = r.choice(T[name]).format(c=c.name, p=r.choice(active_staff(d)).name, n=r.randint(5, 400), plan=c.plan, ind=c.industry,
                                                    dept=p.dept, q=(d.month - 1) // 3 + 1, v=f"v{r.randint(5, 9)}.{r.randint(0, 40)}.{r.randint(0, 9)}",
                                                    m=d.strftime("%b %Y"), y=d.year - 1)
                    if r.random() < 0.15:
                        text = f"<@{uid[r.choice(active_staff(d)).pid]}> {text}"
                    extra = {}
                    if r.random() < 0.2:
                        extra["reactions"] = [{"name": r.choice(EMOJI), "users": [uid[r.choice(active_staff(d)).pid]], "count": 1}]
                    if r.random() < 0.05:
                        extra["edited"] = {"user": uid[p.pid], "ts": ts_of(r, d)}
                    if name == "eng-oncall" and r.random() < 0.3:
                        post(name, d, bots["pagerduty"], "", subtype="bot_message", bot_id=bots["pagerduty"], username="PagerDuty",
                             attachments=[{"fallback": "Triggered: api-gw 5xx > 2%", "color": "a6001a", "title": f"#{r.randint(10000, 99999)} Triggered: api-gw 5xx > 2%"}])
                        continue
                    post(name, d, p.pid, text, **extra)
                if r.random() < 0.01:
                    post(name, d, "USLACKBOT", "", subtype="channel_join")
            d += timedelta(days=1)

    # ---------------------------------------------------------------- GF16: credit approved in a thread
    pool = [c for c in custs if c.cloud_start < date(2020, 6, 1) and (not c.end or c.end > date(2021, 1, 1)) and c.currency == "USD"
            and c.seats(date(2020, 9, 17)) >= 60 and id(c) not in {id(x) for x in g.values()}]
    cust = pool[0]
    d16 = date(2020, 9, 17)
    seats = cust.seats(d16)
    monthly = round(seats * cust.unit_price(d16) * (1 - cust.discount), 2)
    csm = active_staff(d16, ("Customer Success",))[0]
    root = post("cs-escalations", d16, csm.pid,
                f"<!here> {cust.name} was down most of yesterday (sync outage). They want a one-month service credit, ${monthly:,.2f}. "
                f"Needs VP approval per policy. <@{uid['E005']}> <@{uid['E004']}>", ts=ts_of(r, d16, 14, 14))
    rep1 = post("cs-escalations", d16, "E005", "I'm out until Monday, can sales cover this one?", ts=ts_of(r, d16, 15, 15), thread_ts=root["ts"], parent_user_id=uid[csm.pid])
    rep2 = post("cs-escalations", d16, "E004", "approved. one month, apply as a credit note not a refund", ts=ts_of(r, d16, 16, 16), thread_ts=root["ts"], parent_user_id=uid[csm.pid])
    rep3 = post("cs-escalations", d16, csm.pid, "thanks! sending to finance-ops", ts=ts_of(r, d16, 17, 17), thread_ts=root["ts"], parent_user_id=uid[csm.pid])
    root.update({"thread_ts": root["ts"], "reply_count": 3, "reply_users_count": 2, "latest_reply": rep3["ts"],
                 "reply_users": [uid["E005"], uid["E004"]], "replies": [{"user": x["user"], "ts": x["ts"]} for x in (rep1, rep2, rep3)]})
    add_fact(world, {"id": "GF16", "difficulty": "medium", "kind": "chat-identity",
                     "question": f"Who approved the September 2020 service credit for {cust.name}, and for how much?",
                     "answer": f"Gideon Ashdown (VP Sales) approved a one-month credit of ${monthly:,.2f} in a #cs-escalations thread on {d16:%B %d, %Y}. "
                               f"The approval only shows the Slack user ID ({uid['E004']}); that account is deactivated, so the name comes from users.json.",
                     "trail": [f"{RAW}/slack_export_2019-2026/cs-escalations/{d16}.json (thread replies)", f"{RAW}/slack_export_2019-2026/users.json (deleted user)"],
                     "traps": ["The VP Customer Success was tagged first but declined", "Deactivated users have no title or email"],
                     "values": {"approver": "Gideon Ashdown", "slack_user_id": uid["E004"], "amount_usd": monthly, "customer": cust.name}})

    # ---------------------------------------------------------------- GF17 decoy in Slack (US reading of a UK date)
    post("kestrel-integration", date(2022, 2, 15), "E011", "so Lantern GA is March 4? need to update the price book before then")
    post("kestrel-integration", date(2022, 2, 15), "E020", "that's what I heard too, March 4")

    for (ch, d), ms in sorted(msgs_by_day.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        ms.sort(key=lambda m: float(m["ts"]))
        write_text(base / ch / f"{d}.json", json.dumps(ms, indent=4, ensure_ascii=False))

    # ---------------------------------------------------------------- Teams (Kestrel)
    tbase = out / "teams_export_kestrel_2021-2023"
    kes = [p for p in world.people if p.origin == "kestrel"] + [P["E019"], P["E006"], P["E020"]]
    gid = {p.pid: uuid_like(r) for p in kes}
    team_lines = ["Morning all, standup notes in the OneNote", "Xero export done for {m}", "VAT return figures attached",
                  "Can we move the Brindle sync to Thursday?", "Lantern demo went well with the board", "Leeds office closed Monday (bank holiday)",
                  "Who has the GBP price list?", "SSO migration is done for the UK tenants"]
    for chan, start, end in [("General", date(2021, 6, 1), date(2023, 5, 31)), ("Lantern Launch", date(2021, 11, 1), date(2022, 6, 30))]:
        msgs = []
        d = start
        while d <= end:
            if d.weekday() < 5 and r.random() < 0.5:
                p = r.choice(kes)
                dt = datetime.combine(d, time(r.randint(8, 17), r.randint(0, 59), r.randint(0, 59), r.randint(0, 999) * 1000))
                msgs.append({"id": str(int(dt.timestamp() * 1000)), "replyToId": None, "etag": str(int(dt.timestamp() * 1000)), "messageType": "message",
                             "createdDateTime": dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "lastModifiedDateTime": None, "deletedDateTime": None,
                             "subject": None, "importance": "normal", "locale": "en-us",
                             "from": {"application": None, "device": None, "user": {"id": gid[p.pid], "displayName": p.name, "userIdentityType": "aadUser"}},
                             "body": {"contentType": "html", "content": f"<p>{r.choice(team_lines).format(m=d.strftime('%B'))}</p>"},
                             "attachments": [], "mentions": [], "reactions": []})
            d += timedelta(days=1)
        if chan == "Lantern Launch":
            dt = datetime(2022, 2, 14, 10, 3, 21, 517000)
            msgs.append({"id": str(int(dt.timestamp() * 1000)), "replyToId": None, "messageType": "message", "createdDateTime": "2022-02-14T10:03:21.517Z",
                         "importance": "high", "locale": "en-gb", "subject": "Lantern GA date",
                         "from": {"user": {"id": gid["E019"], "displayName": "Bronwen Llewellyn", "userIdentityType": "aadUser"}},
                         "body": {"contentType": "html", "content": "<div><p>Right, it's locked: <strong>Lantern GA is 3/4</strong> &#127881; "
                                  "Release notes will go out on the day. Pricing stays at &pound;316/month for UK tenants.</p>"
                                  "<p><at id=\"0\">Tomasz Kowalski</at> please confirm the US side can flip the flag that morning.</p></div>"},
                         "attachments": [], "mentions": [{"id": 0, "mentionText": "Tomasz Kowalski", "mentioned": {"user": {"id": gid["E006"], "displayName": "Tomasz Kowalski"}}}],
                         "reactions": [{"reactionType": "like", "createdDateTime": "2022-02-14T10:05:00Z", "user": {"user": {"id": gid["E006"]}}}]})
        msgs.sort(key=lambda m: m["createdDateTime"])
        write_text(tbase / "Kestrel Analytics" / chan / "messages.json", json.dumps({"@odata.context": "https://graph.microsoft.example/v1.0/$metadata#teams('…')/channels('…')/messages",
                                                                                      "value": msgs}, indent=2, ensure_ascii=False))
    write_text(tbase / "README.txt", "Exported with the Graph API by IT on 2023-06-02 before the Kestrel tenant was shut down.\r\n"
                                     "Only the General and Lantern Launch channels were kept. Times are UTC.\r\n", encoding="cp1252")
    add_fact(world, {"id": "GF17", "difficulty": "medium", "kind": "date-locale",
                     "question": "When did Brindle Insights (Project Lantern) become generally available?",
                     "answer": "3 April 2022. The Kestrel managing director wrote 'Lantern GA is 3/4' in Teams, which is day/month in the UK. "
                               "US staff in Slack read it as March 4; the release notes PDF confirms April 3.",
                     "trail": [f"{RAW}/teams_export_kestrel_2021-2023/Kestrel Analytics/Lantern Launch/messages.json (2022-02-14, locale en-gb)",
                               f"{RAW}/product_docs/release_notes/Brindle_Insights_1.0_release_notes.pdf",
                               f"{RAW}/slack_export_2019-2026/kestrel-integration/2022-02-15.json (wrong: 'March 4')"],
                     "traps": ["US colleagues repeat 'March 4' in Slack"],
                     "values": {"ga_date": "2022-04-03"}})
    world.lantern_ga = date(2022, 4, 3)

    # ---------------------------------------------------------------- GF18: discount agreed by SMS (Android backup XML)
    c18 = g["sms_discount"]
    ct = c18.contacts[0]
    num = "+1" + "".join(ch for ch in ct.phone if ch.isdigit())
    sign = c18.cloud_start - timedelta(days=14)
    convo = [
        (sign - timedelta(days=6), 1, f"Hi Renata, {ct.first} here. Board meets Thursday. We're at {c18.seats0} seats but the {c18.plan} price is over budget."),
        (sign - timedelta(days=6), 2, "Understood. What number gets this done?"),
        (sign - timedelta(days=5), 1, "If you can do 12% off for the life of the contract we sign this week"),
        (sign - timedelta(days=5), 2, "I can do 12% off list as long as you sign by Friday. I'll have billing set it up, no need to redo the order form"),
        (sign - timedelta(days=5), 1, "Deal. Thanks!!"),
        (sign - timedelta(days=4), 2, "Great talking. Sending DocuSign now"),
    ]
    rows, k = [], 0
    filler_nums = ["+1614555" + f"{r.randint(100, 199):04d}"[-4:] for _ in range(12)]
    filler = ["running 5 late", "can you call me", "ok", "On site at the customer, will call after", "👍", "Did the PO come through?",
              "Lunch?", "Yes", "Sent", "call me when you can", "they signed!!", "Meeting moved to 2"]
    d = date(2022, 1, 3)
    entries = []
    while d <= date(2023, 1, 20):
        if r.random() < 0.6:
            entries.append((d, r.choice([1, 2]), r.choice(filler), r.choice(filler_nums), None))
        d += timedelta(days=1)
    for i, (d, typ, body) in enumerate(convo):
        entries.append((d, typ, body, num, ct.name, time(16, 2 + 9 * i, 17 + i)))
    entries = [e if len(e) == 6 else e + (None,) for e in entries]
    entries.sort(key=lambda e: (e[0], e[5] or time(0)))
    lines = []
    for d, typ, body, addr, name, fixed in entries:
        k += 1
        dt = datetime.combine(d, time(r.randint(8, 21), r.randint(0, 59), r.randint(0, 59)))
        if fixed:
            dt = datetime.combine(d, fixed)
        dst = 3 < d.month < 11 or (d.month == 3 and d.day >= 8 + (6 - date(d.year, 3, 8).weekday()) % 7) or (d.month == 11 and d.day < 1 + (6 - date(d.year, 11, 1).weekday()) % 7)
        ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000) + (4 if dst else 5) * 3600 * 1000
        esc = body.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace("'", "&apos;")
        esc = "".join(ch if ord(ch) < 0x10000 else "".join(f"&#{u};" for u in [0xD800 + ((ord(ch) - 0x10000) >> 10), 0xDC00 + ((ord(ch) - 0x10000) & 0x3FF)]) for ch in esc)
        lines.append(f'  <sms protocol="0" address="{addr}" date="{ms}" type="{typ}" subject="null" body="{esc}" toa="null" sc_toa="null" '
                     f'service_center="{"null" if typ == 2 else "+13123149810"}" read="1" status="-1" locked="0" date_sent="{ms - 2000 if typ == 1 else 0}" '
                     f'sub_id="1" readable_date="{dt:%b %d, %Y %I:%M:%S %p}" contact_name="{name or "(Unknown)"}" />')
    # one MMS (a photo of a whiteboard) to show the other record type
    png = base64.b64encode(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")).decode()
    lines.append(f'  <mms date="1661000000000" ct_t="application/vnd.wap.multipart.related" msg_box="1" address="{filler_nums[0]}" read="1" '
                 f'readable_date="Aug 20, 2022 8:53:20 AM" contact_name="(Unknown)">\n    <parts>\n'
                 f'      <part seq="0" ct="image/png" name="IMG_2231.png" chset="null" cl="IMG_2231.png" text="null" data="{png}" />\n'
                 f'      <part seq="1" ct="text/plain" name="null" chset="106" cl="txt000.txt" text="whiteboard from today" />\n    </parts>\n  </mms>')
    xml = ("<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n<!--File Created By SMS Backup &amp; Restore v10.16.004 on 20/01/2023 18:02:11-->\n"
           f'<smses count="{len(lines)}" backup_set="{uuid_like(r)}" backup_date="1674237731000" type="full">\n' + "\n".join(lines) + "\n</smses>\n")
    write_text(out / "phone_backups" / "sms_renata_esposito_2023-01.xml", xml)
    add_fact(world, {"id": "GF18", "difficulty": "hard", "kind": "text-message",
                     "question": f"Why is {c18.name} billed 12% below list price?",
                     "answer": f"Renata Esposito (VP Sales) agreed 12% off list for the life of the contract by text message with {ct.name} "
                               f"on {sign - timedelta(days=5):%B %d, %Y}, on condition they signed that week. The order form was never amended; "
                               f"the only record is Renata's phone backup.",
                     "trail": [f"{RAW}/phone_backups/sms_renata_esposito_2023-01.xml (date attribute is epoch milliseconds; type 1 = received, 2 = sent)",
                               f"{RAW}/billing_v3_2017-now/subscriptions.csv", f"{RAW}/crm_salesforce_export_2026-10/Account.csv"],
                     "traps": ["No contract document mentions the discount"],
                     "values": {"customer": c18.name, "discount_pct": 12, "agreed_on": str(sign - timedelta(days=5))}})

    # ---------------------------------------------------------------- iMessage export (CSV, decoy-rich)
    im = ["Message Date,Delivered Date,Read Date,Service,Type,Sender ID,Sender Name,Status,Replying to,Subject,Text,Attachment,Attachment type"]
    d = date(2017, 1, 3)
    while d <= date(2017, 6, 30):
        if r.random() < 0.5:
            c = r.choice(world.customers)
            t = r.choice(["Incoming", "Outgoing"])
            im.append(",".join([f"{d} {r.randint(8, 20):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}", "", "", r.choice(["iMessage", "SMS"]), t,
                                "" if t == "Outgoing" else f"+1513555{r.randint(100, 199):04d}"[-12:], "" if t == "Outgoing" else c.contacts[0].name if c.contacts else "",
                                "Read" if t == "Incoming" else "Delivered", "", "",
                                '"' + r.choice(["Can we push the call to 3?", f"Got the renewal for {c.name}?", "Thanks Bryce", "Sending the PO today", "Will do"]).replace('"', "'") + '"',
                                "", ""]))
        d += timedelta(days=1)
    write_text(out / "phone_backups" / "imessage_bkittredge_2017.csv", "\n".join(im) + "\n", bom=True, newline="\r\n")
    return {}
