"""Old office formats: mainframe print-to-file reports, Lotus 1-2-3, a spreadsheet with a hidden sheet, diagrams.

Renders:
  brix_mainframe/reports/AGEDAR_091231.PRN        132-column aged receivables report, page headers, form feeds, subtotals
  brix_mainframe/reports/AGEDAR_100331.PRN        the next quarter's run (decoy for date questions)
  finance_lotus_1997/BUDGET97.WK1                 Lotus 1-2-3 binary worksheet, first draft
  finance_lotus_1997/BUDG97R.WK1                  revised budget, board-approved
  renewals/Q3_2025_renewals_tracker.xlsx          visible summary uses formulas with no cached values; the list is on a hidden sheet
  architecture/billing_architecture_2021.drawio   draw.io file with the diagram deflate+base64 compressed (as draw.io saved it then)
  architecture/platform_2023_aws.drawio           uncompressed XML, after the AWS move
  architecture/dataflow_finance.dot               Graphviz source

Planted:
  GF24  total 90+ days past due on BRIX at 2009-12-31 (from the PRN report, not by summing every number in it)
  GF25  the board-approved FY1997 marketing budget (binary Lotus file, revised version)
  GF26  how many Q3 2025 renewals were flagged at risk and their ARR (hidden sheet)
  GF27  where billing v3's database ran before the AWS move (compressed draw.io)
"""
from __future__ import annotations

import base64
import struct
import zlib
from datetime import date, datetime, timedelta
from urllib.parse import quote

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..util import add_fact, rng_for, write_bytes, write_text
from ..world import ADDON_PRICE

RAW = "data/raw"
FX = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}


# --------------------------------------------------------------------------- PRN aged AR
def aged_ar(world, asof: date):
    rows = []
    for inv in world.invoices:
        if inv.system != "brix" or inv.issued > asof or inv.status == "void":
            continue
        if inv.paid_on and inv.paid_on <= asof:
            continue
        if inv.status == "uncollectible" and inv.issued + timedelta(days=365) <= asof:
            continue        # written off after a year
        if inv.status == "refunded":
            continue
        age = (asof - inv.issued).days
        rows.append((inv, age))
    rows.sort(key=lambda x: (x[0].cust.ids.get("brix", ""), x[0].issued, x[0].seq))
    return rows


def bucket(age):
    return 0 if age <= 30 else 1 if age <= 60 else 2 if age <= 90 else 3


def amt(x):
    return f"{x:>14,.2f}" if x else " " * 14


def prn_report(world, asof: date, run: datetime, r):
    rows = aged_ar(world, asof)
    lines, page, out_pages = [], 0, []
    hdr_cols = (f"{'CUST NO':<8} {'CUSTOMER NAME':<30} {'INVOICE':<8} {'INV DATE':<9} {'DAYS':>5} "
                f"{'CURRENT':>14} {'31-60':>14} {'61-90':>14} {'OVER 90':>14}")

    def header():
        nonlocal page
        page += 1
        return [f"BRXAR040{' ' * 30}BRINDLE DATA SYSTEMS INC{' ' * 30}RUN {run:%m/%d/%y %H.%M}   PAGE {page:>4}",
                f"{' ' * 38}AGED ACCOUNTS RECEIVABLE - DETAIL AS OF {asof:%m/%d/%Y}",
                "", hdr_cols, "-" * 132]

    body = []
    grand = [0.0] * 4
    by_cust = {}
    for inv, age in rows:
        by_cust.setdefault(inv.cust.ids.get("brix", "??????"), []).append((inv, age))
    for cno, items in by_cust.items():
        sub = [0.0] * 4
        for inv, age in items:
            b = bucket(age)
            cols = [0.0] * 4
            cols[b] = inv.total
            sub[b] += inv.total
            body.append(f"{cno:<8} {inv.cust.name.upper()[:30]:<30} {inv.seq % 10 ** 7:07d}  {inv.issued:%m/%d/%y}  {age:>5} "
                        + " ".join(amt(v) for v in cols))
        body.append(f"{'':<8} {'** CUSTOMER TOTAL':<30} {'':<8} {'':<9} {'':>5} " + " ".join(f"{v:>14,.2f}" for v in sub))
        body.append("")
        grand = [g + s for g, s in zip(grand, sub)]
    body.append("=" * 132)
    body.append(f"{'':<8} {'*** REPORT TOTAL':<30} {'':<8} {'':<9} {'':>5} " + " ".join(f"{v:>14,.2f}" for v in grand))
    body.append(f"{'':<8} {'*** TOTAL OUTSTANDING':<30} {'':<8} {'':<9} {'':>5} {sum(grand):>14,.2f}")
    body.append("")
    body.append("END OF REPORT BRXAR040   RECORDS READ " + f"{len(world.invoices) % 100000:>6}" + f"   SELECTED {len(rows):>5}")
    per = 54
    for i in range(0, len(body), per):
        out_pages.append("\r\n".join(header() + body[i:i + per]))
    text = "\x0c" + "\r\n\x0c".join(out_pages) + "\r\n"
    return text, grand, len(rows)


