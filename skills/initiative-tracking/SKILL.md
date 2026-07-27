---
name: initiative-tracking
description: >-
  How multi-week, multi-issue initiatives ("epics") are tracked —
  they live as a single issue in the configured tracker (see
  `.claude/issue-tracker.yaml`) labelled `epic`, with sub-issues
  for each phase or sub-task. The epic description is evergreen
  (goal, scope, success criteria, design spec) and is edited only
  when the initiative's own goal or scope changes, never per
  child — child membership, per-child status, and next-up are
  derived live by the `/resume-initiative` slash command from the
  tracker's native parent-child linkage on every read, never
  stored. Non-derivable structure (phases, a sub-epic's parent
  pointer, the current-branch signal, the scope probe, the
  decision log) lives in one optional marker-tagged machine-block
  comment. Epics filed before this shape existed still carry the
  older body `## Status block`; those keep working indefinitely via
  `/resume-initiative`'s legacy reader (no forced migration) —
  convert one with `/resume-initiative --adopt`. Issues here, like
  in the sibling tracker skills, are consumed by Claude Code
  agents — the epic is an **agent-readable index** of the
  initiative, and each sub-issue's body is an agent prompt that
  satisfies the same locus / scope / acceptance requirements as a
  feature-request or bug. Use this skill whenever scope is
  genuinely multi-week and spans more than one PR — kicking off a
  new initiative, filing the sub-issues for an existing one, or
  reorganising phases. The siblings bug-tracking, feature-request,
  and followup-tracking cover single-issue shapes; this one covers
  the *index* over many issues. Initiatives may nest more than one
  level — a child of an epic can itself be an epic (a "sub-epic")
  with its own children — and `/resume-initiative` walks the whole
  tree; see "Nested initiatives". An epic may declare an optional
  `## Scope probe` (an operator-authored ground-truth command) that
  `/resume-initiative` diffs against enumerated scope on resume,
  surfacing drift — see "Scope probe — optional ground-truth hook".
---

# Initiative Tracking — Multi-Week Effort as Epic + Sub-Issues

The canonical tracker is the one configured in the consumer
project's `.claude/issue-tracker.yaml`. The plugin's
`backends/_interface.md` documents the ten operations every
backend implements; `backends/<backend>.md` (e.g.
`backends/github.md`) documents the literal CLI / MCP invocation
for each operation.

An initiative is not a different *tracker* — it is a different
*shape of tracked work*: one epic issue indexes many child issues,
all under the same label convention, with child membership and
status derived live by the operator-facing `/resume-initiative`
command from the tracker's own native linkage — nothing to keep in
sync by hand. (Epics still carrying the older body `## Status
block` shape keep working via `/resume-initiative`'s legacy reader
— see "Legacy epics" below.)

**Slash-command entry-point.** [`/file-epic`](../../commands/file-epic.md) is a
discoverable wrapper around this skill — it surfaces in Claude Code's command
palette and triggers the exact flow described here, adding no behaviour of its
own. This skill is the source of truth; filing by intent ("open an epic") is
equivalent. Once the epic exists, [`/resume-initiative`](../../commands/resume-initiative.md)
walks its tree.

## Why structure matters

A multi-week initiative tracked only as a pile of un-related
issues is indistinguishable from the regular backlog. The operator
can't see "where am I" without reading every issue. An agent
picking up work tomorrow has no idea which child is next. Native
sub-issue linkage — derived live, plus the optional machine-block
comment for whatever the tracker can't express natively — solves
both: `/resume-initiative` computes the whole picture from the
tracker itself, nothing hand-maintained to go stale.

An unstructured "epic" issue (just a list of links in the body)
fails the same way the other tracker skills fail when an issue
body is vague: the next agent can't pick it up cold.

## Triage gate — is this actually an initiative?

This skill is for multi-week, multi-issue work. **Most things are
not.** Default-favour the lighter-weight sibling skills:

| Signal | Use this skill | Use a single-issue sibling instead |
|---|---|---|
| Fits in one PR | no | yes — `feature-request` or `bug-tracking` |
| Spans 1–3 days | no | yes — single issue |
| Spans weeks | yes | — |
| Multiple phases with checkpoints | yes | — |
| Has a design spec | yes (link it) | optional |
| Decomposes into 3+ independent issues | yes | — |

If you would only file 1–2 sub-issues, you don't have an
initiative — you have a feature. Bounce out: file via
`feature-request` instead.

