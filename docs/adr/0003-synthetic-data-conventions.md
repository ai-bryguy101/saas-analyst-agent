# ADR-0003: Reserved domains, and the generated data committed to the repo

- Status: Proposed (Claude's default; Bryan has not confirmed or objected)
- Date: 2026-11-10
- Decider: Bryan

## Context
Synthetic emails, domains and phone numbers could collide with real ones.
The data estate can either be committed or generated locally by each user.

## Options considered
1. Realistic-looking real domains: more convincing, risk of hitting real ones.
2. Reserved `.example` domains, 555-01xx phones, documentation IP ranges:
   obviously fake, never collide.
3. Commit `data/raw/` (~221 MB): clone and go, browsable on GitHub.
4. Generate locally only: small repo, but a setup step before anything works.

## Decision
Options 2 and 3, as defaults. Reversible: the generator can rebuild the data
with other settings, and `data/raw/` can move to generate-locally.

## Consequences
The repo is large for a code repo but within GitHub's limits (no file over
25 MB). Everything a visitor sees is plainly fictional.
