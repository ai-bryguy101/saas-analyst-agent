# Tasks: Brindlecove Analyst

Input: [plan.md](plan.md), [spec.md](spec.md), [data-model.md](data-model.md).
`[P]` = can run in parallel with the task before it. `[USn]` = user story.
Phase 7 (deploy) waits on the hosting decision (D7).

## Phase 1: Setup
- [ ] T001 Create `backend/`, `frontend/`, `Makefile` and the layout in plan.md
- [ ] T002 [P] `docker-compose.yml` with Postgres 17 + pgvector, API and site
- [ ] T003 [P] Pin Python and Node dependencies; `backend/app/config.py` holds model id, caps and quotas
- [ ] T004 Database migrations for the three schemas and three roles in data-model.md
- [ ] T005 [P] CI on every pull request: lint, unit tests, secret scanning (no paid calls)

## Phase 2: Ingest and search (US1, US2)
- [ ] T006 [US1] File registry: extension and magic bytes to parser; unknown files logged, not dropped
- [ ] T007 [P] [US1] Text parsers: email (eml, mbox), chat and SMS JSON, tickets, HTML, RTF, docx, pptx, text PDFs, VTT transcripts, ics, vcf, markdown
- [ ] T008 [P] [US2] Structured parsers: CSV (encodings, delimiters, locales), JSON lines, xlsx and xls, parquet, Avro, XML, YAML
- [ ] T009 [P] [US2] Legacy parsers: EBCDIC with copybook (CPY), Lotus WK1, PRN fixed width, dBase, protobuf logs, Windows event logs, gzipped files, EDI, HL7, LDIF
- [ ] T010 [P] [US1] Use existing OCR text for scans and scanned PDFs
- [ ] T011 [US1] Shape-aware chunker: one message, ticket, slide, page or section per passage; 500-token split with overlap; offsets and metadata kept
- [ ] T012 [US2] Load analytics tables with `_source_file_id` and `_source_line`
- [ ] T013 [US1] Flag injection-like text at ingest (`injection_suspect`); GF51 must be flagged
- [ ] T014 [US1] Keyword search over `tsv`
- [ ] T015 [US1] Retrieval eval, keyword only: trail files in top 8 for each golden fact. First number on the board
- [ ] T016 [US1] Embed passages with voyage-4, cached by content hash (needs Voyage key)
- [ ] T017 [US1] Vector search and reciprocal rank fusion; retrieval eval reports keyword, vector and hybrid side by side
- [ ] T018 [US1] Vision descriptions for about 146 images with Haiku 5.5, cached by file hash, logged against the cap (needs Anthropic key)
- [ ] T019 [US1] `make ingest` rebuilds everything from `data/raw/`; test that two runs give the same passage hashes

## Phase 3: Agent (US1, US2)
- [ ] T020 [US2] Query engine interface (`query/engine.py`) and Postgres engine
- [ ] T021 [US2] SQL guard: one statement, SELECT only, allowed tables only, row cap
- [ ] T022 [P] [US1] Tools: search_docs, describe_schema, run_sql, open_doc
- [ ] T023 [US1] Agent loop on the Messages API with prompt caching; spend checked before every call
- [ ] T024 [US1] Retrieved text sent as marked untrusted blocks; system prompt rules for conflicts, drafts, units and time zones
- [ ] T025 [US1] Citation checker: strip and mark any citation not in this answer's fetched passages or queries
- [ ] T026 [US2] SQL citations: query text plus source files and lines of the rows read
- [ ] T027 [US1] `make ask Q="..."` prints answer, citations and trace

## Phase 4: API and site (US1, US3)
- [ ] T028 [US1] `POST /ask` streams the answer with server-sent events
- [ ] T029 [P] [US1] `GET /documents/{id}` returns plain text with the cited span marked
- [ ] T030 [US1] Site: ask box, streaming answer, clickable citations
- [ ] T031 [P] [US1] Document viewer; images shown beside their machine description
- [ ] T032 [US3] Trace panel: tool calls, SQL, passages, tokens and cost
- [ ] T033 [P] [US3] How it works page with the pipeline diagram and latest scorecard

## Phase 5: Security (US4)
- [ ] T034 [US4] Invite links: create, expire after 14 days, revoke; token stored hashed
- [ ] T035 [US4] Per-invite daily quota (15) and per-IP rate limit
- [ ] T036 [US4] Global $10 monthly cap; site switches to read-only demo when reached
- [ ] T037 [P] [US4] Turnstile on first visit
- [ ] T038 [P] [US4] Strict CSP, plain-text rendering, security headers
- [ ] T039 [US4] Logs with hashed IPs; admin view of questions, cost and invite usage
- [ ] T040 [US4] Red-team set of about 20 prompts (injection, SQL escape, cap drain, data exfiltration)

## Phase 6: Eval (US1 to US4)
- [ ] T041 Fix the 15 held-out facts; tuning code cannot read them
- [ ] T042 Full eval: exact checks for numbers, IDs and dates; grader rubric for "why" answers; trap checks; patterns P01 to P04
- [ ] T043 Committed scorecard; run only on Bryan's yes with a stated budget
- [ ] T044 Model comparison: Haiku 5.5 vs Sonnet 5.5 vs Opus 5.5 on the same set (Bryan's yes per run)

## Phase 7: Deploy (US4, US5), waits on D7
- [ ] T045 Choose host (D7), record ADR-0012
- [ ] T046 Deploy with Compose behind Cloudflare; secrets from the host's environment only
- [ ] T047 [US5] README rebuild guide; a fresh clone reproduces the scorecard (SC-007)

## Phase 8: Scaling benchmark (ADR-0004)
- [ ] T048 Grow the data with `generator --scale`; fixed set of timed analytics queries
- [ ] T049 Chart query time against size; record where Postgres misses its time budget
- [ ] T050 If it does, add a DuckDB engine behind the same interface and compare
