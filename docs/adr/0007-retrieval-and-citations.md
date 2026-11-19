# ADR-0007: Shape-aware passages, hybrid search merged by rank, server-checked citations

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
This is the RAG core: how documents become passages, how passages are found,
and how a citation proves where an answer came from.

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
- Passages: fixed windows; follow each document's own shape; whole documents.
- Search: meaning only; keyword only; hybrid merged by rank.
- Citations: file-level links; exact passage trusted as written; exact passage
  checked by the server.

## Decision
- **Follow the document's own shape**: one email, ticket, slide, PDF page or wiki
  section per passage; long ones split at about 500 tokens with a little
  overlap. Each passage keeps source file, character offsets, page, date,
  author, version and source system.
- **Hybrid search merged by rank**: Postgres full-text plus pgvector, combined
  with reciprocal rank fusion (ranks, not raw scores, so the two scales never
  need comparing).
- **Exact passage, checked by the server**: every citation must match a passage
  the agent actually retrieved for that answer; unmatched citations are
  stripped and the answer is marked. Numbers from SQL cite the query plus the
  source files and lines of the rows it read.

## Consequences
- One parser per format (most were needed anyway).
- One ingest step builds both indexes, so they cannot drift.
- The free retrieval eval can score keyword, meaning and hybrid separately.
