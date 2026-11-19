# Architecture Decision Records

One file per significant decision, numbered in order. Each records the
context, the options considered, the choice and its consequences, so anyone
(including an interviewer) can see why the system looks the way it does.

Status values: **Proposed** (written, waiting on Bryan), **Accepted**,
**Superseded by ADR-NNNN**.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-decisions-and-use-spec-kit.md) | Record decisions as ADRs; follow GitHub Spec Kit | Accepted |
| [0002](0002-fictional-saas-company-public-repo.md) | Fictional SaaS company; public repo | Accepted |
| [0003](0003-synthetic-data-conventions.md) | Reserved domains and committed data | Proposed |
| [0004](0004-postgres-pgvector-with-scaling-benchmark.md) | Postgres + pgvector now; benchmark decides when to add DuckDB | Accepted |
| [0005](0005-haiku-own-loop-10-dollar-cap.md) | Claude Haiku 5.5, our own loop, $10 a month cap | Accepted |
| [0006](0006-voyage-4-embeddings.md) | Voyage AI voyage-4 embeddings | Accepted |
| [0007](0007-retrieval-and-citations.md) | Shape-aware passages, hybrid search, server-checked citations | Accepted |
| [0008](0008-ingestion-scope-with-vision.md) | Text, OCR and legacy formats plus images read by a vision model | Accepted |
| [0009](0009-invite-link-per-employer.md) | Invite link per employer plus bot check | Accepted |
| [0010](0010-fastapi-react-stack.md) | FastAPI + React (TypeScript) | Accepted |
| [0011](0011-eval-plan.md) | Free checks on every change, full eval before merge | Accepted |

Hosting (D7) is the one open decision. It is listed in `specs/001-analyst-app/spec.md`,
section 5, and becomes ADR-0012 once chosen.

## Template

```markdown
# ADR-NNNN: Title

- Status: Proposed | Accepted | Superseded by ADR-NNNN
- Date: YYYY-MM-DD
- Decider: Bryan

## Context
What forces are at play.

## Options considered
1. Option A: pros, cons, cost.
2. Option B: ...

## Decision
What was chosen, in one or two sentences.

## Consequences
What gets easier, what gets harder, what we must watch.
```