# --------------------------------------------------------------------------- Lotus WK1
def wk1(cells, ncols, nrows) -> bytes:
    """Minimal Lotus 1-2-3 release 2 worksheet: BOF, RANGE, then LABEL/NUMBER cells, EOF."""
    out = struct.pack("<HHH", 0x0000, 2, 0x0406)
    out += struct.pack("<HH4H", 0x0006, 8, 0, 0, ncols - 1, nrows - 1)
    for (col, row), v in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if isinstance(v, str):
            data = struct.pack("<BHH", 0xFF, col, row) + b"'" + v.encode("cp437") + b"\x00"
            out += struct.pack("<HH", 0x000F, len(data)) + data
        elif isinstance(v, int) and -32768 <= v <= 32767:
            out += struct.pack("<HHBHHh", 0x000D, 7, 0xFF, col, row, v)
        else:
            out += struct.pack("<HHBHHd", 0x000E, 13, 0x82, col, row, float(v))
    out += struct.pack("<HH", 0x0001, 0)
    return out


def budget_cells(title, depts, note):
    cells = {(0, 0): title, (0, 1): note, (0, 3): "DEPARTMENT", (1, 3): "Q1", (2, 3): "Q2", (3, 3): "Q3", (4, 3): "Q4", (5, 3): "FY TOTAL"}
    row = 4
    tot = [0.0] * 4
    for name, qs in depts:
        cells[(0, row)] = name
        for i, q in enumerate(qs):
            cells[(1 + i, row)] = float(q)
            tot[i] += q
        cells[(5, row)] = float(sum(qs))
        row += 1
    cells[(0, row + 1)] = "TOTAL"
    for i in range(4):
        cells[(1 + i, row + 1)] = tot[i]
    cells[(5, row + 1)] = sum(tot)
    return cells, row + 2


# --------------------------------------------------------------------------- helpers
def arr_usd(c, d):
    fx = FX[c.currency]
    seats = c.seats(d)
    mrr = seats * c.unit_price(d) * (1 - c.discount) * fx
    for a in c.addons:
        mrr += ADDON_PRICE[a] * fx * (1 if a == "Insights" else seats)
    return round(mrr * 12, 2)


def drawio_compress(xml: str) -> str:
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    raw = co.compress(quote(xml, safe="~()*!.'").encode("ascii")) + co.flush()
    return base64.b64encode(raw).decode("ascii")


