"""The 2023+ AWS data lake: Parquet, Avro change-data-capture, protobuf audit logs.

Renders:
  datalake/usage_daily/year=YYYY/month=MM/part-00000.snappy.parquet   Hive-partitioned daily usage per tenant, 2024-01 -> 2026-10
                                                                      schema v2 from 2025-07: api_calls int32 -> int64, new mobile_sessions
  datalake/cdc/billing.public.subscriptions/YYYY-MM.avro              Debezium-style envelopes (before/after/op/source), deflate codec
                                                                      2025 only; includes snapshot rows (op=r) and a connector restart
                                                                      that re-sent part of March 2025
  datalake/api_audit/audit-YYYY-MM.binpb                              length-delimited protobuf AuditEvent messages, 2025
  datalake/api_audit/audit_event.proto                                the schema
  identity/okta_users_export_2026-10.csv                              maps opaque actor ids to people (deprovisioned users kept)

Planted:
  GF28  the tenant with the most API calls in March 2026 (a runaway integration; tenant slug -> customer via tenants.csv)
  GF29  how many subscriptions were canceled in 2025 according to CDC (dedupe the replayed events)
  GF30  a salesperson exported the customer list in their last week before leaving in 2025
"""
from __future__ import annotations

import io
import json
import struct
import zlib
from datetime import date, datetime, time, timedelta, timezone

import pyarrow as pa
import pyarrow.parquet as pq

from ..util import AS_OF, add_fact, add_months, b62, csv_line, month_iter, rng_for, write_bytes, write_text

RAW = "data/raw"


# --------------------------------------------------------------------------- avro (hand-rolled, deterministic)
def zz(n: int) -> bytes:
    n = (n << 1) ^ (n >> 63)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def a_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return zz(len(b)) + b


def a_value(v):
    if v is None:
        return zz(0)
    return zz(1) + (zz(len(v["id"].encode())) + v["id"].encode() + a_str(v["customer"]) + a_str(v["status"]) + a_str(v["plan"])
                    + zz(v["quantity"]) + zz(v["unit_amount"]) + a_str(v["currency"])
                    + (zz(0) if v["current_period_end"] is None else zz(1) + zz(v["current_period_end"])) + zz(v["updated_at"]))


AVRO_SCHEMA = {
    "type": "record", "name": "Envelope", "namespace": "bcprod.public.subscriptions",
    "fields": [
        {"name": "before", "type": ["null", {"type": "record", "name": "Value", "fields": [
            {"name": "id", "type": "string"}, {"name": "customer", "type": "string"}, {"name": "status", "type": "string"},
            {"name": "plan", "type": "string"}, {"name": "quantity", "type": "int"}, {"name": "unit_amount", "type": "long"},
            {"name": "currency", "type": "string"},
            {"name": "current_period_end", "type": ["null", {"type": "long", "logicalType": "timestamp-millis"}], "default": None},
            {"name": "updated_at", "type": {"type": "long", "logicalType": "timestamp-micros"}}]}], "default": None},
        {"name": "after", "type": ["null", "Value"], "default": None},
        {"name": "source", "type": {"type": "record", "name": "Source", "namespace": "io.debezium.connector.postgresql", "fields": [
            {"name": "version", "type": "string"}, {"name": "connector", "type": "string"}, {"name": "name", "type": "string"},
            {"name": "ts_ms", "type": "long"}, {"name": "snapshot", "type": ["null", "string"], "default": None},
            {"name": "db", "type": "string"}, {"name": "table", "type": "string"}, {"name": "lsn", "type": ["null", "long"], "default": None}]}},
        {"name": "op", "type": "string"},
        {"name": "ts_ms", "type": ["null", "long"], "default": None}]}


