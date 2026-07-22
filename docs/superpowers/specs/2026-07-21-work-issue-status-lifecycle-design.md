# Design — /work-issue cross-backend initiative status lifecycle (start-side)

Issue: #86. Date: 2026-07-21. Status: approved for implementation (operator-delegated autonomous run; both design forks resolved to the issue's recommended options).

## Problem

`/work-issue` is initiative-blind: starting work on an epic's child leaves the parent epic's Status block stale (`Current branch` wrong, no in-progress signal anywhere), and no cross-backend in-progress primitive exists — the only in-progress surface is the GitHub Projects board flip, wired solely to `/resume-initiative --start`.

## Fork resolutions

### Fork #1 — cross-backend in-progress primitive → **Option A: per-backend optional affordances**

No ninth contract operation. Rationale:

- GitHub has no native issue-level status; a `transition_issue` contract op could not be uniformly implemented — its GitHub mapping would still be the board or a label. A contract op that is best-effort-optional on one backend is a worse contract, not a better one.
- The precedent already exists: `_interface.md` "Optional backend-specific capabilities" was created for exactly this shape (the Projects board affordance). Plain `##` headings, invisible to the op-parity CI grep.
- Blast radius: Option B touches the "eight operations" invariant, op-parity CI, `/tracker-doctor`, and CONTRIBUTING. Option A touches none of them.

Concrete affordances:

- **GitHub** — `github.project` set → set the child's board item Status to `In Progress` (existing mechanics in `backends/github.md`; the trigger generalises from "`/resume-initiative --start`" to "any driver starting work on the issue", which now includes `/work-issue`). No new config key.
- **Jira** — new optional config key `jira.in_progress_transition` (default **unset** → no-op; deliberately NOT defaulted to `In Progress`, because firing workflow transitions on unconfigured consumers would be a surprising behaviour change). When set, resolve the transition id by name per-issue via `getTransitionsForJiraIssue` (ids are workflow-scoped — same rule as `done_transition`) and apply via `transitionJiraIssue`. Best-effort.
- **Fallback (nothing configured)** — the epic Status block's `Current branch` line (written by the start-side sync below) is the cross-backend in-progress signal. A parentless issue with no configured mechanism gets no marker: documented no-op, run proceeds.

### Fork #2 — close-side epic maintenance → **deferred to a follow-up issue** (Option C direction, after #85)

Not shipped in this PR. Rationale:

- Option C (reconcile-on-read) lands in `commands/resume-initiative.md`, which issue #85's session owns right now — a guaranteed textual collision.
- There is a real design tension to resolve against whatever #85 lands: #85's constraints say resume-initiative stays read-only and "never mutate the epic body's mirror automatically", while Option C writes direct-child status back on read. These are distinguishable (drift-scope inference vs tracker-confirmed close state) but the reconciliation belongs in one design pass over the merged #85 text.
- Option D (issue-closed automation) stays the composable opt-in candidate it already was (`initiative-tracking` Maintenance note).

The follow-up issue carries acceptance criterion 3 of #86, the `resume-initiative.md` doc updates (including `/resume-initiative --start` parity for the new Jira transition affordance), and the #85 coordination note.

## Start-side sync — what `/work-issue` Step 3 gains

After worktree creation + branch rename, best-effort and WARN-and-continue on every step:

1. **Parent discovery** — parse the child issue body for a `## Parent epic` block; the ref on its first non-blank line names the immediate parent. Portable across backends. Do NOT use `view_issue`'s `parent?` (absent on GitHub plain reads). No block → skip epic sync (not an error).
2. **Epic Status sync** — `view_issue(parent)` → read-modify-write: set `- **Current branch:**` to the new branch, bump `- **Last updated:**` to today → `edit_body`. Touch nothing else (no `Phase`, no `Next up`, no `## Children`). Parent unfetchable or missing a Status block → WARN, skip.
3. **Mark in-progress** — via the configured per-backend affordance above. Nothing configured → no-op.

Failure semantics: every write is best-effort; a failure WARNs and never blocks the run, the worktree, or the eventual PR. No `.claude/issue-tracker.yaml` → the whole feature no-ops (fail-open).

`/work-issue`'s dispatch surface grows from `view_issue` (+ optional `add_label`/`close_issue`) to also include `edit_body` — header, Conventions, and Failure modes updated accordingly. Still contract-ops-only.

## Files touched (collision-audited vs #85)

| File | Change | #85 collision risk |
|---|---|---|
| `commands/work-issue.md` | Step 3 start-side sync; ops list; conventions; failure modes | none (mine alone) |
| `skills/initiative-tracking/SKILL.md` | new "In-progress status (optional affordances)" subsection; board wording generalised; Maintenance automation note points at follow-up | low — #85 edits mirror/adoption + a new Scope-probe section; keep edits surgical |
| `skills/initiative-tracking/references/github-projects-board.md` | In Progress bullet: trigger generalised to both drivers | none |
| `backends/github.md` | board section: In Progress trigger names both drivers | none |
| `backends/jira.md` | new `## In-progress transition (optional)` affordance section; n/a-board section cross-points to it | none |
| `backends/_interface.md` | "Optional backend-specific capabilities" names the in-progress affordance as the second instance | low — #85 may annotate `list_child_issues` |
| `examples/issue-tracker.yaml.example` | `jira.in_progress_transition` key; `github.project` comment mentions `/work-issue` | none |
| `CHANGELOG.md` | `## [Unreleased]` entry | trivial append conflict, resolved at merge |

Explicitly NOT touched: `commands/resume-initiative.md` (owned by #85 right now; its updates ride the follow-up).

## Invariants preserved

- `backends/_interface.md` keeps exactly eight `` ### `op` `` headings → op-parity CI green.
- Every status write best-effort; WARN-and-continue.
- `edit_body` is destructive → read-modify-write everywhere it appears.
- Rolled-up counts stay read-only; start-side writes only `Current branch` + `Last updated`.
- Merge gate untouched: no auto-merge behaviour added or changed.

## Verification

`python -m pytest -q` (unchanged surface — must stay green), the CI `backend-contract` grep run locally, `yamllint -d relaxed .`, markdownlint on the CHANGELOG. Manual: grep-count `### \`` headings in `_interface.md` == 8.