The same gate applies one level down. If an existing **child** of an
epic turns out to itself decompose into 3+ independent sub-issues,
it has outgrown leaf status and should be promoted to a **sub-epic**
under its existing parent — not flattened, and not spun off as a new
root initiative. A child with only 1–2 sub-tasks is still a leaf;
file those as a plain checklist in its body or as `followup`s, not
as a sub-epic. See "Nested initiatives" for the promotion mechanics.

If the work is genuinely multi-week BUT there's no design spec
yet, run `superpowers:brainstorming` → `superpowers:writing-plans`
first. This skill takes a written spec as input.

## When to file an epic

File an epic when:

- A design spec (in `docs/superpowers/specs/`) describes work
  that spans multiple PRs / weeks / phases.
- Scope deferred from in-flight work has grown into its own
  multi-PR effort. Supersede the original followup-tracking issue
  with a one-line "superseded by `<epic-ref>`" close-comment via
  your backend's `close_issue` operation.
- The operator says: "this is a big one", "spin this up as its
  own initiative", "let's plan this across weeks."

Do **not** file when:

- The work is single-PR. Use `feature-request` or `bug-tracking`.
- There is no design spec yet. Run brainstorming +
  writing-plans first.
- A similar epic already exists — invoke the backend's
  `list_open_issues` operation with `label: epic` first. Most
  "new" initiatives are continuations of existing ones.

## Adopting an existing epic into the template

Sometimes the epic already exists in the tracker but is NOT in the
evergreen shape — it was filed by hand, by another tool, or before
this skill existed, so its body still carries the older `## Status
block` + `## Children` mirror shape (or something else entirely).
"Make this epic evergreen" is an *adoption*, not a fresh file.

**The load-bearing rule, unchanged since before this shape existed:
never infer the child set from the epic body's prose — query the
tracker.** The body is the exact artifact adoption rewrites, so it
is the least trustworthy source for "what are this epic's
children?" A line like "child tickets to be filed when prioritized"
can be months stale while children already exist (some closed, some
in review). This is the founding principle both the old mirror-based
model and the current evergreen model share — only the *destination*
shape changed.

