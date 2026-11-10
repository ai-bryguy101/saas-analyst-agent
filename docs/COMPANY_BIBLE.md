# Brindlecove Software, Inc. — company bible

> **Synthetic.** Everything here is invented. This file is the "truth" the
> generator renders from; the raw files only ever show partial, messy,
> sometimes wrong views of it. An agent should never read this file when
> answering questions — it is for humans building and grading the agent.

## One-paragraph story

Brindle Data Systems was founded in **Dayton, Ohio in March 1994** to sell
"Brindle Classic", an on-premise maintenance and work-order system for
facilities teams (schools, councils, property managers, hospitals). Licenses
were billed from **BRIX**, a COBOL batch system on a midrange box. In **July
2011** the company launched a SaaS product, **Brindle Ops Cloud**, moved
billing to a home-grown MySQL system called **Ledger**, and later renamed
itself **Brindlecove Software, Inc.** It bought three companies (TallyFlow,
Meridian Dispatch, Kestrel Analytics), migrated CRM and billing twice, moved
to AWS, and sunset Classic on **June 30, 2020**. The data snapshot is taken
on **October 31, 2026**.

## Timeline

| Date | Event |
|---|---|
| 1994-03 | Founded as Brindle Data Systems. BRIX billing starts 1994-04 |
| 1996-01 | Earliest readable BRIX invoice tapes (1994-95 tapes unreadable) |
| 2000-01 | Y2K: some late-fee rows written with century flag 0 before the patch |
| 2003 | Sales team keeps contacts in a dBase III file |
| 2006-02 | SugarCRM rolled out |
| 2011-07-01 | Ops Cloud launches; BRIX retired; Ledger (MySQL) billing starts |
| 2014-09-15 | Acquires **TallyFlow** (Austin, TX) — becomes the Invoicing add-on |
| 2015 | NetSuite becomes the general ledger |
| 2016-05-14 | Sugar → Salesforce migration weekend (crosswalk spreadsheet has errors) |
| 2017-04-01 | Billing v3 (Stripe-style) replaces Ledger; Ledger history imported in dollars, not cents |
| 2017-11-05 | DB pool outage during the DST change (logs in local time) |
| 2018-02-01 | Acquires **Meridian Dispatch** (Winnipeg, MB, CAD) — Dispatch add-on |
| 2018-03-12 | App logs switch from US/Central local time to UTC |
| 2019-07-01 | Meridian billing folded into billing v3; helpdesk replaced by Jira |
| 2019-11-14 | Exec staff decides Classic end-of-life terms |
| 2020-06-30 | Brindle Classic end of life |
| 2021-06-01 | Acquires **Kestrel Analytics** (Leeds, UK, GBP) — "Project Lantern" = Brindle Insights |
| 2022-04-01 | Kestrel billing folded into billing v3 |
| 2023-02-18 | Data-centre to AWS cutover |
| 2026-10-31 | Snapshot date of every export |

## Products and prices

Ops Cloud is priced per seat per month. List prices by price book:

| Effective | Starter | Pro | Enterprise |
|---|---|---|---|
| 2011-07-01 | $15 | $29 | $45 |
| 2015-01-01 | $17 | $32 | $49 |
| 2019-01-01 | $19 | $35 | $54 |
| 2023-01-01 | $22 | $39 | $59 |

Add-ons: Invoicing $6/seat, Dispatch $9/seat, Insights $400/month flat.
Classic was a one-off license ($8k–$60k) plus 18% annual maintenance billed
quarterly. Canadian customers pay in CAD (~1.32× list), UK customers in GBP
(~0.79× list). Planning FX: CAD 0.75, GBP 1.27 to USD; NetSuite holds the
actual monthly rates, which disagree.

Existing customers are grandfathered on their old price book. Some have
contract-specific discounts that appear only in the contract.

## People (all invented)

