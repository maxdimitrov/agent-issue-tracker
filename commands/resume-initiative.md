---
description: Show open epic initiatives and the next-up child issue; optionally start work on the next child.
---

# /resume-initiative [epic-ref] [--start]

Pick up where multi-week initiative work was left off. Invokes the configured backend's `list_open_issues({label: 'epic'})` operation to list open initiatives with their progress, and points at the next-up child issue. Optionally enters the worktree for the next child or creates one if absent. The configured backend is determined by `.claude/issue-tracker.yaml` in the consumer project.

This command is generic — it works for any initiative tracked via the `initiative-tracking` skill, not just the engine/operator split.

After the worktree is created, `/resume-initiative --start` hands off to `superpowers:brainstorming` inline so the standard agent workflow (brainstorm → plan → execute) starts immediately in the same session. Do NOT stop and tell the operator to open a new window — `EnterWorktree` already switched the session's CWD into the worktree.

Named `/resume-initiative` (not `/resume`) to avoid shadowing Claude Code's built-in `/resume`, which resumes a prior conversation.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/resume-initiative` | List all open epic issues + their next-up child. Pick one. |
| `/resume-initiative <ref>` | Load epic `<ref>`. Show phase progress + next-up child issue. |
| `/resume-initiative <ref> --start` | Load epic `<ref>`, enter the worktree for the next-up child, and hand off to `superpowers:brainstorming` inline. |

## What you should do

### Mode 1 — no argument: list open epics

1. Invoke the configured backend's `list_open_issues({label: 'epic'})` operation; see `backends/<backend>.md` for the literal invocation. The returned list contains `[{ref, title, status}, ...]` entries. For each epic in the list, call `view_issue({ref})` to fetch the full issue body so the Status block can be parsed. (The N+1 cost is acceptable — open-epic count is typically <20.)

