"""Email archives: mbox exports by mailbox, plus loose .eml files from a legal hold.

Real-world mess on purpose: FW:/RE: chains with quoted history, top-posting,
disclaimers, encoded-word headers, quoted-printable bodies, Latin-1 parts,
auto-replies, and newsletters mixed into the same mailbox.
"""
from __future__ import annotations

import mailbox
from datetime import date, datetime, timedelta
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime
from datetime import timezone


def et(x: datetime) -> datetime:
    """Rough US Eastern offset (EDT Apr-Oct) so output never depends on the machine's TZ."""
    return x.replace(tzinfo=timezone(timedelta(hours=-4 if 4 <= x.month <= 10 else -5)))

from ..util import AS_OF, rand_date, rng_for
from ..world import COMPETITORS, ERA

DISCLAIMER = ("\n\n--\nCONFIDENTIALITY NOTICE: This e-mail and any attachments are for the exclusive and confidential use of the "
              "intended recipient. If you are not the intended recipient, please do not read, distribute or take action in reliance "
              "upon this message.")
DISCLAIMER_OLD = "\n\n___________________________________\nBrindle Data Systems, Inc. | 1 Riverside Plz | Dayton OH\n"


def quote(text):
    return "\n".join("> " + ln if ln else ">" for ln in text.split("\n"))


def sig(p, d):
    company = "Brindle Data Systems" if d < ERA["saas_launch"] else "Brindlecove Software"
    return f"\n\n{p.first}\n{p.name} | {p.title}\n{company}\n"


def mk(r, frm, to, subject, body, d: datetime, cc=None, reply_to_id=None, charset="utf-8", attach=None):
    msg = MIMEMultipart(boundary=f"----=_NextPart_{r.randint(10**11, 10**12 - 1):x}") if attach else MIMEText(body, "plain", charset)
    if attach:
        msg.attach(MIMEText(body, "plain", charset))
        fname, data, sub = attach
        part = MIMEApplication(data, _subtype=sub)
        part.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(part)
    msg["From"] = frm
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = Header(subject, "utf-8").encode() if any(ord(c) > 127 for c in subject) else subject
    msg["Date"] = format_datetime(d)
    # built by hand: email.utils.make_msgid mixes in the clock and PID, which breaks reproducibility
    mid = f"<{int(d.timestamp() * 100)}.{r.randint(100, 9999)}.{r.randint(10**15, 10**19)}@{'mail.brindlecove.example' if d.year >= 2011 else 'exch01.brindledata.local'}>"
    msg["Message-ID"] = mid
    if reply_to_id:
        msg["In-Reply-To"] = reply_to_id
        msg["References"] = reply_to_id
    msg["X-Mailer"] = r.choice(["Microsoft Outlook 14.0", "Apple Mail (2.3445)", "Microsoft Outlook 16.0", "iPhone Mail (16A366)"]) if d.year > 2010 else "Microsoft Outlook, Build 10.0.6626"
    return msg, mid


def dt(d: date, r, h0=8, h1=19):
    return et(datetime(d.year, d.month, d.day, r.randint(h0, h1), r.randint(0, 59), r.randint(0, 59)))


def add(box, msg, d):
    m = mailbox.mboxMessage(msg)
    frm = msg["From"].split("<")[-1].strip(">") if "<" in msg["From"] else msg["From"]
    m.set_from(frm, d.timetuple())
    box.add(m)


