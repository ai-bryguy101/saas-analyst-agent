"""Phone system: voicemail transcripts, call detail records, recorded sales calls.

Renders:
  phone_system/extensions.csv                     extension -> person (as of 2026, people who left are 'VACANT')
  phone_system/extensions_2020-01-15.csv          older snapshot found on a share
  phone_system/cdr/cdr_YYYY.csv                   CUCM-style call detail records, epoch seconds, UTC
  voicemail_transcripts/VM_<ext>_<YYYYMMDD-HHMMSS>.txt   speech-to-text voicemail, low confidence, local time
  sales_calls_gong/<call-id>.json                 recorded call metadata + diarised transcript (2023+)

Planted:
  GF19  a customer's first cancellation request exists only as a voicemail to a CSM
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from ..util import AS_OF, add_fact, rand_date, rng_for, uuid_like, write_text

RAW = "data/raw"
ET_OFF = {True: 4, False: 5}   # crude EDT/EST offset by month, good enough for a phone system


def is_dst(d: date) -> bool:
    return 3 < d.month < 11 or (d.month == 3 and d.day >= 10) or (d.month == 11 and d.day < 3)


def asr_garble(r, text):
    subs = {"Brindlecove": r.choice(["Brindle cove", "Brendel cove", "brindle code"]), "renewal": r.choice(["renewal", "renew all"]),
            "fifteen": r.choice(["fifteen", "fifty"]), "thirty": r.choice(["thirty", "thirteen"]), "cancel": r.choice(["cancel", "cancel", "can sell"])}
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def render(world, out, seed):
    r = rng_for(seed, "voice")
    base = out / "phone_system"
    people = [p for p in world.people if p.dept in ("Customer Success", "Support", "Sales", "Finance", "Executive", "Operations")]
    ext = {}
    used = set()
    for p in people:
        e = r.randint(2100, 2899)
        while e in used:
            e += 1
        used.add(e)
        ext[p.pid] = e
    rows = ["Extension,Display Name,Department,Device,Voicemail"]
    rows_old = ["EXT;NAME;DEPT"]
    for p in sorted(people, key=lambda p: ext[p.pid]):
        gone = p.left and p.left <= AS_OF
        rows.append(f"{ext[p.pid]},{'VACANT' if gone else p.name},{'' if gone else p.dept},SEP{r.randint(0, 16 ** 12 - 1):012X},{'N' if gone else 'Y'}")
        if p.hired <= date(2020, 1, 15) and (not p.left or p.left >= date(2020, 1, 15)):
            rows_old.append(f"{ext[p.pid]};{p.last.upper()}, {p.first};{p.dept}")
    write_text(base / "extensions.csv", "\n".join(rows) + "\n")
    write_text(base / "extensions_2020-01-15.csv", "\n".join(rows_old) + "\n", encoding="cp1252", newline="\r\n")

    # ---------------------------------------------------------------- GF19 target
    pool = [c for c in world.customers if c.cloud_start and c.end and date(2021, 3, 1) <= c.end <= date(2024, 12, 31) and c.currency == "USD"
            and c.csm and c.contacts and id(c) not in {id(x) for x in world.golden.values()} and not c.deleted_in_crm]
    pool.sort(key=lambda c: (-c.seats(c.end), c.name))
    tgt = pool[0]
    csm = next(p for p in world.people if p.pid == tgt.csm)
    if csm.pid not in ext:
        ext[csm.pid] = 2999
    caller = tgt.contacts[0]
    caller_num = "1" + "".join(ch for ch in caller.phone if ch.isdigit())
    vm_day = tgt.end - timedelta(days=74)
    while vm_day.weekday() >= 5:
        vm_day -= timedelta(days=1)
    vm_local = datetime.combine(vm_day, time(17, 48, 12))
    vm_utc = vm_local + timedelta(hours=ET_OFF[is_dst(vm_day)])

    # ---------------------------------------------------------------- CDRs + voicemails
    cdr_hdr = ("cdrRecordType,globalCallID_callId,dateTimeOrigination,callingPartyNumber,originalCalledPartyNumber,finalCalledPartyNumber,"
               "dateTimeConnect,dateTimeDisconnect,duration,origDeviceName,destDeviceName,lastRedirectRedirectReason")
    by_year = {}
    vms = []
    cid = 100000
    d = date(2018, 1, 2)
    while d <= AS_OF:
        if d.weekday() < 5:
            for _ in range(r.randint(25, 60)):
                cid += 1
                p = r.choice(people)
                if p.hired > d or (p.left and p.left < d):
                    continue
                t0 = datetime.combine(d, time(r.randint(12, 23), r.randint(0, 59), r.randint(0, 59)), tzinfo=timezone.utc)
                c = r.choice(world.customers)
                num = "1" + "".join(ch for ch in (c.contacts[0].phone if c.contacts else "(937) 555-0100") if ch.isdigit())
                voicemail = r.random() < 0.12
                dur = 0 if voicemail and r.random() < 0.5 else r.randint(5, 2400)
                ep = int(t0.timestamp())
                by_year.setdefault(d.year, []).append(f"1,{cid},{ep},{num},{ext[p.pid]},{'' if not voicemail else 8000},{0 if voicemail else ep + 7},"
                                                      f"{ep + dur + 7},{dur},SIP_TRUNK_1,{'CiscoUM1-VI3' if voicemail else 'SEP' + str(ext[p.pid])},"
                                                      f"{2 if voicemail else 0}")
                if voicemail and r.random() < 0.3 and len(vms) < 900:
                    local = t0.replace(tzinfo=None) - timedelta(hours=ET_OFF[is_dst(d)])
                    msg = r.choice(["Hi it's {n} from {c}, just calling about our invoice, it looks like we got charged twice, give me a call back",
                                    "Hey this is {n}, calling about the renewal, can you send over the quote again",
                                    "Hi, {n} with {c}, the mobile app isn't syncing for our techs since this morning",
                                    "Yeah hi it's {n}, just returning your call, I'm around after three",
                                    "This is {n} at {c}, we need to add fifteen seats before the first of the month"])
                    vms.append((ext[p.pid], local, num, asr_garble(r, msg.format(n=c.contacts[0].first if c.contacts else "Mike", c=c.name)), dur or r.randint(9, 70)))
        if d == vm_day:
            cid += 1
            ep = int(vm_utc.replace(tzinfo=timezone.utc).timestamp())
            by_year.setdefault(d.year, []).append(f"1,{cid},{ep},{caller_num},{ext[csm.pid]},8000,0,{ep + 71},0,SIP_TRUNK_1,CiscoUM1-VI3,2")
        d += timedelta(days=1)
    for y, rows in by_year.items():
        write_text(base / "cdr" / f"cdr_{y}.csv", cdr_hdr + "\n" + "\n".join(rows) + "\n")

    first = tgt.name.split()[0]
    vm_text = (f"Hi {csm.first}, it's {caller.first} from {first}, um, {asr_garble(r, 'Brindlecove')} account. Look I wanted to let you know before the "
               f"renewal paperwork comes, we've decided we're going to can sell at the end of the term. Budget got cut and, uh, we're consolidating "
               f"on one vendor. I'll put it in writing but wanted you to hear it from me. Call me back, thanks.")
    vms.append((ext[csm.pid], vm_local, caller_num, vm_text, 71))
    for e, local, num, text, dur in vms:
        conf = round(r.uniform(0.41, 0.93), 2)
        if (e, local) == (ext[csm.pid], vm_local):
            conf = 0.57
        body = (f"Unity Connection - Voice Message Transcription\r\nMailbox: {e}\r\nReceived: {local:%m/%d/%Y %I:%M %p}\r\n"
                f"From: {num if r.random() > 0.1 else 'Unknown'}\r\nLength: 0:{dur // 60:02d}:{dur % 60:02d}\r\n"
                f"Transcription confidence: {conf}\r\n\r\n{text}\r\n\r\n-- This transcription was generated automatically and may contain errors. --\r\n")
        if (e, local) == (ext[csm.pid], vm_local):
            body = body.replace(f"From: Unknown", f"From: {num}")
        write_text(out / "voicemail_transcripts" / f"VM_{e}_{local:%Y%m%d-%H%M%S}.txt", body, encoding="cp1252")

    add_fact(world, {"id": "GF19", "difficulty": "hard", "kind": "voicemail",
                     "question": f"When did {tgt.name} first tell Brindlecove they intended to cancel?",
                     "answer": f"{vm_local:%B %d, %Y} at {vm_local:%-I:%M %p} Eastern, in a voicemail from {caller.name} to their CSM {csm.name} "
                               f"(extension {ext[csm.pid]}). That is 74 days before the {tgt.end} churn date in the CRM. The transcript garbles 'cancel' "
                               f"and the company name; the caller is identified by matching the phone number to the CRM contact.",
                     "trail": [f"{RAW}/voicemail_transcripts/VM_{ext[csm.pid]}_{vm_local:%Y%m%d-%H%M%S}.txt",
                               f"{RAW}/phone_system/cdr/cdr_{vm_day.year}.csv (dateTimeOrigination is UTC epoch seconds)",
                               f"{RAW}/phone_system/extensions.csv", f"{RAW}/crm_salesforce_export_2026-10/Contact.csv (phone number)"],
                     "traps": ["Transcript says 'can sell'", "The CRM only records the churn date, not the first notice"],
                     "values": {"customer": tgt.name, "voicemail_local": vm_local.isoformat(), "csm": csm.name, "days_before_churn": 74}})

    # ---------------------------------------------------------------- recorded sales calls (Gong-style)
    reps = [p for p in world.people if p.dept == "Sales"]
    lines_rep = ["Thanks for making the time today.", "Can you walk me through how your techs log work today?", "We can do a pilot with ten seats.",
                 "Pricing for Pro is per seat per month.", "Dispatch is an add-on, it's nine dollars a seat.", "I'll send a recap after this call."]
    lines_cust = ["We're on spreadsheets and a whiteboard, honestly.", "What does onboarding look like?", "Our budget cycle starts in July.",
                  "We looked at Plinthwise too.", "Does it work offline? Half our sites have no signal.", "I need to loop in our controller."]
    for k in range(160):
        d = rand_date(r, date(2023, 1, 9), AS_OF)
        rep = r.choice([p for p in reps if p.hired <= d and (not p.left or p.left >= d)] or reps)
        pr = r.choice(world.prospects) if world.prospects else None
        comp = pr["name"] if pr else r.choice(world.customers).name
        cid = uuid_like(r)
        t, sentences = 0, []
        for i in range(r.randint(12, 40)):
            who = i % 2
            txt = r.choice(lines_rep if who == 0 else lines_cust)
            dur = 1000 * max(2, len(txt) // 12)
            sentences.append({"speakerId": "s0" if who == 0 else "s1", "topic": None, "sentences": [{"start": t, "end": t + dur, "text": txt}]})
            t += dur + r.randint(200, 3000)
        doc = {"metaData": {"id": cid, "url": f"https://app.gong.example/call?id={cid}", "title": f"{comp} | Brindlecove Discovery",
                            "scheduled": f"{d}T{r.randint(13, 21):02d}:00:00Z", "started": f"{d}T{r.randint(13, 21):02d}:0{r.randint(0, 9)}:12Z",
                            "duration": t // 1000, "primaryUserId": rep.pid, "direction": "Conference", "system": "Zoom", "scope": "External",
                            "media": "Video", "language": "eng"},
               "parties": [{"id": "s0", "name": rep.name, "affiliation": "Internal", "emailAddress": rep.email(d)},
                           {"id": "s1", "name": None, "affiliation": "External", "emailAddress": None}],
               "transcript": sentences}
        write_text(out / "sales_calls_gong" / f"{d}_{cid[:8]}.json", json.dumps(doc, indent=1))
    return {}
