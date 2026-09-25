# Design — post-merge finish phase for `/work-issue` (`--finish`, `merge_method`, `jira.merged_transition`)

Issue: #115. Date: 2026-09-25. Status: approved for implementation (operator-delegated autonomous run; every fork resolved to the issue's recommended option).

## Problem

The plugin's lifecycle ends at the PR. After a merge, nothing moves the ticket to a *merged* status, nothing refreshes the parent index, nothing removes the worktree and local branch `/work-issue` Step 3 created, and the only merge method is a hardcoded squash. On a Jira consumer with a merged-then-released convention (`Ready for Release` → `Done` on tag) every one of those steps is manual, and a second merge path — `/tracker-loop babysit --merge` — shares the hardcoded squash and runs none of the post-merge steps either.

## Decisions

### 1. Entry point: `/work-issue <ref> --finish [--released <tag>]`

- A new invocation mode, not a new command. Idempotent; safe to run any time after the merge, from any directory of the repo (it does not need the worktree to still exist).
- **Gate first, write never otherwise.** Resolve the PR for `<ref>` (`gh pr list --repo <nwo> --state all --search "<ref>"`, newest first; fall back to `--head <branch>` with the Step 3 branch derivation). If no PR, or `state != MERGED`, print the state and **stop with no writes**. This covers `--merge` runs whose auto-merge landed after the session ended.
- Runs the six steps below in order; each is best-effort (WARN and continue) except the cleanup gates, which refuse rather than force.

### 2. `merge_method: merge | squash | rebase` (top-level config key, default `squash`)

- Read by `/work-issue --merge` (Step 6) and by `/tracker-loop babysit`'s merge row. Maps to `gh pr merge --<method>`. Default keeps today's behaviour byte-for-byte.
- `--merge` pins the head: `gh pr merge --<method> --match-head-commit <sha>` where `<sha>` is the head Step 5 verified. Refuses (no merge) when the PR is already merged, or when the base moved since verification (`git rev-parse origin/<base>` differs from the base recorded at Step 5) — the fix is a rebase + re-verify, which is the babysit loop's `rebase` row, not a silent merge.
- On GitHub, squashing a PR via the CLI also changes the account's preselected method in the web UI for the next manual merge; consumers on a merge-commit convention set `merge_method: merge` for that reason alone.
- `/tracker-doctor` Phase 1: WARN when `merge_method` is set to anything but the three values.

### 3. Jira: `jira.merged_transition` (optional, unset = today)

