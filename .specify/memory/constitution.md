# saas-analyst-agent Constitution

The rules every spec, plan, task and line of code in this repository must
follow. A spec or plan that breaks one of these is wrong, not the rule.
Change a rule only through the amendment process at the bottom.

## Core Principles

### I. Every answer shows its evidence

The agent never states a fact about Brindlecove without pointing to where it
came from: a file path plus the exact passage (page, line or character range)
for documents, or the SQL query plus the source files of the rows it read for
structured data. A citation must refer to something the agent actually
retrieved in that same answer; the server checks this and strips any citation
it cannot match. When the evidence conflicts or is missing, the answer says so
instead of guessing.

### II. Documents are data, never instructions

Text inside the data estate (emails, quotes, chat logs, web pages) is
untrusted. It is passed to the model inside clearly marked data blocks, it can
never change the agent's instructions or tools, and text that looks like an
instruction to an AI is flagged to the analyst (golden fact GF51 tests this).
Every tool the agent can call is read-only.

### III. Secure by default for a public demo

The site is meant to be opened by people we do not control, so:
- No secret ever reaches the browser. The browser talks only to our own API.
- The database role the agent uses can only `SELECT` from an analytics schema,
  with a statement timeout and a row cap. It cannot see app tables such as
  visitor tokens or logs.
- Every visitor and the whole site have hard spending caps. When a cap is hit
  the site degrades to a read-only demo; it never keeps spending.
- Rendered output is sanitized; source documents are shown as text, never as
  live HTML.
- Every question, tool call, SQL statement and cost is logged.

### IV. Measured, not assumed

The golden facts in `data/GOLDEN_FACTS.yaml` are the definition of "works".
No change to retrieval, prompts or models is called an improvement unless the
eval says so. Part of the answer key is held out and never used for tuning,
so the headline score is honest.

### V. Decisions are the owner's, and are written down

Bryan makes every significant choice. Claude prepares the options with
trade-offs and a recommendation; Bryan picks. Each choice is recorded as an
ADR in `docs/adr/` with the options considered and why. Nothing is merged,
published, paid for or signed up for without Bryan's explicit yes.

### VI. Simple, explainable parts

Prefer one well-understood component over a clever stack. Each part must be
something Bryan can explain in an interview: what it does, why it was chosen
over the alternatives, and how it fails. No framework is added only to save a
few lines.

### VII. Reproducible end to end

Anyone can clone the repo, run one documented command, and get the same data
estate, the same index and the same eval score (within model noise). Seeds,
dependency versions and model IDs are pinned.

## Constraints

- All company data is synthetic (see `README.md`). Real personal data is never
  added to the repo, the index or the logs.
- Monthly spend has a hard ceiling set in ADR form; the app enforces it in
  code and the provider account enforces it as a backstop.
- The project stays separate from Hangpost: no shared code, accounts or
  infrastructure.

## Development workflow

1. GitHub Spec Kit order: constitution, spec, plan, tasks, implement.
2. Open questions in a spec are marked `[NEEDS CLARIFICATION]` and resolved by
   Bryan before the plan is written.
3. Work happens on branches; a branch is merged only on Bryan's yes, after
   his separate ChatGPT review of large changes.
4. Every pull request runs the free checks (lint, unit tests, retrieval-only
   eval). The paid full eval runs on demand before merge, inside a stated
   budget, and its scorecard is committed.

## Governance

This constitution outranks every other document in the repo. An amendment
needs Bryan's yes, a version bump below and an ADR explaining the change.

**Version**: 0.1.0 (draft, awaiting Bryan's review) | **Ratified**: pending | **Last amended**: 2026-11-18
