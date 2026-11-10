"""Shared helpers: deterministic RNG streams, messy formatting, file writing.

Everything here is about making the *same* fact look different in each
source system, the way it does in a real company's data estate.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import os
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

AS_OF = date(2026, 10, 31)          # the "snapshot" date of the whole estate
FIXED_MTIME = 1_793_404_800          # 2026-11-01T00:00:00Z, for reproducible archives


def rng_for(seed: int, name: str) -> random.Random:
    """Independent, stable RNG stream per module (no reliance on hash())."""
    h = hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()
    return random.Random(int(h[:16], 16))


# --------------------------------------------------------------------------- dates
DATE_STYLES = {
    "iso": "%Y-%m-%d",
    "us": "%m/%d/%Y",
    "us_short": "%m/%d/%y",
    "eu": "%d/%m/%Y",
    "eu_dot": "%d.%m.%Y",
    "mon": "%d-%b-%Y",
    "long": "%B %d, %Y",
    "compact": "%Y%m%d",
}


def fmt_date(d: date | datetime | None, style: str = "iso") -> str:
    if d is None:
        return ""
    return d.strftime(DATE_STYLES.get(style, style))


def messy_date(r: random.Random, d: date | None, styles=("iso", "us", "us_short", "mon", "long")) -> str:
    if d is None:
        return r.choice(["", "N/A", "00/00/0000", "TBD"])
    return fmt_date(d, r.choice(styles))


def excel_serial(d: date) -> int:
    """What a date turns into when someone pastes it as a number."""
    return (d - date(1899, 12, 30)).days


def month_iter(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield date(y, m, 1)
        m += 1
        if m == 13:
            y, m = y + 1, 1


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


def rand_date(r: random.Random, start: date, end: date) -> date:
    span = (end - start).days
    return start + timedelta(days=r.randint(0, max(span, 0)))


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- nulls
NULLS = ["", "N/A", "n/a", "-", "NULL", "null", "None", "#N/A", "?", " "]


def maybe_null(r: random.Random, value, p: float = 0.03, pool=NULLS):
    return r.choice(pool) if r.random() < p else value


# --------------------------------------------------------------------------- typos
def typo(r: random.Random, s: str, p: float = 1.0) -> str:
    if not s or r.random() > p or len(s) < 4:
        return s
    i = r.randrange(1, len(s) - 1)
    op = r.choice(["swap", "drop", "dup", "case"])
    if op == "swap":
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]
    if op == "drop":
        return s[:i] + s[i + 1:]
    if op == "dup":
        return s[:i] + s[i] + s[i:]
    return s[:i] + s[i].swapcase() + s[i + 1:]


def mojibake(s: str) -> str:
    """UTF-8 bytes read back as Windows-1252: 'Café' -> 'CafÃ©'."""
    try:
        return s.encode("utf-8").decode("cp1252")
    except UnicodeDecodeError:
        return s.encode("utf-8").decode("latin-1")


# --------------------------------------------------------------------------- money
def money_str(r: random.Random, amount: float, currency: str = "USD", style: str | None = None) -> str:
    style = style or r.choice(["plain", "comma", "symbol", "code", "paren_neg"])
    sym = {"USD": "$", "CAD": "C$", "GBP": "£", "EUR": "€"}.get(currency, "$")
    neg = amount < 0
    a = abs(amount)
    if style == "plain":
        s = f"{a:.2f}"
    elif style == "comma":
        s = f"{a:,.2f}"
    elif style == "symbol":
        s = f"{sym}{a:,.2f}"
    elif style == "code":
        s = f"{a:,.2f} {currency}"
    else:
        s = f"{a:,.2f}"
        return f"({s})" if neg else s
    return f"-{s}" if neg else s


# --------------------------------------------------------------------------- files
def write_text(path: Path, text: str, encoding: str = "utf-8", newline: str = "\n", bom: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", newline).encode(encoding, errors="replace")
    if bom:
        data = {"utf-16-le": b"\xff\xfe", "utf-16-be": b"\xfe\xff"}.get(encoding.lower(), b"\xef\xbb\xbf") + data
    path.write_bytes(data)


def write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_gz(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=6) as g:
        g.write(text.encode("utf-8"))
    path.write_bytes(buf.getvalue())


def csv_line(fields, delim=",", quote_all=False) -> str:
    out = []
    for f in fields:
        s = "" if f is None else str(f)
        needs = quote_all or any(c in s for c in (delim, '"', "\n", "\r"))
        if needs:
            s = '"' + s.replace('"', '""') + '"'
        out.append(s)
    return delim.join(out)


def b62(r: random.Random, n: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(r.choice(alphabet) for _ in range(n))


def hexid(r: random.Random, n: int) -> str:
    return "".join(r.choice("0123456789abcdef") for _ in range(n))


def uuid_like(r: random.Random) -> str:
    h = hexid(r, 32)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def rel(path: Path, root: Path) -> str:
    return os.path.relpath(path, root).replace(os.sep, "/")


def normalize_office_files(root):
    """Pin the build-time clock out of every OOXML file under root.

    openpyxl, python-docx and python-pptx stamp zip entries (and openpyxl the
    'modified' property) with the current time, so two runs differ byte-wise.
    Rewrite each package with entry times taken from its own 'created' date and,
    where 'modified' is after AS_OF, set it back to 'created'.
    """
    import re
    import zipfile
    from pathlib import Path
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file() or p.suffix.lower() in (".gz", ".pdf", ".txt", ".csv", ".json", ".xml", ".html") or not zipfile.is_zipfile(p):
            continue
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            if "docProps/core.xml" not in names:
                continue
            items = [(i, z.read(i.filename)) for i in z.infolist()]
        items_by_name = {i.filename: b for i, b in items}
        core = items_by_name["docProps/core.xml"].decode("utf-8")
        m = re.search(r"<dcterms:created[^>]*>(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)Z?</dcterms:created>", core)
        created = tuple(int(x) for x in m.groups()) if m else (2000, 1, 1, 0, 0, 0)
        stamp = f"{created[0]:04d}-{created[1]:02d}-{created[2]:02d}T{created[3]:02d}:{created[4]:02d}:{created[5]:02d}Z"

        def fix_mod(mm):
            return mm.group(0) if mm.group(2) <= AS_OF.isoformat() else f"{mm.group(1)}{stamp}{mm.group(3)}"
        core = re.sub(r"(<dcterms:modified[^>]*>)(\d{4}-\d\d-\d\d)[^<]*(</dcterms:modified>)",
                      lambda mm: fix_mod(mm), core)
        items_by_name["docProps/core.xml"] = core.encode("utf-8")
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for i, _ in items:
                zi = zipfile.ZipInfo(i.filename, date_time=max(created, (1980, 1, 1, 0, 0, 0)))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o600 << 16
                z.writestr(zi, items_by_name[i.filename])


# --------------------------------------------------------------------------- archives (reproducible)
def zip_bytes(entries, when=(2019, 10, 30, 17, 5, 0)) -> bytes:
    """entries: list of (path_in_zip, bytes[, (y,m,d,H,M,S)]). Fixed timestamps, stable order."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for e in entries:
            name, data = e[0], e[1]
            zi = zipfile.ZipInfo(name, date_time=e[2] if len(e) > 2 else when)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
    return buf.getvalue()


def targz_bytes(entries, mtime=FIXED_MTIME) -> bytes:
    import tarfile
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as t:
        for name, data in entries:
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime, ti.mode, ti.uname, ti.gname = len(data), mtime, 0o644, "www-data", "www-data"
            t.addfile(ti, io.BytesIO(data))
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0) as g:
        g.write(raw.getvalue())
    return out.getvalue()


def write_gz_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=6) as g:
        g.write(data)
    path.write_bytes(buf.getvalue())


def add_fact(world, fact: dict):
    """Round-2 modules plant their own golden facts here; golden.write_golden appends them."""
    if not hasattr(world, "extra_facts"):
        world.extra_facts = []
    world.extra_facts = [f for f in world.extra_facts if f["id"] != fact["id"]] + [fact]
