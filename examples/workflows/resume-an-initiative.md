# Walkthrough: resuming an initiative

Weeks have passed. You filed an epic + sub-issues using [`initiative-tracking`](../../skills/initiative-tracking/SKILL.md); some sub-issues closed; you're returning cold. This page shows what [`/resume-initiative`](../../commands/resume-initiative.md) does when you ask Claude Code to pick up where you left off.

**Configured for this walkthrough:** same `.claude/issue-tracker.yaml` as [filing a bug](file-a-bug.md) — `backend: github`. The Jira variation is shown at the bottom.

## Mode 1 — no argument: list open epics

You type:

> /resume-initiative

The command invokes the configured backend's `list_open_issues({label: 'epic'})` (per [`backends/github.md`](../../backends/github.md)) and `view_issue` on each result to fetch the Status block. It renders a compact list:

```text
#200  extract shared logging into obs/logging   Phase 1 · 2/4 closed    Next: #203 api + worker cutover
#175  workspaces dashboard rebuild              Phase 2 · 5/7 closed    Next: #182 datepicker accessibility
```

Then asks which to resume.

## Mode 2 — `<ref>`: load and display one epic

You type:

> /resume-initiative #200

The command calls `view_issue({ref: #200})`, parses the body's Status block per the four canonical field prefixes (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`), and walks the `## Children` task-list mirror to fetch each child's title + status.

Output:

```text
Epic #200 — extract shared logging into obs/logging
Design spec: docs/superpowers/specs/2026-05-28-shared-logging-design.md (main)

Phase 1 · 2/4 sub-issues closed
Next up: #203 — api + worker cutover
Current branch: none
Last updated: 2026-05-27

Children:
  [x] #201 — obs/logging skeleton (Phase 0) — closed 2026-05-22
  [x] #202 — logging format spec (Phase 0) — closed 2026-05-25
  [ ] #203 — api + worker cutover (Phase 1) — OPEN
  [ ] #204 — scheduler cutover + delete legacy loggers (Phase 1) — OPEN

Pick up the next-up child (#203), pick a specific one, or stop?
```

You answer "next-up" — recurses into Mode 3 with `#203`.

## Mode 3 — `<ref> --start`: enter the worktree for the next child

You can also skip Mode 2 by passing `--start`:

> /resume-initiative #200 --start

The command:

1. Re-runs Mode 2 to identify the next-up child (`#203`).
2. Checks for an existing worktree at `.claude/worktrees/<branch-slug>`. If absent:
3. Creates a worktree via the `superpowers:using-git-worktrees` skill (or the native `EnterWorktree` tool). Branch name inferred from the child issue body's `Branch:` line, else from the type label (`feat/<short-slug>` for enhancements, `fix/<short-slug>` for bugs).
4. After `EnterWorktree`, renames the branch from the tool's default `worktree-<sanitized>` shape to the conventional `feat/<slug>`.
5. Calls `view_issue({ref: #203})` to fetch the sub-issue body.
6. Hands off to `superpowers:brainstorming` inline with the sub-issue body as starting context. The body is already an agent prompt (Goal / Locus / Sketch / Acceptance / Verify); brainstorming uses it as input, not re-derivation.

The session is now inside the worktree, brainstorming the sub-issue. You did NOT need to open a new window.

## Three ref shapes — all work

The `## Children` task-list mirror in the epic body can carry three ref shapes; the parser handles all three:

| Shape | Example | Meaning |
| --- | --- | --- |
| `#N` | `#203` | Same repo as the epic (per `.claude/issue-tracker.yaml` `github.repo`) |
| `owner/repo#N` | `your-org/other-repo#142` | Cross-repo GitHub ref — fetch from that repo |
| `PROJ-123` | `LOG-15` | Jira issue key (project-scoped) |

This is the canonical cross-backend index. Native sub-issue API queries (e.g. GitHub's `/repos/<owner>/<repo>/issues/<N>/sub_issues`) are an optional augmentation — useful for showing native-linkage discrepancies — but the task-list mirror is what the parser trusts.

**Mixed-backend mismatch:** if the configured backend is `github` and a `PROJ-123`-shaped ref appears in the mirror (or vice versa), the command logs a one-line soft warning ("skipping child `LOG-15` — ref syntax doesn't match the configured backend") and continues. It does NOT crash.

## Variations

- **`backend: jira`** — same flow, different refs. The epic ref becomes `LOG-1`; sub-issues come back as `LOG-2..5`. Dispatch routes through [`backends/jira.md`](../../backends/jira.md) — `searchJiraIssuesUsingJql` for Mode 1, `getJiraIssue` for `view_issue`, etc. The Status block format is byte-identical; the `<ref>` syntax in `Next up:` is the only visible difference.
- **Cross-repo initiative** — an epic in `trading-bot` with a sub-issue in `agent-issue-tracker`. The mirror line is `- [ ] maxdimitrov/agent-issue-tracker#29 — title`. The parser resolves `view_issue` against the cross-repo target; the worktree still lands in the consumer's CWD.
- **No machine-readable Status block** — if the epic body was hand-edited away from the canonical four-line format, the command reports "epic exists but has no machine-readable status; update via the `initiative-tracking` skill or use `view_issue` directly" and stops.
- **No open epics** — Mode 1 reports "no open epics" and exits cleanly.
- **`Next up: none`** — Mode 3 (`--start`) refuses to create a worktree from nothing; reports "no next-up child to start" and exits.

## See also

- [`/resume-initiative` command](../../commands/resume-initiative.md) — the full command reference (all three modes, failure modes, conventions).
- [`initiative-tracking` skill](../../skills/initiative-tracking/SKILL.md) — what writes the Status block this command parses.
- [`templates/epic-body.md`](../../templates/epic-body.md) — the canonical epic body skeleton with the four field prefixes.
- [Walkthrough: filing an epic](file-an-epic.md) — what to do at the start of an initiative.
