"""Personal information manager exports: calendars (.ics) and address books (.vcf).

Renders:
  calendars/pricing_committee_export_2024-06-30.ics   one recurring series with EXDATE, cancelled and moved instances
  calendars/lwhitlock_calendar_2023.ics                the CFO's copy of the same series, exported before the exceptions synced
  calendars/holidays_brindlecove_2019-2026.ics         all-day events, VALUE=DATE
  calendars/cs_team_2024.ics                           assorted one-offs, some floating times, some with TZID
  contacts/resp_phone_backup_2024-04.vcf               vCard 2.1 with QUOTED-PRINTABLE and CHARSET params, folded lines
  contacts/outlook_export_2019.vcf                     vCard 3.0, one card per contact

Planted:
  GF22  how many pricing-committee meetings were actually held in 2023 (needs RRULE expansion minus exceptions)
  GF23  the current mobile number for Calloway's facilities director exists only in a phone's vCard backup
"""
from __future__ import annotations

import quopri
from datetime import date, datetime, timedelta

from ..util import AS_OF, add_fact, rng_for, uuid_like, write_text

RAW = "data/raw"

VTZ_NY = """BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""

# Outlook writes its own name for Eastern time, which most parsers do not recognise
VTZ_OUTLOOK = VTZ_NY.replace("TZID:America/New_York", "TZID:Eastern Standard Time")


def fold(line: str, width: int = 75) -> str:
    """RFC 5545 line folding: CRLF + single space."""
    out, b = [], line
    while len(b) > width:
        out.append(b[:width])
        b = " " + b[width:]
    out.append(b)
    return "\r\n".join(out)


def ics(lines) -> str:
    return "\r\n".join(fold(l) for l in "\n".join(lines).split("\n")) + "\r\n"


def nth_weekday(y, m, weekday, n):
    d = date(y, m, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def render(world, out, seed):
    r = rng_for(seed, "pim")
    cal = out / "calendars"
    people = {p.pid: p for p in world.people}

    # ------------------------------------------------------------- GF22 recurring series
    # Pricing committee: first Tuesday of each month, 10:00-11:00 New York time, Sep 2022 to Jun 2024.
    uid = f"{uuid_like(r).upper()}@brindlecove.example"
    series_start = date(2022, 9, 6)
    occ = []
    y, m = 2022, 9
    while (y, m) <= (2024, 6):
        occ.append(nth_weekday(y, m, 1, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    occ_2023 = [d for d in occ if d.year == 2023]
    exdates = [date(2023, 1, 3), date(2023, 7, 4)]           # New Year week and Independence Day: removed from the series
    cancelled = date(2023, 11, 7)                              # cancelled instance (STATUS:CANCELLED override)
    moved_from, moved_to = date(2023, 4, 4), date(2023, 4, 6)  # moved to Thursday, still held
    held_2023 = [d for d in occ_2023 if d not in exdates and d != cancelled]
    held_2023 = sorted([moved_to if d == moved_from else d for d in held_2023])
    organizer = people["E003"]
    attendees = [people[p] for p in ("E003", "E007", "E005", "E011", "E012")]

    def att_lines(on):
        return [f"ATTENDEE;CN={p.name};ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED:mailto:{p.email(on)}" for p in attendees]

    ev = ["BEGIN:VCALENDAR", "PRODID:-//Microsoft Corporation//Outlook 16.0 MIMEDIR//EN", "VERSION:2.0", "METHOD:PUBLISH",
          "X-WR-CALNAME:Pricing Committee", VTZ_OUTLOOK,
          "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20240630T221500Z",
          f"DTSTART;TZID=Eastern Standard Time:{series_start:%Y%m%d}T100000",
          f"DTEND;TZID=Eastern Standard Time:{series_start:%Y%m%d}T110000",
          "RRULE:FREQ=MONTHLY;UNTIL=20240630T235959Z;BYDAY=1TU",
          "EXDATE;TZID=Eastern Standard Time:" + ",".join(f"{d:%Y%m%d}T100000" for d in exdates),
          "SUMMARY:Pricing Committee (monthly)", "LOCATION:Dayton HQ - Mad River room / Teams",
          f"ORGANIZER;CN={organizer.name}:mailto:{organizer.email(series_start)}"] + att_lines(series_start) + [
          "DESCRIPTION:Standing review of discount requests over 15%\\, price book changes and renewals at risk.\\n"
          "Pre-read goes out the Friday before.", "SEQUENCE:4", "STATUS:CONFIRMED", "TRANSP:OPAQUE",
          "X-MICROSOFT-CDO-BUSYSTATUS:BUSY", "END:VEVENT",
          # moved instance
          "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20230329T141200Z",
          f"RECURRENCE-ID;TZID=Eastern Standard Time:{moved_from:%Y%m%d}T100000",
          f"DTSTART;TZID=Eastern Standard Time:{moved_to:%Y%m%d}T140000",
          f"DTEND;TZID=Eastern Standard Time:{moved_to:%Y%m%d}T150000",
          "SUMMARY:Pricing Committee (monthly) - MOVED to Thu", "SEQUENCE:5", "STATUS:CONFIRMED", "END:VEVENT",
          # cancelled instance
          "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20231106T171900Z",
          f"RECURRENCE-ID;TZID=Eastern Standard Time:{cancelled:%Y%m%d}T100000",
          f"DTSTART;TZID=Eastern Standard Time:{cancelled:%Y%m%d}T100000",
          f"DTEND;TZID=Eastern Standard Time:{cancelled:%Y%m%d}T110000",
          "SUMMARY:Canceled: Pricing Committee (monthly)", "SEQUENCE:6", "STATUS:CANCELLED",
          "DESCRIPTION:Cancelling this one - most of us are at the Columbus user conference. See you in December.",
          "END:VEVENT", "END:VCALENDAR"]
    write_text(cal / "pricing_committee_export_2024-06-30.ics", ics(ev))

    # the CFO's personal export from early 2023: same series, no exceptions synced yet, other meetings mixed in
    cfo = ["BEGIN:VCALENDAR", "PRODID:-//Apple Inc.//macOS 13.2//EN", "VERSION:2.0", "CALSCALE:GREGORIAN", VTZ_NY,
           "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20230118T090000Z",
           f"DTSTART;TZID=America/New_York:{series_start:%Y%m%d}T100000",
           f"DTEND;TZID=America/New_York:{series_start:%Y%m%d}T110000",
           "RRULE:FREQ=MONTHLY;BYDAY=1TU", "SUMMARY:Pricing Committee (monthly)", "END:VEVENT"]
    for k in range(40):
        d = date(2023, 1, 2) + timedelta(days=r.randint(0, 360))
        if d.weekday() >= 5:
            continue
        h = r.randint(8, 16)
        cfo += ["BEGIN:VEVENT", f"UID:{uuid_like(r)}", "DTSTAMP:20230118T090000Z",
                f"DTSTART;TZID=America/New_York:{d:%Y%m%d}T{h:02d}0000", f"DTEND;TZID=America/New_York:{d:%Y%m%d}T{h:02d}3000",
                f"SUMMARY:{r.choice(['1:1 Ines', 'Board prep', 'Audit walkthrough', 'Bank call', 'FP&A sync', 'Hold - focus'])}",
                "END:VEVENT"]
    cfo.append("END:VCALENDAR")
    write_text(cal / "lwhitlock_calendar_2023.ics", ics(cfo))

    hol = ["BEGIN:VCALENDAR", "PRODID:-//Brindlecove IT//Holiday feed//EN", "VERSION:2.0", "X-WR-CALNAME:Company holidays"]
    for yr in range(2019, 2027):
        for name, d in [("New Year's Day", date(yr, 1, 1)), ("Memorial Day", date(yr, 5, 31) - timedelta(days=date(yr, 5, 31).weekday())),
                        ("Independence Day", date(yr, 7, 4)), ("Labor Day", nth_weekday(yr, 9, 0, 1)),
                        ("Thanksgiving", nth_weekday(yr, 11, 3, 4)), ("Day after Thanksgiving", nth_weekday(yr, 11, 3, 4) + timedelta(days=1)),
                        ("Christmas Day", date(yr, 12, 25))]:
            hol += ["BEGIN:VEVENT", f"UID:hol-{d:%Y%m%d}@brindlecove.example", "DTSTAMP:20190102T000000Z",
                    f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}", f"SUMMARY:{name} (office closed)",
                    "TRANSP:TRANSPARENT", "END:VEVENT"]
    hol.append("END:VCALENDAR")
    write_text(cal / "holidays_brindlecove_2019-2026.ics", ics(hol))

    cs = ["BEGIN:VCALENDAR", "PRODID:-//Google Inc//Google Calendar 70.9054//EN", "VERSION:2.0", "X-WR-TIMEZONE:America/New_York"]
    cust = [c for c in world.customers if c.active(date(2024, 6, 1)) and c.cloud_start]
    for k in range(180):
        d = date(2024, 1, 2) + timedelta(days=r.randint(0, 360))
        c = r.choice(cust)
        h = r.randint(13, 21)
        floating = r.random() < 0.15
        start = f"DTSTART:{d:%Y%m%d}T{h:02d}0000" if floating else f"DTSTART:{d:%Y%m%d}T{h:02d}0000Z"
        cs += ["BEGIN:VEVENT", f"UID:{uuid_like(r)}@calendar.example", "DTSTAMP:20241231T000000Z", start,
               f"DURATION:PT{r.choice([30, 45, 60])}M", f"SUMMARY:{r.choice(['QBR', 'Renewal call', 'Onboarding', 'Check-in'])} - {c.name}",
               "END:VEVENT"]
    cs.append("END:VCALENDAR")
    write_text(cal / "cs_team_2024.ics", ics(cs))

    add_fact(world, {"id": "GF22", "difficulty": "hard", "kind": "calendar recurrence",
                     "question": "How many Pricing Committee meetings were actually held in 2023?",
                     "answer": f"{len(held_2023)}. The series repeats on the first Tuesday of every month (12 in 2023), but two dates are "
                               f"removed with EXDATE ({', '.join(str(d) for d in exdates)}), the {cancelled} meeting is a STATUS:CANCELLED "
                               f"override, and the {moved_from} meeting was moved to {moved_to} (still held).",
                     "trail": [f"{RAW}/calendars/pricing_committee_export_2024-06-30.ics"],
                     "traps": ["The CFO's 2023 export shows the same series with no exceptions (12 meetings)",
                               "TZID 'Eastern Standard Time' is an Outlook name, not an IANA zone",
                               "The moved instance has a new DTSTART but still counts as held"],
                     "values": {"held_2023": len(held_2023), "held_dates": [str(d) for d in held_2023]}})

    # ------------------------------------------------------------- vCards
    calloway = world.golden["calloway"]
    tv = calloway.contacts[0]
    new_mobile = "(513) 555-0188"
    renata = people["E007"]

    def qp(s):
        return quopri.encodestring(s.encode("cp1252"), quotetabs=False).decode("ascii").replace("\n", "")

    cards21 = []
    sample = [c for c in world.customers if c.contacts and c.active(date(2024, 3, 1)) and c.cloud_start]
    sample = r.sample(sample, 140)
    for c in sample:
        ct = c.contacts[0]
        note = r.choice(["", "", "met at FieldOps Expo", "prefers text", "assistant: ask for the controller", "Café meeting 2nd Thu"])
        lines = ["BEGIN:VCARD", "VERSION:2.1", f"N:{ct.last};{ct.first};;;", f"FN:{ct.name}",
                 f"ORG:{c.name}", f"TITLE:{ct.title}", f"TEL;WORK;VOICE:{ct.phone}", f"EMAIL;PREF;INTERNET:{ct.email}"]
        if note and any(ord(ch) > 127 for ch in note):
            lines.append(f"NOTE;CHARSET=WINDOWS-1252;ENCODING=QUOTED-PRINTABLE:{qp(note)}")
        elif note:
            lines.append(f"NOTE:{note}")
        lines += [f"REV:{2019 + r.randint(0, 4)}{r.randint(1, 12):02d}{r.randint(1, 28):02d}T120000Z", "END:VCARD"]
        cards21.append("\r\n".join(lines))
    tv_note = "New cell as of 3/14/24 - old 0142 number is the front desk now, don't use."
    cards21.insert(r.randint(10, 120), "\r\n".join([
        "BEGIN:VCARD", "VERSION:2.1", f"N:{tv.last};{tv.first};;;", f"FN:{tv.name}", f"ORG:{calloway.name}", f"TITLE:{tv.title}",
        f"TEL;CELL;PREF:{new_mobile}", f"TEL;WORK;VOICE:{tv.phone}", f"EMAIL;PREF;INTERNET:{tv.email}",
        f"NOTE;CHARSET=WINDOWS-1252;ENCODING=QUOTED-PRINTABLE:{qp(tv_note + ' — R.E.')}", "REV:20240314T163000Z", "END:VCARD"]))
    write_text(out / "contacts" / "resp_phone_backup_2024-04.vcf", "\r\n".join(cards21) + "\r\n", encoding="cp1252")

    cards30 = []
    old = [c for c in world.customers if c.contacts and c.active(date(2019, 6, 1))]
    for c in r.sample(old, 220) + [calloway]:
        for ct in c.contacts[:2]:
            cards30.append("\r\n".join([
                "BEGIN:VCARD", "VERSION:3.0", f"N:{ct.last};{ct.first};;;", f"FN:{ct.name}", f"ORG:{c.name.replace(',', chr(92) + ',')}",
                f"TITLE:{ct.title}", f"TEL;TYPE=WORK,VOICE:{ct.phone}", f"EMAIL;TYPE=INTERNET,PREF:{ct.email}",
                f"ADR;TYPE=WORK:;;;{c.city};{c.region};;{'USA' if c.country == 'US' else c.country}", "END:VCARD"]))
    write_text(out / "contacts" / "outlook_export_2019.vcf", "\r\n".join(cards30) + "\r\n")

    add_fact(world, {"id": "GF23", "difficulty": "medium", "kind": "contact card",
                     "question": f"What is the best phone number to reach {tv.name}, the facilities director at {calloway.name}?",
                     "answer": f"The mobile number {new_mobile}. A vCard in {renata.name}'s March 2024 phone backup says the old {tv.phone} number "
                               f"now rings the front desk. The CRM and the 2019 Outlook export still have only {tv.phone}.",
                     "trail": [f"{RAW}/contacts/resp_phone_backup_2024-04.vcf (NOTE is QUOTED-PRINTABLE, cp1252)",
                               f"{RAW}/crm_salesforce_export_2026-10/Contact.csv"],
                     "traps": ["CRM Contact.csv has only the old number", "The NOTE field must be decoded from quoted-printable"],
                     "values": {"phone": new_mobile, "old_phone": tv.phone}})
    return {}
