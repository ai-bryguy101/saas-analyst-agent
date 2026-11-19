# Implementation Plan: Brindlecove Analyst

**Branch**: `claude/project-thread-ofnqev` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)
**Status**: Draft for Bryan's review. Hosting (D7) is open, so deployment is
the one phase not planned in detail.

## Summary
An analyst asks a question in plain English about the fictional SaaS company
Brindlecove. An agent searches 8,000+ messy documents and queries structured
tables, then answers with every claim linked to the exact passage or SQL query
it came from. The site is public but invite-only, capped at $10 a month of
model spend, and scored against 52 planted answers.

## Technical context

| Item | Choice | Record |
|---|---|---|
| Languages | Python 3.12 (API, agent, ingest, eval); TypeScript (site) | ADR-0010 |
| API | FastAPI, answers streamed with server-sent events | ADR-0010 |
| Site | React + Vite + TypeScript | ADR-0010 |
| Database | Postgres 17 with pgvector; full-text search built in | ADR-0004 |
| Model | Claude Haiku 5.5 (`claude-haiku-5-5`), one config value | ADR-0005 |
| Agent loop | Our own loop on the Messages API, about 100 lines | ADR-0005 |
| Embeddings | Voyage AI voyage-4, 1024 dimensions (my default, under the 2,000 index limit) | ADR-0006 |
| Retrieval | Shape-aware passages, keyword + vector merged by reciprocal rank fusion | ADR-0007 |
| Ingest scope | Text, OCR text, legacy tables, images described by the vision model | ADR-0008 |
| Access | Invite link per employer, Cloudflare Turnstile bot check | ADR-0009 |
| Eval | Free checks per PR, paid full eval before merge, 15 facts held out | ADR-0011 |
| Packaging | Docker Compose (Postgres, API, site); runs the same on a laptop or any host | ADR-0004 |
| Hosting | **[NEEDS CLARIFICATION: D7]** | pending |
| Budget | $10 a month model cap in code and on the provider account | ADR-0005 |

**Performance goals**: answer starts streaming within 3 s, finishes within
30 s (SC-004). **Scale**: about 8,150 files, 204 MB; my estimate is under 20
million tokens of text and a few million table rows.

## Constitution check

| Principle | How this plan meets it |
|---|---|
| I. Every answer shows its evidence | Citation checker strips any citation not in the passages or queries fetched for that answer (T031) |
| II. Documents are data | Retrieved text goes in marked untrusted blocks; injection-like text flagged at ingest and at answer time; no tool can write, send or browse (T029, T033) |
| III. Secure by default | Keys only on the server; `agent_reader` role is SELECT-only with a 5 s timeout and row cap; SQL guard; spend meter; invite quotas; CSP and plain-text rendering (Phase 5) |
| IV. Measured, not assumed | Retrieval eval from Phase 2 onward; full eval and held-out split before any merge (Phase 6) |
| V. Decisions are Bryan's | ADR-0004 to ADR-0011 accepted; D7 open; accounts and spend wait for his yes |
| VI. Simple, explainable parts | One database, one loop we wrote, no agent framework |
| VII. Reproducible | `make ingest` rebuilds everything from `data/raw/`; pinned versions and model IDs; vision descriptions cached by file hash |

No violations.

## Project structure

```text
backend/
  app/
    main.py            # FastAPI app, routes mounted here
    config.py          # model id, caps, quotas: one place
    api/               # ask (SSE), documents, admin, invites
    agent/             # loop.py, tools.py, prompts.py, citations.py
    retrieval/         # keyword.py, vector.py, fuse.py (RRF)
    query/             # engine.py (interface), postgres.py, guard.py (SQL allowlist)
    security/          # invites.py, quota.py, spend.py, turnstile.py, logging.py
    db/                # schema migrations, roles
  ingest/
    cli.py             # make ingest
    registry.py        # file extension -> parser
    parsers/           # text/, legacy/, structured/, images/
    chunk.py           # shape-aware passages
    tables.py          # analytics tables with lineage columns
    embed.py           # voyage-4 batches, cached by content hash
    vision.py          # image descriptions, cached by file hash
  eval/
    retrieval_eval.py  # free: trail files in top 8
    full_eval.py       # paid: answers, citations, traps
    redteam/           # about 20 attack prompts
    scorecards/        # committed results
  tests/
frontend/
  src/                 # ask box, answer with citations, document viewer, trace panel, How it works
benchmark/             # Phase 8: scaling benchmark, DuckDB engine
docker-compose.yml
Makefile
.github/workflows/ci.yml
generator/ data/ docs/ specs/   # existing
```

## Data model
See [data-model.md](data-model.md).

## Phases

| Phase | Delivers | Needs from Bryan |
|---|---|---|
| 1. Setup | Repo layout, Compose with Postgres + pgvector, CI with tests and secret scanning | Nothing |
| 2. Ingest and search | Every format parsed, passages and analytics tables loaded with lineage, keyword search, then vector search and the first free retrieval score | Voyage AI key for the vector half (account is his step) |
| 3. Agent | Tools, loop, SQL guard, citation checker, spend meter; ask from the command line | Anthropic API key with a spend limit (his step) |
| 4. API and site | Streaming answers, clickable citations, document viewer, trace panel, How it works page | Nothing |
| 5. Security | Invites, quotas, Turnstile, CSP, logging, admin view, red-team set | Cloudflare account at deploy time |
| 6. Eval | Full eval with held-out split, committed scorecard, Haiku vs Sonnet vs Opus comparison | His yes on each paid run budget |
| 7. Deploy | Public site behind Cloudflare | **D7 decision**, host account |
| 8. Scaling benchmark | Data grown with `--scale`, timed queries, DuckDB engine if Postgres misses budget | Nothing |

Phases 1 to 4 run fully on a laptop. Nothing is deployed, published or paid for
without Bryan's yes.

## Risks
- **Haiku on hard facts**: weakest at multi-step traps; if the eval lands below
  40 of 52, the fix is a one-line model change, at a higher cost per question.
- **Legacy parsers**: EBCDIC, Lotus WK1 and length-prefixed protobuf are the
  slowest to get right; they are isolated so the rest can ship first.
- **Image citations**: a description is model text, not the source; the viewer
  always shows the image beside it.
