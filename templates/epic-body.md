# Epic Body Template

This is the canonical agent-readable body for filing an epic via
the `initiative-tracking` skill. Use it verbatim — each section
maps to the index `/resume-initiative` reads when an operator
returns to a multi-week initiative.

The four field-prefix strings under `## Status block` are CANONICAL
and exact — `- **Phase:**`, `- **Next up:**`, `- **Current branch:**`,
`- **Last updated:**`. `/resume-initiative` parses them
character-for-character across both GitHub and Jira backends. Do
not reword.

To file, fill in this template and pass the result as the `body`
argument to your backend's `create_issue` operation with
`type: epic`. See `backends/<backend>.md` for the literal
invocation.

---

## Goal
<one sentence — what exists after the initiative is done. State it
as an observable outcome an outside reader can verify, e.g. "the
worker/queue redesign ships behind a feature flag with the
classic-codepath fallback removed">

## Design spec
Path to the design spec that scopes this initiative, plus the
branch and commit it landed on.
- `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (branch
  `<branch>`, commit `<sha>`)

## Status block
The four field prefixes below are CANONICAL — they appear literally
because `/resume-initiative` parses them character-for-character.
Update them whenever a sub-issue closes (see the
`initiative-tracking` skill's Maintenance section).
- **Phase:** <phase-name> · <closed>/<total> sub-issues closed
- **Next up:** <ref> — <title> (or `none` if no open children)
- **Current branch:** <branch-name> (or `none` if no active branch)
- **Last updated:** YYYY-MM-DD

The `<ref>` syntax depends on the backend — `#N` on GitHub,
`PROJ-123` on Jira. `/resume-initiative` parses both; the backend
module renders the syntax.

## Phases
Numbered, with sub-issue refs. Each phase is a milestone, not a
single PR — phase N's sub-issues are typically 2-5 issues filed
against the configured tracker.
- **Phase 0** — <phase goal> — sub-issues: <ref>, <ref>
- **Phase 1** — <phase goal> — sub-issues: <ref>, <ref>
- **Phase 2** — <phase goal> — sub-issues: <ref>
- ...

## Children
Task-list mirror of all sub-issues filed for this initiative. This
list is the **cross-backend source of truth** —
`/resume-initiative` parses these lines regardless of whether the
backend has native sub-issue linkage in place. Always keep it in
sync after a sub-issue is filed or closes.

Native parent-child linkage in the tracker (via `link_sub_issue`)
is additional, per-backend metadata for the tracker's UI — it does
NOT replace this list.
- [ ] <ref> — <title> (Phase 0)
- [x] <ref> — <title> (Phase 0) — closed YYYY-MM-DD
- ...

## Decision log
Append-only — each entry is dated and one paragraph. Record
non-trivial decisions made during a sub-issue's PR: the rationale
the next agent will need but cannot rederive from the diff or the
sub-issue body.

- **YYYY-MM-DD** — <what was decided and why>

## Resume from here
Run `/resume-initiative <this-epic-ref>` in a fresh Claude Code
session. The command parses the Status block and surfaces the
next-up child, optionally checks out the branch / worktree, and
hands off to the next sub-issue's brainstorm.
