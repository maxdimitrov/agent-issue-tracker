# examples + workflows + CI — implementation plan

**Date:** 2026-05-28
**Tracker:** [maxdimitrov/agent-issue-tracker#29](https://github.com/maxdimitrov/agent-issue-tracker/issues/29)
**Design spec:** [2026-05-28-examples-workflows-ci-design.md](../specs/2026-05-28-examples-workflows-ci-design.md)
**Branch:** `feat/examples-workflows-ci` (worktree)

## Execution mode

Controller-direct authoring. Per CLAUDE.md operator preference: "controller-direct authoring is preferred for single-file write-from-scratch tasks (the PR #28 lesson — the haiku Task 1 subagent violated Subagent CWD discipline)." All five new files are single-file write-from-scratch markdown/YAML; no parallel work needed.

## Task order (sequential)

The five new files have no dependencies on each other at write time; pick an order that lets verification accumulate. Walkthroughs first (longest, prose-heavy); jira-config.yaml second (validated against the example schema); CI workflow last (validated against the live `backends/` files).

### Task 1 — `examples/workflows/file-a-bug.md`
- Operator-facing voice (second-person).
- Section structure per spec §4.2: Trigger / Skill activation / Body draft / Dispatch / Result / Variations.
- Configured project context: `backend: github`, `areas: [dashboard, backend, frontend, infra]`, `subsystems: [api, worker, scheduler, scripts]` (matches `examples/github-config.yaml`).
- Concrete bug example: a worker/scheduler shutdown bug — agent-prompt-shaped body following `templates/bug-body.md`.
- Cross-links: `skills/bug-tracking/SKILL.md`, `templates/bug-body.md`, `backends/github.md`.

### Task 2 — `examples/workflows/file-an-epic.md`
- Same shape.
- Concrete epic example: a small initiative (e.g. "extract logging into a shared module") — three sub-issues, the four-line Status block, the `## Children` task-list mirror showing the three ref shapes (`#N`, `owner/repo#N`, `PROJ-123`).
- Cross-links: `skills/initiative-tracking/SKILL.md`, `templates/epic-body.md`, `templates/sub-issue-body.md`, `backends/github.md`.

### Task 3 — `examples/workflows/resume-an-initiative.md`
- Same shape.
- Concrete resume example: `/resume-initiative #42` (GitHub) and `/resume-initiative TRADE-101` (Jira) — both shapes work.
- Three modes: `--summary` (default), `--start` (worktree), `--list-children` (full mirror).
- Cross-links: `commands/resume-initiative.md`, `skills/initiative-tracking/SKILL.md`.

### Task 4 — `examples/jira-config.yaml`
- Minimal commented YAML; ~30 lines.
- Two-line header comment.
- Required fields per `examples/issue-tracker.yaml.example` lines 66-108: `site`, `cloud_id` (empty string — `/tracker-init` resolves), `project`, `issue_types` (the four-type mapping).
- Reasonable defaults for areas/subsystems matching `examples/github-config.yaml`'s shape.
- Verify with `yamllint -d relaxed examples/jira-config.yaml` after writing.

### Task 5 — `.github/workflows/ci.yml`
- Three jobs per spec §4.3.
- Pinned action versions (`actions/checkout@v4`, `DavidAnson/markdownlint-cli2-action@v16`).
- Backend-contract check as inline shell.
- Tune `grep -oP` pattern to match the live operation heading shape in `backends/_interface.md` (verify in worktree before committing).
- Verify with `yamllint -d relaxed .github/workflows/ci.yml`.

### Task 6 — CHANGELOG append
- Add one bullet under `## [Unreleased]` → `### Added` per spec §4.4.
- Em-dash separator (— U+2014).
- Verify with `grep -P 'Phase 4.*—' CHANGELOG.md` (must match) and `grep -P 'Phase 4.*--' CHANGELOG.md` (must print nothing).

### Task 7 — Cold-read review
- Dispatch a sonnet agent to read the worktree files with no prior context; ask for issues against the design spec + sub-issue acceptance.
- Address every CRITICAL/HIGH finding; document LOW as won't-fix in PR description if applicable.
- This is the quality-review stage from Subagent-Driven Development applied to controller-direct output.

### Task 8 — Verify locally
- All commands from sub-issue Verify block must print expected output.
- `markdownlint-cli2 '**/*.md'` may flag pre-existing issues; only address regressions introduced by THIS PR.
- Backend-contract check must run green against the live `backends/` files.

### Task 9 — PR
- Push branch; open PR with body matching prior Phase 3 sibling shape (Summary / Changes / Test plan / Closes).
- `Closes #29` in body.
- Squash-merge; do not rebase.

### Task 10 — Epic update (after merge)
- Defer to the final pipeline step after #30 also merges (one batched epic update).

## Constraints

- Markdown + YAML only. No Python, no shell scripts in the plugin tree.
- Em-dash discipline (— U+2014) on CHANGELOG and any markdown that would be regression-targeted by future grep gates.
- All cross-links must resolve to files that exist at PR-open time.
- CI must not require secrets.
- No `.github/ISSUE_TEMPLATE/*.md` content (decision recorded in CHANGELOG).

## Risk register

- **Backend-contract pattern mismatch.** The `grep -oP '^### \`\K[a-z_]+(?=\`)'` pattern assumes operation headings are formatted `### \`create_issue\`` etc. Verify against live files before committing. If headings have drifted (e.g. `### Operation: create_issue`), tune the pattern OR file a backend-fix issue (probably the latter — the spec calls for `### \`<op>\``).
- **markdownlint surprise.** New walkthroughs may trip rules the existing files happen to pass (e.g. MD013 line length). Address with file-local overrides only if the lint rule is wrong for prose-heavy walkthroughs; otherwise fix the prose.
- **Em-dash regression.** PRs #19/#22/#28 hit this. Verify CHANGELOG with grep before commit AND before push.
- **Walkthrough sprawl.** Three walkthroughs at ~100 lines each is ~300 lines of new prose; resist the urge to make each one a full skill chapter. Adopters skim these.

## Done when

All acceptance bullets in #29 check; PR squash-merges; CHANGELOG bullet survives the merge byte-identical (em-dash preserved); CI on the merge commit runs green.
