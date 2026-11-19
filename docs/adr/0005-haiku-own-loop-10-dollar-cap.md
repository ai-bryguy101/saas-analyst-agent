# ADR-0005: Claude Haiku 5.5, our own agent loop, $10 a month cap

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
The language model answers every question and is the main running cost of a
public demo. Each question is several model calls (read, call a tool, read the
result, answer). My estimate per question, assuming about 50,000 tokens read and
4,000 written with the fixed instructions cached: Opus 5.5 about $0.17, Sonnet
5.5 about $0.08, Haiku 5.5 about $0.007. Real numbers come from the eval.

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
Model (D2a): Opus 5.5, Sonnet 5.5, Haiku 5.5, or a local open model.
Loop (D2b): our own loop on the Messages API, or a hosted agent service.
Cap: any monthly ceiling; the decision page proposed $20.

## Decision
- Model: **Claude Haiku 5.5** (`claude-haiku-5-5`), set in one config value so
  the eval can compare Sonnet 5.5 and Opus 5.5 later with a one-line change.
- Loop: **our own loop on the Messages API**. Bryan did not name a loop option;
  this was the recommended default and stays unless he says otherwise.
- Cap: **$10 a month**, enforced in code before every model call and also set
  as a spend limit on the provider account. The per-visitor quota stays at the
  proposed default of 15 questions a day until he sets another.

## Consequences
- $10 covers roughly 1,400 questions a month at my Haiku estimate, so the cap
  rarely bites, and the full paid eval costs well under $1 a run.
- Haiku is the weakest of the three at multi-step reasoning and spotting traps
  (stale drafts, unit mix-ups, the GF51 hidden instruction). The 40-of-52 target
  (SC-001) may be harder to hit; the eval will show by how much.
- A Haiku vs Sonnet vs Opus scorecard on the same 52 facts becomes a cheap,
  concrete interview story.
