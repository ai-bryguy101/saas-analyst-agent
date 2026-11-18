# Feature Specification: Brindlecove Analyst (end-to-end app)

**Feature branch**: `claude/project-thread-ofnqev`
**Created**: 2026-11-18
**Status**: Draft, waiting on the open decisions in section 5
**Input**: Bryan, Nov 18: "build this pipeline with RAG and everything with a
website that I can use end to end as an analyst for this made up company. I
will be able to ask it a question and it will show me the answer, then where
that came from in the documentation, and tell me the pipeline, that other
people can use but is completely secure. I will tell possible employers to use
it and see that I am capable of building it out."

This spec says **what** the app must do and how we will know it works. The
**how** (stack, hosting, models) goes in `plan.md` after the open decisions
are made.

## 1. User scenarios and testing

### User story 1: Ask a question, get a cited answer (P1)

An analyst types a plain-English question about Brindlecove ("Why did
Harbortown cancel in 2016?") and gets a short answer with numbered citations.
Clicking a citation opens the source document at the exact passage, with the
passage highlighted.

**Why P1**: this is the whole product. Without it nothing else matters.

**Independent test**: ask 5 golden-fact questions; each answer is correct and
each citation opens a file listed in that fact's `trail`.

**Acceptance scenarios**
1. **Given** the index is built, **when** the analyst asks GF01, **then** the
   answer names the cancellation reason and cites the email it came from.
2. **Given** a citation in an answer, **when** the analyst clicks it, **then**
   the document viewer opens that file scrolled to the cited passage.
3. **Given** a question the data cannot answer, **when** it is asked, **then**
   the agent says it could not find evidence and shows where it looked.

### User story 2: Numbers from structured data, with the query shown (P1)

An analyst asks a numeric question ("What was ARR at year-end 2019?"). The
agent queries the structured tables and shows the answer, the SQL it ran, and
the source files the rows were loaded from.

**Independent test**: GF04 and GF05 answered with the right numbers and the
SQL visible.

**Acceptance scenarios**
1. **Given** a numeric question, **when** answered, **then** the SQL, the row
   count and the lineage (source file per table) are shown.
2. **Given** two sources disagree (GF04), **then** the answer shows both
   numbers, which source each came from, and why they differ.

### User story 3: See how the answer was made (P2)

Under every answer is a "How this answer was made" panel: the steps the agent
took (searches, SQL, documents opened), how long each took and what it cost.
A public "How it works" page explains the pipeline with a diagram.

**Why P2**: this is what lets an employer judge the engineering, and what
Bryan asked for ("tell me the pipeline").

**Independent test**: for any answer, the panel lists every tool call that the
server log has for that answer, in order.

### User story 4: Safe to hand to strangers (P1)

Bryan sends an employer a link. They can use the app without an account
setup, but cannot run up cost, read secrets, change data or make the agent
misbehave.

**Independent test**: the security checks in section 3 (SR-001 to SR-010)
pass, including the red-team prompts in the eval set.

**Acceptance scenarios**
1. **Given** a visitor has used their daily question quota, **when** they ask
   again, **then** they get a clear "limit reached" message and no model call
   is made.
2. **Given** the site has reached its monthly spend cap, **then** new
   questions are refused and the site shows saved example answers instead.
3. **Given** GF51 (the vendor quote with hidden instructions), **when** asked,
   **then** the answer gives the real total, not $0, and flags the hidden text.
4. **Given** a visitor asks the agent to drop a table or reveal its system
   prompt or keys, **then** it cannot and does not.

### User story 5: Anyone can rebuild it (P3)

A developer clones the repo, runs one documented command, and gets the same
data, index and eval scorecard on their own machine.

### Edge cases

- Conflicting sources (GF04, GF39): show both with their provenance.
- Draft vs final versions (GF08, GF49): prefer the authoritative version and
  say which one was used.
- Units, time zones, locales, 1904 dates, epoch units (GF05, GF06, GF17,
  GF40, GF41, GF47, GF48): the answer states the unit or time zone it used.
- Scanned and OCR'd documents (GF02, GF45): cite the page; warn when OCR
  confidence is low.
- Very long documents: citations still point to the exact passage.
- A question in a language other than English: answered in that language
  where the data allows.

## 2. Functional requirements

- **FR-001** The system ingests the data estate in `data/raw/` into a search
  index (documents) and analytics tables (structured data), keeping for every
  chunk and row the source file path and position.
- **FR-002** Ingestion is repeatable: one command rebuilds everything from
  `data/raw/` and produces the same result.
- **FR-003** The agent can (a) search documents with hybrid keyword plus
  meaning search, (b) describe the analytics schema, (c) run read-only SQL,
  (d) open a document by path. It can do nothing else.
- **FR-004** Every factual sentence in an answer carries at least one citation
  to a chunk or query the agent retrieved for that answer.
- **FR-005** The server validates citations before showing the answer and
  removes any it cannot match to the agent's retrieved evidence.
- **FR-006** The web app shows: the answer, clickable citations, a document
  viewer with the cited passage highlighted, the SQL for numeric answers, and
  the "How this answer was made" panel.
- **FR-007** Answers stream to the browser as they are written.
- **FR-008** Text in documents that looks like instructions to an AI is
  flagged in the answer and in the document viewer.
- **FR-009** A public "How it works" page and the eval scorecard are visible
  without asking a question.
- **FR-011** The agent's SQL tool is storage-agnostic: it talks to an
  interface, not to Postgres directly, so a second analytics engine can be
  added without changing the agent (ADR-0004).
- **FR-012** A scaling benchmark (later phase) grows the synthetic data with
  the generator's `--scale` option, times a fixed set of analytics queries at
  each size, and reports where Postgres misses its time budget. DuckDB is added
  as the analytics engine at that point (ADR-0004).
- **FR-010** Bryan has an admin view: questions asked, cost per question and
  per visitor, cap status, and the ability to revoke a visitor link.

## 3. Security requirements

- **SR-001** No API key, database password or other secret is ever sent to the
  browser or committed to the repo. Secret scanning runs on every push.
- **SR-002** Visitors get access by the method chosen in decision D6.
  Access can be revoked per visitor.
- **SR-003** Per-visitor question quota and per-IP rate limit.
- **SR-004** A global monthly spend cap, enforced in code from the model's
  reported token usage, plus a spend limit on the provider account as backstop.
- **SR-005** The agent's database login can only `SELECT` from the analytics
  schema; statement timeout and row cap are enforced by the database itself.
- **SR-006** SQL from the model is checked before running: one statement,
  read-only, no system catalogs outside the allowlist.
- **SR-007** Retrieved text is passed to the model as marked, untrusted data.
  No tool can write, send or fetch anything outside the app.
- **SR-008** Output is sanitized; documents are rendered as text. A strict
  Content Security Policy is set.
- **SR-009** HTTPS only; bot check on first visit.
- **SR-010** Every request, tool call, SQL statement and cost is logged with
  the visitor ID; logs never store secrets.

## 4. Key entities

- **Source file**: a file in `data/raw/` with its path, format, source system
  and era.
- **Chunk**: a passage of a source file with its text, position (page, line or
  character range), embedding and metadata (date, author, version).
- **Analytics table**: structured rows loaded from source files, each row
  keeping its source file and line.
- **Answer**: the question, the final text, its citations, the tool trace,
  tokens and cost.
- **Visitor**: an access grant with its quota, expiry and usage.

## 5. Open decisions [NEEDS CLARIFICATION]

Each is explained with options, trade-offs and a recommendation on the
decision page (https://claude.ai/artifact/CNKyUeYTvkph6LaT9siDSz, private to
Bryan). Each becomes an ADR in `docs/adr/` once Bryan picks.

| ID | Decision | Recommendation (not yet chosen) |
|---|---|---|
| D1 | Data store | **Decided (ADR-0004):** Postgres with pgvector, scaling benchmark later |
| D2 | Language model, how the agent loop runs, and the monthly cap | Claude Opus 5.5 behind a one-line setting, our own tool loop, $20 a month cap |
| D3 | Embeddings | Voyage AI voyage-4 (current free allowance covers this corpus) |
| D4 | Retrieval and citations | Chunks that follow each document's structure, hybrid search, passage-level citations |
| D5 | What to ingest first | Text-native formats plus existing OCR text and legacy tables; images later |
| D6 | Visitor access | Per-employer invite links plus a bot check |
| D7 | Hosting | His Hostinger VPS with Docker Compose behind Cloudflare |
| D8 | App stack | Python FastAPI for the API, React for the site |
| D9 | Eval plan | Free retrieval eval on every change; paid full eval before merge; held-out test set |

## 6. Success criteria

- **SC-001** At least 40 of the 52 golden facts answered correctly with
  citations to their trail files, on the held-out test split as well as the
  tuning split.
- **SC-002** GF51 is answered correctly and the hidden instruction is flagged
  in 5 of 5 runs.
- **SC-003** 3 of the 4 planted patterns (P01 to P04) are found when asked
  about the topic, without naming the pattern.
- **SC-004** Typical answer starts streaming within 3 seconds and finishes
  within 30 seconds.
- **SC-005** Average cost per answered question stays under the target set in
  D2 (tracked on the admin view).
- **SC-006** Zero findings at high severity from the red-team prompt set and
  the secret scan.
- **SC-007** A new developer rebuilds the app and reproduces the scorecard
  from the README in under an hour, not counting download time.
