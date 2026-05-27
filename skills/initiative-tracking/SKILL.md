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
  the *index* over many issues.
---

# Initiative Tracking — Multi-Week Effort as Epic + Sub-Issues

The canonical tracker is the one configured in the consumer
project's `.claude/issue-tracker.yaml`. The plugin's
`backends/_interface.md` documents the seven operations every
backend implements; `backends/<backend>.md` (e.g.
`backends/github.md`) documents the literal CLI / MCP invocation
for each operation.

An initiative is not a different *tracker* — it is a different
*shape of tracked work*: one epic issue indexes many child issues,
all under the same label convention, with a Status block the
operator-facing `/resume-initiative` command can parse without a
human.

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

The Status block fields are CANONICAL and parsed by
`/resume-initiative` character-for-character. Change them only if
you update `/resume-initiative` in the same PR.

## Status block — exact field spec

These are the strings `/resume-initiative` parses. Do not
paraphrase.

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

## Creating sub-issues

Each sub-issue body uses the standard `feature-request` or
`bug-tracking` agent-prompt template (Goal / Locus / Skills to
load / What's missing OR Symptom / Sketch / Constraints /
Acceptance / Verify) plus a `## Parent epic` block. The skill's
contract is: **the body of every child issue is agent-runnable** —
any future agent that picks up the child can do so cold.

Use `templates/sub-issue-body.md` as the composition guide. It
points at `templates/feature-body.md` or `templates/bug-body.md`
based on whether the sub-issue is feature-shaped or bug-shaped,
and documents the `## Parent epic` block to append.

Conventions specific to children of an epic:

- **Title prefix:** `<phase-name>: <capability>` so the tracker's
  issue-list view shows phase membership without needing the epic
  body. Example: `Phase 1: backend interface contract + GitHub
  backend`.
- **`## Parent epic` block** — required; cites the epic's ref and
  one-line title.
- **Labels:** the type-shape label (`bug` for defects,
  `enhancement` for new capabilities) plus the same area label(s)
  as the work touches, plus the same triage label conventions
  (`needs-design` if the sub-issue has open design questions,
  etc.). Do NOT label children with `epic` — that's reserved for
  the index.

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

Per-backend native linkage mechanics — GitHub's native sub-issue
API, Jira's `parent` field or Epic Link customfield — are
documented in `backends/<backend>.md`. The skill does not encode
them.

## Maintenance

Whenever a child closes:

1. Increment the `Phase` line's `<closed>/<total>` count.
2. Recompute `Next up` — first open child by phase order, or
   `none` if all children for the current phase are closed.
3. Bump `Last updated` to today.
4. Flip the `## Children` task-list mirror entry to
   `[x] <ref> — <title> — closed YYYY-MM-DD`.
5. Append to `Decision log` if a non-trivial decision was made
   during the child's PR.

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

## Epic lifecycle

| State | Meaning | Action |
|---|---|---|
| Open + has open children | initiative in progress | `/resume-initiative <ref>` works |
| Open + all children closed | ready to declare done | operator invokes `close_issue` with `reason: completed` plus a one-paragraph wrap-up comment |
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
