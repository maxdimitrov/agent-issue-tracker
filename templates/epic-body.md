# Epic Body Template

The canonical agent-readable description for filing an epic via the
`initiative-tracking` skill. The description is **evergreen** — goal,
scope, success criteria, and spec link only. Edit it only when the
initiative's goal or scope genuinely changes; NEVER per child.

Everything else is either **derived live** or lives in the
**machine-block comment**:

- Child set, per-child open/closed status, direct-child counts,
  rolled-up leaf counts, and next-up are derived by
  `/resume-initiative` at read time from the backend's
  `list_child_issues` + per-child `view_issue`. They are never written
  into the description — closing a child requires no edit here.
- Phases, the sub-epic parent pointer, the current-branch signal, the
  scope probe, and the decision log live in the single marker-tagged
  machine-block comment — see `templates/epic-machine-block.md`.
  A flat epic with none of those carries no comment at all.

To file, fill in this template and pass the result as the `body`
argument to your backend's `create_issue` operation with `type: epic`.
See `backends/<backend>.md` for the literal invocation.

**This template doubles as the sub-epic body.** A sub-epic uses this
same evergreen shape; its `## Parent epic` pointer lives in its
machine-block comment, not in the description. Legacy epics (bodies
still carrying a `## Status block`) keep working via
`/resume-initiative`'s legacy reader; convert one with
`/resume-initiative --adopt <ref>`.

---

## Goal
<one sentence — what exists after the initiative is done. State it
as an observable outcome an outside reader can verify.>

## Scope
In:
- <capability in scope>
- <capability in scope>

Out:
- <adjacent work explicitly out, with the one-line reason>

## Success criteria
Outcome-based and verifiable by an outside reader — never child
counts or phase state (those are derived, and they change).
- [ ] <observable outcome>
- [ ] <observable outcome>

## Design spec
Path to the design spec that scopes this initiative, plus the branch
and commit it landed on.
- `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (branch
  `<branch>`, commit `<sha>`)
