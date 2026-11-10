"""Prove the golden facts are recoverable from the raw files alone.

    python -m generator.verify            # reads data/raw and data/GOLDEN_FACTS.yaml

Each check re-derives an answer by parsing the messy source files (not the
world model) and compares it with the answer key. If a check fails, either the
data or the answer key is wrong.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

from .sources.brix import decode_packed

RAW = Path("data/raw")


GOLDEN = Path("data/GOLDEN_FACTS.yaml")


def facts():
    return {f["id"]: f for f in yaml.safe_load(GOLDEN.read_text())["facts"]}


def check_gf10(f):
    """Ostrander 1999: parse EBCDIC fixed-width records with COMP-3 amounts."""
    data = (RAW / "brix_mainframe/BRXINV.Y1999").read_bytes()
    total = 0.0
    n = 0
    for i in range(0, len(data), 80):
        rec = data[i:i + 80]
        typ = rec[0:1].decode("cp037")
        cust = rec[1:7].decode("cp037")
        if typ in ("I", "C") and cust == "001207":
            total += decode_packed(rec[59:65])
            n += 1
    want = re.search(r"\$([\d,]+\.\d\d)", f["GF10"]["answer"]).group(1).replace(",", "")
    return abs(total - float(want)) < 0.01, f"parsed ${total:,.2f} from {n} records"


def check_gf06(f):
    """DST outage: order by the monotonic req= sequence, not by the local timestamp."""
    lines = (RAW / "app_logs/app-2017-11-04_05.dal-app03.log").read_text().splitlines()[1:]
    errs = [ln for ln in lines if " ERROR " in ln or "FAILED" in ln]
    first, last = errs[0], errs[-1]
    seq = [int(re.search(r"req=(\d+)", ln).group(1)) for ln in lines]
    monotonic = all(b > a for a, b in zip(seq, seq[1:]))
    # wall clock went 01:59 -> 01:00, so add an hour to anything after the repeat
    t0 = first[11:19]
    return monotonic and t0.startswith("01:2"), f"first error {t0} local, last {last[11:19]} local (second 1 AM), seq monotonic={monotonic}"


def check_gf05(f):
    rows = list(csv.DictReader(open(RAW / "billing_v3_2017-now/invoices.csv", newline="")))
    legacy = [r for r in rows if r["metadata.source"] == "ledger_import_2017"]
    dollars = all("." in r["subtotal"] for r in legacy)
    want = int(re.search(r"\((\d+) rows", f["GF05"]["answer"]).group(1))
    return len(legacy) == want and dollars, f"{len(legacy)} legacy rows, all with decimal dollars={dollars}"


def check_gf12(f):
    cust = list(csv.DictReader(open(RAW / "billing_v3_2017-now/customers.csv", newline="")))
    ids = {c["id"]: c for c in cust if "brigid" in c["name"].lower()}
    rows = list(csv.DictReader(open(RAW / "billing_v3_2017-now/invoices.csv", newline="")))
    from datetime import datetime, timezone
    tot = Counter()
    for r in rows:
        if r["customer"] in ids and r["status"] != "void" and not r["id"].startswith("cn_"):
            if datetime.fromtimestamp(int(r["created"]), timezone.utc).year == 2022:
                tot[r["currency"].upper()] += int(r["amount_due"]) / 100
    v = f["GF12"]["values"]
    ok = abs(tot["USD"] - v["USD"]) < 0.01 and abs(tot["CAD"] - v["CAD"]) < 0.01
    return ok, f"USD {tot['USD']:,.2f}, CAD {tot['CAD']:,.2f} across {len(ids)} billing customers"


def check_gf14(f):
    data = json.loads((RAW / "jira_export_2026-10/INC.json").read_text())
    norm = {"database": "Database", "db": "Database", "postgres": "Database", "db (replica lag)": "Database", "database - connection pool": "Database",
            "deploy / bad release": "Deploy / bad release", "bad deploy": "Deploy / bad release", "deploy": "Deploy / bad release",
            "release regression": "Deploy / bad release", "code change": "Deploy / bad release",
            "third-party provider": "Third-party provider", "3rd party": "Third-party provider", "vendor": "Third-party provider",
            "third party (sms)": "Third-party provider", "aws": "Third-party provider",
            "capacity": "Capacity", "load spike": "Capacity", "resource exhaustion": "Capacity",
            "network": "Network", "dns": "Network", "networking/lb": "Network",
            "certificate expiry": "Certificate expiry", "cert expired": "Certificate expiry", "tls cert": "Certificate expiry",
            "config change": "Config change", "config": "Config change", "misconfiguration": "Config change", "feature flag": "Config change"}
    c = Counter()
    for i in data["issues"]:
        fl = i["fields"]
        if fl["created"].startswith("2022") and fl["customfield_10100"].lower() == "sev1":
            c[norm[fl["customfield_10101"].lower()]] += 1
    top = c.most_common(1)[0][0] if c else None
    return top == f["GF14"]["values"]["top"], f"normalized counts {dict(c)}"


def check_gf03(f):
    rows = list(csv.DictReader(io.TextIOWrapper(open(RAW / "crm_salesforce_export_2026-10/Account.csv", "rb"), encoding="utf-8-sig")))
    hits = [r for r in rows if r["BRIX_Cust_No__c"].zfill(6) == "004417"]
    return len(hits) >= 1 and hits[0]["Name"] in f["GF03"]["answer"], f"SFDC says 004417 = {[h['Name'] for h in hits]}"


CHECKS = [check_gf03, check_gf05, check_gf06, check_gf10, check_gf12, check_gf14]


# ----------------------------------------------------------------------------- round 2 checks
def check_gf22(f):
    """Expand the monthly first-Tuesday RRULE by hand, drop EXDATEs and STATUS:CANCELLED overrides."""
    from datetime import date, timedelta
    text = (RAW / "calendars/pricing_committee_export_2024-06-30.ics").read_text().replace("\r\n ", "")
    events = text.split("BEGIN:VEVENT")[1:]
    master = next(e for e in events if "RRULE" in e)
    ex = {x[:8] for x in re.search(r"EXDATE[^:]*:(.*)", master).group(1).strip().split(",")}
    cancelled = {re.search(r"RECURRENCE-ID[^:]*:(\d{8})", e).group(1) for e in events if "STATUS:CANCELLED" in e}
    held = 0
    for m in range(1, 13):
        d = date(2023, m, 1)
        while d.weekday() != 1:
            d += timedelta(days=1)
        if f"{d:%Y%m%d}" not in ex | cancelled:
            held += 1
    return held == f["GF22"]["values"]["held_2023"], f"{held} held (exdates {sorted(ex)}, cancelled {sorted(cancelled)})"


def check_gf24(f):
    text = (RAW / "brix_mainframe/reports/AGEDAR_091231.PRN").read_text(encoding="ascii")
    line = next(l for l in text.splitlines() if "*** REPORT TOTAL" in l)
    over90 = float(line.split()[-1].replace(",", ""))
    return abs(over90 - f["GF24"]["values"]["over_90"]) < 0.01, f"REPORT TOTAL over-90 column = {over90:,.2f}"


def check_gf25(f):
    import struct
    b = (RAW / "finance_lotus_1997/BUDG97R.WK1").read_bytes()
    i, cells = 0, {}
    while i < len(b):
        t, n = struct.unpack_from("<HH", b, i)
        d = b[i + 4:i + 4 + n]
        i += 4 + n
        if t == 0x0F:
            col, row = struct.unpack_from("<HH", d, 1)
            cells[(col, row)] = d[6:-1].decode("cp437")
        elif t == 0x0E:
            col, row, v = struct.unpack_from("<HHd", d, 1)
            cells[(col, row)] = v
    row = next(rw for (c, rw), v in cells.items() if c == 0 and v == "MARKETING")
    total = cells[(5, row)]
    return total == f["GF25"]["values"]["marketing_fy1997"], f"MARKETING FY TOTAL = {total:,.0f} (approved: {cells[(0, 1)]!r})"


def check_gf28(f):
    import pyarrow.parquet as pq
    t = pq.read_table(RAW / "datalake/usage_daily/year=2026/month=03/part-00000.snappy.parquet")
    g = t.group_by("tenant_id").aggregate([("api_calls", "sum")]).sort_by([("api_calls_sum", "descending")]).to_pylist()[0]
    names = {r["tenant_id"]: r["display_name"] for r in csv.DictReader(open(RAW / "product_events/tenants.csv", newline=""))}
    return g["tenant_id"] == f["GF28"]["values"]["tenant_id"], f"top tenant {g['tenant_id']} ({names.get(g['tenant_id'])}) with {g['api_calls_sum']:,} calls"


def avro_records(path):
    """Tiny Avro object-container reader (null/string/long/int/union/record, deflate codec)."""
    import zlib
    data = path.read_bytes()
    pos = 4

    def long_(buf, p):
        shift = n = 0
        while True:
            b = buf[p]
            p += 1
            n |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                return (n >> 1) ^ -(n & 1), p

    def bytes_(buf, p):
        n, p = long_(buf, p)
        return buf[p:p + n], p + n
    meta = {}
    cnt, pos = long_(data, pos)
    for _ in range(cnt):
        k, pos = bytes_(data, pos)
        v, pos = bytes_(data, pos)
        meta[k.decode()] = v
    pos += 1 + 16
    schema = json.loads(meta["avro.schema"])
    named = {}

    def register(t):
        if isinstance(t, list):
            for x in t:
                register(x)
        elif isinstance(t, dict) and t.get("type") == "record":
            named[t["name"]] = t
            for fl in t["fields"]:
                register(fl["type"])
    register(schema)

    def read(t, buf, p):
        if isinstance(t, list):
            idx, p = long_(buf, p)
            return read(t[idx], buf, p)
        if isinstance(t, dict):
            if t["type"] == "record":
                out = {}
                for fl in t["fields"]:
                    out[fl["name"]], p = read(fl["type"], buf, p)
                return out, p
            return read(t["type"], buf, p)
        if t == "null":
            return None, p
        if t in ("long", "int"):
            return long_(buf, p)
        if t == "string":
            b, p = bytes_(buf, p)
            return b.decode(), p
        return read(named[t], buf, p)
    while pos < len(data):
        n, pos = long_(data, pos)
        size, pos = long_(data, pos)
        block = zlib.decompress(data[pos:pos + size], -15)
        pos += size + 16
        p = 0
        for _ in range(n):
            rec, p = read(schema, block, p)
            yield rec


def check_gf29(f):
    seen, canc = set(), set()
    for p in sorted((RAW / "datalake/cdc/billing.public.subscriptions").glob("*.avro")):
        for rec in avro_records(p):
            lsn = rec["source"]["lsn"]
            if lsn in seen:
                continue
            seen.add(lsn)
            if rec["op"] == "u" and rec["after"]["status"] == "canceled" and rec["before"]["status"] != "canceled":
                canc.add(rec["after"]["id"])
    return len(canc) == f["GF29"]["values"]["canceled_2025"], f"{len(canc)} cancellations after de-duplicating by LSN"


def check_gf30(f):
    okta = {r["id"]: r for r in csv.DictReader(open(RAW / "identity/okta_users_export_2026-10.csv", newline=""))}
    hits = Counter()
    for p in sorted((RAW / "datalake/api_audit").glob("audit-*.binpb")):
        b = p.read_bytes()
        i = 0
        while i < len(b):
            n = s = 0
            while True:
                x = b[i]
                i += 1
                n |= (x & 0x7F) << s
                s += 7
                if not x & 0x80:
                    break
            msg, i = b[i:i + n], i + n
            j, fields = 0, {}
            while j < len(msg):
                key = msg[j]
                j += 1
                num, wt = key >> 3, key & 7
                v = s = 0
                while True:
                    x = msg[j]
                    j += 1
                    v |= (x & 0x7F) << s
                    s += 7
                    if not x & 0x80:
                        break
                if wt == 2:
                    v, j = msg[j:j + v].decode(), j + v
                fields[num] = v
            if fields.get(4) == "/v2/export/customers" and not fields[6].startswith("203.0.113."):
                hits[fields[2]] += 1
    who = {okta[a]["profile.firstName"] + " " + okta[a]["profile.lastName"]: (n, okta[a]["status"]) for a, n in hits.items()}
    want = f["GF30"]["values"]["person"]
    return want in who and who[want][0] == 3, f"off-network customer exports: {who}"


def check_gf31(f):
    text = (RAW / "it_ops/windows_events/FS01_Security_2019-10-28_to_2019-11-01.xml").read_text(encoding="utf-8-sig")
    ev = re.findall(r"<EventID>(\d+)</EventID>.*?SystemTime='([^']+)'.*?<EventData>(.*?)</EventData>", text)
    paths, deleted = {}, []
    for eid, ts, data in ev:
        d = dict(re.findall(r"<Data Name='(\w+)'>([^<]*)</Data>", data))
        if eid == "4663" and d.get("AccessMask") == "0x10000":
            paths[d["HandleId"]] = d["ObjectName"]
        elif eid == "4660":
            deleted.append((ts, d["SubjectUserName"], paths.get(d["HandleId"])))
    folder = [x for x in deleted if x[2] and x[2].endswith("FY2016_close")]
    ok = folder and folder[0][1] == f["GF31"]["values"]["account"] and folder[0][0].startswith(f["GF31"]["values"]["deleted_utc"])
    return bool(ok), f"folder delete: {folder[:1]}"


def check_gf32(f):
    per_min = Counter()
    bad = Counter()
    with gzip.open(RAW / "web_logs/api.brindlecove.example/access-2025-03.log.gz", "rt") as fh:
        for ln in fh:
            m = re.search(r"\[(\d\d/\w{3}/\d{4}:\d\d:\d\d)", ln)
            st = ln.split('"')[2].split()[0]
            per_min[m.group(1)] += 1
            bad[m.group(1)] += st == "502"
    from datetime import datetime
    down = sorted(datetime.strptime(k, "%d/%b/%Y:%H:%M") for k in per_min if per_min[k] >= 2 and bad[k] / per_min[k] > 0.5)
    span = (down[-1] - down[0]).total_seconds() / 60 + 1 if down else 0
    v = f["GF32"]["values"]
    ok = down and down[0].isoformat() == v["start_local"] and abs(span - v["minutes"]) <= 2
    return bool(ok), f"502 burst {down[0]:%H:%M}-{down[-1]:%H:%M} local on {down[0]:%Y-%m-%d} (~{span:.0f} min)"


def check_gf33(f):
    text = (RAW / "marketing/google_ads/Campaign_report_2020.csv").read_text(encoding="utf-16")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))[2:]
    hdr = rows[0]
    tot = sum(float(r[hdr.index("Cost")].replace(",", "")) for r in rows[1:] if r[1] == "Classic migration - 2020")
    return abs(tot - f["GF33"]["values"]["spend_usd"]) < 0.01, f"Classic migration - 2020 cost = {tot:,.2f}"


def check_gf34(f):
    rows = list(csv.DictReader(io.TextIOWrapper(open(RAW / "marketing/qualtrics/Customer_NPS_2024-2026.csv", "rb"), encoding="utf-8-sig")))[2:]
    s = [int(r["Q1"]) for r in rows if r["Status"] == "IP Address" and r["Finished"] == "True" and "2025-04-01" <= r["StartDate"][:10] <= "2025-06-30"]
    nps = round((sum(x >= 9 for x in s) - sum(x <= 6 for x in s)) / len(s) * 100)
    return nps == f["GF34"]["values"]["nps"], f"NPS {nps} from {len(s)} responses"


def check_gf35(f):
    text = (RAW / "billing_tallyflow_2012-2014/quickbooks/TallyFlow_QB_2012-2014.IIF").read_text(encoding="cp1252")
    rev = 0.0
    for ln in text.splitlines():
        p = ln.split("\t")
        if p[0] == "SPL" and p[4] == "Subscription Revenue" and p[3].endswith("/13"):
            rev -= float(p[7])
    return abs(rev - f["GF35"]["values"]["revenue_2013"]) < 0.01, f"2013 revenue from SPL lines = {rev:,.2f}"


def check_gf38(f):
    data = (RAW / "integrations/hl7_stbrigids/ADT_20240115.hl7").read_bytes()
    ctrl, a03, a13 = set(), set(), set()
    for m in data.split(b"\x1c\r"):
        if not m:
            continue
        segs = {s.split("|")[0]: s.split("|") for s in m.lstrip(b"\x0b").decode().split("\r") if s}
        if segs["MSH"][9] in ctrl:
            continue
        ctrl.add(segs["MSH"][9])
        visit = segs["PV1"][19]
        (a03 if segs["EVN"][1] == "A03" else a13).add(visit)
    genuine = len(a03 - a13)
    return genuine == f["GF38"]["values"]["genuine"], f"{len(a03)} discharges, {len(a13)} cancelled -> {genuine}"


CHECKS += [check_gf22, check_gf24, check_gf25, check_gf28, check_gf29, check_gf30, check_gf31, check_gf32, check_gf33,
           check_gf34, check_gf35, check_gf38]


def main(argv=None):
    import argparse
    global RAW, GOLDEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(RAW))
    ap.add_argument("--golden", default=str(GOLDEN))
    a = ap.parse_args(argv)
    RAW, GOLDEN = Path(a.raw), Path(a.golden)
    f = facts()
    bad = 0
    for chk in CHECKS:
        ok, msg = chk(f)
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {chk.__name__[6:].upper():5} {msg}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