def avro_file(records, sync: bytes) -> bytes:
    """records: list of dicts {before, after, op, ts_ms, src_ts, snapshot, lsn}."""
    meta = {"avro.schema": json.dumps(AVRO_SCHEMA, separators=(",", ":")).encode(), "avro.codec": b"deflate"}
    out = b"Obj\x01" + zz(len(meta))
    for k, v in meta.items():
        out += a_str(k) + zz(len(v)) + v
    out += zz(0) + sync
    for i in range(0, len(records), 500):
        chunk = records[i:i + 500]
        body = b""
        for rec in chunk:
            body += a_value(rec["before"]) + a_value(rec["after"])
            body += (a_str("2.1.4.Final") + a_str("postgresql") + a_str("bcprod") + zz(rec["src_ts"])
                     + (zz(0) if rec["snapshot"] is None else zz(1) + a_str(rec["snapshot"]))
                     + a_str("billing") + a_str("subscriptions") + zz(1) + zz(rec["lsn"]))
            body += a_str(rec["op"]) + zz(1) + zz(rec["ts_ms"])
        co = zlib.compressobj(6, zlib.DEFLATED, -15)
        comp = co.compress(body) + co.flush()
        out += zz(len(chunk)) + zz(len(comp)) + comp + sync
    return out


# --------------------------------------------------------------------------- protobuf (hand-rolled)
def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def pb_field(num, val):
    if isinstance(val, int):
        return varint(num << 3) + varint(val)
    b = val.encode("utf-8")
    return varint((num << 3) | 2) + varint(len(b)) + b


PROTO = """syntax = "proto3";
package bc.audit.v1;

// Written by api-gateway. One file per month, each message prefixed by its
// length as a varint (writeDelimitedTo). Timestamps are UTC epoch millis.
message AuditEvent {
  int64  ts_ms       = 1;
  string actor_id    = 2;   // Okta user id (00u...), or "svc:<name>" for service accounts
  string method      = 3;
  string path        = 4;   // templated path, query string stripped
  uint32 status      = 5;
  string src_ip      = 6;   // last hop; office NAT is 203.0.113.0/24
  uint64 resp_bytes  = 7;
  string request_id  = 8;
  string user_agent  = 9;   // added 2025-06; absent before
}
"""