| ID | Name | Role |
|---|---|---|
| E001 | Margaret Okonkwo-Hale | Founder, CEO |
| E002 | Desmond Fairweather | CTO (left 2015) |
| E003 | Lorraine Whitlock | CFO |
| E004 | Gideon Ashdown | VP Sales 2012–2021 |
| E005 | Priya Raghunathan | VP Customer Success |
| E006 | Tomasz Kowalski | VP Engineering |
| E007 | Renata Esposito | VP Sales 2021+ |
| E008 | Harold Penhallow | Mainframe operator (BRIX) |
| E009 | Yuki Tanaka | DBA |
| E010 | Callum MacLeod | SRE |
| E011 | Femi Adeyemi | RevOps |
| E012 | Ines Delacroix | Controller |
| E013 | Bryce Kittredge | Senior Account Executive |
| E014 | Sofia Marchetti | Customer Success Manager |
| E015 | Jae-won Park | Support Lead |
| E016 | Abigail Fenwick | General Counsel |
| E017–E019 | — | Heads of the acquired companies |
| E020 | Noor Haddad | Data Analyst |

Email addresses change with the era: `@brindledata.example` before the rename,
`@brindlecove.example` after, and acquired staff keep their old domain
(`@tallyflow.example`, `@meridiandispatch.example`, `@kestrel-analytics.example`)
for a while. Every domain in the estate uses the reserved `.example` suffix.

## Systems by era

| System | Years | Folder | Format |
|---|---|---|---|
| BRIX (COBOL billing) | 1994–2011 | `brix_mainframe/` | Fixed-width ASCII + binary EBCDIC with packed decimal, copybooks, JCL |
| dBase sales contacts | 2003 | `sales_dbase_2003/` | dBase III `.DBF` |
| SugarCRM | 2006–2016 | `crm_sugar_export_2016/` | `;`-delimited CSV in cp1252 |
| CRM migration | 2016 | `crm_migration_2016/` | Hand-made crosswalk `.xlsx` |
| Salesforce | 2016– | `crm_salesforce_export_2026-10/` | Data Loader CSV, UTF-8 with BOM |
| TallyFlow billing | 2012–2014 | `billing_tallyflow_2012-2014/` | XML export |
| Ledger (MySQL) | 2011–2017 | `billing_ledger_mysql_2011-2017/` | `mysqldump` SQL, latin1 tables |
| Meridian billing | 2015–2019 | `billing_meridian_2015-2019/` | French/English CSV, CAD, comma decimals |
| Kestrel billing | 2018–2022 | `billing_kestrel_2018-2022/` | Xero-style CSV, GBP with VAT |
| Billing v3 | 2017– | `billing_v3_2017-now/` | Stripe-style CSV, cents, unix timestamps |
| NetSuite GL | 2015– | `finance_netsuite/` | GL detail CSV per fiscal year, FX table |
| Helpdesk | 2011–2019 | `support_helpdesk_2011-2019/` | Zendesk-style JSON (gzip) |
| Jira | 2019– | `jira_export_2026-10/` | Jira REST JSON (SUP, INC, DATA, ENG) |
| Product telemetry | 2019– | `product_events/` | JSONL (gzip), schema change 2022-03 |
| App logs | 2016–2025 | `app_logs/` | log4j text, local time then UTC |
| Email | 2011–2026 | `email_archive/` | mbox and a legal-hold folder of `.eml` |
| Confluence | 2012– | `wiki_confluence_export/` | HTML space export |
| Contracts | 1990s– | `legal_contracts/` | Image-only scans + OCR, text PDFs, `.docx` |
| Memos | 1999– | `memos/` | RTF |
| Spreadsheets | 2008–2012 | `spreadsheets/` | Excel 97 `.xls` |
| Board and finance | 2019– | `board_and_finance/` | `.pptx` decks, `.xlsx` close file |
| Meetings | 2019– | `meetings/` | WebVTT and Teams-style transcripts |
| Integrations | 2013– | `integrations/` | SOAP XML, webhook JSON, X12 EDI 850 |
| Config | 2011– | `config/` | YAML, INI (CRLF), `.properties` |
| Lotus 1-2-3 budgets | 1996–1997 | `finance_lotus_1997/` | Binary `.WK1` |
| BRIX print reports | 2009–2010 | `brix_mainframe/reports/` | 132-column `.PRN` print-to-file, form feeds |
| QuickBooks (TallyFlow) | 2012–2014 | `billing_tallyflow_2012-2014/quickbooks/` | `.IIF` tab-delimited |
| Phone system | 2018– | `phone_system/`, `voicemail_transcripts/` | CUCM CDR CSV (UTC epoch), speech-to-text voicemail |
| Fax server | 2019–2021 | `fax_server/` | Multi-page CCITT G4 TIFF |
| Slack | 2019– | `slack_export_2019-2026/` | Slack export JSON, one file per channel per day |
| Teams (Kestrel) | 2021–2023 | `teams_export_kestrel_2021-2023/` | Graph chatMessage JSON with HTML bodies |
| Phones | 2017–2023 | `phone_backups/`, `contacts/` | SMS Backup XML, iMessage CSV, vCard 2.1/3.0 |
| Calendars | 2019– | `calendars/` | iCalendar `.ics` with recurrence rules |
| Gong | 2023– | `sales_calls_gong/` | Call JSON with diarised transcript |
| File server FS01 | –2019 | `file_shares/`, `it_ops/` | Share backup zip, Windows Security event XML, AD LDIF |
| AWS data lake | 2023– | `datalake/` | Parquet (Hive partitions), Avro CDC, protobuf audit log |
| Okta | 2019– | `identity/` | User export CSV |
| Web servers | 2025 | `web_logs/` | nginx access logs (gzip) |
| Infra as code | 2023– | `infra/` | Terraform, Kubernetes YAML, Dockerfile |
| Diagrams | 2021–2023 | `architecture/` | draw.io (one compressed), Graphviz |
| Marketing | 2019– | `marketing/` | Google Ads UTF-16 TSV, UA CSV, Mailchimp, Qualtrics |
| Accounts payable | 2016–2023 | `ap_vendor_invoices/` | Vendor PDFs in three layouts, AcroForm |
| St. Brigid's interface | 2024 | `integrations/hl7_stbrigids/` | HL7 v2.5 ADT over MLLP |
| Images | 2019– | `photos/`, `scans/`, `expenses/` | JPEG with EXIF, PNG scans of handwriting |

