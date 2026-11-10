"""BRIX: the 1994-2011 COBOL billing system on the midrange box.

Renders:
  brix_mainframe/BRXCUST.CPY, BRXINV.CPY   copybooks (the only schema docs)
  brix_mainframe/BRXCUST.TXT                customer master, FTP'd in ASCII mode (zoned overpunch signs)
  brix_mainframe/BRXINV.Y1996 ... Y2011     invoice history, raw EBCDIC (cp037), RECFM=FB LRECL=80,
                                            packed-decimal (COMP-3) amounts, CYYMMDD dates, no newlines
  brix_mainframe/README.TXT, EXPORT.JCL     operator notes from 2011
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from ..util import rng_for, write_bytes, write_text
from ..world import ERA

CPY_CUST = """      *================================================================*
      *  BRXCUST  -  BRINDLE DATA SYSTEMS CUSTOMER MASTER                *
      *  LAST CHANGED 03/14/97 HP  (ADDED CREDIT-LIMIT)                  *
      *  RECFM=FB LRECL=150                                              *
      *================================================================*
       01  BRX-CUST-REC.
           05  CUST-NO                 PIC 9(6).
           05  CUST-NAME               PIC X(40).
           05  CUST-ADDR1              PIC X(30).
           05  CUST-CITY               PIC X(20).
           05  CUST-STATE              PIC X(2).
           05  CUST-ZIP                PIC 9(5).
           05  CUST-PHONE              PIC X(12).
           05  CUST-STATUS             PIC X(1).
               88  CUST-ACTIVE                 VALUE 'A'.
               88  CUST-INACTIVE               VALUE 'I'.
               88  CUST-SUSPENDED              VALUE 'S'.
           05  CUST-OPEN-DATE          PIC 9(7).
      *        CYYMMDD  C=0 FOR 19XX, C=1 FOR 20XX
           05  CUST-CREDIT-LIMIT       PIC S9(7)V99.
           05  CUST-BALANCE            PIC S9(7)V99.
           05  CUST-REP                PIC X(3).
           05  FILLER                  PIC X(6).
"""

CPY_INV = """      *================================================================*
      *  BRXINV  -  INVOICE HISTORY  (ONE FILE PER CALENDAR YEAR)        *
      *  RECFM=FB LRECL=80   TRANSFER IN BINARY MODE ONLY !!!            *
      *  Y2K REMEDIATION 11/99 - DATES NOW CYYMMDD  (HP)                 *
      *================================================================*
       01  BRX-INV-REC.
           05  INV-REC-TYPE            PIC X(1).
               88  INV-IS-INVOICE              VALUE 'I'.
               88  INV-IS-CREDIT               VALUE 'C'.
               88  INV-IS-TRAILER              VALUE 'T'.
           05  INV-CUST-NO             PIC 9(6).
           05  INV-NO                  PIC 9(8).
           05  INV-DATE                PIC 9(7).
           05  INV-PERIOD-END          PIC 9(7).
           05  INV-DESC                PIC X(30).
           05  INV-AMT                 PIC S9(9)V99 COMP-3.
           05  INV-TAX                 PIC S9(7)V99 COMP-3.
           05  INV-STATUS              PIC X(1).
      *        P=PAID  O=OPEN  V=VOID  W=WRITTEN OFF
           05  INV-PAID-DATE           PIC 9(7).
           05  FILLER                  PIC X(2).
      *  TRAILER: INV-CUST-NO=999999, INV-NO=RECORD COUNT,
      *           INV-AMT=SUM OF INV-AMT FOR THE FILE
"""

README = """BRIX EXPORT - READ ME FIRST
===========================
Written by H. Penhallow, Mainframe Ops, 06/2011, before the box goes away.

These are the final extracts from BRIX (Brindle Recurring Invoicing eXchange)
before billing moves to the new Ledger system on 7/1/2011.

* BRXCUST.TXT  - customer master. I pulled this one with FTP in ASCII
                 mode so you can read it in Notepad. Signed numbers come
                 out with the sign punched into the last digit, e.g.
                 0001234{ = +123.40   0001234} = -123.40
                 Status A=active I=inactive S=suspended (credit hold).
* BRXINV.Yyyyy - invoice history, one file per year. These are BINARY
                 (EBCDIC, packed decimal). Do NOT open in Notepad and
                 save, you will wreck them. Use the copybook BRXINV.CPY.
                 1994 and 1995 are not here - those tapes would not read.
