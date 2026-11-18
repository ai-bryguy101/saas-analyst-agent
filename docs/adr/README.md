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

Open decisions D1 to D9 are listed in `specs/001-analyst-app/spec.md`,
section 5. Each becomes an ADR here once chosen.

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