## ID schemes (how to join across systems)

| System | Customer ID looks like | Notes |
|---|---|---|
| BRIX | `001207` | 6-digit, zero-padded. Salesforce `BRIX_Cust_No__c` often drops the zeros |
| SugarCRM | `7a461a5d-8e0e-953b-…` | GUID. Some customers have duplicate accounts |
| Salesforce | `001mPORltnrhvwwYVR` | 18-char. `Legacy_Sugar_Id__c`, `BRIX_Cust_No__c`, `Billing_Customer_Id__c`, `NetSuite_Internal_Id__c` |
| Ledger | integer `account_id` | |
| TallyFlow | `TF-…` | Kept as `legacy_ref` in later webhooks |
| Meridian | client code | French field names in exports |
| Billing v3 | `cus_…`, invoices `in_…`, credit notes `cn_…` | `metadata.sfdc_id`, `metadata.netsuite_id` |
| NetSuite | `C10362` + name in GL rows, internal id `10011` | |
| Telemetry | `account_id` (v1) then `tenant_id` slug (v2) | Map with `tenants.csv`. The data lake uses the slug too |
| Billing CDC | `sub_…` subscription, `cus_…` customer | Same ids as `billing_v3` |
| People | `E001` internally; Slack `U…`, Okta `00u…`, AD `sAMAccountName` and SID, phone extension | Map with `slack users.json`, `okta_users_export`, the LDIF and `phone_system/extensions.csv` |

No single key covers every system. Joining is part of the job.
