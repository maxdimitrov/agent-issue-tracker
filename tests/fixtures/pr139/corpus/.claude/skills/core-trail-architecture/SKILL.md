# core-trail-architecture (frozen snapshot for the PR-139 replay)

Minimal excerpt of the trading-bot skill as it stood before PR #139,
keeping only lines that reference files changed in that PR.

The pure-function ratchet lives in `scripts/core_trail.py`; the one-shot
backfill is `scripts/backfill_core_trail.py`; the rendered view is
`memory/CORE-TRAIL.md`; the dashboard reads via
`dashboard/api/app/data/memory_files.py:read_core_trail()`.
