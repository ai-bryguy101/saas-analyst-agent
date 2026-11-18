# ADR-0001: Record decisions as ADRs and follow GitHub Spec Kit

- Status: Accepted
- Date: 2026-11-10
- Decider: Bryan

## Context
The project is for learning and for a portfolio. Bryan wants to make every
significant decision himself, understand the trade-offs, and be able to
defend them. He asked to use a Spec Kit workflow.

## Options considered
1. Ad hoc: decide in chat, build directly. Fast, but the reasoning is lost.
2. GitHub Spec Kit (constitution, spec, plan, tasks, implement) with ADRs for
   each decision. Slower start, but every choice is written down and checkable.

## Decision
Option 2. The constitution lives at `.specify/memory/constitution.md`, specs
under `specs/NNN-name/`, decisions in `docs/adr/`.

## Consequences
Each big choice gets an explainer with options and a recommendation before
code is written. Interviewers can read why each part exists.
