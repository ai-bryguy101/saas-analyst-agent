# ADR-0009: Invite link per employer, plus the free bot check

- Status: Accepted
- Date: 2026-11-19
- Decider: Bryan

## Context
The site is public and every question costs money, so visitors must be told
apart. All other security controls are always on (constitution Principle III).

> Bryan, 2026-11-19: "Haiku, $10, voyage-4, follow the document's own shape, hybrid merged by rank, Exact passage, checked by the server, B, plus images read by a vision model, invite link per employer, [hosting question], Python FastAPI + React (TypeScript), free checks on every change, full eval before merge"

## Options considered
1. Open to anyone, bot check only.
2. One shared access code.
3. Invite link per employer.
4. Full sign-in with Google or GitHub.

## Decision
An **invite link per employer**: Bryan makes one per company from the admin
page. Each link has its own quota, a 14-day expiry and a usage log, and can be
revoked alone. The free Cloudflare Turnstile bot check runs on first visit.

## Consequences
- One click for the hiring manager, no account to create.
- Nobody can drain the shared cap, and Bryan sees who actually tried it.
- Bryan generates a link each time he shares the demo.
