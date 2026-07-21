---
name: initiative-tracking
description: >-
  How multi-week, multi-issue initiatives ("epics") are tracked —
  they live as a single issue in the configured tracker (see
  `.claude/issue-tracker.yaml`) labelled `epic`, with sub-issues
  for each phase or sub-task. The epic body holds a
  machine-readable Status block that the `/resume-initiative`
  slash command parses on session start. Issues here, like in the
  sibling tracker skills, are consumed by Claude Code agents — the
  epic body is an **agent-readable index** of the initiative, and
  each sub-issue's body is an agent prompt that satisfies the
  same locus / scope / acceptance requirements as a
  feature-request or bug. Use this skill whenever scope is
  genuinely multi-week and spans more than one PR — kicking off a
  new initiative, filing the sub-issues for an existing one,
  updating the Status block after a child closes, or reorganising
  phases. The siblings bug-tracking, feature-request, and
  followup-tracking cover single-issue shapes; this one covers
  the *index* over many issues. Initiatives may nest more than one
  level — a child of an epic can itself be an epic (a "sub-epic")
  with its own children — and `/resume-initiative` walks the whole
  tree; see "Nested initiatives". An epic may declare an optional
  `## Scope probe` (an operator-authored ground-truth command) that
  `/resume-initiative` diffs against enumerated scope on resume,
  surfacing drift — see "Scope probe".
---

# Initiative Tracking — Multi-Week Effort as Epic + Sub-Issues

The canonical tracker is the one configured in the consumer
project's `.claude/issue-tracker.yaml`. The plugin's
`backends/_interface.md` documents the eight operations every
backend implements; `backends/<backend>.md` (e.g.
`backends/github.md`) documents the literal CLI / MCP invocation
for each operation.

An initiative is not a different *tracker* — it is a different
*shape of tracked work*: one epic issue indexes many child issues,
all under the same label convention, with a Status block the
operator-facing `/resume-initiative` command can parse without a
human.

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
picking up work tomorrow has no idea which child is next. The
Status block + sub-issue linkage solves both: one query gives
`/resume-initiative` everything it needs.

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

Sometimes the epic already exists in the tracker but is NOT in
this template's shape — it was filed by hand, by another tool, or
before this skill existed, so it has no `## Status block` and no
`## Children` mirror (or a stale one). "Make this epic follow the
template" is an *adoption*, not a fresh file.

**The load-bearing rule: never infer the child set from the epic
body's prose — query the tracker.** The body is the exact artifact
you are about to rewrite, so it is the least trustworthy source for
"what are this epic's children?" A line like "child tickets to be
filed when prioritized" can be months stale while children already
exist (some closed, some in review). Trusting it silently produces
an empty `## Children` mirror and a wrong `Next up`. Always call the
backend's `list_child_issues(epic_ref)` operation (see
`backends/_interface.md`) and build from what the tracker actually
returns.

Procedure:

1. `list_child_issues(epic_ref)` → the epic's real **direct**
   children (open AND closed). This is the source of truth for the
   mirror, not the body.
2. Build the `## Children` mirror from that list: each closed child
   → `[x] <ref> — <title> (Phase N) — closed YYYY-MM-DD`, each open
   child → `[ ] <ref> — <title> (Phase N)`. Group children into
   `## Phases` using the sequencing the existing body / design spec
   already describes; if none is stated, ask the operator rather
   than inventing phases.
3. Fill the `## Status block` from the real data — `Phase`
   direct-child `<closed>/<total>` count, `Next up` = first open
   child by phase order (or `none`), `Current branch`, and
   `Last updated` = today.
4. **Preserve, don't destroy.** Fold the existing body's narrative
   into `## Goal` / `## Design spec`, and keep any per-item detail
   the children don't already carry as an appendix below the
   template sections. `edit_body` is a destructive whole-body
   replace (cross-backend invariant 2) — read-modify-write so
   nothing load-bearing is lost.
5. For a nested initiative, recurse: call `list_child_issues` once
   per epic node (root, then each sub-epic) to build that node's
   own direct-children mirror.

**Reconcile, tracker wins.** If a pre-existing `## Children` mirror
disagrees with `list_child_issues`, the tracker's native linkage is
authoritative — add children it returns that the mirror is missing.
Before dropping a mirror-only entry (in the body but not returned),
check it isn't a cross-repo `owner/repo#N` child or one whose native
link was never established; if so, fix the link (`link_sub_issue`)
rather than deleting the line.