2. For each epic, parse its body for the **Status block** (a markdown section the `initiative-tracking` skill maintains). The four field-prefix strings are canonical and exact (see the `initiative-tracking` skill's "Status block — exact field spec" table):
   - `- **Phase:**` — e.g. `Phase 1a · 2/4 sub-issues closed`
   - `- **Next up:**` — `#<N>` or `PROJ-123` or `owner/repo#<N>` — or literal `none`
   - `- **Current branch:**` — branch name or literal `none`
   - `- **Last updated:**` — `YYYY-MM-DD`

3. Render a compact list to the operator:
   ```
   #123  engine/operator split          Phase 1a · 2/4 closed   Next: #126 reserve-ledger schema
   PROJ-150  observability rollout      Phase 0  · 1/3 closed   Next: PROJ-152 metrics emitter
   ```

4. Ask the operator which epic to resume. On their reply, recurse into Mode 2 with the chosen `<ref>`.

### Mode 2 — `<ref>`: load and display one epic

1. Invoke `view_issue({ref})` where `<ref>` may be `#N` (GitHub), `owner/repo#N` (cross-repo GitHub), or `PROJ-123` (Jira). See `backends/<backend>.md` for the literal call signature. The returned `{ref, title, body, labels[], status, parent?}` carries the body needed for Status-block parsing.

2. Show the operator:
   - The epic's title + design-spec link (read from the body's `## Design spec` section — the first non-blank line under that heading is the spec path; the `initiative-tracking` skill's "Epic body template" pins the convention)
   - Phase breakdown with status (from the body's `## Phases` section)
   - Current branch / worktree (from the Status block's `- **Current branch:**` line)
   - Next-up child issue ref + title (from the Status block's `- **Next up:**` line)

3. List open child issues. The canonical source is the `## Children` task-list mirror in the epic body. For each unchecked `- [ ] <ref> — <title>` line, parse the ref to determine the backend:

   **Three ref shapes:**
   - `#N` (bare) — same repo as the epic; use the configured `github.repo` on GitHub
   - `owner/repo#N` — explicit cross-repo GitHub ref; use that `owner/repo`, NOT the configured one
   - `PROJ-123` — Jira issue key (project-scoped)

   For each child ref, call `view_issue({ref})` to fetch the title + status. **Mixed-backend handling:** if the configured backend is `github` and a `PROJ-123`-shaped ref appears in the mirror (or vice versa), log a one-line soft warning ("skipping child `<ref>` — ref syntax doesn't match the configured backend") and continue with the remaining children. Do NOT crash.

   The native sub-issue API relation MAY be queried as an optional augmentation (e.g. GitHub's `/repos/<owner>/<repo>/issues/<N>/sub_issues` endpoint) and displayed alongside the task-list parse, but the task-list mirror is the canonical cross-backend index per `skills/initiative-tracking/SKILL.md`.

4. Ask the operator: "Pick up the next-up child, pick a specific one, or stop?" Wait for their reply. If they pick a child (next-up or specific), recurse into Mode 3 with that child's ref — Mode 3 creates the worktree AND starts the brainstorm inline. Do NOT stop after the worktree is created.

### Mode 3 — `<ref> --start`: enter the worktree for the next child

1. Run Mode 2 to identify the next-up child issue. If `Next up:` is the literal `none`, or the children list is empty, or no child issue can be located, STOP — report `no next-up child to start; epic <ref> has no open children` and exit. Do NOT attempt worktree creation from nothing.

2. If a worktree for that child already exists (convention: `.claude/worktrees/<branch-with-slash-replaced-by-plus>`), report its path and stop. Otherwise:

3. Use the `superpowers:using-git-worktrees` skill (or the native `EnterWorktree` tool) to create one. The branch name comes from the child issue body's `Branch:` line if present, otherwise infer:
   - `feat/<short-slug-of-title>` for `enhancement`-labelled children
   - `fix/<short-slug>` for `bug`
   - `docs/<short-slug>` for `documentation`

   **Branch-naming caveat for the native `EnterWorktree` tool.** It sanitizes the branch name to `worktree-<slug>+<rest>` (prefix + `/` replaced by `+`), which does NOT match the project's convention (`feat/...`, `fix/...`, `docs/...`). Immediately after `EnterWorktree` returns, rename the branch in place:
   ```bash
   git branch -m worktree-<sanitized> <conventional-name>
   ```
   The worktree directory keeps its `<sanitized>` name (that matches the existing on-disk convention `feat+<slug>`); only the branch is renamed.

4. Report the new worktree path. `EnterWorktree` already switched the session's CWD into the worktree, so the agent workflow continues inline — do NOT stop and ask the operator to open a new window.
   Invoke `view_issue({ref: child-ref})` to fetch the child issue body (where `child-ref` may carry an `owner/repo#N` prefix for cross-repo cases); pass the returned `body` to `superpowers:brainstorming`. The issue body is already an agent prompt (Goal, Locus, Sketch, Acceptance, Verify) — brainstorming uses it as starting context, it does NOT re-derive the problem from scratch.

   If the operator would rather use a fresh window, they can interrupt — this inline handoff is the default path. The same inline-brainstorm convention applies when re-entering an existing worktree via `EnterWorktree path=...`.

## Conventions assumed

- The epic issue body contains a Status block written by the `initiative-tracking` skill. If it does not, fail gracefully — report the epic exists but has no machine-readable status, and ask the operator to update it or use plain `view_issue` directly (via the backend module).
- The `epic` label is the source of truth for "this is an initiative, not a single-issue task."
- Child issues link back to the parent epic via:
  1. The `## Children` task-list mirror in the parent epic body — the **cross-backend canonical source** per `skills/initiative-tracking/SKILL.md`
  2. Native sub-issue linkage in the tracker (when the backend and parent-child repos match) — optional augmentation for display
  3. A `## Parent epic` block in the child issue body (per `templates/sub-issue-body.md`)

## Failure modes

- Backend authentication or reachability failure → the configured backend reports a reachability failure. Run `/tracker-doctor` to diagnose the setup; see `backends/<backend>.md` setup section and re-invoke.
- `view_issue` returns not-found for the supplied ref → check the ref syntax matches the configured backend (`#42` vs `PROJ-123` vs `owner/repo#42`).
- No open epics → tell the operator. Do not crash.
- The chosen epic body is missing required fields → report which fields are missing; suggest the operator runs the `initiative-tracking` skill to rewrite it.
- `--start` invoked but `Next up:` is `none` or no children exist → report "no next-up child to start" and exit; do not create a worktree from nothing.
- Child ref syntax mismatch (e.g. `PROJ-123` in a GitHub-configured repo) → log a soft warning and skip that child; continue with the remaining children. Do NOT crash.
- Cross-repo `owner/repo#N` child ref → extract the `owner/repo` prefix and dispatch `view_issue({ref: owner/repo#N})` through the configured backend; the backend module documents how it handles cross-repo refs.
