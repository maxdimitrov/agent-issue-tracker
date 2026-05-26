# Contributing to agent-issue-tracker

**Status: v1 under development.** This document is a Phase-0 placeholder. The full contribution guide — including the backend operation contract, the per-backend file layout, and the v1.0.0 release smoke-test gate — lands in Phase 4 of the v1 development plan.

## Where things are decided

The v1 architecture, scope decisions, phase plan, and acceptance criteria live in the design spec at [`maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md). Read it before opening a non-trivial PR.

## Where work is tracked

- **Initiative epic (this repo's v1 development):** filed as an `epic` issue against `maxdimitrov/trading-bot` — see the spec's Tracking section for the issue number.
- **Sub-issues for Phases 0–4:** filed against THIS repo with phase-prefixed titles.
- **Sub-issue for Phase 5 (trading-bot dogfood cutover):** filed against `maxdimitrov/trading-bot`.
- **Post-v1 enhancements:** filed against THIS repo with the `enhancement` label; the day-one set ships at Phase 0 close.

## Issue body shape

All issues filed against this repo follow the same agent-prompt body shape the plugin itself ships:

- Goal
- Locus (file paths, function/route, subsystem)
- Skills to load (which plugin skills + which superpowers skills)
- What's missing (for enhancements) or Symptom + Repro + Impact (for bugs)
- Why
- Sketch (for enhancements) or Root cause hypothesis (optional, for bugs)
- Constraints (out of scope, invariants, style)
- Acceptance (writable as a regression test)
- Verify (exact commands to prove the change)
- Notes

A vague body wastes an agent run. A structured body gets a draft PR back.

## License

This project is MIT-licensed. By contributing you agree your changes ship under the same license.
