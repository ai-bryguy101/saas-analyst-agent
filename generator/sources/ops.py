"""IT operations: Windows event logs, Active Directory, web server logs, infrastructure code.

Renders:
  it_ops/windows_events/FS01_Security_2019-10-28_to_2019-11-01.xml   wevtutil-style export: 4624 logons, 4663 object access, 4660 deletes
  it_ops/ad_export/ad_users_2019-11-04.ldif                          LDIF, objectSid base64, disabled users moved to an OU
  it_ops/syslog/fw01_2022-06.log                                    RFC 3164 syslog, no year in the timestamp
  web_logs/api.brindlecove.example/access-YYYY-MM.log.gz            nginx combined format, local time with offset, 2025
  infra/terraform/*.tf, infra/terraform/terraform.tfstate.redacted.json, infra/k8s/*.yaml, infra/docker/Dockerfile

Planted:
  GF31  who deleted the FY2016_close folder on the finance share, and when (4660 has no file name; join on HandleId)
  GF32  the longest API outage of 2025, seen only in the web logs
"""
from __future__ import annotations

import base64
import gzip
import io
import json
import struct
from datetime import date, datetime, time, timedelta, timezone

from ..util import add_fact, b62, rng_for, write_bytes, write_text

RAW = "data/raw"
DOMAIN_SID = "S-1-5-21-3623811015-3361044348-30300820"


def sid_bytes(rid: int) -> bytes:
    subs = [21, 3623811015, 3361044348, 30300820, rid]
    return struct.pack("<BB", 1, len(subs)) + (5).to_bytes(6, "big") + b"".join(struct.pack("<I", s) for s in subs)


def is_dst(d: date) -> bool:
    return 3 < d.month < 11 or (d.month == 3 and d.day >= 9) or (d.month == 11 and d.day < 2)


def evt(eid, when_utc: datetime, rec, data: dict, task: str, keywords="0x8020000000000000"):
    ts = when_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when_utc.microsecond:06d}" + "0Z"
    fields = "".join(f"<Data Name='{k}'>{v}</Data>" for k, v in data.items())
    return (f"<Event xmlns='http://schemas.microsoft.com/win/2004/08/events/event'><System><Provider Name='Microsoft-Windows-Security-Auditing' "
            f"Guid='{{54849625-5478-4994-A5BA-3E3B0328C30D}}'/><EventID>{eid}</EventID><Version>{1 if eid == 4663 else 0}</Version><Level>0</Level>"
            f"<Task>{task}</Task><Opcode>0</Opcode><Keywords>{keywords}</Keywords><TimeCreated SystemTime='{ts}'/>"
            f"<EventRecordID>{rec}</EventRecordID><Correlation/><Execution ProcessID='4' ThreadID='{rec % 9000 + 100}'/><Channel>Security</Channel>"
            f"<Computer>FS01.corp.brindlecove.example</Computer><Security/></System><EventData>{fields}</EventData></Event>")