Run `/resume-initiative <ref> --adopt` (see `commands/resume-initiative.md`
"Mode 4"). It carries out the query-the-tracker rule mechanically:
`list_child_issues` reconciliation against the body mirror, with live
mirror-only children natively linked where the backend allows; the
machine-block comment assembled from whatever the legacy body already
carries (`## Phases` or the mirror's `(Phase N)` annotations, `##
Decision log`, `## Scope probe`, `## Parent epic`, and the Status
block's `Current branch` when not `none`); and the description
rewritten to the evergreen shape (`templates/epic-body.md`), with
`## Goal` / `## Design spec` carried over and `## Scope` / `##
Success criteria` folded from the body's narrative — anything that
doesn't fold cleanly is preserved, never dropped, under an appended
`## Notes (pre-adoption)` section. Adoption is operator-invoked, per
node — a sub-epic is adopted by naming it directly; adopting a root
does NOT cascade to its sub-epics. If the machine-block write fails,
`--adopt` aborts before touching the body (see that command's Mode 4
failure sequencing) — the epic keeps parsing as legacy and
re-running `--adopt` is safe.

## Nested initiatives

An initiative is a **tree**, not a flat two-level list. Most are
shallow (one epic + leaf children), but a child that grows its own
multi-issue scope becomes a **sub-epic** with children of its own.
The model is recursive and uniform at every level:

- **Root epic** — an epic with no parent. It has the `epic` label
  and carries no `## Parent epic` section anywhere (machine block
  for evergreen, body for legacy).
- **Sub-epic** — an epic that is also a child. Same `epic` label,
  same epic body (`templates/epic-body.md` doubles as the sub-epic
  body), **plus** a `## Parent epic` section naming its immediate
  parent — in its machine-block comment for an evergreen sub-epic,
  in its body for a legacy one. It is simultaneously a parent (of
  its children) and a child (of its parent).
- **Leaf** — a feature/bug sub-issue, directly agent-workable. No
  `epic` label. Its own `## Parent epic` block always lives in its
  body (`templates/sub-issue-body.md`) — leaf bodies are agent
  prompts, not indexes, so they never grow a machine-block comment.

The single distinguishing signal — portable across backends — is
the `## Parent epic` section: a root omits it everywhere, every
non-root node includes it somewhere (machine block or body, per
shape). (`epic` label = "this node has children / is recursable";
`## Parent epic` present = "this node also has a parent".) Don't
rely on native tracker parent fields for this; not all backends
expose them on a plain read (see `backends/_interface.md`
`view_issue` + invariant 6).

### Each node is self-describing

Every epic node — root or sub-epic — carries its **own** child
membership only: derived live from native linkage plus its own
machine-block `## Phases` map (evergreen), or its own `## Children`
mirror (legacy) — either way, its **direct** children only. There
is no single body or comment that holds the whole tree.
`/resume-initiative` walks it top-down from a root, descending into
any child marked `▸ sub-epic` on its rendered tree line (a human
hint) — authoritatively, any child carrying the `epic` label — with
a built-in depth cap and visited-ref cycle guard so traversal
always terminates.

### Counting and "Next up" are local

A node's direct-child count and next-up are always scoped to its
own **direct** children — a sub-epic counts as one unit, closed
when the sub-epic node itself closes. Evergreen nodes derive both
live, on every read, from `list_child_issues` + the machine block's
`## Phases` map — nothing to keep in sync, so there is no "hop" at
all: closing a child, anywhere in the tree, writes nothing. Legacy
nodes still count via their own Status block's `- **Phase:** …
<closed>/<total>` line, maintained one hop at a time (see
"Maintenance" below) — a sub-epic's close is itself a child-close
from its parent's view, so the ritual runs once more, on the
grandparent. Either way, the true rolled-up leaf totals across a
subtree are computed by `/resume-initiative` at read time for
display; never hand-maintain a transitive count anywhere. A node's
next-up names its next direct child (derived, or the Status block's
`- **Next up:**` line for legacy); when that child is a sub-epic,
the command drills into it to surface the next workable *leaf*,
reporting the path (`root ▸ sub-epic ▸ leaf`).

### Promoting a leaf to a sub-epic

When a child outgrows leaf status (3+ independent sub-issues — the
triage gate, one level down):

1. Rewrite the child to the epic body shape (`templates/epic-body.md`)
   — the evergreen description (`## Goal`, `## Scope`, `## Success
   criteria`, `## Design spec`). Keep its existing ref and title.
2. Post its machine-block comment with a `## Parent epic` section
   pointing at its parent (`upsert_comment`) — see "Machine-block
   comment" above.
3. Add the `epic` label to it (`add_label`). It is now a recursable
   node — this label alone is what `/resume-initiative` uses to
   recurse into it; there is nothing to mark on the parent's side.
4. If the parent is phased, append this new sub-epic's ref to the
   parent's machine-block `## Phases` map via `upsert_comment`
   (legacy parent: append to its `## Children` mirror, marked
   `▸ sub-epic`).
5. File its sub-issues as children of it (`create_issue` +
   `link_sub_issue` with the sub-epic as `parent_ref`), appending
   each to the sub-epic's own machine-block `## Phases` map when
   phased.

### Depth and backend ceilings

Nesting depth is bounded by `/resume-initiative`'s recursion cap
(not a config setting) and by each backend's native-linkage
ceiling. GitHub sub-issues nest arbitrarily; Jira's standard
hierarchy spans three levels (Epic → Story/Task → Sub-task), so
on Jira interior nodes map to Story/Task and only leaves map to
Sub-task — and any nesting past the native cap is carried by the
machine-block `## Phases` map alone (legacy: the `## Children` body
mirror alone).

**The skill enforces the type convention — the tracker does not.**
On Jira the create/parent path is enforcement-soft: the MCP
silently accepts a Sub-task parented directly under an Epic (the
Epic → Sub-task level-skip is not bounced — see `backends/jira.md`
invariant 6). So a **direct leaf of the root Epic is a Story** (or
Task), **never a Sub-task**; a Sub-task is legal only under a
Story/Task interior node (Jira hierarchyLevel 0 — e.g. a sub-epic
mapped to a Story), never directly under an Epic. Do not assume a
malformed Sub-task-under-Epic `create_issue` will be rejected — the
skill must place the correct issue type itself. See
`backends/_interface.md` invariant 6 and the per-backend modules.

## Filing the epic

Invoke the configured backend's `create_issue` operation. Pass:

- `type`: `epic`
- `title`: `epic: <one-line initiative name>` — the literal
  `epic:` prefix makes it visually distinct from single issues
  in the tracker's issue-list view.
- `labels`: `[epic, <area>]` where `<area>` is one of your
  configured `areas:` enum from `.claude/issue-tracker.yaml`.
- `body`: the filled-in `templates/epic-body.md` template — the
  evergreen shape (`## Goal`, `## Scope`, `## Success criteria`,
  `## Design spec`). See "Epic body template" below.

See `backends/<backend>.md` for the literal invocation.

If the initiative's phases or (for a sub-epic) its parent are
already known at file time, post the machine-block comment in the
same flow: `upsert_comment({ref, marker:
"<!-- agent-issue-tracker:machine-block -->", body})` with a
`## Phases` and/or `## Parent epic` section filled in — see
"Machine-block comment" below. When neither is known yet (a flat
root epic), post no comment at all; the epic carries zero machine
cruft until there is something non-derivable to say. This write is
best-effort — WARN and continue on failure; the epic is still
validly filed with just the description.

## Epic body template

The body is **evergreen** — `## Goal`, `## Scope` (in/out), `##
Success criteria`, `## Design spec` — and nothing else. See
`templates/epic-body.md` for the canonical skeleton with
placeholders. Edit it only when the initiative's goal or scope
genuinely changes; never per child, and never to record phase or
child-count state (`## Success criteria` is outcome-based and
verifiable by an outside reader, never a `<closed>/<total>` count —
those are derived, and they change).

Everything non-derivable that used to live in the body — phases,
the sub-epic parent pointer, the current-branch signal, the scope
probe, the decision log — moves to the machine-block comment; see
"Machine-block comment" below. Child set, per-child status, and
next-up are never written anywhere; `/resume-initiative` derives
them live from the tracker's native linkage.

## Machine-block comment

Non-derivable structure — phases, a sub-epic's parent pointer, the
current-branch signal, the scope probe, and the decision log — lives
in ONE comment on the epic issue carrying the literal sentinel
`<!-- agent-issue-tracker:machine-block -->`. See
`templates/epic-machine-block.md` for the canonical skeleton and
`backends/_interface.md` "Machine-block comment convention" for the
contract-level rules. Write it ONLY via the backend's
`upsert_comment` operation (destructive whole-comment replace —
read-modify-write: `read_comments` first, modify in memory, write
back the whole thing).

The five canonical section headings — OMIT any that would be empty,
and OMIT the comment entirely when every section would be empty:

| Heading | Contents |
|---|---|
| `## Phases` | phase name + ordered child **refs** only — no titles, no status |
| `## Parent epic` | sub-epics only — immediate parent ref + one-line title |
| `## Current branch` | branch name — the in-progress fallback signal |
| `## Scope probe` | prose line + first fenced code block = the probe command |
| `## Decision log` | append-only, dated entries |

**Trust rule.** Readers select the **earliest marker-carrying
comment from a trusted author** (`read_comments`'s `author_trust` —
GitHub: `authorAssociation` ∈ {OWNER, MEMBER, COLLABORATOR}; Jira:
true by default, org-internal instances). A marker comment from an
untrusted author is ignored with a one-line WARN naming it.
Earliest-wins means a block legitimately created at file/adopt time
can never be shadowed by a later attacker comment — the author
check covers the window before any block exists.

**Legacy epics** (body still carries a `## Status block` heading) do
not use the machine block at all — their non-derivable structure
stays in the body. See "Legacy epics" below.

## Legacy epics (Status block shape)

Pre-evergreen epics — filed before this skill existed, or by hand —
keep the older shape indefinitely: a body `## Status block` heading
plus a `## Children` task-list mirror, instead of an evergreen
description and machine-block comment. No forced migration;
`/resume-initiative` keeps resuming them correctly via its legacy
reader (see `commands/resume-initiative.md` "Two epic shapes"). New
epics filed by this skill are always evergreen — see "Filing the
epic" above. Convert an existing legacy epic in place with
`/resume-initiative <ref> --adopt` — see "Adopting an existing epic
into the template" above. If you choose not to adopt, a legacy
epic's Status block and `## Children` mirror can still be
hand-updated per the field spec below; adoption removes that ritual
entirely (see "Maintenance" below, which documents the evergreen
model).

### Status block — exact field spec

`/resume-initiative` matches each line on its **bold field label**
(`**Phase:**`, `**Next up:**`, `**Current branch:**`, `**Last
updated:**`) and is tolerant of the leading list-bullet character
(`-`/`*`/`+`) that precedes it — the Atlassian Remote MCP rewrites a
leading `-` bullet to `*` on the markdown→ADF round-trip, so a
strictly-literal `- ` match would break on Jira after the first edit
(see `backends/jira.md` invariant 1).

| Line prefix | Format | Example | Required |
|---|---|---|---|
| `- **Phase:**` | `<phase-name> · <int>/<int> sub-issues closed` | `Phase 1 · 2/4 sub-issues closed` | yes |
| `- **Next up:**` | `<ref> — <title>` or literal `none` | `#42 — worker/queue retry-policy refactor` | yes |
| `- **Current branch:**` | branch name or literal `none` | `feat/worker-queue-retry` | yes |
| `- **Last updated:**` | `YYYY-MM-DD` | `2026-05-27` | yes |

The `<ref>` value accepts both `#N` (GitHub) and `PROJ-123` (Jira)
ref syntaxes. `/resume-initiative` parses both; the backend module
renders the syntax.

**Every legacy epic node carries its own Status block** — a
sub-epic has the exact same four prefixes as a root. The
`<closed>/<total>` count is always **direct children only** (a
sub-epic counts as one unit in its parent's count); rolled-up
subtree totals are a read-time view computed by
`/resume-initiative`, never written into a body. See "Nested
initiatives".

## Scope probe — optional ground-truth hook

For enumerate-the-work initiatives (a test migration, a lint sweep —
epics whose children mirror a countable artifact set), the enumerated
batch drifts as the codebase moves: files land after the list was
frozen. An epic node MAY declare a `## Scope probe` section — in its
machine-block comment (evergreen; see `templates/epic-machine-block.md`)
or its body (legacy) — so `/resume-initiative` can diff enumerated
scope against ground truth on every resume (see that command's
"Drift reconciliation (per node)").

Exact block spec:

- Heading: `## Scope probe`. Evergreen epics: inside the
  machine-block comment (by convention after `## Phases`). Legacy
  epics: anywhere in the epic body (by convention after `##
  Children`).
- The **first fenced code block** under the heading holds a shell
  command; the language tag is advisory. Prose around the fence is
  ignored by the runner (use it to say what the probe enumerates).
- The command runs from the **consumer repo root** (the resuming
  session's CWD), under the session's normal tool permissions, and is
  shown to the operator before it runs.
- stdout is the ground-truth work set, **one item per line**; blank
  lines ignored. Non-zero exit → `/resume-initiative` soft-warns and
  skips the diff.
- Scope: the declaring node's own subtree. A sub-epic may declare its
  own probe.
- Omit the section entirely when the initiative has no countable ground
  truth — behaviour is then exactly as before (the probe is opt-in;
  membership reconciliation runs regardless).

**Trust model:** for a legacy epic, the probe is operator-authored
shell embedded in the issue body — anyone who can edit the body can
put a command there. For an evergreen epic, the probe lives in the
machine-block comment instead, so the "Machine-block comment" trust
rule above applies FIRST: only the earliest marker-carrying comment
from a trusted author (`read_comments`'s `author_trust`) is honoured
at all, which closes off the wider exposure of comment space (anyone
can comment on a public GitHub issue, unlike the body, which only
the author/maintainers can edit). Either way, only declare/run
probes on epics whose authorship — body edit or trusted comment —
you trust; the harness's own permission layer still gates execution,
and the probe command is always shown to the operator before it runs
as the last line of defense.

### Worked example

The iOS Swift-Testing migration epic that motivated the feature — the
batch was frozen at 9 files while the directory grew to 13. Posted
inside the machine-block comment (see `templates/epic-machine-block.md`
for the full skeleton):

````markdown
## Scope probe
Lists the in-scope XCTest files still to migrate or already migrated.
```sh
git ls-files 'MyAppTests/**/*Tests.swift'
```
````

On resume, the four files that landed after the freeze surface as
`present but unenumerated`, and `/resume-initiative` offers a
`followup-tracking` filing for each (`Why deferred: drift`, parent =
this epic). Items matched by a live child title (or, legacy nodes
only, a `## Children` mirror line) count as enumerated.

### What resume reconciles even without a probe

Evergreen nodes have no separate reconciliation pass to run — the
union derivation in `/resume-initiative`'s "Deriving child state"
(native `list_child_issues` ∪ the machine block's `## Phases` map)
already produces `unlinked` (live, phase-mapped, not natively
linked) and dead-phase-map-ref findings as a side effect of
computing membership. Legacy nodes still run an explicit
mirror-vs-native diff, unchanged from before this shape existed:
`/resume-initiative` always diffs each node's `## Children` mirror
against the backend's `list_child_issues` — the tracker's native
linkage is authoritative for *membership*, the mirror is the
traversal index. Either way, drift is **reported, never
auto-repaired** — resume stays read-only; the repair path is
`link_sub_issue` / editing the machine block's `## Phases` section
directly (evergreen) or this skill's adoption procedure (legacy). A
live phase-map or mirror entry without a native link is NOT drift by
itself (invariant 6: native linkage is best-effort — cross-repo
children and children past a backend's ceiling legitimately live in
the phase map / mirror alone). See `commands/resume-initiative.md`
"Drift reconciliation (per node)" for the full report shape.

## Creating sub-issues

Each leaf sub-issue body uses the standard `feature-request` or
`bug-tracking` agent-prompt template (Goal / Locus / Skills to
load / What's missing OR Symptom / Sketch / Constraints /
Acceptance / Verify) plus a `## Parent epic` block. The skill's
contract is: **the body of every leaf child is agent-runnable** —
any future agent that picks up the child can do so cold. (A sub-epic
child is the exception — it is an index, not a leaf prompt; it uses
the epic body shape. See "Nested initiatives".)

Use `templates/sub-issue-body.md` as the composition guide. It
points at `templates/feature-body.md`, `templates/bug-body.md`, or
(for a sub-epic) `templates/epic-body.md` based on the sub-issue's
shape, and documents the `## Parent epic` block to append.

Conventions specific to children of an epic:

- **Title prefix:** `<phase-name>: <capability>` so the tracker's
  issue-list view shows phase membership without needing the epic
  body. Example: `Phase 1: backend interface contract + GitHub
  backend`.
- **`## Parent epic` block** — required for a **leaf** child; cites
  the **immediate** parent's ref and one-line title (which may be a
  sub-epic, not the root — see "Nested initiatives"). A **sub-epic**
  child omits this body block entirely — its parent pointer lives in
  its own machine-block comment instead (`upsert_comment`; see
  "Machine-block comment" above and `templates/sub-issue-body.md`).
- **Labels:** the type-shape label (`bug` for defects,
  `enhancement` for new capabilities) plus the same area label(s)
  as the work touches, plus the same triage label conventions
  (`needs-design` if the sub-issue has open design questions,
  etc.). Do NOT label a **leaf** child with `epic`. The one
  exception is a **sub-epic** child: it carries `epic` precisely
  because it is itself a recursable index — that label is what
  `/resume-initiative` keys on to descend into it.

### Linking children to the epic

After creating the child, invoke the configured backend's
`link_sub_issue` operation to attach the child as a native
sub-issue of the epic. The skill does not parse refs — pass the
child ref and the epic ref to the backend; the backend module
handles the per-tracker mechanism (GitHub's typed-int sub-issue
API, Jira's `parent` field or Epic Link customfield depending on
`jira.parent_link_style`). See `backends/<backend>.md` for the
literal invocation.

### Child membership — derived, not mirrored

Child membership has ONE authoritative action: invoking
`link_sub_issue` (above) to attach the child as a native sub-issue
of the epic. There is no body or comment mirror to additionally
maintain — **`/resume-initiative` derives the child set and status
from native linkage (`list_child_issues` is load-bearing); the
machine-block comment holds only non-derivable structure.**

If the epic is phased, additionally append the new child's ref to
the machine-block comment's `## Phases` map via `upsert_comment` —
this records which phase the child belongs to (a native-linkage-only
child would otherwise render `unphased`, which is
correct-but-uninformative for a phased epic). A flat (unphased) epic
skips this — nothing to append to. This write is best-effort: WARN
and continue on failure; the child is still validly linked via
`link_sub_issue` either way.

Past a backend's native-linkage ceiling (invariant 6 — e.g. Jira's
three-level cap), `link_sub_issue` cannot reach; the child then
lives in the phase map alone and renders `unlinked` on resume — a
remediation pointer (`link_sub_issue` where the backend allows), not
an error.

In a nested initiative, each epic node's own machine-block `##
Phases` map lists only its **direct** children (in ref form — no
titles, no status; see `templates/epic-machine-block.md`); the full
tree is the union of native linkage across every node, recursively.
A child that is itself a sub-epic is recognised by its `epic` label
(authoritative — not by any marker in the parent's phase map).

**Legacy parents** keep the older `## Children` task-list mirror
instead: append a new child as an unchecked task-list item when
filed, flip the checkbox and append `— closed YYYY-MM-DD` when it
closes (see "Maintenance" below for the read-modify-write
mechanics). Each node owns a mirror listing only its own direct
children; a child that is itself a sub-epic gets a trailing `▸
sub-epic` marker on its line (authoritative signal regardless: the
child's `epic` label).

Per-backend native linkage mechanics — GitHub's native sub-issue
API, Jira's `parent` field or Epic Link customfield — are
documented in `backends/<backend>.md`. The skill does not encode
them.

**Optional board mirror.** If the consumer configures `github.project` (GitHub
backend only), also add each newly filed/linked child to the GitHub Projects (v2)
board and set its Status to `Todo` — root epic, sub-epics, and leaves, including
cross-repo `owner/repo#N` children. This is a human-facing **view**, orthogonal
to the tracker's native linkage. Best-effort — a board failure WARNs and never
blocks the file/link. See the `## GitHub Projects board (optional)` section below
(and its detailed reference
`skills/initiative-tracking/references/github-projects-board.md`) plus
`backends/github.md` for the literal `gh project` calls. With `github.project`
unset, skip this.

## Maintenance

**Child close writes nothing.** Under the evergreen model, closing a
child touches no epic anywhere — not the description, not the
machine-block comment. `/resume-initiative` derives membership,
per-child status, counts, and next-up live from `list_child_issues`
+ `view_issue` on every read, so the next resume already reflects
the close. This supersedes the old close-side body-reconcile-on-read
follow-up (#87) entirely — there is no close-side write left to
automate.

The writes that remain are all evergreen-comment or evergreen-body
edits, made when something genuinely non-derivable changes, and all
best-effort (WARN and continue on failure, never block the run):

- **Goal or scope changes** — `edit_body` on the description
  (read-modify-write, cross-backend invariant 2). The one remaining
  description write; still never per child.
- **A non-trivial decision** — append a dated entry to the
  machine-block comment's `## Decision log` via `upsert_comment`
  (read the current comment, append in memory, write back the whole
  comment — same invariant, applied to comments).
- **Work starts on a child** — set the machine-block comment's
  `## Current branch` section via `upsert_comment` (see
  "In-progress status" below).
- **Board sync** — if `github.project` is set (GitHub backend), set
  the closed child's board item Status to `Done` (best-effort —
  WARN and continue on failure). The board is a human-facing view,
  orthogonal to the (now fully derived) child state — see "GitHub
  Projects board (optional)" below and
  `skills/initiative-tracking/references/github-projects-board.md`.

**Legacy epics** (body still carries a `## Status block`) keep the
older one-hop ritual: closing a direct child updates only its
immediate parent's Status block (`Phase` count, `Next up`, `Last
updated`) and flips that parent's `## Children` mirror entry, via
`edit_body` read-modify-write — never a multi-body fan-out, and
never walking the ancestor chain re-rolling totals
(`/resume-initiative` computes rolled-up subtree progress at read
time regardless of shape). A sub-epic's last direct child closing
makes the sub-epic itself eligible to close (see "Epic lifecycle");
closing it is then a child-close from *its* parent's perspective, so
the ritual runs once more, on the grandparent. Adopting the epic
(`/resume-initiative --adopt`) removes this ritual entirely by
converting it to the evergreen shape above.

**How to edit the epic body safely.** Whole-body edits are
destructive — the configured backend's `edit_body` operation
replaces the entire description in one call (cross-backend
invariant 2 from `backends/_interface.md`). There is no
append-only API on either supported backend. The skill is
responsible for the read-modify-write cycle: invoke `view_issue`
first, modify only what changed in memory, then invoke `edit_body`
with the full new body. The same cycle applies to `upsert_comment`
(invariant 2 extends to comments): `read_comments` first, modify the
machine-block comment in memory, write back the whole comment.

```text
view_issue(epic-ref)  →  body
  modify body in memory  →
edit_body(epic-ref, new_body)
```

The backend module documents the literal calls — see
`backends/<backend>.md`. Both supported backends today (GitHub
via `gh issue view` + `gh issue edit --body-file`; Jira via the
Atlassian MCP's `getJiraIssue` + `editJiraIssue` with
markdown→ADF translation handled by the MCP) satisfy the
destructive-edit invariant.

## In-progress status (optional affordances)

"This issue is being worked" has no cross-backend primitive —
`close_issue` is the contract's only state-change operation. The
in-progress signal is therefore a per-backend **optional
affordance** (see `backends/_interface.md` "Optional
backend-specific capabilities"), set by a driver when work starts
(`/work-issue` Step 3 today; `/resume-initiative --start` via
follow-up #88):

- **GitHub** — `github.project` configured → set the child's
  board item Status to `In Progress` (see `backends/github.md`).
- **Jira** — `jira.in_progress_transition` configured → fire that
  workflow transition (see `backends/jira.md` "In-progress
  transition (optional)").
- **Neither configured** — the fallback signal is the parent
  epic's `## Current branch` section, set via `upsert_comment` on
  the machine-block comment (evergreen parents) or the Status
  block's `- **Current branch:**` line via `edit_body` (legacy
  parents — today's path, unchanged); a parentless issue gets no
  marker. No-op, run proceeds.

Every such write is best-effort: a failure WARNs and never blocks
the run, the worktree, or the file operation. Start-side writes
touch ONLY the current-branch signal: the machine-block `## Current
branch` section for evergreen parents; the Status block's `Current
branch` + `Last updated` lines for legacy parents, as today — never
`## Phases`, `## Decision log`, or (legacy) `Phase` / `Next up` /
the `## Children` mirror — those are Maintenance, above (evergreen:
derived on close, no write at all; legacy: the one-hop ritual).

## GitHub Projects board (optional)

Only relevant when the consumer's `.claude/issue-tracker.yaml` sets
`github.project` (GitHub backend only). When it does, mirror the initiative tree
onto that GitHub Projects (v2) board as a **human-facing view** — the tracker's
native linkage (derived live by `/resume-initiative`; legacy epics: the
`## Children` task-list mirror) stays the source of truth, and every board write
is best-effort (a failure WARNs and never blocks the issue operation). With
`github.project` unset, skip it entirely; behaviour is unchanged.

The three-state lifecycle (`Todo` on file/link, `In Progress` when a driver
starts work — `/resume-initiative --start` or `/work-issue` — `Done` on close)
and the backfill procedure for an existing tree are documented in
`skills/initiative-tracking/references/github-projects-board.md`. The literal
`gh project` calls live in `backends/github.md` "GitHub Projects v2 board
(optional)". Load the reference only when `github.project` is set.

## Epic lifecycle

The lifecycle is the same for a root epic and a sub-epic — a
sub-epic is just an epic that also has a parent.

| State | Meaning | Action |
|---|---|---|
| Open + has open children | initiative in progress | `/resume-initiative <ref>` works |
| Open + all children closed | ready to declare done | operator invokes `close_issue` with `reason: completed` plus a one-paragraph wrap-up comment |
| Sub-epic + all children closed | sub-initiative done | close it like any epic; its close is then a child-close from its parent's view — evergreen: nothing further to do, derived on next resume; legacy: run the one-hop Maintenance ritual once on the parent |
| Closed | initiative shipped | preserved as history; design spec link still valid |
| Closed + reason `not_planned` | abandoned | comment explains why; surviving children get triaged separately via `bug-tracking` / `feature-request` / `followup-tracking` |

## Session titles

Sessions in a configured project are auto-titled at start/resume by the
plugin's SessionStart hook (`<ref> <slug> · <what it was doing> · idle Nd`).
Hooks cannot retitle a running session — so when the working focus shifts to
a different issue/epic mid-session, or the issue being driven completes,
offer the operator a paste-ready rename line, e.g.:

    /rename #42 board-support — done

Agents cannot run `/rename`; only the operator can paste it. Offer once per
focus shift, not on every message. If the operator manually renames a
session, the hook never overwrites their name.

## Returning the epic ref

When the skill is invoked as part of a brainstorm →
writing-plans → implementation flow, return the new epic ref to
the operator as the final action:

> "Epic created: `<ref>`. Resume any time with
> `/resume-initiative <ref>`."

The ref syntax depends on the configured backend — `#N` on
GitHub, `PROJ-123` on Jira. The backend module renders the
syntax; the skill names the intent.

---

See also: `skills/feature-request/` (capability-shaped sibling),
`skills/bug-tracking/` (defect-shaped sibling),
`skills/followup-tracking/` (scope-deferred sibling — when a
followup compounds into multiple PRs, supersede it with an epic).