def ts_ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def render(world, out, seed):
    r = rng_for(seed, "datalake")
    if not hasattr(world, "tenants"):
        raise RuntimeError("datalake needs the telemetry module to run first (tenant slugs)")
    lake = out / "datalake"

    # ----------------------------------------------------------------- GF28 parquet usage
    custs = [c for c in world.customers if c.key in world.tenants]
    runaway_pool = sorted([c for c in custs if c.plan == "Pro" and not c.end and c.cloud_start < date(2023, 1, 1)
                           and 20 <= c.seats(date(2026, 3, 1)) <= 40 and id(c) not in {id(x) for x in world.golden.values()}],
                          key=lambda c: c.name)
    runaway = runaway_pool[len(runaway_pool) // 2]
    loop_days = {date(2026, 3, d) for d in range(9, 21)}
    api_by_tenant = {}
    for m in month_iter(date(2024, 1, 1), AS_OF):
        nxt = add_months(m, 1)
        v2 = m >= date(2025, 7, 1)
        cols = {"tenant_id": [], "usage_date": [], "active_users": [], "work_orders_created": [], "api_calls": []}
        if v2:
            cols["mobile_sessions"] = []
        active = [c for c in custs if c.cloud_start <= m and (c.end is None or c.end >= m)]
        d = m
        while d < nxt and d <= AS_OF:
            wk = d.weekday() < 5
            for c in active:
                if c.end and d > c.end:
                    continue
                seats = c.seats(d)
                au = max(0, int(seats * (r.uniform(0.45, 0.9) if wk else r.uniform(0.02, 0.15))))
                api = int(au * r.uniform(5, 60))
                if c is runaway and d in loop_days:
                    api = 2_000_000 + r.randint(0, 400_000)     # retry loop in their ERP connector
                cols["tenant_id"].append(world.tenants[c.key])
                cols["usage_date"].append(d)
                cols["active_users"].append(au)
                cols["work_orders_created"].append(int(au * r.uniform(0.5, 3.0)))
                cols["api_calls"].append(api)
                if v2:
                    cols["mobile_sessions"].append(int(au * r.uniform(0.2, 1.5)))
                if m == date(2026, 3, 1):
                    api_by_tenant[c.key] = api_by_tenant.get(c.key, 0) + api
            d += timedelta(days=1)
        fields = [pa.field("tenant_id", pa.string()), pa.field("usage_date", pa.date32()), pa.field("active_users", pa.int32()),
                  pa.field("work_orders_created", pa.int32()), pa.field("api_calls", pa.int64() if v2 else pa.int32())]
        if v2:
            fields.append(pa.field("mobile_sessions", pa.int32()))
        if not v2:
            cols["api_calls"] = [min(x, 2 ** 31 - 1) for x in cols["api_calls"]]
        tbl = pa.Table.from_pydict(cols, schema=pa.schema(fields, metadata={"writer": "usage-rollup-job", "schema_version": "2" if v2 else "1"}))
        p = lake / "usage_daily" / f"year={m.year}" / f"month={m.month:02d}" / "part-00000.snappy.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        pq.write_table(tbl, buf, compression="snappy", row_group_size=200_000)
        write_bytes(p, buf.getvalue())
    write_text(lake / "usage_daily" / "_README.md",
               "# usage_daily\n\nDaily rollup per tenant, written by the usage-rollup-job (Glue). Partitioned by year/month.\n"
               "Schema v2 from 2025-07: `api_calls` widened to int64 (v1 capped at int32 max), `mobile_sessions` added.\n"
               "`tenant_id` is the tenant slug; join to `product_events/tenants.csv` for the customer.\n")
    top_key = max(api_by_tenant, key=lambda k: (api_by_tenant[k], k))
    assert top_key == runaway.key
    second = sorted(api_by_tenant.values(), reverse=True)[1]
    add_fact(world, {"id": "GF28", "difficulty": "medium", "kind": "parquet data lake",
                     "question": "Which customer made the most API calls in March 2026?",
                     "answer": f"{runaway.name} (tenant {world.tenants[runaway.key]}) with {api_by_tenant[runaway.key]:,} calls, almost all "
                               f"between March 9 and 20 (a retry loop). The next highest tenant had {second:,}.",
                     "trail": [f"{RAW}/datalake/usage_daily/year=2026/month=03/part-00000.snappy.parquet",
                               f"{RAW}/product_events/tenants.csv (slug -> customer)"],
                     "traps": ["Parquet holds tenant slugs, not customer names", "Schema changed in 2025-07 (int32 -> int64)"],
                     "values": {"customer": runaway.name, "tenant_id": world.tenants[runaway.key], "api_calls": api_by_tenant[runaway.key]}})

    # ----------------------------------------------------------------- GF29 avro CDC
    subs = [c for c in world.customers if "sub" in c.ids and c.cloud_start and c.cloud_start <= date(2025, 12, 31)
            and (c.end is None or c.end >= date(2025, 1, 1))]
    fx = {"USD": 1.0, "CAD": 1.32, "GBP": 0.79}

    def val(c, d, status):
        upd = datetime.combine(d, time(r.randint(0, 23), r.randint(0, 59), r.randint(0, 59)))
        return {"id": c.ids["sub"], "customer": c.ids["billing"], "status": status,
                "plan": f"ops_{c.plan.lower()}_{'year' if c.annual else 'month'}ly", "quantity": c.seats(d),
                "unit_amount": int(round(c.unit_price(d) * 100 * fx[c.currency])), "currency": c.currency.lower(),
                "current_period_end": ts_ms(datetime.combine(add_months(d.replace(day=1), 1), time(0))),
                "updated_at": ts_ms(upd) * 1000}

    lsn = 88_412_000_000
    by_month = {}
    canceled = []
    sync = bytes(r.getrandbits(8) for _ in range(16))
    snap_ts = ts_ms(datetime(2025, 1, 1, 0, 4, 11))
    for c in sorted(subs, key=lambda c: c.ids["sub"]):
        if c.cloud_start < date(2025, 1, 1):
            lsn += r.randint(100, 900)
            by_month.setdefault(1, []).append({"before": None, "after": val(c, date(2025, 1, 1), "active"), "op": "r", "ts_ms": snap_ts,
                                               "src_ts": snap_ts, "snapshot": "true", "lsn": lsn})
    events = []
    for c in subs:
        prev = c.seats(date(2025, 1, 1)) if c.cloud_start < date(2025, 1, 1) else None
        for m in month_iter(date(2025, 1, 1), date(2025, 12, 1)):
            if c.cloud_start.replace(day=1) == m:
                d = c.cloud_start
                events.append((d, c, "c", None, val(c, d, "active")))
                prev = c.seats(d)
                continue
            if prev is None or (c.end and m > c.end):
                continue
            s = c.seats(m)
            if s != prev:
                d = m + timedelta(days=r.randint(0, 3))
                events.append((d, c, "u", val(c, d - timedelta(days=1), "active") | {"quantity": prev}, val(c, d, "active")))
                prev = s
        if c.end and date(2025, 1, 1) <= c.end <= date(2025, 12, 31):
            d = c.end
            events.append((d, c, "u", val(c, d, "active"), val(c, d, "canceled")))
            canceled.append(c)
    events.sort(key=lambda e: (e[0], e[1].ids["sub"], e[2]))
    for d, c, op, before, after in events:
        lsn += r.randint(100, 9000)
        t = ts_ms(datetime.combine(d, time(r.randint(0, 23), r.randint(0, 59), r.randint(0, 59))))
        by_month.setdefault(d.month, []).append({"before": before, "after": after, "op": op, "ts_ms": t + r.randint(40, 900),
                                                 "src_ts": t, "snapshot": None, "lsn": lsn})
    # connector restart on 2025-03-19: the last 40% of March's events are delivered twice
    mar = by_month.get(3, [])
    replay = mar[int(len(mar) * 0.6):]
    by_month[3] = mar + [dict(e, ts_ms=e["ts_ms"] + 86_400_000) for e in replay]
    cdc = lake / "cdc" / "billing.public.subscriptions"
    for mo, recs in sorted(by_month.items()):
        write_bytes(cdc / f"2025-{mo:02d}.avro", avro_file(recs, sync))
    dup_cancels = sum(1 for e in replay if e["after"] and e["after"]["status"] == "canceled" and e["op"] == "u")
    add_fact(world, {"id": "GF29", "difficulty": "hard", "kind": "change data capture",
                     "question": "How many subscriptions were canceled in 2025, according to the billing change log?",
                     "answer": f"{len(canceled)}. Count update events whose after.status is 'canceled', de-duplicated by source.lsn: a "
                               f"connector restart re-sent the end of March 2025, which adds {dup_cancels} duplicate cancellations.",
                     "trail": [f"{RAW}/datalake/cdc/billing.public.subscriptions/2025-*.avro",
                               f"{RAW}/billing_v3_2017-now/subscriptions.csv (canceled_at)"],
                     "traps": ["March 2025 contains replayed events (same source.lsn)", "January starts with snapshot rows (op = r)",
                               "updated_at is in microseconds, ts_ms in milliseconds"],
                     "values": {"canceled_2025": len(canceled), "duplicates_in_replay": dup_cancels}})

    # ----------------------------------------------------------------- GF30 protobuf audit + okta
    okta_ids = {}
    rows = [["id", "status", "created", "activated", "statusChanged", "lastLogin", "profile.login", "profile.firstName",
             "profile.lastName", "profile.department", "profile.title"]]
    for p in sorted(world.people, key=lambda p: p.pid):
        if p.left and p.left < date(2019, 6, 1):
            continue
        oid = "00u" + b62(r, 17)
        okta_ids[p.pid] = oid
        created = max(p.hired, date(2019, 6, 3))
        gone = p.left and p.left <= AS_OF
        rows.append([oid, "DEPROVISIONED" if gone else "ACTIVE", f"{created}T13:{r.randint(0, 59):02d}:00.000Z",
                     f"{created}T14:{r.randint(0, 59):02d}:00.000Z",
                     f"{p.left}T23:59:00.000Z" if gone else f"{created}T14:00:00.000Z",
                     f"{p.left}T{r.randint(12, 22):02d}:{r.randint(0, 59):02d}:00.000Z" if gone else f"{AS_OF - timedelta(days=r.randint(0, 9))}T14:02:00.000Z",
                     p.email(p.left if gone else AS_OF), p.first, p.last, p.dept, p.title])
    write_text(out / "identity" / "okta_users_export_2026-10.csv", "\n".join(csv_line(x) for x in rows) + "\n")

    leavers = sorted([p for p in world.people if p.dept == "Sales" and p.left and date(2025, 3, 1) <= p.left <= date(2025, 11, 30)
                      and p.pid in okta_ids], key=lambda p: (p.left, p.pid))
    leaver = leavers[0]
    last_day = leaver.left
    while last_day.weekday() >= 5:
        last_day -= timedelta(days=1)
    export_days = [last_day - timedelta(days=6), last_day - timedelta(days=2), last_day]
    exports = [datetime.combine(export_days[0], time(22, 41, 7)), datetime.combine(export_days[1], time(23, 5, 52)),
               datetime.combine(export_days[2], time(1, 12, 30)) + timedelta(days=1)]   # 01:12 UTC = evening of the last day, US time
    _staff = {}

    def active_staff(d):
        if d not in _staff:
            _staff[d] = [p for p in world.people if p.pid in okta_ids and p.hired <= d and (not p.left or p.left >= d)]
        return _staff[d]
    paths = ["/v2/work-orders", "/v2/work-orders/{id}", "/v2/technicians", "/v2/invoices", "/v2/customers/{id}", "/v2/reports/usage",
             "/v2/sites/{id}", "/v1/sync"]
    revops = okta_ids["E011"]
    export_total = 0
    for m in month_iter(date(2025, 1, 1), date(2025, 12, 1)):
        nxt = add_months(m, 1)
        msgs = []
        for _ in range(7000):
            d = m + timedelta(days=r.randint(0, (nxt - m).days - 1))
            t = datetime.combine(d, time(r.randint(11, 23), r.randint(0, 59), r.randint(0, 59), r.randint(0, 999) * 1000))
            if r.random() < 0.3:
                actor = "svc:" + r.choice(["netsuite-sync", "mobile-bff", "report-scheduler"])
            else:
                actor = okta_ids[r.choice(active_staff(d)).pid]
            msgs.append((t, actor, r.choice(["GET", "GET", "GET", "POST", "PATCH"]), r.choice(paths), r.choice([200] * 30 + [201, 204, 400, 404, 500]),
                         f"203.0.113.{r.randint(2, 250)}", r.randint(200, 90_000)))
        # RevOps runs the customer export on the first business day of each month (legitimate)
        fbd = m
        while fbd.weekday() >= 5:
            fbd += timedelta(days=1)
        msgs.append((datetime.combine(fbd, time(13, 30, 2)), revops, "GET", "/v2/export/customers", 200, "203.0.113.17", 48_211_904 + r.randint(0, 900_000)))
        for t in exports:
            if t.year == m.year and t.month == m.month:
                b = 48_900_000 + r.randint(0, 900_000)
                export_total += b
                msgs.append((t, okta_ids[leaver.pid], "GET", "/v2/export/customers", 200, f"198.51.100.{r.randint(2, 250)}", b))
        msgs.sort(key=lambda x: x[0])
        blob = bytearray()
        for t, actor, meth, path, st, ip, nb in msgs:
            body = (pb_field(1, ts_ms(t)) + pb_field(2, actor) + pb_field(3, meth) + pb_field(4, path) + pb_field(5, st)
                    + pb_field(6, ip) + pb_field(7, nb) + pb_field(8, b62(r, 22)))
            if m >= date(2025, 6, 1):
                body += pb_field(9, r.choice(["bc-web/7.4", "BrindleOps-iOS/5.2", "python-requests/2.32.3", "NetSuite-SuiteScript"]))
            blob += varint(len(body)) + body
        write_bytes(lake / "api_audit" / f"audit-{m:%Y-%m}.binpb", bytes(blob))
    write_text(lake / "api_audit" / "audit_event.proto", PROTO)
    add_fact(world, {"id": "GF30", "difficulty": "hard", "kind": "binary audit log",
                     "question": "Did anyone who left Brindlecove in 2025 export the customer list shortly before leaving?",
                     "answer": f"Yes. {leaver.name} ({leaver.title}, last day {leaver.left}) called GET /v2/export/customers 3 times in the "
                               f"final week, from outside the office network (198.51.100.x), the last one on the evening of their last day "
                               f"(01:12 UTC on {exports[2].date()}). RevOps' monthly exports from the office are routine.",
                     "trail": [f"{RAW}/datalake/api_audit/audit-{last_day:%Y-%m}.binpb (length-delimited protobuf, see audit_event.proto)",
                               f"{RAW}/identity/okta_users_export_2026-10.csv (actor_id -> person, status DEPROVISIONED)"],
                     "traps": ["actor_id is an opaque Okta id", "Timestamps are UTC; the last call is the previous evening in US time",
                               "RevOps (Femi Adeyemi) runs the same export monthly, which is normal"],
                     "values": {"person": leaver.name, "left": str(leaver.left), "export_calls": 3,
                                "export_utc": [t.isoformat() for t in exports]}})
    return {}