def render(world, out, seed):
    r = rng_for(seed, "ops")
    people = {p.pid: p for p in world.people}

    # ----------------------------------------------------------------- AD users (LDIF)
    def sam(p):
        return (p.first[0] + p.last).lower().replace("'", "").replace(" ", "").replace("-", "")[:20]

    rids = {}
    ld = ["version: 1", ""]
    asof = date(2019, 11, 4)
    for i, p in enumerate(sorted(world.people, key=lambda p: p.pid)):
        if p.hired > asof or (p.left and p.left < date(2018, 1, 1)):
            continue
        rid = 1104 + i * 3
        rids[p.pid] = rid
        gone = p.left and p.left <= asof
        ou = "OU=Disabled Users" if gone else f"OU={p.dept.replace(' ', '')},OU=Staff"
        ld += [f"dn: CN={p.name},{ou},DC=corp,DC=brindlecove,DC=example", "objectClass: top", "objectClass: person",
               "objectClass: organizationalPerson", "objectClass: user", f"cn: {p.name}", f"sn: {p.last}", f"givenName: {p.first}",
               f"displayName: {p.name}", f"sAMAccountName: {sam(p)}", f"userPrincipalName: {sam(p)}@corp.brindlecove.example",
               f"objectSid:: {base64.b64encode(sid_bytes(rid)).decode()}", f"department: {p.dept}", f"title: {p.title}",
               f"userAccountControl: {514 if gone else 512}", f"whenCreated: {p.hired:%Y%m%d}120000.0Z"]
        if gone:
            ld.append(f"description: Termed {p.left.month}/{p.left.day}/{p.left.year} - per HR ticket, do not delete until 90 days")
        ld.append("")
    write_text(out / "it_ops" / "ad_export" / "ad_users_2019-11-04.ldif", "\n".join(ld))

    # ----------------------------------------------------------------- GF31 Windows events
    yuki = people["E009"]
    files = ["FY2016_close\\AJE_proposed_v1.xlsx", "FY2016_close\\AJE_proposed_v2.xlsx", "FY2016_close\\TB_final_12-31-16.xlsx",
             "FY2016_close\\rev_rec_memo_DRAFT.docx", "FY2016_close\\auditor_PBC_list.xlsx", "FY2016_close\\Thumbs.db", "FY2016_close"]
    staff = [p for p in world.people if p.pid in rids and p.hired <= date(2019, 10, 28) and (not p.left or p.left >= date(2019, 11, 1))]
    events = []
    rec = 81_204_331
    t = datetime(2019, 10, 28, 11, 0, 0)
    while t < datetime(2019, 11, 2, 3, 0, 0):
        t += timedelta(seconds=r.randint(20, 400))
        p = r.choice(staff)
        if r.random() < 0.3:
            events.append((t, 4624, {"SubjectUserSid": "S-1-0-0", "TargetUserSid": f"{DOMAIN_SID}-{rids[p.pid]}", "TargetUserName": sam(p),
                                     "TargetDomainName": "CORP", "LogonType": "3", "IpAddress": f"10.20.{r.randint(1, 9)}.{r.randint(10, 250)}"}, "12544"))
        else:
            share = r.choice(["Finance\\Month-end\\", "Finance\\AP\\", "Sales\\Quotes\\", "IT\\scripts\\", "Finance\\FY2016_close\\"])
            events.append((t, 4663, {"SubjectUserSid": f"{DOMAIN_SID}-{rids[p.pid]}", "SubjectUserName": sam(p), "SubjectDomainName": "CORP",
                                     "ObjectServer": "Security", "ObjectType": "File",
                                     "ObjectName": f"C:\\Shares\\{share}{r.choice(['report.xlsx', 'notes.docx', 'export.csv', 'Thumbs.db'])}",
                                     "HandleId": f"0x{r.randint(0x1000, 0xfffff):x}", "AccessList": "%%4416", "AccessMask": "0x1",
                                     "ProcessName": "System"}, "12800"))
    del_local = datetime(2019, 10, 30, 17, 31, 4)
    del_utc = del_local + timedelta(hours=4)
    handles = []
    for k, f in enumerate(files):
        tt = del_utc + timedelta(milliseconds=k * 37)
        h = f"0x{0x2a40 + k * 0x1c:x}"
        handles.append(h)
        base = {"SubjectUserSid": f"{DOMAIN_SID}-{rids['E009']}", "SubjectUserName": sam(yuki), "SubjectDomainName": "CORP",
                "SubjectLogonId": "0x3e1a7f2"}
        events.append((tt, 4663, base | {"ObjectServer": "Security", "ObjectType": "File", "ObjectName": f"C:\\Shares\\Finance\\{f}",
                                         "HandleId": h, "AccessList": "%%1537", "AccessMask": "0x10000", "ProcessName": "System"}, "12800"))
        events.append((tt + timedelta(microseconds=900), 4660, base | {"ObjectServer": "Security", "HandleId": h, "ProcessId": "0x4",
                                                                        "ProcessName": "", "TransactionId": "{00000000-0000-0000-0000-000000000000}"}, "12800"))
    events.sort(key=lambda e: e[0])
    xml = ["<Events>"]
    for when, eid, data, task in events:
        rec += 1
        xml.append(evt(eid, when + timedelta(microseconds=r.randint(0, 999_999)) if eid == 4624 else when, rec, data, task))
    xml.append("</Events>")
    write_text(out / "it_ops" / "windows_events" / "FS01_Security_2019-10-28_to_2019-11-01.xml", "\r\n".join(xml) + "\r\n", bom=True)
    add_fact(world, {"id": "GF31", "difficulty": "hard", "kind": "windows event log",
                     "question": "Who deleted the FY2016_close folder from the finance file share, and when?",
                     "answer": f"{yuki.name} (account {sam(yuki)}) at {del_local:%-I:%M %p} Eastern on {del_local:%B %-d, %Y}, the day before "
                               f"their last day. Event 4660 (object deleted) carries only a HandleId, so it has to be joined to the 4663 event "
                               f"with the same HandleId to get the path. A copy survives in the share backup zip taken 26 minutes earlier.",
                     "trail": [f"{RAW}/it_ops/windows_events/FS01_Security_2019-10-28_to_2019-11-01.xml (SystemTime is UTC)",
                               f"{RAW}/it_ops/ad_export/ad_users_2019-11-04.ldif", f"{RAW}/file_shares/FS01_Finance_share_2019.zip"],
                     "traps": ["4660 has no ObjectName", "SystemTime is UTC (21:31Z = 5:31 PM EDT)",
                               "Many routine 4663 reads of the same folder by other people"],
                     "values": {"person": yuki.name, "account": sam(yuki), "deleted_local": del_local.isoformat(), "deleted_utc": del_utc.isoformat()}})

    # ----------------------------------------------------------------- syslog
    sl = []
    t = datetime(2022, 6, 1, 0, 0, 3)
    while t < datetime(2022, 7, 1):
        t += timedelta(seconds=r.randint(1, 90))
        sl.append(f"{t:%b} {t.day:>2} {t:%H:%M:%S} fw01 kernel: [WAN_IN-{r.choice(['default-D', '2000-A', '3010-D'])}]IN=eth0 OUT= "
                  f"SRC=198.51.100.{r.randint(1, 254)} DST=203.0.113.10 LEN={r.randint(40, 1500)} PROTO={r.choice(['TCP', 'UDP'])} "
                  f"SPT={r.randint(1024, 65535)} DPT={r.choice([22, 443, 3389, 445, 8080])}")
    write_text(out / "it_ops" / "syslog" / "fw01_2022-06.log", "\n".join(sl) + "\n")

    # ----------------------------------------------------------------- GF32 nginx access logs
    outage_start = datetime(2025, 3, 18, 14, 2, 0)      # local (EDT, -0400)
    outage_end = datetime(2025, 3, 18, 14, 49, 0)
    blip = (datetime(2025, 8, 6, 9, 15, 0), datetime(2025, 8, 6, 9, 24, 0))
    paths = ["/v2/work-orders", "/v2/work-orders/{n}", "/v2/technicians", "/v1/sync", "/v2/invoices?page={p}", "/health", "/v2/sites/{n}"]
    uas = ["BrindleOps-iOS/5.1 (iPhone; iOS 18.2)", "BrindleOps-Android/5.1", "python-requests/2.32.3", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "NetSuite-SuiteScript/2.1", "ELB-HealthChecker/2.0"]
    for mo in range(1, 13):
        d0 = datetime(2025, mo, 1)
        d1 = datetime(2025 + (mo == 12), mo % 12 + 1, 1)
        buf = []
        t = d0
        while t < d1:
            t += timedelta(seconds=r.expovariate(1 / 20))
            st = r.choice([200] * 60 + [201, 204, 304, 400, 401, 404])
            if r.random() < 0.0008:
                st = r.choice([500, 502, 504])
            if outage_start <= t < outage_end or blip[0] <= t < blip[1]:
                st = 502 if r.random() < 0.93 else 200
            off = "-0400" if is_dst(t.date()) else "-0500"
            path = r.choice(paths).format(n=r.randint(1000, 999999), p=r.randint(1, 40))
            buf.append(f"10.40.{r.randint(0, 3)}.{r.randint(2, 250)} - - [{t:%d/%b/%Y:%H:%M:%S} {off}] \"{r.choice(['GET'] * 5 + ['POST', 'PATCH'])} {path} HTTP/1.1\" "
                       f"{st} {0 if st == 502 else r.randint(120, 40000)} \"-\" \"{r.choice(uas)}\" {r.uniform(0.002, 1.8) if st != 502 else 60.0:.3f}")
        raw = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as g:
            g.write(("\n".join(buf) + "\n").encode())
        write_bytes(out / "web_logs" / "api.brindlecove.example" / f"access-2025-{mo:02d}.log.gz", raw.getvalue())
    mins = int((outage_end - outage_start).total_seconds() // 60)
    add_fact(world, {"id": "GF32", "difficulty": "medium", "kind": "web server logs",
                     "question": "What was the longest API outage in 2025?",
                     "answer": f"March 18, 2025, from {outage_start:%-I:%M} to {outage_end:%-I:%M %p} Eastern ({mins} minutes), when almost every "
                               f"request returned 502. The only other burst (August 6, about 9 minutes) was shorter. Neither has an incident ticket.",
                     "trail": [f"{RAW}/web_logs/api.brindlecove.example/access-2025-03.log.gz (local time with -0400 offset)",
                               f"{RAW}/jira_export_2026-10/INC.json (no matching incident)"],
                     "traps": ["Times carry a local offset that changes with DST", "Scattered single 5xx errors all year are noise"],
                     "values": {"date": "2025-03-18", "start_local": outage_start.isoformat(), "end_local": outage_end.isoformat(), "minutes": mins}})

    # ----------------------------------------------------------------- infra as code
    inf = out / "infra"
    write_text(inf / "terraform" / "rds.tf", """# billing database after the AWS move (cutover 2023-02-18)
resource "aws_db_instance" "billing_prod" {
  identifier              = "billing-prod"
  engine                  = "postgres"
  engine_version          = "14.6"
  instance_class          = "db.r6g.xlarge"
  allocated_storage       = 500
  multi_az                = true
  username                = "billing_admin"
  password                = var.billing_db_password   # REDACTED - stored in SSM /prod/billing/db
  backup_retention_period = 14
  deletion_protection     = true
  tags = { owner = "cmacleod", cost_center = "ENG-PLAT" }
}
""")
    write_text(inf / "terraform" / "variables.tf", 'variable "billing_db_password" {\n  type      = string\n  sensitive = true\n}\n')
    state = {"version": 4, "terraform_version": "1.3.9", "serial": 212, "lineage": f"{b62(r, 8)}-REDACTED",
             "resources": [{"mode": "managed", "type": "aws_db_instance", "name": "billing_prod", "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                            "instances": [{"attributes": {"identifier": "billing-prod", "engine": "postgres", "engine_version": "14.6",
                                                          "endpoint": "billing-prod.REDACTED.us-east-2.rds.amazonaws.com:5432",
                                                          "password": "REDACTED", "multi_az": True}}]}]}
    write_text(inf / "terraform" / "terraform.tfstate.redacted.json", json.dumps(state, indent=2) + "\n")
    write_text(inf / "k8s" / "billing-svc.yaml", """apiVersion: apps/v1
kind: Deployment
metadata:
  name: billing-svc
  namespace: billing
spec:
  replicas: 3
  selector: {matchLabels: {app: billing-svc}}
  template:
    metadata: {labels: {app: billing-svc}}
    spec:
      containers:
      - name: app
        image: REDACTED.dkr.ecr.us-east-2.amazonaws.com/billing-svc:2025.10.3
        env:
        - {name: DB_HOST, value: billing-prod.REDACTED.us-east-2.rds.amazonaws.com}
        - name: DB_PASSWORD
          valueFrom: {secretKeyRef: {name: billing-db, key: password}}
        - {name: STRIPE_COMPAT_MODE, value: "cents"}   # amounts in cents since v3; ledger imports were dollars
""")
    write_text(inf / "docker" / "Dockerfile", """FROM python:3.11-slim
# billing-svc. Built by CI; do not build locally with prod creds.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV TZ=UTC
CMD ["gunicorn", "billing.wsgi", "-w", "4", "-b", "0.0.0.0:8000"]
""")
    return {}
