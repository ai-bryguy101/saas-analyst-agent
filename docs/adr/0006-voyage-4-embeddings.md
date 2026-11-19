# ADR-0006: Voyage AI voyage-4 for embeddings

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
Meaning search needs an embedding model; Claude does not make embeddings.
Every passage is embedded once at ingest and each question once at ask time.

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
1. Voyage AI voyage-4: strong retrieval, a free allowance far above this corpus
   (my estimate: under 20 million tokens), optional reranker later.
2. OpenAI text-embedding-3: second AI vendor; price not checked.
3. Open model on our own server: no outside calls, but needs server RAM and CPU
   and is usually weaker at retrieval.

## Decision
voyage-4, with an embedding size under pgvector's 2,000-dimension index limit.

## Consequences
- Likely $0 for ingest at this size; one more account and API key, which stay
  on the server only. Opening that account is Bryan's step.
- voyage-4-lite is the fallback; a Voyage reranker can be added if the eval
  shows it helps.