- New optional key, sibling of `in_progress_transition` and `done_transition`. Resolved by **name per issue** via `getTransitionsForJiraIssue`, applied via `transitionJiraIssue` — never a hardcoded id (workflow-scoped).
- `--finish` applies `merged_transition` to `<ref>`. `done_transition` is **never** applied on merge when `merged_transition` is set; it stays the release/close step.
- `--finish --released <tag>`: only when `merged_transition` is set. Check `git merge-base --is-ancestor <merge-sha> <tag>`; if true, apply `done_transition` (via the contract's `close_issue` with `reason: completed` and a comment naming the tag); if false, WARN and skip. One ref per invocation; a multi-ticket sweep is out of scope (file a follow-up if a consumer needs it).
- GitHub has no merged status: `Closes <ref>` in the PR body closes on merge. With `github.project` set, `--finish` sets the board item Status to `Done` (existing affordance, `backends/github.md`).
- Documented as the fourth optional backend-specific affordance in `backends/_interface.md`; no contract operation added; eleven ops stay eleven.

### 4. Other tickets the PR fixed

- Parse the PR body for `Fixes|Closes|Resolves <ref>` lines (all refs, the same ref-syntax the backend owns). For every ref other than `<ref>`:
  - Jira: apply `merged_transition` (when set) and leave an evidence comment via `upsert_comment` with marker `<!-- work-issue:finish -->` and body `Merged in <PR url> (<merge sha>)`. Idempotent by marker.
  - GitHub: nothing — the keywords already closed them; board `Done` sync if `github.project` is set.

### 5. Parent index refresh

- Discover the parent the portable way: the `## Parent epic` block in the issue body (as Step 3 does). No block → skip.
- **Legacy parent** (body has `## Status block`): run the one-hop Maintenance ritual from `skills/initiative-tracking/SKILL.md` in one read-modify-write `edit_body`: recount `- **Phase:**` `<closed>/<total>` over direct children, set `- **Next up:**` to the first open direct child in `## Children` order (or `none`), set `- **Current branch:**` to `none` if it names this branch, set `- **Last updated:**` to today, and flip this child's `## Children` line to `- [x]`.
- **Evergreen parent**: `read_comments` → append a dated `## Decision log` entry `- **YYYY-MM-DD** — <ref> merged in <PR url>` and clear `## Current branch` when it names this branch → `upsert_comment` (whole-comment replace). Child state itself is derived on read; nothing else is written.

### 6. Local cleanup (provenance-gated, never forced)

- Only the worktree Step 3 created: path `.claude/worktrees/<branch-with-slash-as-plus>` whose checked-out branch is the Step 3 branch. Anything else is left alone.
- Gates, all required: the PR is `MERGED`; the local branch tip equals the PR's `headRefOid` (nothing unpushed — squash and rebase merges rewrite history, so "tip is an ancestor of base" is the wrong test); `git -C <worktree> status --porcelain -uall` is empty. Any gate fails → print what is at stake and stop cleanup (the other finish steps still ran).
- Then, from the main checkout: `git worktree remove <path>` (no `--force`), `git worktree prune`, `git branch -D <branch>` (`-D` because a squash-merged branch is never "fully merged" in git's sense; the head-equals-PR-head gate is what makes it safe).
- **Remote branch: never deleted by the plugin.** When the repo has `deleteBranchOnMerge` enabled GitHub already removed it; when it does not, the repo keeps merged branches by policy and the plugin honours that. `--merge` must therefore not pass `--delete-branch`.
- The session exits the worktree first when it is still inside it (`ExitWorktree`), otherwise the removal runs from the primary checkout.

### 7. Loop coordination (`/tracker-loop`)

- Babysit merge row: `gh pr merge --<merge_method> --match-head-commit <pr.headRefOid> --auto` (direct merge only where auto-merge is unavailable), no `--delete-branch`.
- Babysit `stop: done` row: when `pr.state == MERGED` and the record's ref is an issue ref (or `SB.ticket.key` resolves one), run `/work-issue <ref> --finish` as the stop action; a failure there is a WARN in the stop line, never a reason to keep looping. Clear and poll modes reach it through the same babysit iteration.
- After arming auto-merge the loop does not stop: it keeps iterating (`wait-ci` while checks run) until the first row sees `MERGED`, so `--finish` always runs from the loop. A direct merge (auto-merge unavailable) lands at once, so the merge row runs `--finish` itself and stops.

### 8. Doctor

- Phase 1 WARN-only: `merge_method` not in `merge|squash|rebase`; Jira-only `[INFO]` when `jira.merged_transition` is unset (same render-only shape as `in_progress_sprint`).

## Out of scope (say so in the docs)

- Multi-ticket `--released` sweeps; release tagging itself; re-running verification at merge time (Step 5 stays the gate; babysit's CI rows cover drift); any change to push auth; workspace notes/memory.
- No new contract operation. If a consumer needs a generic `transition_issue` op, that is the fork #86 raised; this design stays on optional affordances.

## Files

| File | Change |
|---|---|
| `commands/work-issue.md` | `--finish [--released <tag>]` invocation row; `--merge` row reads `merge_method` and pins the head; new **Step 8 — Finish** with the six steps above; Conventions + Failure modes (unmerged PR refuses; gates refuse cleanup; Jira transition absent → WARN) |
| `commands/tracker-loop.md` | merge row + `stop: done` row per §7; Safety rails line "never delete a remote branch" |
| `backends/jira.md` | new `## Merged transition (optional)` section (keys, calls, `--released` rule, WARN paths); `close_issue` unchanged |
| `backends/github.md` | short `## Post-merge (optional)` note: keywords close, board `Done`, `deleteBranchOnMerge` read (`gh repo view --json deleteBranchOnMerge`), remote branch never deleted by the plugin |
| `backends/_interface.md` | fourth affordance paragraph |
| `skills/initiative-tracking/SKILL.md` | Maintenance: the legacy one-hop ritual and the evergreen decision-log append now have a driver (`/work-issue --finish`); "Epic lifecycle" unchanged |
| `commands/tracker-doctor.md` | Phase 1 rows per §8 |
| `examples/issue-tracker.yaml.example` | top-level `merge_method`; `jira.merged_transition` |
| `README.md` | Roadmap bullet for #115 removed |
| `CHANGELOG.md` | `## [Unreleased]` entry |
