"""Product telemetry and server logs.

Renders:
  product_events/events_YYYY-MM.jsonl.gz     2019-01..2026-10, schema v1 (epoch ms, account_id) until 2022-03,
                                             schema v2 (ISO-8601, tenant_id, nested props) after
  product_events/tenants.csv                 tenant slug -> billing customer id (incomplete)
  app_logs/app-YYYY-MM-DD.log[.gz]           log4j-style; before 2018-03-12 local Dallas time with NO offset
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from ..util import AS_OF, csv_line, hexid, month_iter, rng_for, write_gz, write_text

EVENTS = [("login", 30), ("wo_created", 25), ("wo_closed", 20), ("mobile_sync", 15), ("report_exported", 4),
          ("asset_added", 3), ("pm_schedule_run", 2), ("invoice_sent", 1)]
SCHEMA_V2 = date(2022, 3, 1)


def slug(name):
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.replace("’", ""))
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:28]


def render(world, out, seed):
    r = rng_for(seed, "telemetry")
    base = out / "product_events"
    tenants = {}
    trows = [["tenant_id", "display_name", "billing_customer", "region", "created"]]
    for c in world.customers:
        if c.cloud_start and (c.end is None or c.end >= date(2019, 1, 1)):
            t = slug(c.name)
            if t in tenants.values():
                t = t + "-" + hexid(r, 3)
            tenants[c.key] = t
            trows.append([t, c.name if r.random() > 0.2 else r.choice(c.variants),
                          c.ids.get("billing", "") if r.random() > 0.07 else "", {"US": "us-east", "CA": "ca-central", "GB": "eu-west"}[c.country],
                          str(max(c.cloud_start, date(2019, 1, 1)))])
    write_text(base / "tenants.csv", "\n".join(csv_line(x) for x in trows) + "\n")

    names, weights = zip(*EVENTS)
    wo_2024 = Counter()
    for m in month_iter(date(2019, 1, 1), AS_OF):
        nxt = date(m.year + (m.month == 12), (m.month % 12) + 1, 1)
        active = [c for c in world.customers if c.key in tenants and c.cloud_start <= m and (c.end is None or c.end >= m)]
        lines = []
        weights_c = [c.seats(m) for c in active]
        n = 8000
        picks = r.choices(active, weights_c, k=n)
        for c in picks:
            ev = r.choices(names, weights)[0]
            secs = r.randint(0, int((datetime(nxt.year, nxt.month, 1) - datetime(m.year, m.month, 1)).total_seconds()) - 1)
            t = datetime(m.year, m.month, 1, tzinfo=timezone.utc) + timedelta(seconds=secs)
            user = "u_" + hexid(r, 10)
            if ev == "wo_created" and m.year == 2024:
                wo_2024[c.key] += 1
            if m < SCHEMA_V2:
                rec = {"ts": int(t.timestamp() * 1000), "event": ev, "account_id": tenants[c.key], "user": user,
                       "platform": r.choice(["web", "ios", "android", "web", "api"]), "v": 1}
                if ev == "wo_created":
                    rec["priority"] = r.choice(["low", "med", "high", "EMERGENCY"])
            else:
                rec = {"event_time": t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "event_name": ev, "tenant_id": tenants[c.key],
                       "actor": {"id": user, "role": r.choice(["tech", "dispatcher", "admin", "requester"])},
                       "context": {"platform": r.choice(["web", "ios", "android", "web", "api"]), "app_version": f"{m.year - 2016}.{m.month}.{r.randint(0, 9)}"},
                       "schema_version": 2}
                if ev == "wo_created":
                    rec["properties"] = {"priority": r.choice(["low", "medium", "high", "emergency"]), "source": r.choice(["web", "email", "qr", "api"])}
            lines.append(rec)
        # bot / synthetic monitor noise and duplicated delivery
        for _ in range(r.randint(50, 150)):
            lines.append(dict(lines[r.randrange(len(lines))]))
        lines.append({"ts" if m < SCHEMA_V2 else "event_time": None, "event": "healthcheck", "account_id": "synthetic-monitor"})
        lines.sort(key=lambda x: str(x.get("ts") or x.get("event_time") or ""))
        write_gz(base / f"events_{m:%Y-%m}.jsonl.gz", "\n".join(json.dumps(x) for x in lines) + "\n")
    world.wo_2024 = wo_2024
    world.tenants = tenants

    render_logs(world, out, r)
    return {}


def render_logs(world, out, r):
    base = out / "app_logs"
    # --- the DST incident, local time without offset (America/Chicago)
    lines = []
    seq = 88_100_000
    t = datetime(2017, 11, 4, 22, 0, 0)          # local wall clock
    phase = "pre"
    # true UTC of first and last error: 06:20Z and 07:59Z
    utc = datetime(2017, 11, 5, 3, 0, 0)
    end_utc = datetime(2017, 11, 5, 11, 0, 0)
    while utc < end_utc:
        utc += timedelta(seconds=r.randint(4, 40))
        local = utc - timedelta(hours=5 if utc < datetime(2017, 11, 5, 7, 0) else 6)
        seq += 1
        down = datetime(2017, 11, 5, 6, 20) <= utc < datetime(2017, 11, 5, 8, 0)
        if down:
            if r.random() < 0.7:
                lines.append(f"{local:%Y-%m-%d %H:%M:%S},{r.randint(0, 999):03d} ERROR [http-nio-8443-exec-{r.randint(1, 200)}] c.b.ops.db.PoolManager - req={seq} "
                             f"Cannot get a connection, pool error Timeout waiting for idle object")
            else:
                lines.append(f"{local:%Y-%m-%d %H:%M:%S},{r.randint(0, 999):03d} WARN  [http-nio-8443-exec-{r.randint(1, 200)}] c.b.ops.web.Health - req={seq} healthcheck FAILED (503)")
        else:
            lvl, msg = r.choice([("INFO ", "c.b.ops.web.Access - req={s} GET /api/v2/workorders 200 {ms}ms"),
                                 ("INFO ", "c.b.ops.sync.MobileSync - req={s} sync ok tenant={t} items={n}"),
                                 ("DEBUG", "c.b.ops.sched.PmRunner - req={s} pm tick"),
                                 ("WARN ", "c.b.ops.mail.Sender - req={s} SMTP slow {ms}ms")])
            lines.append(f"{local:%Y-%m-%d %H:%M:%S},{r.randint(0, 999):03d} {lvl} [http-nio-8443-exec-{r.randint(1, 200)}] " +
                         msg.format(s=seq, ms=r.randint(20, 900), t=r.choice(list(world.tenants.values()) or ["x"]), n=r.randint(1, 80)))
    lines.insert(0, "# host=app03.dal.brindlecove.local  log4j 1.2  pattern=%d %-5p [%t] %c - %m%n")
    write_text(base / "app-2017-11-04_05.dal-app03.log", "\n".join(lines) + "\n")
    world.dst_incident = {"start_utc": "2017-11-05T06:20:00Z", "end_utc": "2017-11-05T08:00:00Z", "minutes": 100}

    # --- a normal pre-switch day and a post-switch UTC day (one per year-ish), gzipped
    for d in [date(2016, 3, 8), date(2018, 3, 13), date(2021, 7, 19), date(2023, 2, 18), date(2025, 11, 2) if date(2025, 11, 2) < date(2026, 10, 31) else date(2025, 1, 2)]:
        lines = []
        utc_mode = d >= date(2018, 3, 12)
        cur = datetime(d.year, d.month, d.day)
        for _ in range(12000):
            cur += timedelta(seconds=r.randint(1, 13))
            if cur.date() != d:
                break
            seq += 1
            stamp = cur.strftime("%Y-%m-%dT%H:%M:%S.") + f"{r.randint(0, 999):03d}Z" if utc_mode else cur.strftime("%Y-%m-%d %H:%M:%S,") + f"{r.randint(0, 999):03d}"
            lvl = r.choices(["INFO ", "WARN ", "ERROR", "DEBUG"], [80, 8, 2, 10])[0]
            if d == date(2016, 3, 8) and 13 <= cur.hour < 17:
                lvl = r.choice(["ERROR", "ERROR", "WARN "])
            msg = {"INFO ": f"c.b.ops.web.Access - req={seq} GET /api/v{2 if utc_mode else 1}/workorders 200 {r.randint(20, 400)}ms",
                   "WARN ": f"c.b.ops.web.Access - req={seq} slow request {r.randint(2000, 9000)}ms",
                   "ERROR": f"c.b.ops.db.PoolManager - req={seq} " + r.choice(["Cannot get a connection, pool error Timeout waiting for idle object",
                                                                                 "SQLState: 40001 deadlock detected", "NullPointerException at WorkOrderService.java:412"]),
                   "DEBUG": f"c.b.ops.sched.PmRunner - req={seq} pm tick"}[lvl]
            if r.random() < 0.002:
                msg += f" user=jdoe@example.com token=[REDACTED] ip=10.{r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(0, 255)}"
            lines.append(f"{stamp} {lvl} [exec-{r.randint(1, 64)}] {msg}")
        host = "app01.dal.brindlecove.local" if d < date(2023, 2, 18) else "ip-10-20-3-17.ec2.internal"
        write_gz(base / f"app-{d}.{host.split('.')[0]}.log.gz", f"# host={host}\n" + "\n".join(lines) + "\n")
