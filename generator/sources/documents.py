"""Office documents: contracts (scanned + digital PDF, DOCX), RTF memos, old .xls, .xlsx, board decks (.pptx).

Renders:
  legal_contracts/scanned/*.pdf (+ .ocr.txt)   image-only scans, skewed and noisy; OCR sidecars with typical errors
  legal_contracts/pdf/*.pdf                     text-layer order forms 2011-2019 (reportlab)
  legal_contracts/docx/*.docx                   2019+ order forms with drafting notes left in
  memos/*.rtf                                   2000s-2019 memos, incl. a superseded DRAFT
  spreadsheets/*.xls                            BIFF8 workbooks (merged cells, multi-row headers, notes sheets)
  board_and_finance/*.pptx, *.xlsx              board decks and the finance close workbook
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta

import xlwt
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pptx import Presentation
from pptx.util import Inches, Pt as PPt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from ..golden import compute
from ..util import AS_OF, rand_date, rng_for, write_bytes, write_text
from ..world import ERA, FX_TO_USD, PRICE_BOOK, first_year_arr_local

FIXED_DT = datetime(2026, 11, 1)


def font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ----------------------------------------------------------------------------- scans
def scan_pages(r, pages_text, when):
    imgs = []
    f = font(22)
    for text in pages_text:
        img = Image.new("L", (1275, 1650), 250)
        d = ImageDraw.Draw(img)
        y = 110
        for line in text.split("\n"):
            d.text((120 + r.randint(-2, 2), y), line, fill=r.randint(15, 60), font=f)
            y += 34
        # stamp + signature scribble
        d.ellipse((900, 1380, 1150, 1500), outline=90, width=3)
        d.text((935, 1425), "RECEIVED", fill=90, font=font(24))
        for _ in range(1800):
            x, yy = r.randint(0, 1274), r.randint(0, 1649)
            img.putpixel((x, yy), r.randint(0, 120))
        img = img.rotate(r.uniform(-1.6, 1.6), fillcolor=235, resample=Image.BICUBIC)
        img = img.filter(ImageFilter.GaussianBlur(0.6))
        imgs.append(img.convert("RGB").resize((850, 1100)))
    buf = io.BytesIO()
    stamp = datetime(when.year, when.month, when.day, 16, 5)   # scanner clock, not the build machine's
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:], resolution=100.0, creationDate=stamp.timetuple(), modDate=stamp.timetuple())
    return buf.getvalue()


def ocr_noise(r, text, rate=0.03):
    swaps = {"l": "1", "O": "0", "m": "rn", "e": "c", "S": "5", "i": "l", "h": "b", ",": ".", "B": "8"}
    out = []
    for ch in text:
        if ch in swaps and r.random() < rate and not ch.isdigit():
            out.append(swaps[ch])
        else:
            out.append(ch)
    return "".join(out)


def msa_text(c, net, list_price, pct, seats_min, signer, sig_date):
    p1 = f"""MASTER SUBSCRIPTION AGREEMENT

This Master Subscription Agreement ("Agreement") is entered into as of
{sig_date:%B %d, %Y} ("Effective Date") between Brindlecove Software, Inc.,
an Ohio corporation ("Brindlecove"), and {c.name}
("Customer").

1. SERVICES. Brindlecove will provide Customer access to Brindle Ops Cloud
   (the "Service") as described in each Order Form.

2. TERM. Initial term of thirty-six (36) months from the Service start date
   of {c.cloud_start:%B %d, %Y}, renewing for successive twelve (12) month terms
   unless either party gives sixty (60) days written notice.

3. CLASSIC LICENSE. Customer's perpetual Brindle Classic license dated
   {c.first_seen:%m/%d/%Y} is terminated on the Service start date. No refund.

(continued on next page)"""
    p2 = f"""4. FEES.
   4.1 Subscription fees are invoiced monthly in advance in U.S. Dollars.
   4.2 Special Pricing. In consideration of Customer's long relationship
       with Brindlecove, Customer shall receive a discount of {pct}% off the
       then-current Enterprise list price (currently ${list_price:.2f} per seat
       per month), i.e. ${net:.2f} per seat per month, for so long as
       Customer maintains at least {seats_min} active seats. This price
       shall not be subject to future list price increases.
   4.3 If seats fall below {seats_min} for two consecutive months the
       discount ends at the next renewal.

5. CONFIDENTIALITY. The terms of Section 4.2 are Confidential.

IN WITNESS WHEREOF:

