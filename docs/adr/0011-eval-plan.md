# ADR-0011: Free checks on every change, full eval before merge

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
The 52 golden facts and 4 planted patterns are the answer key. The full eval
calls the model, so it costs money.

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
1. Full eval on every change.
2. Free checks on every change, full eval before merge.
3. Manual spot checks.

## Decision
- Every pull request runs unit tests, the free retrieval eval (did the right
  trail files come back in the top 8) and secret scanning.
- The paid full eval (answers, citations, traps, red-team prompts) runs before
  merge, on request and within a set budget; its scorecard is committed.
- 15 of the 52 facts are held out and never used for tuning. Target: 40 of 52
  on both splits (SC-001).

## Consequences
- With Haiku 5.5 (ADR-0005) a full run is my estimate of well under $1, so it
  can run more often than first planned.
- Answer-quality regressions show up at merge, not at push.