def mx(cells):
    parts = ['<mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" '
             'pageScale="1" pageWidth="1169" pageHeight="827" math="0" shadow="0"><root><mxCell id="0"/><mxCell id="1" parent="0"/>']
    for i, (kind, a, b, label, x, y) in enumerate(cells, start=2):
        lab = label.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;").replace("\n", "&lt;br&gt;")
        if kind == "box":
            parts.append(f'<mxCell id="n{a}" value="{lab}" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">'
                         f'<mxGeometry x="{x}" y="{y}" width="180" height="70" as="geometry"/></mxCell>')
        else:
            parts.append(f'<mxCell id="e{i}" value="{lab}" style="edgeStyle=orthogonalEdgeStyle;html=1;" edge="1" parent="1" source="n{a}" target="n{b}">'
                         f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    parts.append("</root></mxGraphModel>")
    return "".join(parts)


def render(world, out, seed):
    r = rng_for(seed, "legacy_office")

    # ----------------------------------------------------------------- GF24 PRN aged AR
    rep = out / "brix_mainframe" / "reports"
    asof = date(2009, 12, 31)
    text, grand, nsel = prn_report(world, asof, datetime(2010, 1, 4, 2, 17), r)
    write_text(rep / "AGEDAR_091231.PRN", text, encoding="ascii", newline="\n")
    text2, grand2, _ = prn_report(world, date(2010, 3, 31), datetime(2010, 4, 2, 2, 11), r)
    write_text(rep / "AGEDAR_100331.PRN", text2, encoding="ascii", newline="\n")
    write_text(rep / "README.TXT", "BRXAR040 REPORTS - PRINT-TO-FILE FROM SPOOL\r\nPULLED OFF THE AS/400 BEFORE DECOMMISSION, HP 4/2012\r\n"
               "132 COL, FORM FEED BETWEEN PAGES. DAYS = DAYS SINCE INVOICE DATE (NOT DUE DATE).\r\n", encoding="ascii", newline="\n")
    add_fact(world, {"id": "GF24", "difficulty": "medium", "kind": "print-to-file report",
                     "question": "How much BRIX receivables were more than 90 days old at the end of 2009?",
                     "answer": f"${grand[3]:,.2f} (the OVER 90 column of the *** REPORT TOTAL line in the 12/31/2009 aged AR run). "
                               f"Total outstanding was ${sum(grand):,.2f}.",
                     "trail": [f"{RAW}/brix_mainframe/reports/AGEDAR_091231.PRN", f"{RAW}/brix_mainframe/reports/README.TXT"],
                     "traps": ["Summing every number in the OVER 90 column double counts the ** CUSTOMER TOTAL lines",
                               "Page headers repeat every 54 lines and pages are split by form feeds",
                               "AGEDAR_100331.PRN is the next quarter's run",
                               "Aging is from invoice date, not due date"],
                     "values": {"over_90": round(grand[3], 2), "total_outstanding": round(sum(grand), 2)}})

    # ----------------------------------------------------------------- GF25 Lotus budget
    lot = out / "finance_lotus_1997"
    depts = [("SALES", 41000), ("MARKETING", 23500), ("DEVELOPMENT", 88000), ("SUPPORT", 31000), ("G&A", 27500), ("FACILITIES", 12750)]
    draft, revised = [], []
    for name, base in depts:
        qs = [round(base * r.uniform(0.9, 1.1), -2) for _ in range(4)]
        draft.append((name, qs))
        if name == "MARKETING":
            qs = [round(q * 0.8, -2) for q in qs]   # board cut marketing 20%
        revised.append((name, qs))
    c1, n1 = budget_cells("BRINDLE DATA SYSTEMS - FY1997 OPERATING BUDGET (DRAFT 1)", draft, "")
    c1[(0, 1)] = "PREPARED D.F. 11/18/96 - FOR DISCUSSION"
    write_bytes(lot / "BUDGET97.WK1", wk1(c1, 6, n1))
    c2, n2 = budget_cells("BRINDLE DATA SYSTEMS - FY1997 OPERATING BUDGET (REVISED)", revised, "")
    c2[(0, 1)] = "APPROVED BY BOARD 2/20/97 - MKTG REDUCED PER M.O-H."
    write_bytes(lot / "BUDG97R.WK1", wk1(c2, 6, n2))
    mk_draft = sum(dict(draft)["MARKETING"])
    mk_final = sum(dict(revised)["MARKETING"])
    add_fact(world, {"id": "GF25", "difficulty": "medium", "kind": "binary legacy spreadsheet",
                     "question": "What was the board-approved FY1997 marketing budget?",
                     "answer": f"${mk_final:,.0f}, from the revised Lotus 1-2-3 file BUDG97R.WK1 ('APPROVED BY BOARD 2/20/97'). "
                               f"The first draft BUDGET97.WK1 had ${mk_draft:,.0f}.",
                     "trail": [f"{RAW}/finance_lotus_1997/BUDG97R.WK1"],
                     "traps": ["BUDGET97.WK1 is the draft", "WK1 is binary: record type, length, then cells (labels start with an apostrophe)"],
                     "values": {"marketing_fy1997": mk_final, "draft": mk_draft}})

    # ----------------------------------------------------------------- GF26 hidden sheet
    q_start, q_end = date(2025, 7, 1), date(2025, 9, 30)
    pool = [c for c in world.customers if c.cloud_start and c.currency == "USD" and c.cloud_start <= q_start
            and (c.end is None or c.end > q_end) and c.cloud_start.month in (7, 8, 9) and c.seats(q_start) >= 40]
    pool.sort(key=lambda c: (c.cloud_start.month, c.cloud_start.day, c.name))
    at_risk = [c for c in pool if c.end and c.end <= date(2026, 10, 31)]
    people = {p.pid: p for p in world.people}
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Q3 2025 Renewals - US book (seats >= 40)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A3"], ws["B3"] = "Renewals in quarter", "=COUNTA(Renewals!A2:A1000)"
    ws["A4"], ws["B4"] = "Renewal ARR (USD)", "=SUM(Renewals!E2:E1000)"
    ws["A5"], ws["B5"] = "At-risk accounts", "=COUNTA(at_risk!A2:A1000)"
    ws["A6"], ws["B6"] = "At-risk ARR (USD)", "=SUM(at_risk!D2:D1000)"
    ws["A8"] = "At-risk list is restricted - ask Priya. Do not forward outside CS leadership."
    ws["A8"].font = Font(italic=True, color="C00000")
    ren = wb.create_sheet("Renewals")
    ren.append(["Account", "Renewal date", "CSM", "Seats", "ARR (USD)", "Status"])
    for c in pool:
        ren.append([c.name, date(2025, c.cloud_start.month, min(c.cloud_start.day, 28)), people.get(c.csm).name if c.csm in people else "",
                    c.seats(q_start), arr_usd(c, q_start), r.choice(["Committed", "Verbal", "In progress", "Not started", ""])])
    for row in ren.iter_rows(min_row=2, min_col=2, max_col=2):
        for cell in row:
            cell.number_format = "m/d/yyyy"
    hid = wb.create_sheet("at_risk")
    hid.append(["Account", "Risk reason", "CSM", "ARR (USD)", "Exec sponsor engaged?"])
    for c in at_risk:
        hid.append([c.name, r.choice(["Budget cut", "Champion left", "Evaluating " + r.choice(["Plinthwise", "Corbelry", "Tessaroo"]),
                                      "Low usage", "M&A"]), people.get(c.csm).name if c.csm in people else "", arr_usd(c, q_start),
                    r.choice(["Y", "N", "N", "?"])])
    hid.sheet_state = "hidden"
    hid["G1"].fill = PatternFill("solid", fgColor="FFFF00")
    piv = wb.create_sheet("Pivot (old)")
    piv.append(["Row Labels", "Count of Account", "Sum of ARR (USD)"])
    stale = r.sample(pool, max(1, len(pool) * 2 // 3))
    for st in ("Committed", "Verbal", "In progress", "Not started"):
        sub = r.sample(stale, max(1, len(stale) // 4))
        piv.append([st, len(sub), round(sum(arr_usd(c, date(2025, 6, 1)) for c in sub), 2)])
    piv.append(["Grand Total", None, None])
    piv["A9"] = "refreshed 6/2/2025 - stale, do not use"
    wb.properties.creator = "praghunathan"
    wb.properties.created = datetime(2025, 6, 2, 13, 40)
    wb.properties.modified = datetime(2025, 7, 9, 16, 5)
    p = out / "renewals" / "Q3_2025_renewals_tracker.xlsx"
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(p)
    risk_arr = round(sum(arr_usd(c, q_start) for c in at_risk), 2)
    add_fact(world, {"id": "GF26", "difficulty": "hard", "kind": "hidden sheet",
                     "question": "How many Q3 2025 renewals (US book, 40+ seats) were flagged at risk, and how much ARR did they carry?",
                     "answer": f"{len(at_risk)} accounts with ${risk_arr:,.2f} ARR. The list is on the hidden sheet 'at_risk'; the Summary "
                               f"cells are formulas with no cached values, and the 'Pivot (old)' sheet is a stale June refresh.",
                     "trail": [f"{RAW}/renewals/Q3_2025_renewals_tracker.xlsx (hidden sheet at_risk)"],
                     "traps": ["Reading with data_only=True returns None for the Summary formulas",
                               "The 'Pivot (old)' sheet has stale counts", "The at_risk sheet is hidden"],
                     "values": {"count": len(at_risk), "arr_usd": risk_arr, "accounts": [c.name for c in at_risk]}})

    # ----------------------------------------------------------------- GF27 diagrams
    arch = out / "architecture"
    old = mx([("box", 1, 0, "Customers (web + mobile)", 40, 40), ("box", 2, 0, "app-web01..04\nnginx + Java 8", 300, 40),
              ("box", 3, 0, "billing-svc (v3)\nPython 3.6", 300, 180), ("box", 4, 0, "billing-db01\nMySQL 5.7 (primary)\nCobalt Ridge colo, cage 14", 560, 180),
              ("box", 5, 0, "billing-db02\nMySQL 5.7 (replica)\nCobalt Ridge colo, cage 14", 560, 320),
              ("box", 6, 0, "NetSuite (SaaS)\nnightly GL export", 300, 320), ("box", 7, 0, "ops-db (Postgres 9.6)\ncage 14", 820, 40),
              ("edge", 1, 2, "HTTPS", 0, 0), ("edge", 2, 3, "REST", 0, 0), ("edge", 3, 4, "JDBC/TLS", 0, 0),
              ("edge", 4, 5, "async replication", 0, 0), ("edge", 3, 6, "CSV via SFTP 02:00 ET", 0, 0), ("edge", 2, 7, "", 0, 0)])
    drawio_old = (f'<mxfile host="app.diagrams.net" modified="2021-03-09T15:22:41.118Z" agent="5.0 (Windows)" etag="{r.getrandbits(64):x}" '
                  f'version="14.4.3" type="device"><diagram id="{r.getrandbits(48):x}" name="Billing - current state">'
                  f'{drawio_compress(old)}</diagram></mxfile>')
    write_text(arch / "billing_architecture_2021.drawio", drawio_old)
    new = mx([("box", 1, 0, "Customers", 40, 40), ("box", 2, 0, "ALB -> EKS (ops-web)", 300, 40),
              ("box", 3, 0, "billing-svc (v3) on EKS", 300, 180), ("box", 4, 0, "RDS PostgreSQL 14\nbilling-prod (Multi-AZ)", 560, 180),
              ("box", 5, 0, "S3 data lake\ns3://bc-lake-prod", 560, 320), ("box", 6, 0, "NetSuite", 300, 320),
              ("edge", 1, 2, "HTTPS", 0, 0), ("edge", 2, 3, "gRPC", 0, 0), ("edge", 3, 4, "", 0, 0),
              ("edge", 4, 5, "Debezium CDC -> Avro", 0, 0), ("edge", 3, 6, "SuiteTalk API", 0, 0)])
    write_text(arch / "platform_2023_aws.drawio",
               f'<mxfile host="app.diagrams.net" modified="2023-03-01T10:04:12.551Z" agent="5.0 (Macintosh)" version="20.8.16" type="device">'
               f'<diagram id="{r.getrandbits(48):x}" name="Platform after AWS move">{new}</diagram></mxfile>')
    write_text(arch / "dataflow_finance.dot", """// finance data flow, hand-maintained by F. Adeyemi. last touched 2022-11
digraph finance {
  rankdir=LR; node [shape=box, fontname="Helvetica"];
  billing_v3 -> netsuite [label="nightly GL"];
  ledger_mysql -> billing_v3 [label="2017 one-time import\\n(amounts in DOLLARS)"];
  meridian_sage -> netsuite [label="until 2019-07"];
  kestrel_xero -> netsuite [label="until 2022-04", style=dashed];
  salesforce -> board_deck [label="contracted ARR"];
  billing_v3 -> finance_arr_xlsx [label="live ARR"];
  // TODO: tallyflow? (QuickBooks, never integrated)
}
""")
    add_fact(world, {"id": "GF27", "difficulty": "medium", "kind": "compressed diagram",
                     "question": "Before the February 2023 AWS move, where did the billing v3 database run?",
                     "answer": "On billing-db01, MySQL 5.7, with a replica billing-db02, both in the Cobalt Ridge colocation facility (cage 14). "
                               "After the move it is RDS PostgreSQL 14.",
                     "trail": [f"{RAW}/architecture/billing_architecture_2021.drawio (diagram body is deflate + base64 + URL-encoded)",
                               f"{RAW}/architecture/platform_2023_aws.drawio"],
                     "traps": ["The 2021 diagram body is compressed, so a text search finds nothing",
                               "The 2023 diagram shows the new state only"],
                     "values": {"server": "billing-db01", "engine": "MySQL 5.7", "site": "Cobalt Ridge"}})
    return {}
