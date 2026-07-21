# GitHub Projects board (optional) — detailed reference

Load this only when the consumer's `.claude/issue-tracker.yaml` sets
`github.project` (GitHub backend only). With `github.project` unset, skip
it entirely — initiative behaviour is unchanged and you never need this file.

This is the detailed mechanics for mirroring an initiative tree onto a GitHub
Projects (v2) board. The triggering rules live inline in `SKILL.md` (the
"Children task-list mirror" note and "Maintenance" step 6); this file holds the
lifecycle and backfill procedure.

## What the board is

When the consumer's `.claude/issue-tracker.yaml` sets `github.project` (GitHub
backend only), mirror the initiative tree onto that GitHub Projects (v2) board in
addition to the canonical `## Children` task-list mirror. **The board is a
human-facing view; the `## Children` mirror stays the source of truth.** With
`github.project` unset, skip this entirely — behaviour is unchanged.

All board writes are **best-effort**: a failure WARNs and continues, never blocking
the issue operation. See `backends/github.md` "GitHub Projects v2 board (optional)"
for the literal `gh project` calls and scope setup
(`gh auth refresh -s project,read:project`).

## Status lifecycle — three states, each a real event

- **Todo** — when a child is filed + linked (see the `SKILL.md` "Children
  task-list mirror" section), add it to the board and set Status `Todo`. Applies
  to every node: root epic, sub-epics, and leaves, including cross-repo
  `owner/repo#N` children (added by full issue URL).
- **In Progress** — set when a driver starts work on a child and its worktree is
  entered — `/resume-initiative --start` (see `commands/resume-initiative.md`) or
  `/work-issue` (see `commands/work-issue.md`).
- **Done** — when a child closes (see `SKILL.md` "Maintenance" step 6), set Status
  `Done`.

## Backfilling an existing tree onto a board

When `github.project` is newly configured on an in-flight initiative — or an
operator asks to "populate the board" — walk each epic node's `## Children` mirror
top-down (root -> sub-epics -> leaves) and add every node, setting Status from its
current state (open -> `Todo`, closed -> `Done`). Idempotent: GitHub Projects v2
stores a content item at most once, so re-adding an already-present issue returns
the existing item — no duplicates. This is a documented procedure, not a slash
command.