## Nested initiatives

An initiative is a **tree**, not a flat two-level list. Most are
shallow (one epic + leaf children), but a child that grows its own
multi-issue scope becomes a **sub-epic** with children of its own.
The model is recursive and uniform at every level:

- **Root epic** — an epic with no parent. It has the `epic` label
  and an epic body, and its body has **no** `## Parent epic` block.
- **Sub-epic** — an epic that is also a child. Same `epic` label,
  same epic body (`templates/epic-body.md` doubles as the sub-epic
  body), **plus** a `## Parent epic` block naming its immediate
  parent. It is simultaneously a parent (of its children) and a
  child (of its parent).
- **Leaf** — a feature/bug sub-issue, directly agent-workable. No
  `epic` label.

The single distinguishing signal — portable across backends — is
the `## Parent epic` block: a root omits it, every non-root node
includes it. (`epic` label = "this node has children / is
recursable"; `## Parent epic` present = "this node also has a
parent".) Don't rely on native tracker parent fields for this; not
all backends expose them on a plain read (see
`backends/_interface.md` `view_issue` + invariant 6).

### Each node is self-describing

Every epic node — root or sub-epic — carries its **own** Status
block and its **own** `## Children` mirror listing only its
**direct** children. The full tree is the recursion over each
node's mirror; there is no single body that holds the whole tree.
`/resume-initiative` walks it top-down from a root, descending into
any child marked `▸ sub-epic` (authoritatively: any child carrying
the `epic` label), with a built-in depth cap and visited-ref cycle
guard so traversal always terminates.

### Counting and "Next up" are local

A node's `- **Phase:** … <closed>/<total>` counts its **direct
children only** — a sub-epic counts as one unit, closed when the
sub-epic node itself closes. This keeps maintenance one-hop (see
"Maintenance"). The true rolled-up leaf totals across a subtree are
computed by `/resume-initiative` at read time for display; never
hand-maintain a transitive count in a body. A node's
`- **Next up:**` names its next direct child; when that child is a
sub-epic, the command drills into it to surface the next workable
*leaf*, reporting the path (`root ▸ sub-epic ▸ leaf`).

### Promoting a leaf to a sub-epic

When a child outgrows leaf status (3+ independent sub-issues — the
triage gate, one level down):

1. Edit the child to the epic body shape (`templates/epic-body.md`)
   — add a Status block, a `## Children` mirror, and a
   `## Parent epic` block pointing at its parent. Keep its existing
   ref and title.
2. Add the `epic` label to it (`add_label`). It is now a recursable
   node.
3. In the **parent's** `## Children` mirror, mark this child's line
   `▸ sub-epic`.
4. File its sub-issues as children of it (`create_issue` +
   `link_sub_issue` with the sub-epic as `parent_ref`), and list
   them in the sub-epic's own `## Children` mirror.

### Depth and backend ceilings

Nesting depth is bounded by `/resume-initiative`'s recursion cap
(not a config setting) and by each backend's native-linkage
ceiling. GitHub sub-issues nest arbitrarily; Jira's standard
hierarchy spans three levels (Epic → Story/Task → Sub-task), so
on Jira interior nodes map to Story/Task and only leaves map to
Sub-task — and any nesting past the native cap is carried by the
`## Children` body mirror alone.

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
- `body`: the filled-in `templates/epic-body.md` template.

See `backends/<backend>.md` for the literal invocation.

## Epic body template

The body is divided into a human-readable preamble and a
machine-readable Status block. See `templates/epic-body.md` for
the canonical skeleton with placeholders.

The Status block fields are CANONICAL. `/resume-initiative` matches
each line on its **bold field label** (`**Phase:**`, `**Next up:**`,
`**Current branch:**`, `**Last updated:**`) and is tolerant of the
leading list-bullet character (`-`/`*`/`+`) that precedes it — the
Atlassian Remote MCP rewrites a leading `-` bullet to `*` on the
markdown→ADF round-trip, so a strictly-literal `- ` match would
break on Jira after the first edit (see `backends/jira.md`
invariant 1). Write them in the canonical `- **Label:**` form; change
the labels themselves only if you update `/resume-initiative` in the
same PR.

## Status block — exact field spec

These are the canonical strings to **write**. `/resume-initiative`
matches each line on its **bold field label** and tolerates the
leading list-bullet character (`-`/`*`/`+`), so it is the labels and
value formats below that must not be paraphrased — the bullet glyph
itself is not load-bearing on read (Jira's ADF round-trip flips a
leading `-` to `*`).

| Line prefix | Format | Example | Required |
|---|---|---|---|
| `- **Phase:**` | `<phase-name> · <int>/<int> sub-issues closed` | `Phase 1 · 2/4 sub-issues closed` | yes |
| `- **Next up:**` | `<ref> — <title>` or literal `none` | `#42 — worker/queue retry-policy refactor` | yes |
| `- **Current branch:**` | branch name or literal `none` | `feat/worker-queue-retry` | yes |
| `- **Last updated:**` | `YYYY-MM-DD` | `2026-05-27` | yes |

The `<ref>` value accepts both `#N` (GitHub) and `PROJ-123` (Jira)
ref syntaxes. `/resume-initiative` parses both; the backend module
renders the syntax. If `/resume-initiative` can't parse a field,
it reports which one is missing and asks the operator to update
the epic body. The skill is responsible for keeping the Status
block accurate after every sub-issue closes — see "Maintenance"
below.

**Every epic node carries its own Status block** — a sub-epic has
the exact same four prefixes as a root. The `<closed>/<total>`
count is always **direct children only** (a sub-epic counts as one
unit in its parent's count); rolled-up subtree totals are a
read-time view computed by `/resume-initiative`, never written into
a body. See "Nested initiatives".

### Worked example

A real Status block from an in-flight initiative — the
worker/queue redesign tracked as a 4-phase epic:

```markdown
## Status block
- **Phase:** Phase 2 · 1/3 sub-issues closed
- **Next up:** #43 — worker/queue: extract retry-policy into table
- **Current branch:** feat/worker-queue-retry-policy
- **Last updated:** 2026-05-27
```

After `#43` closes, the maintenance read-modify-write cycle
updates `Phase` to `Phase 2 · 2/3 sub-issues closed`, recomputes
`Next up` to the next open child, bumps `Last updated`, and flips
the `## Children` task-list entry for `#43` to
`[x] #43 — ... — closed 2026-05-27`.

## Scope probe — optional ground-truth hook

For enumerate-the-work initiatives (a test migration, a lint sweep —
epics whose children mirror a countable artifact set), the enumerated
batch drifts as the codebase moves: files land after the list was
frozen. An epic node MAY declare a `## Scope probe` section so
`/resume-initiative` can diff enumerated scope against ground truth on
every resume (see that command's "Drift reconciliation (per node)").

Exact block spec:

- Heading: `## Scope probe`, anywhere in the epic body (by convention
  after `## Children`).
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
  mirror-vs-linkage reconciliation runs regardless).

**Trust model:** the probe is operator-authored shell embedded in an
issue body — anyone who can edit the body can put a command there. Only
declare/run probes on epics whose authorship you trust; the harness's
own permission layer still gates execution.

### Worked example

The iOS Swift-Testing migration epic that motivated the feature — the
batch was frozen at 9 files while the directory grew to 13:

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
this epic). Items matched by a `## Children` mirror line or a live
child title (literal case-sensitive substring) count as enumerated.

### What resume reconciles even without a probe

`/resume-initiative` always diffs each node's `## Children` mirror
against the backend's `list_child_issues` — the same invariant the
adoption procedure enforces ("Reconcile, tracker wins"): the mirror is
the canonical traversal index, but the tracker's native linkage is
authoritative for *membership*. Drift (an unmirrored native child, a
dead mirror entry) is **reported, never auto-repaired** — resume stays
read-only; the repair path is this skill's adoption procedure. A live
mirror entry without a native link is NOT drift (invariant 6: native
linkage is best-effort — cross-repo children and children past a
backend's ceiling live in the mirror alone).

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
- **`## Parent epic` block** — required; cites the **immediate**
  parent's ref and one-line title (which may be a sub-epic, not the
  root — see "Nested initiatives").
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

### Children task-list mirror — the cross-backend index

**Always** maintain the `## Children` task-list mirror in the
epic body — it is what `/resume-initiative` parses (cross-backend
invariant). Additionally invoke `link_sub_issue` (above) to
establish native parent-child linkage in the tracker — this is
what makes the tracker's UI show the relationship, but
`/resume-initiative` does not depend on it.

When a child is filed, append it to the epic body's `## Children`
section as an unchecked task-list item. When it closes, flip the
checkbox and append `— closed YYYY-MM-DD`. See "Maintenance"
below for the read-modify-write mechanics.

In a nested initiative, each epic node owns a `## Children` mirror
listing **only its own direct children**; the full tree is the
recursion over every node's mirror. A child that is itself a
sub-epic gets a trailing `▸ sub-epic` marker on its line so
`/resume-initiative` knows to recurse into it (authoritative signal:
the child's `epic` label). The line grammar is otherwise unchanged.

Per-backend native linkage mechanics — GitHub's native sub-issue
API, Jira's `parent` field or Epic Link customfield — are
documented in `backends/<backend>.md`. The skill does not encode
them.

**Optional board mirror.** If the consumer configures `github.project` (GitHub
backend only), also add each newly filed/linked child to the GitHub Projects (v2)
board and set its Status to `Todo` — root epic, sub-epics, and leaves, including
cross-repo `owner/repo#N` children. This is a human-facing **view**; the
`## Children` mirror stays canonical. Best-effort — a board failure WARNs and never
blocks the file/link. See the `## GitHub Projects board (optional)` section below
(and its detailed reference
`skills/initiative-tracking/references/github-projects-board.md`) plus
`backends/github.md` for the literal `gh project` calls. With `github.project`
unset, skip this.

## Maintenance

Whenever a child closes, update **only its immediate parent's**
body (the node whose `## Children` mirror lists it):

1. Increment that parent's `Phase` line `<closed>/<total>` count.
2. Recompute that parent's `Next up` — first open direct child by
   phase order, or `none` if all its direct children are closed.
3. Bump `Last updated` to today.
4. Flip the parent's `## Children` task-list mirror entry to
   `[x] <ref> — <title> — closed YYYY-MM-DD`.
5. Append to `Decision log` if a non-trivial decision was made
   during the child's PR.
6. If `github.project` is set (GitHub backend), set the closed child's board item
   Status to `Done` (best-effort — WARN and continue on failure). See "GitHub
   Projects board (optional)" below and its reference
   `skills/initiative-tracking/references/github-projects-board.md`.

**One-hop, not whole-chain.** Because each node counts only its
direct children, closing a leaf touches exactly one body — the
parent's. Do **not** walk up the ancestor chain re-rolling totals;
`/resume-initiative` computes rolled-up subtree progress on read.
The chain advances one hop at a time *only* through closes: when a
sub-epic's last direct child closes, the sub-epic itself becomes
eligible to close (see "Epic lifecycle"); closing the sub-epic is a
child-close from *its* parent's perspective, so you then run these
same five steps once on the grandparent. Each step is a single
node's read-modify-write — never a multi-body fan-out.

**How to edit the epic body safely.** Whole-body edits are
destructive — the configured backend's `edit_body` operation
replaces the entire description in one call (cross-backend
invariant from `backends/_interface.md`). There is no
append-only API on either supported backend. The skill is
responsible for the read-modify-write cycle: invoke `view_issue`
first, modify only the Status-block lines + the relevant
`## Children` line in memory, then invoke `edit_body` with the
full new body.

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

Optional — a CI job that does steps 1-3 automatically on
issue-closed events. Out of scope for this skill; a candidate
follow-up `feature-request`.

## GitHub Projects board (optional)

Only relevant when the consumer's `.claude/issue-tracker.yaml` sets
`github.project` (GitHub backend only). When it does, mirror the initiative tree
onto that GitHub Projects (v2) board as a **human-facing view** — the `## Children`
task-list mirror stays the source of truth, and every board write is best-effort
(a failure WARNs and never blocks the issue operation). With `github.project`
unset, skip it entirely; behaviour is unchanged.

The three-state lifecycle (`Todo` on file/link, `In Progress` on
`/resume-initiative --start`, `Done` on close) and the backfill procedure for an
existing tree are documented in
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
| Sub-epic + all children closed | sub-initiative done | close it like any epic; its close is then a child-close from its parent's view — run the Maintenance steps once on the parent (one hop up) |
| Closed | initiative shipped | preserved as history; design spec link still valid |
| Closed + reason `not_planned` | abandoned | comment explains why; surviving children get triaged separately via `bug-tracking` / `feature-request` / `followup-tracking` |

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