Brindlecove Software, Inc.            {c.name[:34]}
By: /s/ Desmond Fairweather          By: /s/ {signer}
Title: CTO & Co-founder              Title: Facilities Director
Date: {sig_date:%m/%d/%Y}                     Date: {sig_date:%m/%d/%Y}"""
    return [p1, p2]


# ----------------------------------------------------------------------------- reportlab order form
def order_form_pdf(r, c, d, seats, price, currency, rep):
    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=letter, invariant=1)
    cv.setTitle(f"Order Form - {c.name}")
    cv.setAuthor(rep)
    cv.setFont("Helvetica-Bold", 16)
    cv.drawString(72, 720, "ORDER FORM" if d.year >= 2011 else "LICENSE ORDER")
    cv.setFont("Helvetica", 10)
    cv.drawString(72, 700, f"Brindlecove Software, Inc.  |  Order #{r.randint(10000, 99999)}  |  Date: {d:%m/%d/%Y}")
    cv.drawString(72, 680, f"Customer: {c.name}")
    cv.drawString(72, 666, f"Bill to: {c.city}, {c.region}   Contact: {c.contacts[0].name} <{c.contacts[0].email}>")
    y = 630
    cv.setFont("Helvetica-Bold", 10)
    for x, h in zip([72, 300, 380, 470], ["Product", "Qty", "Unit", "Total"]):
        cv.drawString(x, y, h)
    cv.setFont("Helvetica", 10)
    y -= 18
    lines = [(f"Brindle Ops Cloud {c.plan} (seat/mo)", seats, price)] + [(f"{a} add-on", 1 if a == "Insights" else seats, 400.0 if a == "Insights" else (6.0 if a == "Invoicing" else 9.0)) for a in c.addons]
    tot = 0
    for name, q, p in lines:
        cv.drawString(72, y, name)
        cv.drawString(300, y, str(q))
        cv.drawString(380, y, f"{p:,.2f}")
        cv.drawString(470, y, f"{q * p:,.2f} {currency}")
        tot += q * p
        y -= 16
    cv.drawString(380, y - 10, "Monthly total:")
    cv.drawString(470, y - 10, f"{tot:,.2f} {currency}")
    cv.drawString(72, y - 50, "Term: 12 months, auto-renews. Payment terms: Net 30. Subject to the Master Subscription Agreement.")
    if r.random() < 0.25:
        cv.drawString(72, y - 66, r.choice(["Customer may cancel for convenience with 90 days notice (non-standard, approved GA).",
                                            "Price locked for 24 months.", "Includes 10 hours onboarding at no charge.",
                                            "Net 60 payment terms approved by CFO."]))
    cv.showPage()
    cv.save()
    return buf.getvalue()


# ----------------------------------------------------------------------------- RTF
def rtf(text, title, author, d):
    def esc(s):
        out = []
        for ch in s:
            if ch in "\\{}":
                out.append("\\" + ch)
            elif ord(ch) > 127:
                out.append(f"\\'{ord(ch.encode('cp1252', 'replace')[0:1].decode('latin-1')):02x}")
            elif ch == "\n":
                out.append("\\par\n")
            else:
                out.append(ch)
        return "".join(out)
    return ("{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0\\froman Times New Roman;}{\\f1\\fswiss Arial;}}\n"
            f"{{\\info{{\\title {esc(title)}}}{{\\author {esc(author)}}}{{\\creatim\\yr{d.year}\\mo{d.month}\\dy{d.day}}}}}\n"
            "\\paperw12240\\paperh15840\\margl1440\\margr1440\\f0\\fs24\n" + esc(text) + "\n}")


def render(world, out, seed):
    r = rng_for(seed, "documents")
    f = compute(world)
    g = world.golden
    P = {p.pid: p for p in world.people}
    lc = out / "legal_contracts"

    # ---------------------------------------------------------------- scanned contracts
    cal = g["calloway"]
    pages = msa_text(cal, f["calloway_net"], f["calloway_list"], f["calloway_discount_pct"], 150, "Theodora Vance", date(2013, 6, 14))
    write_bytes(lc / "scanned" / "Calloway_MSA_2013_signed.pdf", scan_pages(r, pages, date(2013, 6, 21)))
    ocr = "\n\f\n".join(pages)
    ocr = ocr_noise(r, ocr, 0.035)
    write_text(lc / "scanned" / "Calloway_MSA_2013_signed.ocr.txt", "[OCR engine 3.02 - confidence 0.81]\n" + ocr)
    for c in [c for c in world.customers if c.origin == "classic" and c.cloud_start][1:7]:
        d = c.cloud_start - timedelta(days=r.randint(10, 40))
        pages = msa_text(c, round(c.unit_price(c.cloud_start) * (1 - c.discount), 2), c.unit_price(c.cloud_start),
                         int(c.discount * 100), max(5, c.seats0 // 2), c.contacts[0].name, d)
        pages[1] = pages[1].replace("Special Pricing. In consideration of Customer's long relationship\n       with Brindlecove, Customer",
                                    "Pricing. Customer") if c.discount == 0 else pages[1]
        safe = "".join(ch for ch in c.name if ch.isalnum())[:24]
        write_bytes(lc / "scanned" / f"{safe}_MSA_{d.year}_signed.pdf", scan_pages(r, pages, d + timedelta(days=5)))
        if r.random() < 0.6:
            write_text(lc / "scanned" / f"{safe}_MSA_{d.year}_signed.ocr.txt", "[OCR engine 3.02]\n" + ocr_noise(r, "\n\f\n".join(pages), 0.05))

    # ---------------------------------------------------------------- text-layer order forms 2011-2019
    picks = [c for c in world.customers if c.cloud_start and ERA["saas_launch"] <= (c.signed or c.first_seen) < date(2019, 6, 1) and c.origin == "cloud"]
    for c in r.sample(picks, min(70, len(picks))):
        d = c.signed or c.first_seen
        seats = c.seats(c.cloud_start)
        price = round(c.unit_price(c.cloud_start) * (1 - c.discount), 2)
        safe = "".join(ch for ch in c.name if ch.isalnum())[:30]
        rep = P.get(c.owner).name if c.owner in P else "Sales"
        write_bytes(lc / "pdf" / f"OrderForm_{safe}_{d:%Y%m%d}.pdf", order_form_pdf(r, c, d, seats, price, c.currency, rep))

    # ---------------------------------------------------------------- docx order forms 2019+
    picks = [c for c in world.customers if c.cloud_start and (c.signed or c.first_seen) >= date(2019, 6, 1)]
    for c in r.sample(picks, min(45, len(picks))):
        d = c.signed or c.first_seen
        doc = Document()
        doc.core_properties.author = P[c.owner].name if c.owner in P else "Sales"
        doc.core_properties.created = datetime(d.year, d.month, d.day)
        doc.core_properties.modified = datetime(d.year, d.month, d.day) + timedelta(days=2)
        doc.core_properties.last_modified_by = r.choice(["Abigail Fenwick", "legal", "Renata Esposito"])
        doc.add_heading("Order Form", 0)
        doc.add_paragraph(f"Customer: {c.name}\nEffective: {d:%B %d, %Y}\nService start: {c.cloud_start:%B %d, %Y}")
        t = doc.add_table(rows=1, cols=4)
        t.style = "Table Grid"
        for cell, h in zip(t.rows[0].cells, ["Item", "Qty", "Unit price", "Currency"]):
            cell.text = h
        seats = c.seats(c.cloud_start)
        fx = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]
        for name, q, p in [(f"Ops Cloud {c.plan}", seats, round(c.unit_price(c.cloud_start) * (1 - c.discount) * fx, 2))] + \
                          [(a, 1 if a == "Insights" else seats, {"Invoicing": 6.0, "Dispatch": 9.0, "Insights": 400.0}[a] * fx) for a in c.addons]:
            row = t.add_row().cells
            row[0].text, row[1].text, row[2].text, row[3].text = name, str(q), f"{p:,.2f}", c.currency
        if r.random() < 0.3:
            doc.add_paragraph(r.choice(["[NOTE TO DRAFT: confirm with Finance whether CAD pricing applies - AF]",
                                        "[RE: please remove before sending]", "[Customer redline: Net 45. ACCEPTED? - RE]"]))
        doc.add_paragraph("Governed by the Master Subscription Agreement at brindlecove.example/legal/msa (version in effect on the Effective Date).")
        safe = "".join(ch for ch in c.name if ch.isalnum())[:30]
        p = lc / "docx" / f"{safe}_OrderForm_{d:%Y-%m-%d}{r.choice(['', '', '_final', '_FINAL_v2', '_signed', ' (1)'])}.docx"
        p.parent.mkdir(parents=True, exist_ok=True)
        doc.save(p)

    # ---------------------------------------------------------------- RTF memos
    memos = out / "memos"
    write_text(memos / "Classic_EOL_memo_DRAFT_v2.rtf", rtf(
        "DRAFT - NOT FOR DISTRIBUTION\n\nTo: Exec Staff\nFrom: Margaret Okonkwo-Hale\nDate: November 4, 2019\nRe: Brindle Classic end of life\n\n"
        "Proposal: end all Classic support and license renewals on June 30, 2020.\n\nIncentive: Classic customers who migrate before the deadline receive a "
        "20% credit on Ops Cloud fees for 12 months.\n\nOpen questions: Do we extend for government customers? What about the 31 sites still on Classic 4.x?",
        "Classic EOL memo", "mokonkwohale", date(2019, 11, 4)), encoding="cp1252")
    memo_topics = [("Y2K readiness", "All BRIX programs have been remediated for CYYMMDD dates. The late fee job will be patched over the holiday."),
                   ("Fax cover sheets", "Please use the new cover sheet with the Brindle Data Systems logo."),
                   ("Price increase 2015", "List prices go up January 1, 2015. Existing customers are grandfathered until they re-price."),
                   ("Moving to SaaS", "We will launch Brindle Ops Cloud on July 1, 2011. Classic remains supported."),
                   ("TallyFlow acquisition", "We have acquired TallyFlow (Austin, TX). Their customers keep their TF account references."),
                   ("Meridian Dispatch", "Welcome to the Meridian team in Winnipeg. Billing stays on their system until mid-2019. All amounts CAD."),
                   ("Expense policy", "Per diem is $55. Receipts required over $25."),
                   ("Holiday party", "The holiday party will be at the Dayton Art Institute on Dec 15."),
                   ("Office move", "We are moving to 1 Riverside Plaza in March. Pack your desks by the 10th."),
                   ("Data retention", "Customer data is retained for 90 days after cancellation, then purged. Billing records are kept 7 years.")]
    for i, (t_, body) in enumerate(memo_topics):
        d = [date(1999, 10, 4), date(2002, 3, 1), date(2014, 10, 1), date(2011, 5, 2), date(2014, 9, 16), date(2018, 2, 5), date(2008, 1, 7),
             date(2005, 11, 20), date(2013, 2, 11), date(2016, 9, 1)][i]
        a = r.choice([p for p in world.people if p.dept == "Executive" and p.hired <= d] or world.people)
        write_text(memos / f"memo_{d:%Y%m%d}_{t_.replace(' ', '_')}.rtf",
                   rtf(f"MEMORANDUM\n\nTo: All Staff\nFrom: {a.name}\nDate: {d:%B %d, %Y}\nRe: {t_}\n\n{body}", t_, a.name, d), encoding="cp1252")

    # ---------------------------------------------------------------- old .xls
    sp = out / "spreadsheets"
    sp.mkdir(parents=True, exist_ok=True)
    wb = xlwt.Workbook(encoding="cp1252")
    ws = wb.add_sheet("codes")
    bold = xlwt.easyxf("font: bold on")
    ws.write_merge(0, 0, 0, 3, "BRIX CUSTOMER STATUS CODES - as used in practice (HP 2/2012)", bold)
    for j, h in enumerate(["Code", "Meaning", "In copybook?", "Notes"]):
        ws.write(2, j, h, bold)
    for i, row in enumerate([("A", "Active", "Y", ""), ("I", "Inactive / cancelled", "Y", ""), ("S", "Suspended - credit hold", "Y", "AR sets this manually"),
                             ("X", "Migrated to Ledger (cloud) - BRIX record frozen", "N", "Added 7/2011 by hand, never added to BRXCUST.CPY"),
                             ("D", "Duplicate - do not bill", "N", "Only a handful, 1997")]):
        for j, v in enumerate(row):
            ws.write(3 + i, j, v)
    ws2 = wb.add_sheet("notes")
    ws2.write(0, 0, "If you see a status not listed here ask Harold before Harold leaves on 3/30/2012.")
    wb.save(str(sp / "BRIX_status_codes_2012.xls"))

    for year in (2008, 2009, 2010):
        wb = xlwt.Workbook(encoding="cp1252")
        ws = wb.add_sheet(f"Q4 {year}")
        ws.write_merge(0, 0, 0, 6, f"SALES COMMISSIONS - FY{year} - CONFIDENTIAL", bold)
        ws.write_merge(1, 1, 0, 1, "Rep", bold)
        ws.write_merge(1, 1, 2, 4, "Bookings ($)", bold)
        ws.write_merge(1, 1, 5, 6, "Commission", bold)
        for j, h in enumerate(["First", "Last", "License", "Maint", "Total", "Rate", "Payout"]):
            ws.write(2, j, h, bold)
        reps = [p for p in world.people if p.dept == "Sales" and p.hired <= date(year, 12, 31) and (not p.left or p.left.year >= year)]
        for i, p in enumerate(reps[:18]):
            lic = sum(c.classic_license for c in world.customers if c.owner == p.pid and c.origin == "classic" and c.first_seen.year == year)
            maint = round(lic * 0.18, 2)
            ws.write(3 + i, 0, p.first)
            ws.write(3 + i, 1, p.last)
            ws.write(3 + i, 2, lic)
            ws.write(3 + i, 3, maint if r.random() > 0.1 else "n/a")
            ws.write(3 + i, 4, xlwt.Formula(f"C{4 + i}+IF(ISNUMBER(D{4 + i}),D{4 + i},0)"))
            ws.write(3 + i, 5, r.choice([0.06, 0.08, 0.08, "8%", 0.1]))
            ws.write(3 + i, 6, round(lic * 0.08, 2))
        ws.write(4 + len(reps[:18]), 0, "TOTAL", bold)
        ws.write(4 + len(reps[:18]), 4, xlwt.Formula(f"SUM(E4:E{3 + len(reps[:18])})"))
        wb.save(str(sp / f"Commissions_FY{year}{'_FINAL' if year != 2009 else '_final_REVISED_bk'}.xls"))

    wb = xlwt.Workbook(encoding="cp1252")
    ws = wb.add_sheet("Pipeline")
    hdr = ["Account", "Contact", "Est. Seats", "Est. Value", "Stage", "Close", "Notes"]
    for j, h in enumerate(hdr):
        ws.write(0, j, h, bold)
    date_style = xlwt.easyxf(num_format_str="M/D/YY")
    for i, p in enumerate([p for p in world.prospects if date(2009, 1, 1) <= p["created"] < date(2011, 6, 1)][:250]):
        ws.write(1 + i, 0, p["name"].upper() if r.random() < 0.3 else p["name"])
        ws.write(1 + i, 1, f"{r.choice(['Mr.', 'Ms.', ''])} {p['name'].split()[0]}")
        ws.write(1 + i, 2, p["seats"] if r.random() > 0.1 else "~" + str(p["seats"]))
        ws.write(1 + i, 3, p["seats"] * 350)
        ws.write(1 + i, 4, r.choice(["Lead", "Demo", "Proposal", "Verbal", "LOST", "lost", "Closed?"]))
        cd = rand_date(r, p["created"], p["created"] + timedelta(days=180))
        if r.random() < 0.7:
            ws.write(1 + i, 5, datetime(cd.year, cd.month, cd.day), date_style)
        else:
            ws.write(1 + i, 5, cd.strftime(r.choice(["%m/%d/%Y", "%b %Y", "Q%m"])))
        ws.write(1 + i, 6, r.choice(["", "wants cloud", "budget in July", "competitor: UpKeepr", "call back", "see email"]))
    wb.save(str(sp / "Pipeline_2009-2011_bk.xls"))

    # ---------------------------------------------------------------- finance close workbook (xlsx)
    bf = out / "board_and_finance"
    bf.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "ARR bridge"
    ws["A1"] = "FY2019 ARR CLOSE - LIVE ARR (finance definition)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Prepared by Controller. Planning FX: CAD 0.75, GBP 1.27. See FIN/ARR Definitions."
    rows = [("Live ARR 12/31/2018", round(compute_arr(world, date(2018, 12, 31)), 2)),
            ("Live ARR 12/31/2019", f["arr_finance_2019"])]
    for i, (k, v) in enumerate(rows):
        ws.cell(row=4 + i, column=1, value=k)
        ws.cell(row=4 + i, column=2, value=v).number_format = "$#,##0"
    ws["A7"] = "Contracted-not-live is reported by Sales and is EXCLUDED here."
    ws2 = wb.create_sheet("By currency")
    ws2.append(["Currency", "Live ARR (local)", "Planning FX", "Live ARR (USD)"])
    for cur in ("USD", "CAD", "GBP"):
        local = compute_arr(world, date(2019, 12, 31), only=cur)
        ws2.append([cur, round(local, 2), FX_TO_USD[cur], round(local * FX_TO_USD[cur], 2)])
    wb.properties.creator = "idelacroix"
    wb.properties.created = datetime(2020, 1, 14)
    wb.properties.modified = datetime(2020, 1, 21)
    wb.save(bf / "FY2019_ARR_close_finance.xlsx")

    # ---------------------------------------------------------------- board decks
    def deck(path, slides, created):
        prs = Presentation()
        prs.core_properties.author = "Lorraine Whitlock"
        prs.core_properties.created = created
        prs.core_properties.modified = created + timedelta(days=1)
        prs.core_properties.last_modified_by = "Lorraine Whitlock"
        for title, bullets, notes in slides:
            s = prs.slides.add_slide(prs.slide_layouts[1])
            s.shapes.title.text = title
            body = s.placeholders[1].text_frame
            body.text = bullets[0]
            for b in bullets[1:]:
                p = body.add_paragraph()
                p.text = b
            if notes:
                s.notes_slide.notes_text_frame.text = notes
        prs.save(path)

    board = f["arr_board_2019"]
    deck(bf / "Board_Deck_Q4_2019_FINAL.pptx", [
        ("Brindlecove - Q4 2019 Board Update", ["Confidential", "January 28, 2020"], None),
        ("Headline metrics", [f"ARR: ${board / 1e6:.2f}M (contracted)", "Net revenue retention: 104%", "Logo churn (TTM): 9.1%",
                              "Classic sunset on track for June 30, 2020"], "ARR here is contracted ARR incl. signed-not-started per FIN definitions."),
        ("Classic migration", ["Migration credit: 25% for 12 months", "Target: 70% of remaining Classic sites migrated by June"], None),
        ("Meridian (Canada)", ["Billing migrated to v3 in July 2019", "Dispatch attach rate rising in US base"], None),
    ], datetime(2020, 1, 27))
    deck(bf / "Board_Deck_Q4_2019_v6_DRAFT.pptx", [
        ("Brindlecove - Q4 2019 Board Update (DRAFT v6)", ["DRAFT - numbers not final"], None),
        ("Headline metrics", [f"ARR: ${board * 0.987 / 1e6:.2f}M", "NRR: TBD", "Logo churn: 9.4%?"], "waiting on Dec bookings from RevOps"),
    ], datetime(2020, 1, 20))
    deck(bf / "Kestrel_Integration_Plan_2021.pptx", [
        ("Kestrel Analytics - integration plan", ["Closed June 1, 2021", "Leeds, UK - 34 staff"], None),
        ("Day 1 - Day 90", ["Keep Kestrel accounting (GBP) until Q2 2022", "Cross-sell to US Enterprise base"], None),
        ("Project Lantern", ["Lantern = Kestrel's analytics engine relaunched inside Ops Cloud as 'Brindle Insights'",
                             "Pricing: flat monthly fee, GBP 316 / USD 400", "GA target: Q1 2022"], "Codename only - never use externally."),
        ("Risks", ["Two GL systems for 3 quarters", "Duplicate customer records (UK customers already on Ops Cloud)"], None),
    ], datetime(2021, 6, 20))
    for y in (2021, 2023, 2025):
        live = compute_arr(world, date(y, 12, 31))
        deck(bf / f"Board_Deck_Q4_{y}.pptx", [
            (f"Q4 {y} Board Update", ["Confidential"], None),
            ("Headline metrics", [f"ARR: ${live / 1e6:.2f}M", f"Customers: {sum(1 for c in world.customers if c.cloud_start and c.cloud_start <= date(y, 12, 31) and (not c.end or c.end > date(y, 12, 31)))}",
                                  "GBP converted at planning rate 1.27" if y >= 2021 else ""], None),
        ], datetime(y + 1, 1, 25))
    return {}


def compute_arr(world, d, only=None):
    """Live ARR in USD at planning FX (or local currency if `only` is given)."""
    from ..world import ADDON_PRICE
    tot = 0.0
    for c in world.customers:
        if only and c.currency != only:
            continue
        if not c.cloud_start or c.cloud_start > d or (c.end and c.end < d):
            continue
        fx = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}[c.currency]
        seats = c.seats(d)
        mrr = seats * c.unit_price(d) * (1 - c.discount) * fx
        for a in c.addons:
            mrr += ADDON_PRICE[a] * fx * (1 if a == "Insights" else seats)
        tot += mrr * 12 * (1 if only else FX_TO_USD[c.currency])
    return tot
