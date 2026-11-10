"""Every billing system after BRIX, plus the finance GL.

Renders:
  billing_ledger_mysql_2011-2017/ledger_dump_2017-03-31.sql   MySQL dump, latin1 tables holding double-encoded UTF-8,
                                                               '0000-00-00' zero dates, DECIMAL dollars
  billing_tallyflow_2012-2014/invoices_export.xml             TallyFlow's XML export (pre-acquisition)
  billing_meridian_2015-2019/factures_*.csv                    Meridian Dispatch, CAD, DD/MM/YYYY, French/English headers
  billing_kestrel_2018-2022/kestrel_sales_invoices.csv         UK accounting export, GBP, DD/MM/YYYY, VAT
  billing_v3_2017-now/{customers,subscriptions,invoices,invoice_lines}.csv
                                                               Stripe-style, amounts in CENTS, unix timestamps,
                                                               except legacy-imported rows (DOLLARS) - see Jira DATA-212
  finance_netsuite/gl_detail_FY20xx.csv                        GL detail, subsidiaries, deferred revenue
  finance_netsuite/fx_rates_monthly.csv
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from ..util import add_months, b62, csv_line, fmt_date, hexid, mojibake, rng_for, write_gz, write_text, AS_OF
from ..world import ERA

FIRST_FY = 2015


def ts(d: date, r=None, hour=None) -> int:
    h = hour if hour is not None else (r.randint(0, 23) if r else 0)
    return int(datetime(d.year, d.month, d.day, h, (r.randint(0, 59) if r else 0), tzinfo=timezone.utc).timestamp())


def fx_series(r):
    """Monthly USD per unit of CAD/GBP. Wanders around the planning rate."""
    rates = {}
    cad, gbp = 0.80, 1.55
    for y in range(2014, 2027):
        for m in range(1, 13):
            cad = min(0.86, max(0.68, cad + r.uniform(-0.012, 0.011)))
            gbp = min(1.60, max(1.15, gbp + r.uniform(-0.025, 0.02)))
            if (y, m) == (2016, 7):
                gbp -= 0.14   # a sudden drop
            rates[(y, m)] = {"CAD": round(cad, 4), "GBP": round(gbp, 4), "USD": 1.0}
    return rates


# ----------------------------------------------------------------------------- Ledger (MySQL)
def render_ledger(world, out, r):
    invs = [i for i in world.invoices if i.system == "ledger"]
    custs = {}
    for i in invs:
        custs.setdefault(i.cust.key, i.cust)
    lines = ["-- MySQL dump 10.13  Distrib 5.5.54, for debian-linux-gnu (x86_64)", "--",
             "-- Host: ledger-db01.int.brindlecove.com    Database: ledger_prod",
             "-- ------------------------------------------------------", "-- Server version\t5.5.54-0ubuntu0.14.04.1-log", "",
             "/*!40101 SET NAMES latin1 */;", "/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;", "",
             "DROP TABLE IF EXISTS `customers`;",
             "CREATE TABLE `customers` (\n  `id` int(11) NOT NULL AUTO_INCREMENT,\n  `name` varchar(120) NOT NULL,\n"
             "  `brix_no` varchar(10) DEFAULT NULL COMMENT 'legacy BRIX customer number',\n  `tf_ref` varchar(12) DEFAULT NULL,\n"
             "  `city` varchar(60) DEFAULT NULL,\n  `state` char(2) DEFAULT NULL,\n  `plan` varchar(20) DEFAULT NULL,\n"
             "  `seat_price` decimal(8,2) DEFAULT NULL,\n  `discount_pct` decimal(5,2) DEFAULT '0.00',\n"
             "  `is_active` tinyint(1) NOT NULL DEFAULT '1',\n  `created_at` datetime NOT NULL DEFAULT '0000-00-00 00:00:00',\n"
             "  PRIMARY KEY (`id`)\n) ENGINE=MyISAM AUTO_INCREMENT=4000 DEFAULT CHARSET=latin1;", ""]
    rows = []
    for c in custs.values():
        lid = c.ids.get("ledger") or str(9000 + int(c.key[1:]))
        c.ids["ledger"] = lid
        name = mojibake(c.name) if any(ord(ch) > 127 for ch in c.name) else c.name
        created = f"'{c.cloud_start or ERA['ledger_start']} 09:{r.randint(10, 59)}:00'" if r.random() > 0.05 else "'0000-00-00 00:00:00'"
        brix = f"'{c.ids['brix']}'" if "brix" in c.ids else "NULL"
        tf = f"'{c.ids['tallyflow']}'" if "tallyflow" in c.ids else "NULL"
        disc = f"{c.discount * 100:.2f}"
        if c is world.golden["calloway"]:
            disc = "0.00"   # the discount lived in the contract, Ledger only knew the net seat price
        price = round(c.unit_price(c.cloud_start or ERA['ledger_start']) * ((1 - c.discount) if c is world.golden["calloway"] else 1), 2)
        rows.append(f"({lid},'{name.replace(chr(39), chr(92) + chr(39))}',{brix},{tf},'{c.city}','{c.region[:2]}','{c.plan.lower()}',{price},{disc},"
                    f"{0 if c.end and c.end < date(2017, 3, 31) else 1},{created})")
    lines.append("LOCK TABLES `customers` WRITE;")
    for k in range(0, len(rows), 200):
        lines.append("INSERT INTO `customers` VALUES " + ",".join(rows[k:k + 200]) + ";")
    lines += ["UNLOCK TABLES;", "",
              "DROP TABLE IF EXISTS `invoices`;",
              "CREATE TABLE `invoices` (\n  `id` int(11) NOT NULL AUTO_INCREMENT,\n  `customer_id` int(11) NOT NULL,\n"
              "  `invoice_date` date NOT NULL,\n  `period_start` date DEFAULT NULL,\n  `period_end` date DEFAULT NULL,\n"
              "  `amount` decimal(12,2) NOT NULL COMMENT 'USD dollars',\n  `status` enum('draft','sent','paid','void','writeoff') DEFAULT 'draft',\n"
              "  `paid_date` date NOT NULL DEFAULT '0000-00-00',\n  `memo` text,\n  PRIMARY KEY (`id`),\n  KEY `cust` (`customer_id`)\n"
              ") ENGINE=MyISAM DEFAULT CHARSET=latin1;", "", "LOCK TABLES `invoices` WRITE;"]
    rows = []
    for n, i in enumerate(invs, start=500001):
        i.ledger_id = n
        st = {"paid": "paid", "open": "sent", "void": "void", "uncollectible": "writeoff", "refunded": "paid"}[i.status]
        paid = f"'{i.paid_on}'" if i.paid_on else "'0000-00-00'"
        memo = "NULL" if r.random() < 0.7 else "'" + r.choice(["per BK", "prorated", "PO# " + str(r.randint(10000, 99999)), "net 45 approved", "resent 2x", "check #" + str(r.randint(1000, 9999))]) + "'"
        rows.append(f"({n},{i.cust.ids['ledger']},'{i.issued}','{i.period_start}','{i.period_end}',{i.total:.2f},'{st}',{paid},{memo})")
    for k in range(0, len(rows), 500):
        lines.append("INSERT INTO `invoices` VALUES " + ",".join(rows[k:k + 500]) + ";")
    lines += ["UNLOCK TABLES;", "", "-- Dump completed on 2017-03-31 23:58:41", ""]
    write_text(out / "billing_ledger_mysql_2011-2017" / "ledger_dump_2017-03-31.sql", "\n".join(lines), encoding="latin-1")


# ----------------------------------------------------------------------------- TallyFlow XML
def render_tallyflow(world, out, r):
    invs = [i for i in world.invoices if i.system == "tallyflow"]
    x = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<!-- TallyFlow nightly export v1.4 - generated 2014-09-14T23:00:02-05:00 -->',
         '<tf:export xmlns:tf="http://schemas.tallyflow.io/export/1.4" generated="2014-09-14T23:00:02-05:00">']
    by_c = defaultdict(list)
    for i in invs:
        by_c[i.cust.key].append(i)
    for key, lst in by_c.items():
        c = lst[0].cust
        x.append(f'  <tf:account ref="{c.ids["tallyflow"]}" status="{"active" if not c.end or c.end > date(2014, 9, 14) else "closed"}">')
        x.append(f"    <tf:name><![CDATA[{c.name}]]></tf:name>")
        x.append(f"    <tf:billingEmail>{c.contacts[0].email if r.random() > 0.1 else ''}</tf:billingEmail>")
        for i in lst:
            amt = f"{i.total:.2f}"
            x.append(f'    <tf:invoice number="TF{i.seq}" issued="{i.issued.isoformat()}T00:00:00-06:00" currency="USD">')
            for desc, q, p in i.lines:
                x.append(f'      <tf:line qty="{q}" unit="{p:.2f}">{desc.replace("&", "&amp;")}</tf:line>')
            x.append(f"      <tf:total>{amt}</tf:total>")
            x.append(f"      <tf:state>{ {'paid': 'PAID', 'open': 'DUE', 'void': 'CANCELLED', 'uncollectible': 'BAD_DEBT', 'refunded': 'REFUNDED'}[i.status] }</tf:state>")
            x.append("    </tf:invoice>")
        x.append("  </tf:account>")
    x.append("</tf:export>")
    write_text(out / "billing_tallyflow_2012-2014" / "invoices_export.xml", "\n".join(x) + "\n")


# ----------------------------------------------------------------------------- Meridian CSV (CAD)
def render_meridian(world, out, r):
    invs = [i for i in world.invoices if i.system == "meridian"]
    by_year = defaultdict(list)
    for i in invs:
        by_year[i.issued.year].append(i)
    for y, lst in by_year.items():
        rows = ["No. facture / Invoice No,Client,Code client,Date,Sous-total,TPS/GST,TVQ/PST,Total,Devise,Statut"]
        for i in lst:
            c = i.cust
            gst = round(i.total * 0.05, 2)
            pst = round(i.total * (0.09975 if c.region == "QC" else 0.07 if c.region in ("MB", "BC", "SK") else 0.0), 2)
            stat = {"paid": "Payée", "open": "Impayée", "void": "Annulée", "uncollectible": "Radiée", "refunded": "Remboursée"}[i.status]
            total = i.total + gst + pst
            # Excel on a French-Canadian machine: comma decimals inside quoted fields for some years
            fmtn = (lambda v: f'"{v:.2f}"'.replace(".", ",")) if y >= 2018 else (lambda v: f"{v:.2f}")
            rows.append(",".join([f"MD{i.seq}", f'"{c.name}"', c.ids["meridian"], i.issued.strftime("%d/%m/%Y"),
                                  fmtn(i.total), fmtn(gst), fmtn(pst), fmtn(total), "CAD", stat]))
        write_text(out / "billing_meridian_2015-2019" / f"factures_{y}.csv", "\n".join(rows) + "\n",
                   encoding="cp1252", newline="\r\n")


# ----------------------------------------------------------------------------- Kestrel (UK)
def render_kestrel(world, out, r):
    invs = [i for i in world.invoices if i.system == "kestrel"]
    rows = ["*ContactName,EmailAddress,InvoiceNumber,Reference,InvoiceDate,DueDate,Total,TaxTotal,InvoiceAmountPaid,InvoiceAmountDue,Currency,Status"]
    for i in invs:
        c = i.cust
        vat = round(i.total * 0.2, 2)
        total = round(i.total + vat, 2)
        paid = total if i.status in ("paid", "refunded") else 0.0
        rows.append(csv_line([c.name, c.contacts[0].email, f"INV-{i.seq:06d}", c.ids["kestrel"], i.issued.strftime("%d/%m/%Y"),
                              (i.issued + timedelta(days=30)).strftime("%d/%m/%Y"), f"{total:.2f}", f"{vat:.2f}",
                              f"{paid:.2f}", f"{total - paid:.2f}", "GBP",
                              {"paid": "PAID", "open": "AUTHORISED", "void": "VOIDED", "uncollectible": "AUTHORISED", "refunded": "PAID"}[i.status]]))
    write_text(out / "billing_kestrel_2018-2022" / "kestrel_sales_invoices.csv", "\n".join(rows) + "\n", bom=True)


# ----------------------------------------------------------------------------- Billing v3 (Stripe-style)
def render_billing_v3(world, out, r):
    base = out / "billing_v3_2017-now"
    custs = [c for c in world.customers if "billing" in c.ids]
    crow = [["id", "created", "email", "name", "description", "currency", "metadata.sfdc_id", "metadata.netsuite_id", "deleted", "address_country"]]
    srow = [["id", "customer", "status", "plan", "quantity", "unit_amount", "currency", "interval", "current_period_start",
             "current_period_end", "cancel_at", "canceled_at", "created", "discount_percent", "metadata.notes"]]
    for c in custs:
        created = max(c.cloud_start, ERA["billing_v3"]) if c.cloud_start else ERA["billing_v3"]
        crow.append([c.ids["billing"], ts(created, r), c.contacts[0].email if r.random() > 0.04 else "", c.name,
                     r.choice(["", "", "migrated from ledger", "TF migrated", c.ids.get("brix", "")]), c.currency.lower(),
                     c.ids.get("sfdc", "") if r.random() > 0.1 else "", c.ids.get("netsuite", ""),
                     "true" if c.end and c.end < AS_OF - timedelta(days=400) and r.random() < 0.3 else "false",
                     {"US": "US", "CA": "CA", "GB": "GB"}[c.country]])
        status = "active" if not c.end else "canceled"
        note = ""
        if c is world.golden["calloway"]:
            note = "price per 2013 MSA - do not reprice (see contract)"
        interval = "year" if c.annual else "month"
        srow.append(["sub_" + b62(r, 14), c.ids["billing"], status, f"ops_{c.plan.lower()}_{interval}ly", c.seats(AS_OF if not c.end else c.end),
                     int(round(c.unit_price(AS_OF) * 100 * {"USD": 1, "CAD": 1.32, "GBP": 0.79}[c.currency])), c.currency.lower(), interval,
                     ts(add_months(AS_OF.replace(day=1), -1) if not c.end else c.end.replace(day=1)),
                     ts(AS_OF.replace(day=1) if not c.end else c.end), ts(c.end) if c.end else "", ts(c.end - timedelta(days=r.randint(1, 40)), r) if c.end else "",
                     ts(created, r), f"{c.discount * 100:.0f}" if c.discount else "", note])
    irow = [["id", "number", "customer", "created", "period_start", "period_end", "status", "currency", "subtotal", "tax",
             "amount_due", "amount_paid", "paid_at", "collection_method", "metadata.legacy_ledger_id", "metadata.source"]]
    lrow = [["invoice", "line_id", "description", "quantity", "unit_amount", "amount", "currency", "proration"]]
    num = 0
    legacy = [i for i in world.invoices if i.system == "ledger" and date(2016, 1, 1) <= i.issued < ERA["billing_v3"] and "billing" in i.cust.ids]
    legacy_set = set(id(i) for i in legacy)
    for i in legacy + [i for i in world.invoices if i.system == "billing"]:
        c = i.cust
        num += 1
        is_legacy = id(i) in legacy_set
        unit = 1 if is_legacy else 100     # the bug: legacy import kept dollars, everything else is cents
        st = {"paid": "paid", "open": "open", "void": "void", "uncollectible": "uncollectible", "refunded": "paid"}[i.status]
        sub = int(round(i.total * unit)) if not is_legacy else f"{i.total:.2f}"
        tax = 0
        due = sub
        inv_id = "in_" + b62(r, 16)
        irow.append([inv_id, f"{hexid(r, 8).upper()}-{num:04d}", c.ids["billing"], ts(i.issued, r), ts(i.period_start, hour=0),
                     ts(i.period_end, hour=23), st, i.currency.lower(), sub, tax, due,
                     (due if st == "paid" else 0), ts(i.paid_on, r) if i.paid_on else "",
                     "send_invoice" if c.annual or c.seats0 > 100 else "charge_automatically",
                     getattr(i, "ledger_id", "") if is_legacy else "", "ledger_import_2017" if is_legacy else ""])
        if not is_legacy:
            for k, (desc, q, p) in enumerate(i.lines):
                lrow.append([inv_id, f"il_{b62(r, 10)}", desc, q, int(round(p * 100)), int(round(q * p * 100)), i.currency.lower(), "false"])
        if i.status == "refunded":
            num += 1
            irow.append(["cn_" + b62(r, 16), f"CN-{num:05d}", c.ids["billing"], ts(i.paid_on, r), "", "", "issued",
                         i.currency.lower(), -sub if not is_legacy else f"-{i.total:.2f}", 0,
                         -due if not is_legacy else f"-{i.total:.2f}", 0, "", "", "", "credit_note"])
    for name, rows in [("customers.csv", crow), ("subscriptions.csv", srow), ("invoices.csv", irow)]:
        write_text(base / name, "\n".join(csv_line(x) for x in rows) + "\n")
    write_gz(base / "invoice_lines.csv.gz", "\n".join(csv_line(x) for x in lrow) + "\n")
    world.legacy_import_count = len(legacy)


# ----------------------------------------------------------------------------- NetSuite GL
def render_netsuite(world, out, r, rates):
    base = out / "finance_netsuite"
    subs = {"USD": "Brindlecove Software, Inc. (US)", "CAD": "Brindlecove Canada ULC", "GBP": "Brindlecove UK Ltd"}
    by_fy = defaultdict(list)
    n = 900000
    for i in world.invoices:
        if i.issued.year < FIRST_FY or i.system in ("brix",):
            continue
        c = i.cust
        if i.system in ("meridian",) and i.issued < ERA["meridian_acq"]:
            continue
        if i.system == "kestrel" and i.issued < ERA["kestrel_acq"]:
            continue
        if "netsuite" not in c.ids:
            continue
        n += 1
        rate = rates[(i.issued.year, i.issued.month)][i.currency]
        name = f"C{c.ids['netsuite']} {c.name}"
        period = i.issued.strftime("%b %Y")
        annual = (i.period_end - i.period_start).days > 40
        acct = "2500 Deferred Revenue" if annual else ("4000 Subscription Revenue" if "MAINT" not in i.lines[0][0] else "4100 Maintenance Revenue")
        status = i.status
        if status == "void":
            continue
        by_fy[i.issued.year].append([n, fmt_date(i.issued, "us"), period, subs[i.currency], acct, name,
                                     f"INV {i.inv_key}", "", f"{i.total:.2f}", i.currency, rate, f"{i.total * rate:.2f}"])
        if annual:
            months = 12
            per = round(i.total / months, 2)
            for k in range(months):
                d = add_months(i.period_start, k)
                if d > AS_OF:
                    break
                n += 1
                rt = rates[(d.year, d.month)][i.currency]
                by_fy[d.year].append([n, fmt_date(d, "us"), d.strftime("%b %Y"), subs[i.currency], "4000 Subscription Revenue",
                                      name, f"Rev rec {i.inv_key} {k + 1}/12", "", f"{per:.2f}", i.currency, rt, f"{per * rt:.2f}"])
        if status == "uncollectible":
            n += 1
            by_fy[i.issued.year].append([n, fmt_date(i.issued + timedelta(days=120), "us"), period, subs[i.currency], "6900 Bad Debt Expense",
                                         name, f"W/O {i.inv_key}", f"{i.total:.2f}", "", i.currency, rate, f"{-i.total * rate:.2f}"])
    hdr = ["Internal ID", "Date", "Period", "Subsidiary", "Account", "Name", "Memo", "Debit", "Credit", "Currency", "Exchange Rate", "Amount (Base Currency)"]
    for fy, rows in sorted(by_fy.items()):
        if fy > AS_OF.year:
            continue
        write_text(base / f"gl_detail_FY{fy}.csv", "\n".join(csv_line(x) for x in [hdr] + rows) + "\n")
    fx = [["period", "CAD_USD", "GBP_USD", "source"]]
    for (y, m), v in sorted(rates.items()):
        if date(y, m, 1) <= AS_OF:
            fx.append([f"{y}-{m:02d}", v["CAD"], v["GBP"], "treasury avg"])
    write_text(base / "fx_rates_monthly.csv", "\n".join(csv_line(x) for x in fx) + "\n")


def render(world, out, seed):
    r = rng_for(seed, "billing")
    rates = fx_series(r)
    world.fx = rates
    render_ledger(world, out, r)
    render_tallyflow(world, out, r)
    render_meridian(world, out, r)
    render_kestrel(world, out, r)
    render_billing_v3(world, out, r)
    render_netsuite(world, out, r, rates)
    return {}
