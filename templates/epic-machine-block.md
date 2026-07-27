# Epic Machine-Block Comment Template

The single marker-tagged comment holding an epic node's non-derivable
structure. Written ONLY via the backend's `upsert_comment` operation
(destructive whole-comment replace — read-modify-write, cross-backend
invariant 2). See `backends/_interface.md` "Machine-block comment
convention".

Rules:

- OMIT the comment entirely when every section below would be empty —
  the simplest epics carry zero machine cruft.
- OMIT any individual section that is empty. Section headings are
  CANONICAL — readers match them literally.
- Readers select the **earliest marker-carrying comment from a trusted
  author** (`read_comments`'s `author_trust`); marker comments from
  untrusted authors are ignored with a one-line WARN.
- Child titles and statuses NEVER appear here — they are derived live.
  Phases hold refs only.

---

<!-- agent-issue-tracker:machine-block -->

## Phases
Phase name + ordered child refs only — no titles, no status. Phase
order and ref order within a phase define next-up ordering; children
natively linked but absent from this map render `unphased` (after all
phased children, in the backend's native return order).
- **Phase 0** — <phase goal> — <ref>, <ref>
- **Phase 1** — <phase goal> — <ref>

## Parent epic
Sub-epics only; a root epic omits this section. Names the IMMEDIATE
parent.
- <parent-ref> — <one-line parent title>

## Current branch
The cross-backend in-progress fallback signal, upserted by a driver
(`/work-issue`, `/resume-initiative --start`) when work starts.
- <branch-name>

## Scope probe
Optional ground-truth hook — same spec as before (first fenced block
under the heading holds the command; shown to the operator before it
runs). Anyone able to comment can attempt to plant one — the trust
rule plus show-before-run gate what executes.
<one line saying what the probe enumerates>
```sh
<command printing one ground-truth item per line>
```

## Decision log
Append-only — each entry dated, one paragraph. Appending is a
read-modify-write upsert of this whole comment.
- **YYYY-MM-DD** — <what was decided and why>