* Dates are CYYMMDD. C=0 means 1900s, C=1 means 2000s.
  Some January 2000 rows went out before the Y2K patch was applied to
  the late-fee job and have C=0. They are really 2000. Sorry.
* Sales tax was only charged on licenses shipped to Ohio addresses.

Questions -> Harold x214 (until 3/2012)
"""

JCL = """//BRXEXP   JOB (ACCT),'BRIX EXTRACT',CLASS=A,MSGCLASS=X,NOTIFY=&SYSUID
//*  NIGHTLY EXTRACT - DISABLED 07/01/2011
//STEP010  EXEC PGM=BRXX010
//STEPLIB  DD DSN=BRINDLE.PROD.LOADLIB,DISP=SHR
//CUSTIN   DD DSN=BRINDLE.PROD.BRXCUST,DISP=SHR
//INVIN    DD DSN=BRINDLE.PROD.BRXINV,DISP=SHR
//CUSTOUT  DD DSN=BRINDLE.EXTR.BRXCUST(+1),DISP=(NEW,CATLG),
//            DCB=(RECFM=FB,LRECL=150,BLKSIZE=27900)
//INVOUT   DD DSN=BRINDLE.EXTR.BRXINV(+1),DISP=(NEW,CATLG),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=27920)
//SYSOUT   DD SYSOUT=*
"""

OVERPUNCH_POS = "{ABCDEFGHI"
OVERPUNCH_NEG = "}JKLMNOPQR"


def overpunch(value: float, digits: int) -> str:
    cents = int(round(abs(value) * 100))
    s = f"{cents:0{digits}d}"[-digits:]
    last = int(s[-1])
    ch = (OVERPUNCH_NEG if value < 0 else OVERPUNCH_POS)[last]
    return s[:-1] + ch


def packed(value: float, digits: int) -> bytes:
    """COMP-3: two digits per byte, sign nibble C (+) or D (-) in the last byte."""
    cents = int(round(abs(value) * 100))
    s = f"{cents:0{digits}d}"[-digits:]
    if len(s) % 2 == 0:
        s = "0" + s
    nibbles = [int(ch) for ch in s] + [0xD if value < 0 else 0xC]
    return bytes((nibbles[i] << 4) | nibbles[i + 1] for i in range(0, len(nibbles), 2))


def cyymmdd(d: date | None, force_c=None) -> str:
    if d is None:
        return "0000000"
    c = (1 if d.year >= 2000 else 0) if force_c is None else force_c
    return f"{c}{d.year % 100:02d}{d.month:02d}{d.day:02d}"


def ebc(s: str, n: int) -> bytes:
    return s.upper()[:n].ljust(n).encode("cp037")


def render(world, out, seed):
    r = rng_for(seed, "brix")
    base = out / "brix_mainframe"
    write_text(base / "BRXCUST.CPY", CPY_CUST)
    write_text(base / "BRXINV.CPY", CPY_INV)
    write_text(base / "README.TXT", README, encoding="cp1252", newline="\r\n")
    write_text(base / "EXPORT.JCL", JCL)

    reps = {p.pid: (p.first[0] + p.last[0] + p.last[1]).upper() for p in world.people}
    classic = [c for c in world.customers if "brix" in c.ids]
    golden = world.golden
    open_bal = defaultdict(float)
    for inv in world.invoices:
        if inv.system == "brix" and inv.status == "open":
            open_bal[inv.cust.key] += inv.total

    # ---- customer master (ASCII, newline-terminated, overpunched signs)
    lines = []
    for c in sorted(classic, key=lambda c: c.ids["brix"]):
        if c.first_seen > ERA["ledger_start"]:
            continue
        if c.cloud_start and c.cloud_start <= ERA["ledger_start"]:
            status = "X"                     # migrated to Ledger - NOT in the copybook's 88-levels
        elif c.end and c.end < ERA["ledger_start"]:
            status = "I"
        else:
            status = r.choices(["A", "S"], [94, 6])[0]
        if c is golden["calloway"]:
            status = "X"
        name = c.name.upper().replace("’", "'")
        if r.random() < 0.04:
            name = name.replace(" CO.", " COMPANY").replace(" INC.", "")
        addr = f"{r.randint(10, 9999)} {r.choice(['MAIN', 'OAK', 'INDUSTRIAL', 'COMMERCE', 'RIVER', 'MARKET', 'HIGH'])} {r.choice(['ST', 'AVE', 'BLVD', 'PKWY', 'RD', 'DR'])}"
        rec = (
            c.ids["brix"].rjust(6, "0")
            + name[:40].ljust(40)
            + addr[:30].ljust(30)
            + c.city.upper()[:20].ljust(20)
            + c.region[:2].ljust(2)
            + f"{r.randint(43001, 45999):05d}"
            + (f"{r.randint(200, 989)}-555-{r.randint(100, 199):04d}" if r.random() > 0.05 else " " * 12)
            + status
            + cyymmdd(c.first_seen)
            + overpunch(r.choice([5000, 10000, 25000, 50000, 0]), 9)
            + overpunch(round(open_bal.get(c.key, 0.0) - (r.choice([0, 0, 0, 125.5, 980.0]) if r.random() < 0.05 else 0), 2), 9)
            + reps.get(c.owner, "HSE")
            + " " * 6
        )
        assert len(rec) == 150, len(rec)
        lines.append(rec)
    write_text(base / "BRXCUST.TXT", "\n".join(lines) + "\n", encoding="ascii", newline="\r\n")

    # ---- invoice history (binary EBCDIC with packed decimals)
    by_year = defaultdict(list)
    for inv in world.invoices:
        if inv.system != "brix" or inv.issued < ERA["brix_readable_from"]:
            continue
        by_year[inv.issued.year].append(inv)
    inv_no = 70000000
    for year in sorted(by_year):
        recs = []
        total = 0.0
        for inv in by_year[year]:
            inv_no += r.randint(1, 3)
            amt = inv.total
            tax = round(amt * 0.06, 2) if ("LICENSE" in inv.lines[0][0] and inv.cust.region == "OH") else 0.0
            status = {"paid": "P", "open": "O", "void": "V", "uncollectible": "W", "refunded": "P"}[inv.status]
            force_c = 0 if (inv.issued.year == 2000 and inv.issued.month == 1 and r.random() < 0.35) else None
            desc = inv.lines[0][0]
            rec = (ebc("I", 1) + ebc(inv.cust.ids["brix"], 6) + ebc(f"{inv_no:08d}", 8)
                   + ebc(cyymmdd(inv.issued, force_c), 7) + ebc(cyymmdd(inv.period_end, force_c), 7)
                   + ebc(desc, 30) + packed(amt, 11) + packed(tax, 9)
                   + ebc(status, 1) + ebc(cyymmdd(inv.paid_on) if inv.paid_on else "0000000", 7) + b"\x00\x00")
            # FILLER is LOW-VALUES (binary zeros), not spaces
            assert len(rec) == 80, len(rec)
            recs.append(rec)
            total += amt
            if inv.status == "refunded":
                inv_no += 1
                rec = (ebc("C", 1) + ebc(inv.cust.ids["brix"], 6) + ebc(f"{inv_no:08d}", 8)
                       + ebc(cyymmdd(inv.paid_on), 7) + ebc(cyymmdd(inv.paid_on), 7)
                       + ebc("CREDIT MEMO - REFUND", 30) + packed(-amt, 11) + packed(-tax, 9)
                       + ebc("P", 1) + ebc(cyymmdd(inv.paid_on), 7) + b"\x00\x00")
                recs.append(rec)
                total -= amt
        trailer = (ebc("T", 1) + ebc("999999", 6) + ebc(f"{len(recs):08d}", 8) + ebc(cyymmdd(date(year, 12, 31)), 7)
                   + ebc("0000000", 7) + ebc(f"TRAILER {year}", 30) + packed(round(total, 2), 11) + packed(0, 9)
                   + ebc(" ", 1) + ebc("0000000", 7) + b"\x00\x00")
        recs.append(trailer)
        write_bytes(base / f"BRXINV.Y{year}", b"".join(recs))
    return {"files": len(by_year) + 5}


def decode_packed(b: bytes) -> float:
    """Reference decoder, used by tests and the answer key."""
    nibbles = [n for x in b for n in (x >> 4, x & 0xF)]
    val = int("".join(str(n) for n in nibbles[:-1])) / 100
    return -val if nibbles[-1] == 0xD else val