def render(world, out, seed):
    r = rng_for(seed, "email")
    base = out / "email_archive"
    base.mkdir(parents=True, exist_ok=True)
    P = {p.pid: p for p in world.people}
    g = world.golden

    def addr(p, d):
        return f"{p.name} <{p.email(d)}>"

    boxes = {}

    def box(name):
        if name not in boxes:
            path = base / f"{name}.mbox"
            if path.exists():
                path.unlink()
            boxes[name] = mailbox.mbox(str(path), create=True)
        return boxes[name]

    # ------------------------------------------------------------- GF01 Harbortown churn thread (Aug 2016)
    hb = g["harbortown"]
    lionel = hb.contacts[0]
    bryce, gideon, priya, sofia = P["E013"], P["E004"], P["E005"], P["E014"]
    d1 = et(datetime(2016, 8, 1, 9, 12, 0))
    body1 = (f"Bryce,\n\nPer section 9.2 of our agreement, please accept this as Harbortown Property Group's 30-day notice that we will not "
             f"renew our Brindle Ops Cloud subscription when the current term ends on August 31, 2016.\n\n"
             f"Honestly this was not an easy call. After the two outages in March (the 8th and the 22nd) our board lost confidence, and "
             f"Plinthwise came in about 30% under your renewal quote with the same mobile features. We signed with them last week.\n\n"
             f"Please send instructions for exporting our work order history.\n\nRegards,\nLionel Ashby\nVP Operations, Harbortown Property Group")
    m1, id1 = mk(r, f"Lionel Ashby <{lionel.email}>", [addr(bryce, d1.date())], "Notice of non-renewal - Harbortown", body1, d1)
    d2 = d1 + timedelta(hours=3, minutes=7)
    body2 = (f"Gideon / Priya - see below. Lost Harbortown. Outages + price, Plinthwise. 120+ seats.\n\nI tried. Can we do anything?"
             + sig(bryce, d2.date()) + "\n-----Original Message-----\nFrom: Lionel Ashby\nSent: Monday, August 01, 2016 9:12 AM\n"
             f"To: Bryce Kittredge\nSubject: Notice of non-renewal - Harbortown\n\n" + body1)
    m2, id2 = mk(r, addr(bryce, d2.date()), [addr(gideon, d2.date()), addr(priya, d2.date())], "FW: Notice of non-renewal - Harbortown", body2, d2,
                 cc=[addr(sofia, d2.date())], reply_to_id=id1)
    d3 = d2 + timedelta(hours=1, minutes=40)
    body3 = ("Too late to save at that price. Log the churn reason as Other in the CRM for now - I don't want 'outage' showing up in the "
             "board churn breakdown before we've presented the reliability plan. We'll clean it up after Q3.\n\nG" + "\n\n" + quote(body2))
    m3, id3 = mk(r, addr(gideon, d3.date()), [addr(bryce, d3.date())], "RE: FW: Notice of non-renewal - Harbortown", body3, d3,
                 cc=[addr(priya, d3.date())], reply_to_id=id2)
    for m, d in [(m1, d1), (m2, d2), (m3, d3)]:
        add(box("sales_bkittredge_2014-2017"), m, d)

    # ------------------------------------------------------------- GF08 Classic sunset (final) - Nov 2019
    ceo = P["E001"]
    d = et(datetime(2019, 11, 20, 16, 5, 0))
    body = ("All,\n\nFollowing last week's staff meeting, this is FINAL:\n\n"
            "  * Brindle Classic (on-prem) reaches end of life on June 30, 2020. No support, patches or license keys after that date.\n"
            "  * Every Classic customer who moves to Ops Cloud before the sunset gets a 25% credit on Ops Cloud subscription fees for their first 12 months.\n"
            "  * Classic maintenance invoices stop with the Q2 2020 quarter.\n\n"
            "Please ignore the earlier draft memo that said 20% - that number was before Lorraine's model.\n\nMargaret")
    m, _ = mk(r, addr(ceo, d.date()), ["all-staff@brindlecove.example"], "Classic end of life - FINAL", body + DISCLAIMER, d)
    add(box("exec_announcements_2012-2026"), m, d)

    # ------------------------------------------------------------- GF02 Calloway (points to the scanned contract)
    gc = P["E002"]
    d = et(datetime(2013, 6, 18, 11, 30, 0))
    body = ("Ines,\n\nCalloway moves to Ops Cloud on 7/1. They negotiated hard - the pricing is in the MSA I signed on 6/14, "
            "scanned into the legal share (Calloway_MSA_2013_signed.pdf). Please set them up in Ledger at the NET seat price per that contract, "
            "not list. Do not apply a separate discount line, it's baked in.\n\nDesmond")
    m, _ = mk(r, addr(gc, d.date()), [addr(P["E012"], d.date())], "Calloway - billing setup for cloud", body + DISCLAIMER, d, charset="iso-8859-1")
    add(box("finance_idelacroix_2013-2026"), m, d)

    # ------------------------------------------------------------- filler mail
    staff = [p for p in world.people]
    cust = [c for c in world.customers if c.cloud_start]
    templates = [
        ("Renewal - {cust}", "Hi {cfirst},\n\nYour Brindle Ops Cloud renewal is coming up on {date}. Current seats: {seats}. Let me know if anything changed.\n"),
        ("Invoice {inv} past due", "Hello,\n\nOur records show invoice {inv} for {amt} is now {days} days past due. Please remit at your earliest convenience.\n\nAccounts Receivable"),
        ("Q{q} board deck - numbers", "Team, need final ARR and churn numbers by Thursday. Use the finance number this time, not the CRM export.\n"),
        ("Automatic reply: {subj}", "I am out of the office until {date} with limited access to email. For urgent matters contact {other}."),
        ("RE: question about seat count", "{cfirst}, you're billed on the peak seat count in the period, not the average. Happy to walk through it.\n"),
        ("Brindlecove Monthly - {month}", "<html><body><h1>What's new in Ops Cloud</h1><p>Recurring PM templates, faster sync, and more.</p><p>Unsubscribe</p></body></html>"),
        ("FW: price increase pushback - {cust}", "They're unhappy about the {year} increase. Can we grandfather? See policy memo.\n"),
        ("Data request: churn by industry", "Can someone pull logo churn by industry for {year}? CRM churn reasons are mostly 'Other' so not sure it's useful.\n"),
        ("[ALERT] PagerDuty: {sev} - API error rate", "Incident triggered. Service: ops-api. Details: error rate > 5% for 5m. Ack required."),
        ("Welcome aboard - {cust}!", "Hi {cfirst},\n\nWelcome to Brindle Ops Cloud! Your onboarding specialist will reach out within 2 business days.\n"),
    ]
    mailboxes = ["sales_shared_2011-2026", "ar_billing_2011-2026", "cs_team_2014-2026", "eng_alerts_2019-2026"]
    for _ in range(2600):
        d0 = rand_date(r, date(2004, 1, 1), AS_OF)
        subj_t, body_t = r.choice(templates)
        if "PagerDuty" in subj_t and d0 < date(2019, 1, 1):
            d0 = rand_date(r, date(2019, 1, 1), AS_OF)
        c = r.choice(cust)
        sender = r.choice([p for p in staff if p.hired <= d0 and (not p.left or p.left >= d0)] or staff)
        other = r.choice(staff)
        ct = r.choice(c.contacts)
        fill = dict(cust=r.choice(c.variants), cfirst=ct.first, date=(d0 + timedelta(days=r.randint(5, 60))).strftime(r.choice(["%m/%d/%Y", "%B %d", "%d %b"])),
                    seats=c.seats(d0), inv=f"{r.randint(500000, 990000)}", amt=f"${r.randint(200, 90000):,}.{r.randint(0, 99):02d}",
                    days=r.choice([15, 30, 45, 60, 90]), q=r.randint(1, 4), subj="Re: " + r.choice(["renewal", "invoice", "meeting"]),
                    other=other.name, month=d0.strftime("%B %Y"), year=d0.year, sev=r.choice(["SEV1", "SEV2", "P1", "P2"]))
        subject = subj_t.format(**fill)
        body = body_t.format(**fill)
        if not body.startswith("<html>"):
            body += sig(sender, d0) + (DISCLAIMER if d0 >= ERA["saas_launch"] else DISCLAIMER_OLD)
        if r.random() < 0.25:
            prev = r.choice(templates)[1].format(**fill)
            body += "\n\nOn " + d0.strftime("%a, %b %d, %Y") + f" at 9:{r.randint(10, 59)} AM, {ct.name} <{ct.email}> wrote:\n" + quote(prev)
        dd = dt(d0, r)
        attach = None
        if "Invoice" in subject and r.random() < 0.2:
            attach = (f"statement_{fill['inv']}.csv", f"invoice,amount,due\n{fill['inv']},{fill['amt']},{fill['date']}\n".encode(), "octet-stream")
        mboxname = r.choice(mailboxes)
        if "PagerDuty" in subject:
            mboxname = "eng_alerts_2019-2026"
        if "Invoice" in subject:
            mboxname = "ar_billing_2011-2026"
        to = [f"{ct.name} <{ct.email}>"] if r.random() < 0.5 else [addr(other, d0)]
        if "Monthly" in subject:
            m = MIMEText(body, "html", "utf-8")
            m["From"], m["To"], m["Subject"], m["Date"] = "Brindlecove <news@brindlecove.example>", to[0], subject, format_datetime(dd)
        else:
            m, _ = mk(r, addr(sender, d0), to, subject, body, dd, charset=r.choice(["utf-8", "utf-8", "iso-8859-1", "windows-1252"]), attach=attach)
        add(box(mboxname), m, dd)

    # ------------------------------------------------------------- legal hold .eml files (2019, Pinecrest dispute)
    lh = base / "legal_hold_2019_LH-0042"
    lh.mkdir(parents=True, exist_ok=True)
    pc = g["pinecrest"]
    for k in range(6):
        d0 = date(2019, 4, 2) + timedelta(days=k * 9)
        sender = P["E016"] if k % 2 == 0 else P["E012"]
        body = r.choice(["Please preserve all records related to the Pinecrest Logistics invoice dispute (Q4 2018 seat true-up).",
                         "Attached is the reconciliation. Pinecrest claims 22 seats, we billed 35. Usage logs support 31 active users.",
                         "Privileged & Confidential - Attorney Work Product. Do not forward.",
                         "Settled: 50% credit on the true-up, no admission. Close the hold once finance confirms the credit memo."])
        m, _ = mk(r, addr(sender, d0), [addr(P["E001"], d0)], f"RE: LH-0042 Pinecrest - item {k + 1}", body + DISCLAIMER, dt(d0, r))
        (lh / f"{k + 1:03d}_{d0:%Y%m%d}.eml").write_bytes(m.as_bytes())
    for b in boxes.values():
        b.flush()
        b.close()
    return {}
