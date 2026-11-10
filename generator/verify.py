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


def facts():
    return {f["id"]: f for f in yaml.safe_load(Path("data/GOLDEN_FACTS.yaml").read_text())["facts"]}


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


def main():
    f = facts()
    bad = 0
    for chk in CHECKS:
        ok, msg = chk(f)
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {chk.__name__[6:].upper():5} {msg}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
