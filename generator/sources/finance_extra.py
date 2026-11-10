"""Finance and back-office leftovers: QuickBooks IIF, vendor invoice PDFs, a nested share backup, HL7 feeds, product PDFs.

Renders:
  billing_tallyflow_2012-2014/quickbooks/TallyFlow_QB_2012-2014.IIF   QuickBooks IIF: !TRNS/!SPL/!ENDTRNS blocks, M/D/YY dates
  ap_vendor_invoices/<vendor>/<year>/*.pdf                            three vendor layouts; one credit memo is a rotated page,
                                                                      one invoice was re-sent as a 'COPY'
  ap_vendor_invoices/vendor_setup_Cobalt_Ridge_2017.pdf               AcroForm with filled fields (bank fields REDACTED)
  compliance/SOC2_Type2_2024_excerpt.pdf                              auditor's exceptions section
  product_docs/release_notes/Brindle_Insights_1.0_release_notes.pdf  release notes, second page rotated landscape
  file_shares/FS01_Finance_share_2019.zip                             share backup: Thumbs.db, desktop.ini, ~$ lock files, a zip inside
  integrations/hl7_stbrigids/ADT_YYYYMMDD.hl7                         MLLP-framed HL7 v2.5 ADT stream with retransmits and A13 cancels
  integrations/hl7_stbrigids/evs_work_orders_YYYY-MM-DD.csv           cleaning work orders the feed created in Brindle Ops

Planted:
  GF35  TallyFlow's 2013 revenue from the QuickBooks file
  GF36  2021 spend with Cobalt Ridge Colocation (ignore the re-sent copy, subtract the credit memo)
  GF37  how the FY2016 proposed audit adjustments to revenue changed from v1 to v2 (inside the nested zip)
  GF38  how many genuine discharge cleaning jobs St. Brigid's feed created on 2024-01-15
"""
from __future__ import annotations

import io
import shutil
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

from ..util import add_fact, add_months, csv_line, normalize_office_files, rng_for, write_bytes, write_text, zip_bytes
from ..world import FIRST, LAST

RAW = "data/raw"


def pdf(draw, pagesize=letter) -> bytes:
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=pagesize, invariant=1)
    draw(cv)
    cv.save()
    return buf.getvalue()


def xlsx_bytes(build, created: datetime) -> bytes:
    wb = Workbook()
    build(wb)
    wb.properties.created = created
    wb.properties.modified = created
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "f.xlsx"
        wb.save(p)
        normalize_office_files(td)
        return p.read_bytes()


def pv1(bed, visit, when):
    f = [""] * 45
    f[0], f[1], f[2], f[9], f[18], f[44] = "1", "I", bed, "MED", visit, f"{when:%Y%m%d%H%M%S}"
    return f


def iif_date(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year % 100:02d}"


