"""Image-only records: faxes, phone photos, handwritten notes, receipts.

Renders:
  fax_server/inbound/FAX_<YYYYMMDD>_<HHMMSS>_<sender>.tif   multi-page 1-bit TIFF, CCITT Group 4, fax header line, skew, speckle
  fax_server/fax_log.txt                                    the fax server's own log (fixed width)
  photos/whiteboard/IMG_<n>.jpg                             phone photos of whiteboards with EXIF dates
  scans/handwritten/*.png                                   scanned handwritten meeting notes
  expenses/receipts/*.jpg                                   photographed receipts with EXIF

Planted:
  GF20  a government customer's new fiscal-year PO number exists only in a faxed TIFF
  GF21  the original AWS cutover date exists only on a whiteboard photo
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..util import AS_OF, add_fact, rand_date, rng_for, write_bytes, write_text

RAW = "data/raw"


def _font(size, kind="mono"):
    paths = {"mono": ["/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"],
             "sans": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
             "hand": ["/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]}[kind]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fax_pages(r, header, pages):
    out = []
    f, fh = _font(30), _font(22)
    for i, text in enumerate(pages, 1):
        img = Image.new("L", (1728, 2200), 255)
        d = ImageDraw.Draw(img)
        d.text((40, 12), header.replace("{p}", f"{i:03d}/{len(pages):03d}"), fill=0, font=fh)
        y = 120
        for line in text.split("\n"):
            d.text((150 + r.randint(-3, 3), y), line, fill=r.randint(0, 40), font=f)
            y += 46
        for _ in range(5000):
            img.putpixel((r.randint(0, 1727), r.randint(0, 2199)), 0)
        for _ in range(r.randint(0, 3)):          # vertical streak from a dirty scanner glass
            x = r.randint(100, 1600)
            d.line((x, 0, x + r.randint(-4, 4), 2199), fill=r.randint(60, 140), width=1)
        img = img.rotate(r.uniform(-1.2, 1.2), fillcolor=255, resample=Image.BICUBIC)
        img = img.point(lambda v: 0 if v < 150 else 255).convert("1")
        out.append(img)
    buf = io.BytesIO()
    out[0].save(buf, "TIFF", compression="group4", save_all=True, append_images=out[1:], dpi=(204, 196))
    return buf.getvalue()


def exif_bytes(when: datetime, make="Apple", model="iPhone 12"):
    ex = Image.Exif()
    ex[0x010F] = make
    ex[0x0110] = model
    ex[0x0132] = when.strftime("%Y:%m:%d %H:%M:%S")
    ex[0x0131] = "16.2"
    ex.get_ifd(0x8769)[0x9003] = when.strftime("%Y:%m:%d %H:%M:%S")
    return ex.tobytes()


def handwriting(r, img, x, y, text, size, color):
    d = ImageDraw.Draw(img)
    f = _font(size, "hand")
    cx = x
    for ch in text:
        d.text((cx, y + r.randint(-3, 3)), ch, fill=color, font=f)
        cx += int(f.getlength(ch) * r.uniform(0.92, 1.12))
    return cx


def render(world, out, seed):
    r = rng_for(seed, "imaging")
    g = world.golden
    fax = out / "fax_server" / "inbound"
    log = ["DATE       TIME     CSID                 PAGES  STATUS   FILE"]
    gov = [c for c in world.customers if c.industry in ("Government", "Education", "Healthcare")]

    def send(d, hh, csid, sender_short, pages, title):
        hdr = f"{d:%b-%d-%Y}".upper() + f" {hh[:2]}:{hh[2:4]}  FROM:{csid:<22} TO:19375550100   P.{{p}}"
        name = f"FAX_{d:%Y%m%d}_{hh}_{sender_short}.tif"
        write_bytes(fax / name, fax_pages(r, hdr, pages))
        log.append(f"{d:%Y-%m-%d} {hh[:2]}:{hh[2:4]}:{hh[4:]} {csid[:20]:<20} {len(pages):>5}  OK       {name}")

    for k in range(46):
        d = rand_date(r, date(2004, 1, 5), date(2019, 12, 20))
        c = r.choice(gov)
        kind = r.choice(["PURCHASE ORDER", "CREDIT APPLICATION", "SIGNED RENEWAL", "TAX EXEMPTION CERTIFICATE", "REMITTANCE ADVICE"])
        body = (f"{c.name.upper()}\n{c.city.upper()}, {c.region}\n\n{kind}\n\nVENDOR: BRINDLE DATA SYSTEMS / BRINDLECOVE\nDATE: {d:%m/%d/%Y}\n\n"
                f"REF: {r.randint(10000, 99999)}\nAMOUNT: ${r.randint(800, 60000):,}.00\n\nAUTHORIZED SIGNATURE: ____________\n")
        send(d, f"{r.randint(8, 17):02d}{r.randint(0, 59):02d}{r.randint(0, 59):02d}", c.name.upper()[:20],
             re.sub(r"[^A-Za-z]", "", c.name)[:12], [body] + (["PAGE 2 OF 2\n\nTERMS AND CONDITIONS ON FILE"] if r.random() < 0.4 else []), kind)

    # ---------------------------------------------------------------- GF20: new FY PO, fax only
    tc = g["sunset_migrator"]
    edi_old = None
    edi_dir = out / "integrations" / "edi"
    if edi_dir.exists():
        for p in sorted(edi_dir.glob(f"850_{tc.ids.get('netsuite', 'x')}_*.edi")):
            m = re.search(r"BEG\*00\*SA\*(PO\d+)", p.read_text())
            edi_old = m.group(1) if m else None
    new_po = f"TC-21-{r.randint(1000, 9999)}"
    d20 = date(2020, 7, 6)
    seats = tc.seats(date(2020, 7, 1))
    pages = [f"TRI-COUNTY PUBLIC WORKS\nPURCHASING DIVISION\n\nPURCHASE ORDER   {new_po}\nFISCAL YEAR 2021 (07/01/2020 - 06/30/2021)\n\n"
             f"VENDOR: BRINDLECOVE SOFTWARE INC\n\nDESCRIPTION: OPS CLOUD SUBSCRIPTION, {seats} USERS\n"
             f"REPLACES PO {edi_old or 'FY20 BLANKET'} (EXPIRED 06/30/2020)\n\nALL INVOICES MUST REFERENCE THIS PO NUMBER\nOR THEY WILL BE RETURNED UNPAID.\n\n"
             f"BUYER: {tc.contacts[0].name.upper()}",
             "STANDARD TERMS\n\nNET 45. TAX EXEMPT, CERT ON FILE.\nSHIP TO: N/A (SOFTWARE)\n\nPAGE 2 OF 2"]
    send(d20, "103315", "TRI CO PW PURCHASING", "TRICOPW", pages, "PO")
    log.sort()
    write_text(out / "fax_server" / "fax_log.txt", "\r\n".join(log) + "\r\n", encoding="ascii")
    add_fact(world, {"id": "GF20", "difficulty": "hard", "kind": "fax-image",
                     "question": "Which purchase order number must Tri-County Public Works' invoices quote from July 2020?",
                     "answer": f"{new_po}, their fiscal-year 2021 PO, faxed on {d20:%B %d, %Y}. It replaces the EDI purchase order "
                               f"{edi_old or '(FY20)'} that expired on June 30, 2020. The fax is an image-only TIFF, so the number has to be read with OCR.",
                     "trail": [f"{RAW}/fax_server/inbound/FAX_{d20:%Y%m%d}_103315_TRICOPW.tif (CCITT G4 TIFF, 2 pages)", f"{RAW}/fax_server/fax_log.txt",
                               f"{RAW}/integrations/edi/ (850 with the old PO)"],
                     "traps": ["The EDI 850 carries an older PO number"],
                     "values": {"po_number": new_po, "old_po": edi_old}})

    # ---------------------------------------------------------------- GF21: whiteboard photo
    def whiteboard(lines, when, name, strike=None):
        img = Image.new("RGB", (1600, 1200), (236, 238, 234))
        d = ImageDraw.Draw(img)
        for i in range(1200):             # glare from a ceiling light
            v = int(18 * (1 - abs(i - 300) / 900))
            d.line((0, i, 1599, i), fill=(236 + max(v, 0) // 2, 238 + max(v, 0) // 2, 234 + max(v, 0) // 2))
        d.rectangle((0, 0, 1599, 40), fill=(150, 150, 152))
        d.rectangle((0, 1150, 1599, 1199), fill=(120, 118, 115))
        y = 90
        for text, color, size in lines:
            end = handwriting(r, img, 80 + r.randint(-10, 10), y, text, size, color)
            if strike and strike in text:
                f = _font(size, "hand")
                sx = 80 + int(f.getlength(text[:text.index(strike)]))
                ImageDraw.Draw(img).line((sx, y + size // 2, sx + int(f.getlength(strike)), y + size // 2 + 4), fill=color, width=6)
            y += int(size * 1.45)
        img = img.rotate(r.uniform(-3, 3), fillcolor=(90, 90, 92), resample=Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.1))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=72, exif=exif_bytes(when))
        write_bytes(out / "photos" / "whiteboard" / name, buf.getvalue())

    blue, red, black, green = (30, 60, 160), (190, 30, 30), (25, 25, 25), (20, 120, 50)
    whiteboard([("AWS MIGRATION - WAR ROOM", black, 64), ("CUTOVER: SAT 2/11  2/18", red, 70), ("(2/11 moved - payroll run + Q4 close)", red, 44),
                ("DNS TTL -> 60s by 2/14", blue, 50), ("Freeze: 2/13 - 2/20", blue, 50), ("Rollback owner: Callum", green, 50),
                ("DB snapshot T-2h, verify row counts", black, 46)], datetime(2023, 2, 6, 15, 22, 10), "IMG_4471.jpg", strike="2/11  ")
    topics = [["SPRINT 41 GOALS", "offline sync v2", "fix dup invoices", "Lantern SSO"], ["Q3 PIPELINE", "commit 1.9M", "best case 2.4M", "slip: 3 gov deals"],
              ["CS TOP ISSUES", "mobile sync", "SSO", "invoice confusion", "Dispatch rates"], ["ONCALL ROTA", "wk1 Callum", "wk2 Priya?", "wk3 ???"]]
    for k in range(14):
        when = datetime.combine(rand_date(r, date(2018, 1, 8), AS_OF), datetime.min.time()) + timedelta(hours=r.randint(9, 17), minutes=r.randint(0, 59))
        t = r.choice(topics)
        whiteboard([(t[0], black, 64)] + [(x, r.choice([blue, red, green, black]), 52) for x in t[1:]], when, f"IMG_{r.randint(1000, 9999)}.jpg")
    add_fact(world, {"id": "GF21", "difficulty": "medium", "kind": "photo-image",
                     "question": "What was the original planned date for the AWS cutover, and why did it move?",
                     "answer": "Saturday February 11, 2023, crossed out on the war-room whiteboard and moved to February 18 because of the payroll run "
                               "and Q4 close. The cutover happened on February 18 (app logs switch hosts that day).",
                     "trail": [f"{RAW}/photos/whiteboard/IMG_4471.jpg (EXIF date 2023-02-06)", f"{RAW}/app_logs/app-2023-02-18.ip-10-20-3-17.log.gz"],
                     "traps": ["Only the photo shows the original date"],
                     "values": {"planned": "2023-02-11", "actual": "2023-02-18"}})

    # ---------------------------------------------------------------- handwritten notes scans
    notes = [["Call w/ Calloway", "- renewal ok", "- wants 3yr term?", "- ask Ines re: discount"], ["1:1 Jae-won", "- hiring tier 2", "- backlog 140", "- SLA misses x3"],
             ["Board prep", "- ARR bridge", "- churn slide", "- Lantern update"], ["Pricing cttee", "- Starter +$3?", "- grandfather to 2024", "- check CAD"]]
    for k in range(24):
        img = Image.new("L", (1275, 1650), 252)
        d = ImageDraw.Draw(img)
        for y in range(160, 1650, 52):
            d.line((60, y, 1215, y), fill=205, width=1)
        d.line((150, 0, 150, 1650), fill=180, width=2)
        y = 120
        for line in r.choice(notes):
            handwriting(r, img, 175, y, line, 42, r.randint(20, 70))
            y += 104
        img = img.filter(ImageFilter.GaussianBlur(0.7))
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=False)
        write_bytes(out / "scans" / "handwritten" / f"scan_{rand_date(r, date(2012, 1, 1), AS_OF):%Y%m%d}_{k:02d}.png", buf.getvalue())

    # ---------------------------------------------------------------- receipts
    vendors = [("COBALT RIDGE DINER", 18, 140), ("SKYPORT PARKING", 12, 60), ("RIVERSIDE TAXI CO", 15, 90), ("HOTEL LINDQUIST", 140, 480), ("OFFICE DEPOT-ISH SUPPLY", 9, 220)]
    for k in range(60):
        v, lo, hi = r.choice(vendors)
        when = datetime.combine(rand_date(r, date(2016, 1, 1), AS_OF), datetime.min.time()) + timedelta(hours=r.randint(7, 22), minutes=r.randint(0, 59))
        amt = round(r.uniform(lo, hi), 2)
        img = Image.new("RGB", (600, 1000), (205, 200, 190))
        paper = Image.new("RGB", (420, 880), (248, 247, 242))
        d = ImageDraw.Draw(paper)
        f = _font(22)
        lines = [v, f"{when:%m/%d/%Y %H:%M}", "-" * 26] + [f"ITEM {i + 1:<12}{amt / 3:>8.2f}" for i in range(3)] + ["-" * 26, f"TOTAL{amt:>20.2f}", "VISA ****" + f"{r.randint(1000, 9999)}", "", "THANK YOU"]
        for i, t in enumerate(lines):
            d.text((24, 30 + i * 34), t, fill=(40, 40, 40), font=f)
        paper = paper.rotate(r.uniform(-6, 6), expand=True, fillcolor=(205, 200, 190))
        img.paste(paper, (40, 40))
        buf = io.BytesIO()
        img.filter(ImageFilter.GaussianBlur(0.8)).save(buf, "JPEG", quality=65, exif=exif_bytes(when, "samsung", "SM-G991U"))
        write_bytes(out / "expenses" / "receipts" / f"receipt_{when:%Y%m%d_%H%M}_{k:02d}.jpg", buf.getvalue())
    return {}
