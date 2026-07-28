# Walkthrough: resuming an initiative

Weeks have passed. You filed an epic + sub-issues using [`initiative-tracking`](../../skills/initiative-tracking/SKILL.md); some sub-issues closed; you're returning cold. This page shows what [`/resume-initiative`](../../commands/resume-initiative.md) does when you ask Claude Code to pick up where you left off — nothing was written to the epic while those sub-issues closed, so everything below is computed fresh, at read time, from the tracker's own linkage.

**Configured for this walkthrough:** same `.claude/issue-tracker.yaml` as [filing a bug](file-a-bug.md) — `backend: github`. The Jira variation is shown at the bottom.

## Mode 1 — no argument: list open epics

You type:

> /resume-initiative

The command invokes the configured backend's `list_open_issues({label: 'epic'})` (per [`backends/github.md`](../../backends/github.md)) and, for each result, `view_issue` plus `read_comments` to locate its machine block. Child membership and progress are derived from `list_child_issues`, not read off the body. It renders a compact list:

```text
#200  extract shared logging into obs/logging   Phase 1 · 2/4 direct · 2/4 leaves   Next: #203 api + worker cutover
#175  workspaces dashboard rebuild              Phase 2 · 5/7 direct · 5/7 leaves   Next: #182 datepicker accessibility
```

Then asks which to resume.

## Mode 2 — `<ref>`: load and display one epic

You type:

> /resume-initiative #200

The command calls `view_issue({ref: #200})` to fetch the evergreen description (`## Goal` / `## Scope` / `## Success criteria` / `## Design spec` — no phase state, no child list to parse there), `read_comments({ref: #200})` to locate the marker-tagged machine-block comment, and `list_child_issues({parent_ref: #200})` to fetch the native child set — native children already carry `{ref, title, status}` from that call. `view_issue` on each child then confirms whether it carries the `epic` label (sub-epic vs. leaf), and is also how a live-but-`unlinked` phase-map-only ref gets its title/status filled in. Membership is the union of native linkage and the machine block's `## Phases` ref map.

Output:

```text
Epic #200 — extract shared logging into obs/logging
Design spec: docs/superpowers/specs/2026-05-28-shared-logging-design.md (main)

Phase 1 · 2/4 direct · 2/4 leaves
Next up: #203 — api + worker cutover
Current branch: none

#200 extract shared logging into obs/logging   2/4 direct · 2/4 leaves
├─ #201 obs/logging skeleton                   (leaf, closed)
├─ #202 logging format spec                    (leaf, closed)
├─ #203 api + worker cutover                   (leaf, open)  ← next-up leaf
└─ #204 scheduler cutover + delete legacy loggers  (leaf, open)

Comments (1 total):
  2026-05-30 · teammate — Blocked on infra ticket TICKET-42 for the
    api cutover — holding off on #203 until that lands.

Pick up the next-up child (#203), pick a specific one, or stop?
```

That "Comments" section explicitly excludes the selected machine-block comment — its `## Phases` / `## Decision log` content already rendered above (as the phase progress and next-up), so re-printing it here would be redundant. Only genuine, non-machine comments on the issue surface here: the latest few plus a total count of that non-machine set. This is a live re-read, not a stored value — a teammate posting a new comment, or `#203` closing, changes this output on the next resume with no epic write in between.

If a live child had been natively linked but never added to the machine block's phase map, it renders `unphased` rather than as drift — the phase map is an organizing hint, not the membership source. A drift finding looks different: a phase-map ref that no longer resolves at all.

```text
Drift report — #200 extract shared logging into obs/logging
  ⚠ #199 (phase map) — no live issue in the tracker
  → fix the machine block's ## Phases section
```

Epics that enumerate a countable work set can additionally declare a
`## Scope probe` in the machine block (see [`initiative-tracking`](../../skills/initiative-tracking/SKILL.md)
"Scope probe — optional ground-truth hook"): an operator-authored command
whose output `/resume-initiative` diffs against the enumerated scope,
offering a [`followup-tracking`](../../skills/followup-tracking/SKILL.md)
filing (`Why deferred: drift`) for each unenumerated item. Declining
files nothing — resume never writes except the confirmed filing.

You answer "next-up" — recurses into Mode 3 with `#203`.

## Mode 3 — `<ref> --start`: enter the worktree for the next child

You can also skip Mode 2 by passing `--start`:

> /resume-initiative #200 --start

The command:

