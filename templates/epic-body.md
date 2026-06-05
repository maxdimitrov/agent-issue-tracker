# Epic Body Template

This is the canonical agent-readable body for filing an epic via
the `initiative-tracking` skill. Use it verbatim — each section
maps to the index `/resume-initiative` reads when an operator
returns to a multi-week initiative.

The four field labels under `## Status block` are CANONICAL —
`**Phase:**`, `**Next up:**`, `**Current branch:**`,
`**Last updated:**`. `/resume-initiative` matches each line on its
**bold field label**, tolerant of the leading list-bullet character
(`-`/`*`/`+`) — on Jira the Atlassian Remote MCP rewrites a leading
`-` bullet to `*` on the ADF round-trip, so the bullet glyph is not
matched literally. Write them in the canonical `- **Label:**` form;
do not reword the labels.

To file, fill in this template and pass the result as the `body`
argument to your backend's `create_issue` operation with
`type: epic`. See `backends/<backend>.md` for the literal
invocation.

**This template doubles as the sub-epic body.** Initiatives may
nest more than one level — a child of an epic can itself be an epic
(a "sub-epic") with its own children. A sub-epic uses THIS template
verbatim and additionally fills in the optional `## Parent epic`
block below. A **root** epic omits that block (it has no parent).
That single difference — `## Parent epic` present or absent — is how
`/resume-initiative` tells a root from a nested node, portably,
without depending on native tracker linkage. See the
`initiative-tracking` skill's "Nested initiatives" section.

---

## Goal
<one sentence — what exists after the initiative is done. State it
as an observable outcome an outside reader can verify, e.g. "the
worker/queue redesign ships behind a feature flag with the
classic-codepath fallback removed">

## Parent epic
OMIT this whole section for a root epic. Include it only when this
epic is itself a child of a larger epic (a sub-epic):
- <parent-ref> — <one-line parent title> (Phase <N>)

When present, the parent's own `## Children` list must carry this
node marked `▸ sub-epic` (see that block below). The `<parent-ref>`
uses the backend's ref syntax — `#N` / `owner/repo#N` / `PROJ-123`.

## Design spec
Path to the design spec that scopes this initiative, plus the
branch and commit it landed on.
- `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (branch
  `<branch>`, commit `<sha>`)

## Status block
The four field labels below are CANONICAL — `/resume-initiative`
matches each line on its **bold field label**, tolerant of the
leading list-bullet character (`-`/`*`/`+`; Jira's ADF round-trip
rewrites a leading `-` to `*`). Write them in the `- **Label:**`
form shown. Update them whenever a sub-issue closes (see the
`initiative-tracking` skill's Maintenance section).
- **Phase:** <phase-name> · <closed>/<total> sub-issues closed
- **Next up:** <ref> — <title> (or `none` if no open children)
- **Current branch:** <branch-name> (or `none` if no active branch)
- **Last updated:** YYYY-MM-DD

The `<ref>` syntax depends on the backend — `#N` on GitHub,
`PROJ-123` on Jira. `/resume-initiative` parses both; the backend
module renders the syntax.

**`<closed>/<total>` counts this node's DIRECT children only.** A
child that is itself a sub-epic counts as a single unit here (closed
when the sub-epic node itself closes), not as its leaf subtree. This
keeps maintenance one-hop: closing a leaf only edits its immediate
parent's Status block. `/resume-initiative` computes the true
rolled-up leaf totals across the whole tree at read time for
display — it does not write them back, so don't hand-maintain a
transitive count here. **`Next up`** likewise names this node's next
direct child; if that child is a sub-epic, `/resume-initiative`
drills into it to surface the next workable *leaf*.

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
NOT replace this list. For initiatives nested deeper than one level,
this per-node mirror is the **tree-of-record** — each epic node
lists only its OWN direct children; the full tree is the recursion
over every node's mirror (see cross-backend invariant 6 in
`backends/_interface.md`).
- [ ] <ref> — <title> (Phase 0)
- [x] <ref> — <title> (Phase 0) — closed YYYY-MM-DD
- [ ] <ref> — <title> (Phase 0) ▸ sub-epic
- [x] <ref> — <title> (Phase 0) ▸ sub-epic — closed YYYY-MM-DD
- ...

A child that is itself a sub-epic carries a trailing ` ▸ sub-epic`
marker, placed AFTER the `(Phase N)` suffix and before any
`— closed YYYY-MM-DD` tail — matching the worked-example lines
above (open: `… (Phase 0) ▸ sub-epic`; closed:
`… (Phase 0) ▸ sub-epic — closed YYYY-MM-DD`). The marker is a
human-readable hint that tells `/resume-initiative` to recurse into
that child's own `## Children` mirror rather than treat it as a
leaf. The authoritative signal is still that the child carries the
`epic` label; old mirrors without the marker keep working because
the command falls back to the label check. The leading
`- [ ] <ref> — <title>` grammar is unchanged.

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
