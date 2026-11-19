# ADR-0010: Python FastAPI for the API and agent, React (TypeScript) for the site

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
The generator and every parser are already Python. The open question was the
website.

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
1. FastAPI + React (TypeScript).
2. All Python with Streamlit.
3. All TypeScript with Next.js.

## Decision
FastAPI for the API, agent loop and ingestion; React with TypeScript for the
site (streaming answers, document viewer, trace panel).

## Consequences
- Python's libraries cover every legacy format in the estate.
- Two languages and two test setups in one repo.