1. Re-runs Mode 2 to identify the next-up leaf (`#203`) — its drift report and comment surfacing print as part of this run; a follow-up offer, if any, is asked once before entering the worktree.
2. Checks for an existing worktree at `.claude/worktrees/<branch-slug>`. If absent:
3. Creates a worktree via the `superpowers:using-git-worktrees` skill (or the native `EnterWorktree` tool). Branch name inferred from the child issue body's `Branch:` line, else from the type label (`feat/<short-slug>` for enhancements, `fix/<short-slug>` for bugs).
4. After `EnterWorktree`, renames the branch from the tool's default `worktree-<sanitized>` shape to the conventional `feat/<slug>`.
5. Reports the new worktree path — the session's CWD already switched into it. If `github.project` is configured (GitHub backend), best-effort sets `#203`'s board item Status to `In Progress` — a failure WARNs and does NOT abort the handoff; with `github.project` unset, this step is skipped entirely.
6. Calls `view_issue({ref: #203})` to fetch the leaf issue body, then hands off to `superpowers:brainstorming` inline with it as starting context. The body is already an agent prompt (Goal / Locus / Sketch / Acceptance / Verify); brainstorming uses it as input, not re-derivation.

The session is now inside the worktree, brainstorming the sub-issue. You did NOT need to open a new window.

**No epic write happens here.** `--start` does not touch the parent's machine block on this branch — matching the `## Current branch` in-progress signal that `/work-issue` Step 3 sets is `--start`'s own follow-up (#88), not yet shipped. Today `--start` only optionally syncs the child's board item, as above.

## Three ref shapes — all work

A machine block's `## Phases` map (or a legacy epic's `## Children` mirror) can carry three ref shapes; the parser handles all three:

| Shape | Example | Meaning |
| --- | --- | --- |
| `#N` | `#203` | Same repo as the epic (per `.claude/issue-tracker.yaml` `github.repo`) |
| `owner/repo#N` | `your-org/other-repo#142` | Cross-repo GitHub ref — fetch from that repo |
| `PROJ-123` | `LOG-15` | Jira issue key (project-scoped) |

For an evergreen epic, the phase map plus native `list_child_issues` linkage together are the canonical cross-backend index — a phase-map ref not natively linked still counts as a child (flagged `unlinked`, with a `link_sub_issue` fix pointer where the backend allows); native linkage past a backend's nesting ceiling (Jira's three-level cap) legitimately lives in the phase map alone.

**Mixed-backend mismatch:** if the configured backend is `github` and a `PROJ-123`-shaped ref appears in the phase map (or vice versa), the command logs a one-line soft warning ("skipping child `LOG-15` — ref syntax doesn't match the configured backend") and continues. It does NOT crash.

## Variations

- **`backend: jira`** — same flow, different refs. The epic ref becomes `LOG-1`; sub-issues come back as `LOG-2..5`. Dispatch routes through [`backends/jira.md`](../../backends/jira.md) — `searchJiraIssuesUsingJql` for Mode 1, `getJiraIssue` for `view_issue`, `getJiraIssue fields:["comment"]` for `read_comments`, etc. The `<ref>` syntax in `Next up:` is the only visible difference.
- **Cross-repo initiative** — an epic in `your-org/api` with a sub-issue in `your-org/lib`. The phase-map ref is `your-org/lib#29`. The parser resolves `view_issue` against the cross-repo target; the worktree still lands in the consumer's CWD.
- **Legacy epic — no machine block, body still has `## Status block`** — the command falls back to its legacy reader: the body's four-line Status block plus its `## Children` task-list mirror, parsed exactly as before this shape existed. No forced migration; convert it in place with `/resume-initiative #200 --adopt`.
- **Unrecognizable epic node** — if the body doesn't resolve to either shape (no evergreen sections, no Status block) and `view_issue` can't otherwise establish it as a recognizable epic node, the command reports "epic exists but has no machine-readable status; update via the `initiative-tracking` skill or use `view_issue` directly" and stops.
- **No open epics** — Mode 1 reports "no open epics" and exits cleanly.
- **`Next up: none`** — Mode 3 (`--start`) refuses to create a worktree from nothing; reports "no next-up child to start" and exits.
- **Unlinked / dead phase-map ref** — a live child in the phase map but not natively linked renders `unlinked` (not drift — remediation is `link_sub_issue`, never an auto-edit); a phase-map ref that no longer resolves prints a drift finding above the child tree, pointing at editing the machine block's `## Phases` section directly.

## See also

- [`/resume-initiative` command](../../commands/resume-initiative.md) — the full command reference (all modes, failure modes, conventions).
- [`initiative-tracking` skill](../../skills/initiative-tracking/SKILL.md) — what writes the machine block this command reads, and derives the rest.
- [`templates/epic-body.md`](../../templates/epic-body.md) — the evergreen epic body skeleton.
- [`templates/epic-machine-block.md`](../../templates/epic-machine-block.md) — the machine-block comment skeleton.
- [Walkthrough: filing an epic](file-an-epic.md) — what to do at the start of an initiative.
