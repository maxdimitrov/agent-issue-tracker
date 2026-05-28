# README rewrite + smoke gate + v1.0.0 release — implementation plan

**Date:** 2026-05-28
**Tracker:** [maxdimitrov/agent-issue-tracker#30](https://github.com/maxdimitrov/agent-issue-tracker/issues/30)
**Design spec:** [2026-05-28-readme-smoke-release-design.md](../specs/2026-05-28-readme-smoke-release-design.md)
**Branch:** `feat/readme-smoke-release`

## Execution mode

Controller-direct authoring. Per CLAUDE.md operator preference for single-file write-from-scratch markdown tasks.

## Task order

### Task 1 — README rewrite
Write the 12-section structure from spec §5. Adopter-facing voice. Verify every cross-link resolves locally before committing.

### Task 2 — CONTRIBUTING update
Append "Release process" + "Adding a backend" sections after the existing "Issue body shape" section. Preserve byte-identical existing prose.

### Task 3 — CHANGELOG release block
Move every Unreleased bullet to `## [1.0.0] - 2026-05-28`. Add a `### Release-gate smokes` sub-section with placeholder outcomes (filled in after Task 5).

### Task 4 — Cold-read review
Dispatch a sonnet sub-agent to read the README + CONTRIBUTING changes with no prior context. Address CRITICAL/HIGH findings.

### Task 5 — Run the five smoke tests
- Smoke 1 (GitHub): file 4 issues against agent-issue-tracker via the skills, verify, close. Capture refs.
- Smoke 2 (Jira): check Atlassian MCP availability via ToolSearch. If absent, mark DEFERRED to Phase 6.
- Smoke 3 (/tracker-init): in a clean scratch directory, simulate the scaffolder against the current command file's prompts.
- Smoke 4 (/tracker-doctor): exercise PASS/WARN/FAIL paths against three config variants.
- Smoke 5 (/resume-initiative): parse `trading-bot#153` Status block + Children mirror.

Update CHANGELOG `### Release-gate smokes` sub-section with actual outcomes.

### Task 6 — Local verify
Run all verification commands from spec §10. Confirm CI passes against the worktree.

### Task 7 — Commit + push + PR
Squash-merge ready PR. Body summarizes README architecture + smoke outcomes.

### Task 8 — Tag v1.0.0
ONLY after the PR squash-merges. Tag the squash commit. Annotated tag. Push to origin.

### Task 9 — Epic #153 update (batched with #29 in the final pipeline step)
Bump 11/15 → 13/15, mark #29 and #30 [x] in Children, append Decision log entry for v1.0.0 ship, refresh Resume-from-here to point at Phase 5.

## Constraints

- README cross-links MUST resolve locally before commit.
- CHANGELOG em-dash discipline (— U+2014).
- Tag annotation names the smoke gate AND any deferrals.
- Do NOT tag before the PR squash-merges.
- Markdown lint passes on README + CONTRIBUTING + CHANGELOG via the `.markdownlint-cli2.jsonc` config from PR #31.

## Risk register

- **Cold-read review may surface README structural issues.** Build in a re-write window after Task 4 before committing the final README.
- **Smoke 1 takes the longest** (filing 5 real issues against the public repo). Use the smoke-test-tag pattern to mark them so they're obviously test issues.
- **Tag annotation typo.** Once pushed, fixing requires force-push tag (destructive). Verify message text before push.
- **Em-dash regression risk on the smoke outcomes lines** — they're written DURING smoke execution, easy to slip back to `--`. Re-grep before commit.

## Done when

All acceptance bullets in #30 check; PR squash-merges; `v1.0.0` annotated tag visible on origin; CHANGELOG `[1.0.0]` block records every Phase 0/1/2/3/4 deliverable + the smoke outcomes.
