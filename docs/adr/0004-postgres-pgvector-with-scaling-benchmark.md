# ADR-0004: Postgres with pgvector now; a scaling benchmark decides when to add DuckDB

- Status: Accepted
- Date: 2026-11-18
- Decider: Bryan

## Context
The app needs three things from storage: tables for analytics questions
("how many", "which customer"), keyword search and meaning (vector) search
over document passages. It is also a public demo, so the agent's database
access must be tightly limited. The data estate is about 221 MB, which my
estimate puts at a few million rows at most once loaded.

Bryan asked whether this handles analytics questions, at what size it
stops doing so well, and whether to run Postgres and DuckDB side by side.

## Options considered
1. **Postgres + pgvector.** Tables, full-text search and vector search in one
   database. Built-in read-only roles, statement timeouts and row limits.
   Row-oriented storage, so large scans and group-bys get slow before a
   column store would. Rough estimate on a small server: a 5-second query
   limit starts to pinch around tens of millions of rows (not measured).
2. **DuckDB + files.** Column-oriented, very fast analytics, no server.
   Vector search extension is experimental; no built-in logins or roles,
   one writer at a time. Awkward behind a public website.
3. **Cloud warehouse (BigQuery).** Scales to anything; a public site can
   trigger paid scans.
4. **Postgres and DuckDB together from day one.** Fast analytics and good
   search, but two copies to keep in sync, two SQL dialects for the agent,
   and DuckDB would need its own access controls.

## Decision
Option 1, Postgres with pgvector. Two additions, at Bryan's request
("okay let's go with the benchmark"):

- The agent's SQL tool sits behind a storage-agnostic interface, so a
  second engine can be added without changing the agent.
- A later phase adds a **scaling benchmark**: the generator grows the
  synthetic data (its `--scale` option) step by step, a fixed set of
  analytics queries is timed at each size, and DuckDB is added as the
  analytics engine at the point where Postgres misses its time budget.

## Consequences
- One database to run, back up and lock down for the first version.
- Analytics on the current data size stays inside the query time limit.
- The benchmark produces a measured answer to "when does a column store
  pay off", with charts, instead of an assumed one.
- If DuckDB is added later, ingest exports the analytics tables to it, and
  the read-only guarantees must be rebuilt for it (it has no logins).