def render(world, out, seed):
    r = rng_for(seed, "finance_extra")

    # ----------------------------------------------------------------- GF35 QuickBooks IIF
    tf = [i for i in world.invoices if i.system == "tallyflow"]
    lines = ["!ACCNT\tNAME\tACCNTTYPE\tDESC", "ACCNT\tAccounts Receivable\tAR\t", "ACCNT\tSubscription Revenue\tINC\tTallyFlow subscriptions",
             "ACCNT\tUndeposited Funds\tOCASSET\t", "ACCNT\tSales Tax Payable\tOCLIAB\t",
             "!CUST\tNAME\tBADDR1\tBADDR2", ]
    seen = set()
    for i in tf:
        if i.cust.name not in seen:
            seen.add(i.cust.name)
            lines.append(f"CUST\t{i.cust.name[:41]}\t{i.cust.name[:41]}\t{i.cust.city}, {i.cust.region}")
    lines += ["!TRNS\tTRNSID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO\tCLEAR\tTOPRINT",
              "!SPL\tSPLID\tTRNSTYPE\tDATE\tACCNT\tNAME\tCLASS\tAMOUNT\tDOCNUM\tMEMO\tCLEAR\tQNTY\tPRICE\tINVITEM",
              "!ENDTRNS"]
    rev = {2012: 0.0, 2013: 0.0, 2014: 0.0}
    credits_2013 = 0.0
    events = []
    for i in tf:
        events.append((i.issued, 0, i))
        if i.paid_on and i.status in ("paid", "refunded"):
            events.append((i.paid_on, 1, i))
        if i.status == "refunded":
            events.append((i.paid_on + timedelta(days=r.randint(1, 20)), 2, i))
    events.sort(key=lambda e: (e[0], e[1], e[2].seq))
    for d, kind, i in events:
        nm = i.cust.name[:41]
        doc = f"{i.seq % 100000:05d}"
        if kind == 0:
            if i.status == "void":
                lines += [f"TRNS\t\tINVOICE\t{iif_date(d)}\tAccounts Receivable\t{nm}\t\t0.00\t{doc}\tVOID: entered twice\tN\tN",
                          f"SPL\t\tINVOICE\t{iif_date(d)}\tSubscription Revenue\t{nm}\t\t0.00\t{doc}\tVOID\tN\t0\t0\tSubscription", "ENDTRNS"]
                continue
            lines.append(f"TRNS\t\tINVOICE\t{iif_date(d)}\tAccounts Receivable\t{nm}\t\t{i.total:.2f}\t{doc}\t\tN\tY")
            for desc, q, p in i.lines:
                lines.append(f"SPL\t\tINVOICE\t{iif_date(d)}\tSubscription Revenue\t{nm}\t\t{-round(q * p, 2):.2f}\t{doc}\t{desc[:31]}\tN\t{-q}\t{p:.2f}\tSubscription")
            lines.append("ENDTRNS")
            if d.year in rev:
                rev[d.year] += i.total
        elif kind == 1:
            lines += [f"TRNS\t\tPAYMENT\t{iif_date(d)}\tUndeposited Funds\t{nm}\t\t{i.total:.2f}\t\tACH\tN\tN",
                      f"SPL\t\tPAYMENT\t{iif_date(d)}\tAccounts Receivable\t{nm}\t\t{-i.total:.2f}\t\t\tN\t\t\t", "ENDTRNS"]
        else:
            lines += [f"TRNS\t\tCREDIT MEMO\t{iif_date(d)}\tAccounts Receivable\t{nm}\t\t{-i.total:.2f}\tCM{doc}\tRefund - cancelled\tN\tN",
                      f"SPL\t\tCREDIT MEMO\t{iif_date(d)}\tSubscription Revenue\t{nm}\t\t{i.total:.2f}\tCM{doc}\tRefund\tN\t1\t{i.total:.2f}\tSubscription",
                      "ENDTRNS"]
            if d.year in rev:
                rev[d.year] -= i.total
            if d.year == 2013:
                credits_2013 += i.total
    write_text(out / "billing_tallyflow_2012-2014" / "quickbooks" / "TallyFlow_QB_2012-2014.IIF", "\n".join(lines) + "\n",
               encoding="cp1252", newline="\r\n")
    rev13 = round(rev[2013], 2)
    add_fact(world, {"id": "GF35", "difficulty": "medium", "kind": "QuickBooks IIF",
                     "question": "What was TallyFlow's 2013 revenue, according to its QuickBooks books?",
                     "answer": f"${rev13:,.2f}: the Subscription Revenue splits of 2013 invoices (stored as negative numbers), less "
                               f"${credits_2013:,.2f} of 2013 credit memos. Payments must not be counted.",
                     "trail": [f"{RAW}/billing_tallyflow_2012-2014/quickbooks/TallyFlow_QB_2012-2014.IIF",
                               f"{RAW}/billing_tallyflow_2012-2014/invoices_export.xml (cross-check)"],
                     "traps": ["Income splits are negative in IIF", "TRNS lines repeat the SPL totals (double counting)",
                               "Dates are M/D/YY", "PAYMENT transactions are cash, not revenue"],
                     "values": {"revenue_2013": rev13, "credit_memos_2013": round(credits_2013, 2)}})

    # ----------------------------------------------------------------- GF36 vendor invoices
    ap = out / "ap_vendor_invoices"
    crc_2021 = []

    def cobalt(num, d, amount, period, copy=False, credit=False):
        def draw(cv):
            if credit:
                cv.setPageRotation(90)
            cv.setFont("Helvetica-Bold", 18)
            cv.drawString(54, 730, "COBALT RIDGE COLOCATION")
            cv.setFont("Helvetica", 9)
            cv.drawString(54, 716, "Data Center 2 - 4400 Ridge Industrial Pkwy - Columbus OH  |  billing@cobaltridge.example")
            cv.setFont("Helvetica-Bold", 14)
            cv.drawString(400, 690, "CREDIT MEMO" if credit else "INVOICE")
            cv.setFont("Helvetica", 10)
            for k, (a, b) in enumerate([("Number", num), ("Date", f"{d:%m/%d/%Y}"), ("Account", "BRC-0014"), ("Service period", period)]):
                cv.drawString(400, 670 - k * 14, f"{a}: {b}")
            cv.drawString(54, 640, "Bill to: Brindlecove Software, Inc. - Accounts Payable - Dayton OH")
            y = 590
            items = ([("SLA credit - power event 9/14 (cage 14)", -amount)] if credit else
                     [("Cage 14 - 2 racks, 30A A+B", round(amount * 0.72, 2)), ("Cross-connects (6)", round(amount * 0.08, 2)),
                      ("Bandwidth 1 Gbps commit", round(amount - round(amount * 0.72, 2) - round(amount * 0.08, 2), 2))])
            for desc, a in items:
                cv.drawString(54, y, desc)
                cv.drawRightString(540, y, f"{a:,.2f}")
                y -= 16
            cv.setFont("Helvetica-Bold", 11)
            cv.drawString(380, y - 10, "TOTAL USD")
            cv.drawRightString(540, y - 10, f"{(-amount if credit else amount):,.2f}")
            if copy:
                cv.setFont("Helvetica-Bold", 40)
                cv.setFillGray(0.75)
                cv.saveState()
                cv.translate(300, 400)
                cv.rotate(30)
                cv.drawCentredString(0, 0, "COPY - REISSUED")
                cv.restoreState()
            cv.showPage()
        return pdf(draw)

    m = date(2017, 1, 1)
    while m <= date(2023, 3, 1):
        amount = round(6400 * (1.03 ** (m.year - 2017)) + r.uniform(-60, 60), 2)
        num = f"CRC-{m:%Y%m}-{r.randint(100, 999)}"
        write_bytes(ap / "Cobalt_Ridge_Colocation" / str(m.year) / f"{num}.pdf",
                    cobalt(num, m, amount, f"{m:%m/01/%Y}-{add_months(m, 1) - timedelta(days=1):%m/%d/%Y}"))
        if m.year == 2021:
            crc_2021.append(amount)
            if m.month == 6:
                write_bytes(ap / "Cobalt_Ridge_Colocation" / "2021" / f"{num}_copy.pdf",
                            cobalt(num, m + timedelta(days=34), amount, f"{m:%m/01/%Y}-{add_months(m, 1) - timedelta(days=1):%m/%d/%Y}", copy=True))
        m = add_months(m, 1)
    credit_amt = 1850.00
    write_bytes(ap / "Cobalt_Ridge_Colocation" / "2021" / "CM-2021-0917.pdf",
                cobalt("CM-2021-0917", date(2021, 9, 30), credit_amt, "09/2021", credit=True))
    spend21 = round(sum(crc_2021) - credit_amt, 2)

    def northgate(num, d, amount):
        def draw(cv):
            cv.setFont("Courier", 10)
            for k, l in enumerate(["NORTHGATE FIBER & VOICE", "STATEMENT / INVOICE", "", f"ACCT 88-41207-3   STMT DATE {d:%d-%b-%Y}".upper(),
                                   f"INVOICE NO {num}", "", "PREVIOUS BALANCE ............ 0.00", f"CURRENT CHARGES ............. {amount:,.2f}",
                                   "  SIP TRUNK (23 CH)", "  DID BLOCK 937-555-01XX", "  TAXES & SURCHARGES", "",
                                   f"TOTAL AMOUNT DUE ............ {amount:,.2f}", f"DUE {d + timedelta(days=21):%m/%d/%y}"]):
                cv.drawString(60, 740 - k * 13, l)
            cv.showPage()
        return pdf(draw)

    def ardent(num, d, items):
        def draw(cv):
            cv.setFont("Times-Roman", 11)
            cv.drawString(60, 740, "Ardent Office Supply Co.")
            cv.drawString(60, 726, f"Invoice {num}  -  {d:%B %d, %Y}")
            y = 690
            tot = 0
            for desc, q, p in items:
                cv.drawString(60, y, f"{q} x {desc}")
                cv.drawRightString(520, y, f"${q * p:,.2f}")
                tot += q * p
                y -= 14
            cv.drawRightString(520, y - 12, f"Total ${tot:,.2f}")
            cv.showPage()
        return pdf(draw)

    for k in range(70):
        d = date(2018, 1, 1) + timedelta(days=r.randint(0, 2400))
        num = f"NG{d:%y%m}{r.randint(1000, 9999)}"
        write_bytes(ap / "Northgate_Fiber" / str(d.year) / f"{num}.pdf", northgate(num, d, round(r.uniform(900, 1400), 2)))
    for k in range(50):
        d = date(2016, 1, 1) + timedelta(days=r.randint(0, 3000))
        num = f"A-{r.randint(40000, 89999)}"
        items = [(r.choice(["Copy paper, case", "Toner HP 26X", "Sticky notes 12pk", "Coffee, 5lb", "Whiteboard markers"]), r.randint(1, 8),
                  round(r.uniform(6, 140), 2)) for _ in range(r.randint(1, 5))]
        write_bytes(ap / "Ardent_Office_Supply" / str(d.year) / f"{num}.pdf", ardent(num, d, items))

    def vendor_form(cv):
        f = cv.acroForm
        cv.setFont("Helvetica-Bold", 14)
        cv.drawString(54, 740, "Brindlecove Software - New Vendor Setup Form (AP-07)")
        cv.setFont("Helvetica", 10)
        fields = [("vendor_name", "Legal name", "Cobalt Ridge Colocation LLC"), ("dba", "DBA", "Cobalt Ridge"),
                  ("remit_addr", "Remit-to address", "PO Box 0000, Columbus OH 43216"), ("tax_id", "Tax ID", "REDACTED"),
                  ("bank_routing", "Bank routing no.", "REDACTED"), ("bank_acct", "Bank account no.", "REDACTED"),
                  ("terms", "Payment terms", "Net 30"), ("approver", "Approved by", "I. Delacroix"), ("date", "Date", "03/06/2017")]
        for k, (name, label, value) in enumerate(fields):
            y = 690 - k * 34
            cv.drawString(54, y + 6, label)
            f.textfield(name=name, value=value, x=200, y=y, width=300, height=20, borderStyle="inset", forceBorder=True)
        cv.showPage()
    write_bytes(ap / "vendor_setup_Cobalt_Ridge_2017.pdf", pdf(vendor_form))
    add_fact(world, {"id": "GF36", "difficulty": "medium", "kind": "vendor invoice PDFs",
                     "question": "How much did Brindlecove pay Cobalt Ridge Colocation for 2021?",
                     "answer": f"${spend21:,.2f}: twelve monthly invoices totalling ${sum(crc_2021):,.2f}, less the ${credit_amt:,.2f} SLA credit memo "
                               f"(a rotated page). The June invoice also exists as a re-sent 'COPY - REISSUED' PDF, which must not be counted twice.",
                     "trail": [f"{RAW}/ap_vendor_invoices/Cobalt_Ridge_Colocation/2021/"],
                     "traps": ["June appears twice (original and _copy)", "The credit memo page is rotated 90 degrees"],
                     "values": {"spend_2021": spend21, "invoices_2021": round(sum(crc_2021), 2), "credit": credit_amt}})

    # ----------------------------------------------------------------- SOC 2 excerpt + release notes
    def soc2(cv):
        cv.setFont("Helvetica-Bold", 13)
        cv.drawString(54, 740, "Section IV - Description of Tests of Controls and Results (excerpt)")
        cv.setFont("Helvetica", 9.5)
        rows = [("CC6.2", "Access is removed within one business day of termination.",
                 "Inspected 25 terminated users. For 2 of 25, Okta access was removed 3 and 6 days after termination.", "Exception noted"),
                ("CC6.3", "Quarterly user access reviews are performed.", "Inspected Q1-Q4 reviews.", "No exceptions noted"),
                ("CC7.2", "Production changes are approved.", "Inspected 40 changes.", "No exceptions noted"),
                ("CC8.1", "Backups are tested quarterly.", "Inspected restore tests.", "No exceptions noted")]
        y = 710
        for c, ctl, test, res in rows:
            cv.drawString(54, y, c)
            cv.drawString(100, y, ctl)
            cv.drawString(100, y - 12, "Test: " + test)
            cv.drawString(100, y - 24, "Result: " + res)
            y -= 48
        cv.drawString(54, y - 10, "Management response (CC6.2): HR offboarding tickets will auto-trigger deprovisioning from Q1 2025.")
        cv.drawString(54, 40, "Brindlecove Software, Inc. - SOC 2 Type II - Period 1 Jan 2024 to 31 Dec 2024 - CONFIDENTIAL")
        cv.showPage()
    write_bytes(out / "compliance" / "SOC2_Type2_2024_excerpt.pdf", pdf(soc2))

    def notes(cv):
        cv.setFont("Helvetica-Bold", 18)
        cv.drawString(54, 730, "Brindle Insights 1.0 - Release Notes")
        cv.setFont("Helvetica", 11)
        for k, l in enumerate(["Released: 3 April 2022 (general availability)", "Formerly Kestrel Lantern. Built by the Kestrel Analytics team, Leeds.",
                               "", "Highlights", "- Dashboards for work-order backlog, first-time-fix rate and technician utilisation",
                               "- Scheduled PDF reports", "- Available as an add-on: flat monthly fee per account (see price book)",
                               "", "Known issues", "- Exports over 100,000 rows time out (fix planned for 1.1)",
                               "- Dates in scheduled reports follow the account's locale (dd/mm for UK accounts)"]):
            cv.drawString(54, 700 - k * 16, l)
        cv.showPage()
        cv.setPageRotation(90)
        cv.setFont("Helvetica-Bold", 12)
        cv.drawString(54, 560, "Appendix A - Feature matrix by plan")
        cv.setFont("Helvetica", 10)
        for k, l in enumerate(["Feature              Starter   Pro   Enterprise", "Backlog dashboard       -       Y        Y",
                               "Scheduled reports       -       Y        Y", "Custom metrics          -       -        Y"]):
            cv.drawString(54, 530 - k * 14, l)
        cv.showPage()
    write_bytes(out / "product_docs" / "release_notes" / "Brindle_Insights_1.0_release_notes.pdf", pdf(notes))

    # ----------------------------------------------------------------- GF37 nested share backup
    v1 = [("AJE-01", "Accrued hosting expense (Dec)", "Hosting expense", 0, 18_420.00),
          ("AJE-02", "Deferred revenue - annual prepaids", "Subscription revenue", -96_300.00, 0),
          ("AJE-03", "Bonus accrual true-up", "Payroll expense", 0, 22_000.00)]
    v2 = [v1[0], ("AJE-02", "Deferred revenue - annual prepaids (revised per auditor)", "Subscription revenue", -112_850.00, 0), v1[2],
          ("AJE-04", "Ledger import - discount stored as price (Q4)", "Subscription revenue", -41_250.00, 0)]

    def aje_sheet(entries, title):
        def build(wb):
            ws = wb.active
            ws.title = "Proposed AJEs"
            ws.append([title])
            ws.append(["Prepared by: Y. Tanaka", "", "Reviewed by:"])
            ws.append([])
            ws.append(["AJE #", "Description", "Account", "Revenue impact", "Expense impact"])
            for e in entries:
                ws.append(list(e))
            n = 4 + len(entries)
            ws.append(["", "Total", "", f"=SUM(D5:D{n})", f"=SUM(E5:E{n})"])
        return build
    aje1 = xlsx_bytes(aje_sheet(v1, "FY2016 PROPOSED AUDIT ADJUSTMENTS - v1"), datetime(2017, 2, 3, 10, 12))
    aje2 = xlsx_bytes(aje_sheet(v2, "FY2016 PROPOSED AUDIT ADJUSTMENTS - v2 (after auditor call 2/9)"), datetime(2017, 2, 10, 16, 40))
    tb = "Account,Debit,Credit\r\n" + "\r\n".join(f"{a},{r.randint(10000, 900000)}.00," for a in ["Cash", "AR", "Prepaids", "Fixed assets"]) + "\r\n"
    inner = zip_bytes([("FY2016_close/AJE_proposed_v1.xlsx", aje1, (2017, 2, 3, 10, 12, 0)),
                       ("FY2016_close/AJE_proposed_v2.xlsx", aje2, (2017, 2, 10, 16, 40, 0)),
                       ("FY2016_close/TB_final_12-31-16.csv", tb.encode(), (2017, 2, 14, 9, 2, 0)),
                       ("FY2016_close/Thumbs.db", bytes(r.getrandbits(8) for _ in range(6144)), (2017, 2, 14, 9, 3, 0))])
    lock = b"\x0cytanaka" + b"\x20" * 42 + b"\x07\x00Y Tanaka" + b"\x00" * 100
    outer = zip_bytes([("Finance/desktop.ini", "[.ShellClassInfo]\r\nIconResource=C:\\Windows\\system32\\imageres.dll,-112\r\n".encode("utf-16")),
                       ("Finance/Thumbs.db", bytes(r.getrandbits(8) for _ in range(12288))),
                       ("Finance/Month-end/~$close_checklist.xlsx", lock),
                       ("Finance/Month-end/close_checklist_2019-09.csv", b"step,owner,done\r\nAR aging,ines,Y\r\nAccruals,yuki,Y\r\n"),
                       ("Finance/FY2016_close.zip", inner),
                       ("Finance/README - do not delete.txt", "Archived FY2016 close here before cleanup. YT 10/30/19\r\n".encode("cp1252"))])
    write_bytes(out / "file_shares" / "FS01_Finance_share_2019.zip", outer)
    r1 = sum(e[3] for e in v1)
    r2 = sum(e[3] for e in v2)
    add_fact(world, {"id": "GF37", "difficulty": "hard", "kind": "nested archive",
                     "question": "How did the proposed FY2016 audit adjustments to revenue change between version 1 and version 2?",
                     "answer": f"Revenue adjustments went from ${r1:,.2f} (v1) to ${r2:,.2f} (v2), a further ${r2 - r1:,.2f}: AJE-02 grew "
                               f"from -96,300 to -112,850 and v2 added AJE-04 (-41,250) for the ledger 'discount stored as price' bug.",
                     "trail": [f"{RAW}/file_shares/FS01_Finance_share_2019.zip -> Finance/FY2016_close.zip -> FY2016_close/AJE_proposed_v1.xlsx, v2.xlsx"],
                     "traps": ["The workbooks are a zip inside a zip", "Total cells are formulas with no cached values",
                               "Thumbs.db, desktop.ini and the ~$ lock file are not data"],
                     "values": {"v1_revenue": r1, "v2_revenue": r2, "change": r2 - r1}})

    # ----------------------------------------------------------------- GF38 HL7 ADT feed
    brigid = world.golden["brigid_us"]
    hl7 = out / "integrations" / "hl7_stbrigids"
    gf38 = None
    for day in [date(2024, 1, 12), date(2024, 1, 15), date(2024, 1, 16)]:
        n_dis = 46 if day == date(2024, 1, 15) else r.randint(30, 50)
        msgs, wos = [], [["wo_number", "created_utc", "site", "location", "type", "source_ref", "status", "closed_utc"]]
        ctrl = 700000 + day.toordinal() % 10000 * 10
        dis = []
        for k in range(n_dis):
            t = datetime.combine(day, time(r.randint(7, 21), r.randint(0, 59), r.randint(0, 59)))
            visit = f"V{day:%y%m%d}{r.randint(10000, 99999)}"
            unit = r.choice(["4W", "4E", "5N", "6S", "ICU2", "MS3"])
            bed = f"{unit}^{r.randint(401, 699)}^{r.choice('AB')}^DETMAIN"
            dis.append((t, visit, bed, f"{r.choice(LAST)}^{r.choice(FIRST)}", f"MRN{r.randint(1000000, 9999999)}", f"19{r.randint(30, 99)}0101"))
        dis.sort()
        cancel = set(v for _, v, *_ in r.sample(dis, 3))
        resend = set(v for _, v, *_ in r.sample(dis, 5))
        wo = 50000 + day.toordinal() % 1000 * 100
        for t, visit, bed, name, mrn, dob in dis:
            ctrl += 1

            def msg(ev, when, cid):
                return "\r".join([f"MSH|^~\\&|EPIC|STBRIGID|BRINDLEOPS|BCOVE|{when:%Y%m%d%H%M%S}||ADT^{ev}^ADT_A03|{cid}|P|2.5",
                                  f"EVN|{ev}|{when:%Y%m%d%H%M%S}", f"PID|1||{mrn}^^^STB^MR||{name}||{dob}|U",
                                  "PV1|" + "|".join(pv1(bed, visit, when))]) + "\r"
            msgs.append((t, msg("A03", t, ctrl)))
            if visit in resend:
                msgs.append((t + timedelta(seconds=30), msg("A03", t, ctrl)))   # no ACK received -> same control id resent
            wo += 1
            st = "Cancelled" if visit in cancel else "Completed"
            wos.append([f"WO-{wo}", f"{t + timedelta(hours=5, seconds=4):%Y-%m-%dT%H:%M:%SZ}", "St. Brigid's Detroit Main", bed.replace("^", " ").strip(),
                        "EVS Discharge Clean", visit, st, f"{t + timedelta(hours=5, minutes=r.randint(25, 90)):%Y-%m-%dT%H:%M:%SZ}" if st == "Completed" else ""])
            if visit in resend and r.random() < 0.6:
                wo += 1
                wos.append([f"WO-{wo}", f"{t + timedelta(hours=5, seconds=35):%Y-%m-%dT%H:%M:%SZ}", "St. Brigid's Detroit Main", bed.replace("^", " ").strip(),
                            "EVS Discharge Clean", visit, "Closed - Duplicate", ""])
            if visit in cancel:
                ct = t + timedelta(minutes=r.randint(10, 50))
                ctrl += 1
                msgs.append((ct, msg("A13", ct, ctrl).replace("ADT_A03", "ADT_A01")))
        msgs.sort(key=lambda m: m[0])
        stream = b"".join(b"\x0b" + m.encode("ascii") + b"\x1c\x0d" for _, m in msgs)
        write_bytes(hl7 / f"ADT_{day:%Y%m%d}.hl7", stream)
        write_text(hl7 / f"evs_work_orders_{day}.csv", "\n".join(csv_line(x) for x in wos) + "\n")
        if day == date(2024, 1, 15):
            gf38 = (n_dis, len(cancel), len(resend), len(wos) - 1)
    write_text(hl7 / "README.txt", f"Interface: {brigid.name} Epic ADT -> Brindle Ops EVS work orders.\r\nMLLP framed (0x0B ... 0x1C 0x0D). "
               "Engine resends a message with the SAME MSH-10 when no ACK within 30s.\r\nA13 = cancel discharge. Work orders are created in UTC.\r\n",
               encoding="ascii", newline="\n")
    n_dis, n_can, n_res, n_wo = gf38
    add_fact(world, {"id": "GF38", "difficulty": "hard", "kind": "HL7 interface",
                     "question": f"On January 15, 2024, how many discharge cleaning jobs did {brigid.name}'s feed genuinely create?",
                     "answer": f"{n_dis - n_can}. The ADT stream has {n_dis} distinct A03 discharges (plus {n_res} resent copies with the same "
                               f"MSH-10 control id) and {n_can} A13 cancellations. The work-order export lists {n_wo} rows because some resends "
                               f"created duplicates (status 'Closed - Duplicate') and cancelled discharges show 'Cancelled'.",
                     "trail": [f"{RAW}/integrations/hl7_stbrigids/ADT_20240115.hl7 (MLLP framed, segments end in CR)",
                               f"{RAW}/integrations/hl7_stbrigids/evs_work_orders_2024-01-15.csv"],
                     "traps": ["Resent messages share MSH-10", "A13 cancels an earlier A03", "Work orders are in UTC, ADT times are local",
                               "Counting work-order rows over-counts"],
                     "values": {"genuine": n_dis - n_can, "discharges": n_dis, "cancelled": n_can, "resent": n_res, "work_order_rows": n_wo}})
    return {}
