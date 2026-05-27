# Port initiative-tracking skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `skills/initiative-tracking/SKILL.md`, `templates/epic-body.md`, and `templates/sub-issue-body.md` in this plugin as tracker-agnostic ports of the same-named trading-bot skill, satisfying agent-issue-tracker#14 (Phase 2 sub-issue of trading-bot epic #153).

**Architecture:** Mechanical re-application of the de-trading-bot-ification transforms (parent design spec §6.1) plus the four surgical transforms specific to this skill (parent spec §6.2; this plan's spec §7). Three new markdown files plus a CHANGELOG line. The skill prose dispatches through the seven-operation backend contract from `backends/_interface.md`. The epic body template carries the four canonical Status-block field-prefix strings literally — `/resume-initiative` (Phase 3) depends on byte-identical parsing. The sub-issue body template is a thin compose-by-reference wrapper around `templates/feature-body.md` or `templates/bug-body.md` plus a `## Parent epic` block — deliberate divergence from `templates/followup-body.md`'s self-contained pattern (rationale in this plan's spec §4.1).

**Tech Stack:** Markdown only — no code, no scripts. `gh` CLI for the PR; `git` for branch operations.

---

## Working directory

All work happens in the primary working tree of `maxdimitrov/agent-issue-tracker`:

```
F:/Claude/Projects/agent-issue-tracker
```

on branch `feat/port-initiative-tracking-skill` (off `origin/main` @ commit `83fd3c2` — the PR #18 / Phase 2 #13 followup-tracking merge — plus this plan's spec at `54558ba`).

**Note on cross-repo session:** the controller session's CWD is `F:/Claude/Projects/Trading` (the trading-bot repo), NOT this working directory. Every subagent dispatch in this plan MUST start with the literal first action:

```bash
cd F:/Claude/Projects/agent-issue-tracker && git status && git rev-parse --abbrev-ref HEAD
```

After each subagent returns, the controller MUST verify the commit landed on the right branch:

```bash
git -C F:/Claude/Projects/agent-issue-tracker log -1 --format='%H %s'
```

No worktree is used for this port — the agent-issue-tracker primary working dir IS the workspace, and the controller has no other parallel work in that dir. For 2+ parallel writing subagents the project's global CLAUDE.md "Parallel agents need isolated workspaces" rule would apply (`isolation: "worktree"` on the Agent call); the serial-task structure of this plan does not need it.

The source skill to port FROM is locally readable at:

```
F:/Claude/Projects/Trading/.claude/skills/initiative-tracking/SKILL.md
```

(258 lines on trading-bot main). The Read tool accepts absolute paths, so subagents can read it directly without copying it into the workspace as a sentinel file.

---

## File Structure

All paths relative to the workspace root (`F:/Claude/Projects/agent-issue-tracker`).

| File | Action | Responsibility |
|---|---|---|
| `docs/superpowers/specs/2026-05-27-port-initiative-tracking-skill-design.md` | Already exists | Design spec — committed as `54558ba` before this plan; ships in the PR alongside the new files. |
| `docs/superpowers/plans/2026-05-27-port-initiative-tracking-skill.md` | Create (this file) | Implementation plan — committed before Task 1 dispatch; ships in the PR. |
| `templates/epic-body.md` | Create | Epic body skeleton — preamble + machine-readable Status block (the four canonical field prefixes appear LITERALLY) + Phases + Children task-list mirror + Decision log + Resume-from-here. ~85-95 lines. All-placeholder content. |
| `templates/sub-issue-body.md` | Create | Sub-issue body composition guide — thin compose-by-reference wrapper. Says: use `templates/feature-body.md` or `templates/bug-body.md` as the base, prepend `<phase-name>:` title prefix convention, append `## Parent epic` block. ~50 lines. |
| `skills/initiative-tracking/SKILL.md` | Create | Tracker-agnostic methodology — triage gate, Status block field spec, sub-issue creation flow, `link_sub_issue` indirection, maintenance / read-modify-write via the destructive-edit cross-backend invariant, lifecycle. Dispatches to `backends/<backend>.md` via the seven-operation contract. ~270 lines. |
| `CHANGELOG.md` | Modify | Append one line under `## [Unreleased]` → `### Added`. |

Pure-addition PR. Estimated total: `+~600 / -0` across 5 new files plus the CHANGELOG one-line append (the spec file already landed in commit `54558ba`).

---

## Pre-flight (do this once before Task 1)

Run from anywhere thanks to `git -C`:

```bash
# 1. Branch is up to date with origin/main
git -C F:/Claude/Projects/agent-issue-tracker fetch origin
git -C F:/Claude/Projects/agent-issue-tracker rev-list --left-right --count HEAD...origin/main
# Expected: "1\t0"
# LEFT = 1: the spec commit 54558ba already on the branch.
# RIGHT = 0: origin/main has NOT moved since branch was cut.
# If RIGHT > 0: origin/main has moved. Rebase or report to operator before starting Task 1.
```

If RIGHT > 0, abort and surface to the operator.

```bash
# 2. Confirm branch and HEAD
git -C F:/Claude/Projects/agent-issue-tracker rev-parse --abbrev-ref HEAD
# Expected: "feat/port-initiative-tracking-skill"

git -C F:/Claude/Projects/agent-issue-tracker log -1 --format='%H %s'
# Expected: "54558ba... docs(spec): port initiative-tracking skill design (#14)"
```

```bash
# 3. Working tree is clean
git -C F:/Claude/Projects/agent-issue-tracker status --porcelain
# Expected: empty output (clean tree)
```

If any of the above fail, STOP and surface to the operator.

---

## Plan-commit step (controller does this BEFORE dispatching Task 1)

The controller commits this plan file on the feature branch first so it ships in the PR alongside the spec, the three new files, and the CHANGELOG entry. Mirrors PR #18's pattern.

```bash
git -C F:/Claude/Projects/agent-issue-tracker add docs/superpowers/plans/2026-05-27-port-initiative-tracking-skill.md
git -C F:/Claude/Projects/agent-issue-tracker commit -m "$(cat <<'EOF'
docs(plan): implementation plan for #14 - port initiative-tracking skill

Three-task structure mirroring PR #18 (followup-tracking port):
templates -> skill+CHANGELOG -> push+PR. Each writing task uses a
haiku subagent constrained to the verbatim file content embedded
in this plan; the controller verifies commits via git log -1
after every return.

Refs #14. Parent epic: maxdimitrov/trading-bot#153 (Phase 2).
EOF
)"
git -C F:/Claude/Projects/agent-issue-tracker log -1 --format='%H %s'
# Expected: "<sha> docs(plan): implementation plan for #14 - port initiative-tracking skill"
```

---

## Task 1: Write `templates/epic-body.md` + `templates/sub-issue-body.md`

**Files:**
- Create: `templates/epic-body.md`
- Create: `templates/sub-issue-body.md`

**Subagent CWD discipline:** the implementer's first action MUST be the `cd` + `git status` + `git rev-parse --abbrev-ref HEAD` triple from the Working-directory section above. Controller verifies via `git log -1` after return.

**Subagent model:** haiku — both files are verbatim content from this plan.

**Blast radius:** two new files. Pure-addition. Rollback: `git restore --staged templates/epic-body.md templates/sub-issue-body.md && rm templates/epic-body.md templates/sub-issue-body.md`.

- [ ] **Step 1.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker
git status
git rev-parse --abbrev-ref HEAD
git log -1 --format='%H %s'
```
Expected:
- `On branch feat/port-initiative-tracking-skill`
- Working tree clean
- `feat/port-initiative-tracking-skill`
- HEAD message: `docs(plan): implementation plan for #14 - port initiative-tracking skill`

- [ ] **Step 1.2: Write `templates/epic-body.md` with this exact content**

Use the Write tool with `file_path: templates/epic-body.md` and this content:

````markdown
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
````

- [ ] **Step 1.3: Write `templates/sub-issue-body.md` with this exact content**

Use the Write tool with `file_path: templates/sub-issue-body.md` and this content:

````markdown
# Sub-issue Body Template

This is the canonical agent-prompt body for filing a sub-issue of
an epic via the `initiative-tracking` skill. **A sub-issue is
either feature-shaped or bug-shaped** — this template is a thin
compose-by-reference wrapper around the type-appropriate sibling
template.

This pattern (compose, not self-contained) is a deliberate
divergence from `templates/followup-body.md`. Followup bodies have
five extra blocks specific to the follow-up shape, so a
self-contained template was the honest expression. A sub-issue
adds ONE extra block (`## Parent epic`) on top of an otherwise
ordinary feature or bug body, so composition is the honest
expression and avoids drift if the sibling templates change.

## How to compose

1. Pick the sibling template that matches the sub-issue's
   type-shape:
   - The sub-issue adds a **new capability or redesign** → use
     `templates/feature-body.md` as the base. Load the
     `feature-request` skill for the agent-prompt requirements.
   - The sub-issue fixes a **defect or regression** → use
     `templates/bug-body.md` as the base. Load the `bug-tracking`
     skill for the agent-prompt requirements.

2. Use the title prefix convention: `<phase-name>: <capability>`.
   The phase prefix makes `list_open_issues` show phase membership
   without needing the epic body. Example titles:
   - `Phase 1: backend interface contract + GitHub backend`
   - `Phase 2: port initiative-tracking skill`

3. Fill in the sibling template normally — Goal / Locus / Skills
   to load / What's missing OR Symptom / Sketch / Constraints /
   Acceptance / Verify (the exact field set depends on which
   sibling template).

4. Append the `## Parent epic` block (literal — exactly the
   skeleton below) to the end of the filled-in sibling body. This
   block links the sub-issue back to its epic and is what
   distinguishes a sub-issue body from a plain feature or bug body.

5. Pass the result as the `body` argument to your backend's
   `create_issue` operation with `type: sub`. See
   `backends/<backend>.md` for the literal invocation. After the
   sub-issue is filed, invoke the backend's `link_sub_issue`
   operation to establish native parent-child linkage.

---

## Parent epic
<epic-ref> — <one-line epic title> (Phase <N>)

<optional: one sentence on which slice of the epic this sub-issue
covers. Keep it short — the epic body's `## Phases` section has
the full breakdown.>
````

- [ ] **Step 1.4: Verify both templates pass the invariant + leakage greps**

Run (from the workspace root):

```bash
# AC: the four canonical Status-block field prefixes appear LITERALLY in templates/epic-body.md
for field in "- **Phase:**" "- **Next up:**" "- **Current branch:**" "- **Last updated:**"; do
  grep -qF "$field" templates/epic-body.md || echo "MISSING field: $field"
done
echo "field-prefix check done"
```
Expected: just `field-prefix check done` (no MISSING lines).

```bash
# AC: templates/sub-issue-body.md has ## Parent epic
grep -F "## Parent epic" templates/sub-issue-body.md
```
Expected: at least one matching line.

```bash
# AC: no maxdimitrov/trading-bot literal in either template
grep -r "maxdimitrov/trading-bot" templates/epic-body.md templates/sub-issue-body.md && echo LEAK || echo clean
```
Expected: `clean`.

```bash
# AC: no trading-bot-specific skill or path leaks
grep -rE "PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" templates/epic-body.md templates/sub-issue-body.md && echo LEAK || echo clean
```
Expected: `clean`.

```bash
# AC: no `gh api repos/` snippet (the native sub-issue API is owned by backends/github.md)
grep -r "gh api repos/" templates/epic-body.md templates/sub-issue-body.md && echo LEAK || echo clean
```
Expected: `clean`.

```bash
# AC: no absolute paths or ~/.claude/ refs
grep -rE "~/\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" templates/epic-body.md templates/sub-issue-body.md && echo BAD_PATH || echo clean
```
Expected: `clean`.

If any check fails, fix the offending template inline and re-run the suite before committing.

- [ ] **Step 1.5: Commit**

```bash
git add templates/epic-body.md templates/sub-issue-body.md
git commit -m "$(cat <<'EOF'
feat(templates): add epic-body and sub-issue-body skeletons

templates/epic-body.md is the canonical epic-body skeleton with
the four CANONICAL Status-block field prefixes appearing literally
(`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`,
`- **Last updated:**`). The cross-backend `/resume-initiative`
parser (Phase 3) depends on these strings byte-for-byte; do not
reword them.

templates/sub-issue-body.md is a thin compose-by-reference wrapper
around templates/feature-body.md or templates/bug-body.md plus a
`## Parent epic` block. Deliberate divergence from
templates/followup-body.md's self-contained pattern: sub-issues
add ONE extra block on top of an ordinary feature or bug body, so
composition is the honest expression and avoids drift if the
sibling templates change.

Both files are all-placeholder. Referenced from
skills/initiative-tracking/SKILL.md (Task 2).

Refs #14 (Phase 2 of trading-bot epic #153).
EOF
)"
```

Verify:
```bash
git log -1 --format='%H %s'
# Expected: "<sha> feat(templates): add epic-body and sub-issue-body skeletons"
git rev-parse --abbrev-ref HEAD
# Expected: "feat/port-initiative-tracking-skill"
git log --oneline -3
# Expected (most recent first):
#   <sha> feat(templates): add epic-body and sub-issue-body skeletons
#   <sha> docs(plan): implementation plan for #14 - port initiative-tracking skill
#   54558ba docs(spec): port initiative-tracking skill design (#14)
```

---

## Task 2: Write `skills/initiative-tracking/SKILL.md` + CHANGELOG entry

**Files:**
- Create: `skills/initiative-tracking/SKILL.md`
- Modify: `CHANGELOG.md`

**Subagent CWD discipline:** same as Task 1.

**Subagent model:** haiku — verbatim content from this plan.

**Blast radius:** one new file + one one-line append. Pure-addition. Rollback: `git reset --hard HEAD~1` (after committing) or `git restore --staged <files> && rm skills/initiative-tracking/SKILL.md && git restore CHANGELOG.md` (before committing).

- [ ] **Step 2.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker
git status
git log -1 --format='%H %s'
```
Expected: `On branch feat/port-initiative-tracking-skill` + the Task 1 commit message at HEAD.

- [ ] **Step 2.2: Create the skill directory and write `skills/initiative-tracking/SKILL.md`**

```bash
mkdir -p skills/initiative-tracking
```

Then write `skills/initiative-tracking/SKILL.md` with this exact content:

````markdown
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
| Spans 1-3 days | no | yes — single issue |
| Spans weeks | yes | — |
| Multiple phases with checkpoints | yes | — |
| Has a design spec | yes (link it) | optional |
| Decomposes into 3+ independent issues | yes | — |

If you would only file 1-2 sub-issues, you don't have an
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
````

- [ ] **Step 2.3: Edit `CHANGELOG.md` to add the Phase 2 (#14) line**

The current `CHANGELOG.md` has a `## [Unreleased]` section with a `### Added` block listing Phase 0, Phase 1, and Phase 2 (#11, #12, #13) entries. Append the Phase 2 (#14) line to that `### Added` list.

Use the Edit tool. `old_string` matches the last existing `### Added` entry (the Phase 2 #13 followup-tracking line); `new_string` keeps that entry and appends a newline + the new line.

`old_string`:
```
- Phase 2 (#13): followup-tracking skill — tracker-agnostic port from trading-bot. Type-orthogonal sibling to bug-tracking + feature-request; covers origination (work deferred from in-flight effort), not type. New `templates/followup-body.md` skeleton — first non-standard body template in the plugin, with five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) preceding the standard tail. Validates the templates/*-body.md pattern for `templates/epic-body.md` (#14).
```

`new_string`:
```
- Phase 2 (#13): followup-tracking skill — tracker-agnostic port from trading-bot. Type-orthogonal sibling to bug-tracking + feature-request; covers origination (work deferred from in-flight effort), not type. New `templates/followup-body.md` skeleton — first non-standard body template in the plugin, with five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) preceding the standard tail. Validates the templates/*-body.md pattern for `templates/epic-body.md` (#14).
- Phase 2 (#14): initiative-tracking skill — tracker-agnostic port from trading-bot, the most-surgery port of the four (parent spec §6.2). Four surgical transforms: native sub-issue API block → `link_sub_issue` indirection; Status-block parser extension (Next-up accepts both `#N` and `PROJ-123`); read-modify-write warning generalized via the destructive-edit cross-backend invariant from `backends/_interface.md`; per-backend fallback section reframed as a cross-backend invariant (the `## Children` task-list mirror is the canonical index; native linkage is per-backend native plumbing). New `templates/epic-body.md` carries the four canonical Status-block field prefixes (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) literally — Phase 3 `/resume-initiative` parses them character-for-character. New `templates/sub-issue-body.md` is a thin compose-by-reference wrapper around feature-body.md / bug-body.md plus a `## Parent epic` block (deliberate divergence from followup-body.md's self-contained pattern).
```

If the exact `old_string` does not match (CHANGELOG drift since PR #18), the agent must Read `CHANGELOG.md` first, locate the `## [Unreleased]` → `### Added` block, and append the new line as the LAST entry under it.

Verify:
```bash
grep -E "Phase 2 \(#14\): initiative-tracking" CHANGELOG.md
# Expected: one matching line
```

- [ ] **Step 2.4: Run the full acceptance grep suite (issue #14 + spec §8 Verify)**

```bash
# AC1: files exist
test -f skills/initiative-tracking/SKILL.md && echo OK_SKILL || echo MISSING_SKILL
test -f templates/epic-body.md && echo OK_EPIC || echo MISSING_EPIC
test -f templates/sub-issue-body.md && echo OK_SUB || echo MISSING_SUB
# All three must echo OK_*

# AC2: no maxdimitrov/trading-bot literal
grep -r "maxdimitrov/trading-bot" skills/initiative-tracking templates/epic-body.md templates/sub-issue-body.md && echo LEAK || echo clean
# Expected: "clean"

# AC3: no trading-bot-specific skill or path leaks
grep -rE "PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" skills/initiative-tracking templates/epic-body.md templates/sub-issue-body.md && echo LEAK || echo clean
# Expected: "clean"

# AC4: no `gh api repos/` snippet in the SKILL (the native sub-issue API is owned by backends/github.md only)
grep -r "gh api repos/" skills/initiative-tracking/SKILL.md && echo LEAK || echo clean
# Expected: "clean"

# AC5: four canonical Status-block field prefixes appear LITERALLY in templates/epic-body.md
for field in "- **Phase:**" "- **Next up:**" "- **Current branch:**" "- **Last updated:**"; do
  grep -qF "$field" templates/epic-body.md || echo "MISSING field: $field"
done
echo "field-prefix check done"
# Expected: just "field-prefix check done"

# AC6: skill cites link_sub_issue, the configured backend, and the generalized read-modify-write warning
grep -E "link_sub_issue" skills/initiative-tracking/SKILL.md | head -3
# Expected: at least one match (in the "Linking children to the epic" + "Children task-list mirror" sections)

grep -E "configured backend|backends/<backend>" skills/initiative-tracking/SKILL.md | wc -l
# Expected: >=5 (Filing + Epic body template + Linking + Children mirror + Maintenance + Lifecycle all dispatch through the backend)

grep -iE "read.modify.write|destructive|edit_body" skills/initiative-tracking/SKILL.md | wc -l
# Expected: >=3 (Maintenance section)

# AC7: skill names both #N and PROJ-123 as acceptable Next-up refs
grep -E "#N.*PROJ-123|PROJ-123.*#N" skills/initiative-tracking/SKILL.md
# Expected: at least one match

# AC8: triage gate table preserved verbatim
grep -E "Fits in one PR|Spans 1-3 days|Spans weeks|Multiple phases" skills/initiative-tracking/SKILL.md | wc -l
# Expected: >=4

# AC9: sibling cross-links
grep -E "feature-request|bug-tracking|followup-tracking" skills/initiative-tracking/SKILL.md | wc -l
# Expected: >=3

# AC10: sub-issue template has ## Parent epic literal
grep -F "## Parent epic" templates/sub-issue-body.md
# Expected: one matching line

# AC11: no absolute paths or ~/.claude/ refs
grep -rE "~/\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" skills/initiative-tracking templates/epic-body.md templates/sub-issue-body.md && echo BAD_PATH || echo clean
# Expected: "clean"

# AC12: CHANGELOG entry present
grep -E "Phase 2 \(#14\): initiative-tracking" CHANGELOG.md
# Expected: one matching line

# AC13: file size sanity
wc -l skills/initiative-tracking/SKILL.md templates/epic-body.md templates/sub-issue-body.md
# Expected (approximate, within reason):
#   skills/initiative-tracking/SKILL.md   -> 230-300 lines
#   templates/epic-body.md                -> 70-100 lines
#   templates/sub-issue-body.md           -> 40-60 lines
```

If any check fails, fix in place and re-run the suite before committing.

- [ ] **Step 2.5: Markdownlint (conditional)**

```bash
[ -f .markdownlint.json ] && npx --yes markdownlint-cli skills/initiative-tracking/SKILL.md templates/epic-body.md templates/sub-issue-body.md
[ -f .markdownlint.json ] || echo "no markdownlint config; deferred to Phase 4 per design spec"
```

The plugin does not ship a markdownlint config today (deferred to Phase 4). Skip and report.

- [ ] **Step 2.6: Cold-read review**

Open the three files in a fresh view (without the source skill nearby) and verify:

1. The skill prose reads as "this is the methodology" without trading-bot pre-knowledge — no orphaned references, no "see the X skill" pointers that don't resolve in this plugin.
2. The four canonical Status-block field-prefix strings in `templates/epic-body.md` appear EXACTLY (no smart quotes, no Unicode bullets, no rewording).
3. The `templates/sub-issue-body.md` composition guide is self-contained — a reader can fill in a sub-issue without reading `skills/initiative-tracking/SKILL.md` first (it points at the sibling templates and names the `## Parent epic` block to append).
4. The `link_sub_issue` indirection paragraph in the skill is one paragraph, names the operation, points at `backends/<backend>.md`, and does NOT include a code block (the typed-int gotcha and other per-tracker mechanics live in the backend module).
5. The read-modify-write warning cites the cross-backend invariant from `backends/_interface.md`, not per-backend mechanics.
6. The `## Children` task-list mirror is named as the **cross-backend source of truth**; `link_sub_issue` is named as additional, per-backend native plumbing.

If any cold-read issue surfaces, fix inline and re-run the AC suite before committing.

- [ ] **Step 2.7: Commit**

```bash
git add skills/initiative-tracking/SKILL.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat(skills): port initiative-tracking from trading-bot

Tracker-agnostic prose; dispatches to backends/<backend>.md via
the seven-operation contract (create_issue / list_open_issues /
view_issue / edit_body / close_issue / link_sub_issue). This is
the most-surgery port of the four (parent design spec section
6.2): four surgical transforms applied.

1. Native sub-issue API block (`gh api .../sub_issues`) becomes
   a methodology paragraph pointing at backends/<backend>.md.
   GitHub's typed-int sub-issue-id gotcha stays in
   backends/github.md; the skill does not re-document it.

2. Status-block field-prefix strings (`- **Phase:**`,
   `- **Next up:**`, `- **Current branch:**`,
   `- **Last updated:**`) are CANONICAL and appear LITERALLY in
   templates/epic-body.md. /resume-initiative (Phase 3) parses
   them character-for-character across both backends. The
   `Next up:` value accepts both `#N` (GitHub) and `PROJ-123`
   (Jira) ref syntaxes; the backend renders the syntax.

3. Read-modify-write warning generalized: cites cross-backend
   invariant #2 from backends/_interface.md (edit_body is
   destructive on every supported backend), not per-backend
   mechanics. The cycle is view_issue -> modify in memory ->
   edit_body, expressed in tracker-neutral terms.

4. Per-backend fallback section reframed as a cross-backend
   invariant: the `## Children` task-list mirror in the epic
   body is the CANONICAL cross-backend index (it is what
   /resume-initiative parses regardless of backend). Native
   linkage via link_sub_issue is additional per-backend native
   plumbing for the tracker's UI - NOT a fallback to the
   task-list mirror.

Sub-issue body template chose compose-by-reference (use
templates/feature-body.md or templates/bug-body.md as base,
append `## Parent epic` block) - deliberate divergence from
templates/followup-body.md's self-contained pattern. Sub-issues
add ONE extra block on top of an ordinary feature or bug body,
so composition is the honest expression and avoids drift if
sibling templates change.

Behaviour-change-zero: triage gate table, Status-block field
prefixes, title format `epic: <name>`, label rules, lifecycle
table, trigger phrases in frontmatter description - all
byte-equivalent to the trading-bot source after the four
surgical transforms.

Trigger phrases preserved verbatim.

Worked example chains off the `worker/queue redesign` thread
used by sibling Phase 2 ports (cli/list --json in
feature-request/followup-tracking; worker/queue in
bug-tracking).

Closes #14.
Refs trading-bot#153 (Phase 2).
EOF
)"
```

Verify:
```bash
git log -5 --format='%H %s'
# Expected (most recent first):
#   <sha> feat(skills): port initiative-tracking from trading-bot
#   <sha> feat(templates): add epic-body and sub-issue-body skeletons
#   <sha> docs(plan): implementation plan for #14 - port initiative-tracking skill
#   54558ba docs(spec): port initiative-tracking skill design (#14)
#   83fd3c2 Phase 2 (#13): port followup-tracking skill (#18)
git status
# Expected: "On branch feat/port-initiative-tracking-skill" + working tree clean
```

---

## Task 3: Push branch + create PR

**Files:** none committed — git/gh operations only.

**Subagent CWD discipline:** controller does this directly (no subagent needed). The controller's main session CWD is `F:/Claude/Projects/Trading` and resets between Bash calls, so every `git`/`gh` invocation uses `git -C` or `cd` first.

**Blast radius:** pushes the branch to origin, opens the PR. Reversible — `git push origin --delete feat/port-initiative-tracking-skill` removes the remote branch; `gh pr close <N>` closes the PR.

- [ ] **Step 3.1: Confirm cwd, branch, and staleness**

```bash
cd F:/Claude/Projects/agent-issue-tracker
git status
git log --oneline -5
# Expected: four new commits on top of the PR #18 merge (83fd3c2):
#   - feat(skills): port initiative-tracking from trading-bot
#   - feat(templates): add epic-body and sub-issue-body skeletons
#   - docs(plan): implementation plan for #14 - port initiative-tracking skill
#   - docs(spec): port initiative-tracking skill design (#14)
# Working tree clean.

git fetch origin
git rev-list --left-right --count HEAD...origin/main
# LEFT side (HEAD) should be exactly 4 (spec + plan + templates + skill+CHANGELOG)
# RIGHT side (origin/main) MUST be 0 - if not, origin/main moved during the work; report to operator
```

If RIGHT > 0, STOP and report. Do not push.

- [ ] **Step 3.2: Push branch with upstream tracking**

```bash
git push -u origin feat/port-initiative-tracking-skill
```

Expected: branch created on origin, tracking set up. Look for `* [new branch]  feat/port-initiative-tracking-skill -> feat/port-initiative-tracking-skill` in the output.

- [ ] **Step 3.3: Create the PR**

```bash
gh pr create \
  --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/port-initiative-tracking-skill \
  --title "Phase 2 (#14): port initiative-tracking skill" \
  --body "$(cat <<'EOF'
## Summary
- Ports the `initiative-tracking` skill from `maxdimitrov/trading-bot` to this plugin in tracker-agnostic prose. The most-surgery port of the four per parent design spec §6.2.
- Adds `templates/epic-body.md` carrying the four CANONICAL Status-block field-prefix strings literally — Phase 3 `/resume-initiative` parses them character-for-character across both backends.
- Adds `templates/sub-issue-body.md` as a thin compose-by-reference wrapper (feature-body.md / bug-body.md + `## Parent epic` block) — deliberate divergence from `templates/followup-body.md`'s self-contained pattern.
- Dispatches to `backends/<backend>.md` via the seven-operation contract landed in Phase 1 (#9). Uses `create_issue` / `list_open_issues` / `view_issue` / `edit_body` / `close_issue` / `link_sub_issue` — the first plugin skill to use the full operation set.

## Files
- `skills/initiative-tracking/SKILL.md` — new (~270 lines)
- `templates/epic-body.md` — new (~85 lines)
- `templates/sub-issue-body.md` — new (~50 lines, compose-by-reference)
- `CHANGELOG.md` — one line appended
- `docs/superpowers/specs/2026-05-27-port-initiative-tracking-skill-design.md` — design spec (committed pre-Task 1)
- `docs/superpowers/plans/2026-05-27-port-initiative-tracking-skill.md` — implementation plan (committed pre-Task 1)

## Decisions settled in brainstorm
1. **Sub-issue body template — compose, not inline.** `templates/sub-issue-body.md` is a thin wrapper around `templates/feature-body.md` / `templates/bug-body.md` + a `## Parent epic` block. Followup-tracking went self-contained because its 5 extra blocks were genuinely shape-specific; sub-issues add ONE extra block, so composition is the honest expression and avoids drift if sibling templates change.
2. **`link_sub_issue` indirection — methodology, not dispatch.** One paragraph in the skill prose names the operation and points at `backends/<backend>.md`. GitHub's typed-int gotcha (`-F` not `-f`, HTTP 422 otherwise) stays in `backends/github.md`; the skill does not re-document it.
3. **Read-modify-write warning — cite the contract invariant.** Skill prose cites cross-backend invariant #2 from `backends/_interface.md` (edit_body is destructive on every supported backend), not per-backend mechanics. The cycle is `view_issue → modify in memory → edit_body`, expressed in tracker-neutral terms.
4. **Per-backend fallback section — reframe as cross-backend invariant.** The source's framing ("native is source of truth, task-list mirror is fallback") was GitHub-centric. Plugin version: the `## Children` task-list mirror in the epic body is the CANONICAL cross-backend index — `/resume-initiative` parses these lines regardless of backend. Native linkage via `link_sub_issue` is additional, per-backend native plumbing for the tracker's UI, NOT a fallback to the task-list mirror.
5. **Examples — generic subject, retain shape.** Source's specific numbers (`#127 — reserve-ledger schema`, `Phase 1a · 2/4`) → generic placeholders that retain shape (`Phase 1 · 2/4 sub-issues closed`, `#42 — <child-title>`). Worked-example block chains off the `worker/queue redesign` thread for cross-skill narrative consistency.

## Transforms applied
Standard de-trading-bot-ification per parent design spec §6.1, plus the four surgical transforms per §6.2:

| Source reference (trading-bot) | Port reference (plugin) |
|---|---|
| `GitHub Issues on maxdimitrov/trading-bot` | `the configured tracker (see .claude/issue-tracker.yaml)` |
| `gh issue create --title ... --label "epic,<area>"` block | `create_issue` operation dispatch paragraph |
| `gh issue view --json body --jq .body > .tmp_epic_body.md` ... `gh issue edit --body-file` | `view_issue` + `edit_body` operation pair, expressed in tracker-neutral terms |
| `gh api repos/.../sub_issues -F sub_issue_id=$CHILD_ID` block | one paragraph: "invoke `link_sub_issue`; backends document per-tracker mechanism" |
| Status-block field-prefix strings | **byte-identical**; the `Next up:` value now accepts both `#N` and `PROJ-123` |
| Read-modify-write warning (GitHub-centric `gh issue edit --body-file` language) | generalized via cross-backend invariant #2 from `backends/_interface.md` |
| "Fallback when native sub-issue API is unavailable" section | reframed: the `## Children` task-list mirror is the cross-backend canonical index; native linkage is per-backend plumbing |
| `gh issue close <N> --comment` | `close_issue` operation with optional `reason` |
| Trading-bot subsystem enum (`ibkr / proposal-service / ...`) | consumer-configured `.claude/issue-tracker.yaml` `subsystems:` enum |
| Trading-bot area labels (`dashboard/backend/frontend/infra`) | consumer-configured `areas:` enum |
| Trading-bot domain skill cross-links (e.g. `ic-memo-framework`, `dca-router`) | dropped — plugin skills cite themselves only |
| `memory/PENDING-FIXES.md is frozen legacy` callout | dropped (trading-bot operator concern, not portable methodology) |
| Trigger phrases in frontmatter `description:` | preserved verbatim (behaviour-change-zero invariant) |
| Title format `epic: <name>` | unchanged (tracker-neutral) |
| Returning the epic number (`"Epic created: #<N>"`) | reworded to `<ref>` to handle both `#N` and `PROJ-123` |

## Compose-by-reference rationale (`templates/sub-issue-body.md`)
A sub-issue legitimately *is* "feature OR bug + one extra block." Followup-tracking went self-contained (with the standard 7 blocks repeated inside `templates/followup-body.md`) because the 5 extra blocks were genuinely sub-shape-specific structure that didn't appear in any sibling template. Sub-issues have ONE extra block (`## Parent epic`). Compose-by-reference is the more honest expression and avoids drift: if `templates/feature-body.md` changes (adding/dropping a block), `templates/sub-issue-body.md` doesn't need a parallel edit. The acceptance criterion (`## Parent epic` section present) is satisfied either way.

## Behaviour-change-zero
Per §8.2 of the parent design spec, the triage gate table, Status-block field-prefix strings, title format `epic: <name>`, label rules (`epic` on the epic; children get type-shape + area + triage labels, NOT `epic`), lifecycle table, and trigger phrases in the frontmatter `description:` are byte-equivalent to the trading-bot source after the four surgical transforms. The Phase 5 cutover PR (against trading-bot) is the explicit gate where trigger-phrase regression is verified end-to-end; this PR only ships the plugin-side port.

## Templates/*-body.md pattern validation
This is the second port whose body template adds structure beyond the standard agent-prompt shape (after `templates/followup-body.md` in #13). `templates/epic-body.md` validates the pattern for the most-structured case (Status block + Phases + Children + Decision log + Resume-from-here). `templates/sub-issue-body.md` validates the alternative compose-by-reference shape that's appropriate when the type adds only one extra block.

## Phase 3 dependency
This port codifies the Status-block format that Phase 3's `/resume-initiative` command parses. The four field-prefix strings (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) are canonical and load-bearing — any rewording is a breaking change to Phase 3's parser. Coordinate with whoever picks up Phase 3 (filed as `agent-issue-tracker#8` per the parent spec sub-issue layout).

## Test plan
Static acceptance from issue #14 + spec §8 (no code, no pytest — markdown-only):

- [x] `skills/initiative-tracking/SKILL.md` exists
- [x] `templates/epic-body.md` exists; contains the four exact Status-block field-prefix strings (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) literally
- [x] `templates/sub-issue-body.md` exists; contains a `## Parent epic` section
- [x] `grep -r "maxdimitrov/trading-bot" skills/initiative-tracking templates/epic-body.md templates/sub-issue-body.md` → no matches
- [x] `grep -r "gh api repos/" skills/initiative-tracking/SKILL.md` → no matches (the native sub-issue API is owned by `backends/github.md` only)
- [x] `grep -rE "PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" skills/initiative-tracking templates/epic-body.md templates/sub-issue-body.md` → no matches
- [x] Skill prose cites `link_sub_issue`, the configured backend, and the generalized read-modify-write warning
- [x] Skill prose names both `#N` and `PROJ-123` as acceptable `Next up:` ref syntaxes
- [x] Triage gate table preserved verbatim from source (four rows: Fits in one PR / Spans 1-3 days / Spans weeks / Multiple phases)
- [x] Sibling cross-links to `feature-request`, `bug-tracking`, `followup-tracking` (≥3 references)
- [x] No absolute paths or `~/.claude/` refs in skill or templates
- [x] CHANGELOG.md has the Phase 2 (#14) line under `[Unreleased]` → `Added`
- [ ] Markdownlint — deferred to Phase 4 (no `.markdownlint.json` yet)
- [ ] Cold-read review by reviewer

Closes #14.
Parent epic: maxdimitrov/trading-bot#153.
Spec: `docs/superpowers/specs/2026-05-27-port-initiative-tracking-skill-design.md` (in this PR).
Plan: `docs/superpowers/plans/2026-05-27-port-initiative-tracking-skill.md` (in this PR).
EOF
)"
```

- [ ] **Step 3.4: Report PR URL and final state to controller**

Capture the PR URL emitted by `gh pr create` and surface it to the operator. Also report:

```bash
git log --oneline -5
# Expected: 4 commits on top of 83fd3c2 — spec, plan, templates, skill+CHANGELOG
git status
# Expected: clean working tree
```

---

## Acceptance (mirrors issue #14 + spec §8)

The PR is mergeable when ALL of these hold:

- [ ] `skills/initiative-tracking/SKILL.md` exists; opens; renders cleanly.
- [ ] `templates/epic-body.md` exists; contains the four exact Status-block field-prefix strings (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) literally.
- [ ] `templates/sub-issue-body.md` exists; contains a `## Parent epic` section (literal).
- [ ] No literal `maxdimitrov/trading-bot` anywhere in the three new files.
- [ ] No `gh api repos/...` snippet in `skills/initiative-tracking/SKILL.md` (the native sub-issue API is owned by `backends/github.md` only).
- [ ] No trading-bot-specific skill or path leaks (PENDING-FIXES, /fix-issue, ic-memo-framework, dca-router, dashboard-maintenance, atr-stops, reserve-ledger, execution-service-architecture, proposal-service-architecture, quant-atelier-design, twr-benchmarking, position-sizing).
- [ ] Skill prose cites `link_sub_issue`, the configured backend (`backends/<backend>.md`), and the generalized read-modify-write warning (`edit_body` cross-backend invariant).
- [ ] Skill prose names both `#N` and `PROJ-123` as acceptable `Next up:` ref syntaxes.
- [ ] Triage gate table preserved verbatim from source (four signal rows).
- [ ] Sibling cross-links present (`feature-request`, `bug-tracking`, `followup-tracking` — at least 3 references).
- [ ] No absolute paths or `~/.claude/` references.
- [ ] CHANGELOG.md `## [Unreleased]` → `### Added` notes the initiative-tracking skill + epic/sub-issue templates landed.
- [ ] Plan file committed to the branch as part of this PR.
- [ ] Spec file committed to the branch as part of this PR.
- [ ] PR title is `Phase 2 (#14): port initiative-tracking skill` and body includes `Closes #14` plus parent epic ref `maxdimitrov/trading-bot#153`.
- [ ] Branch staleness check before push showed `0` on the RIGHT side (origin/main did not move during the work).

---

## Notes

- The cross-repo controller / no-worktree dance is identical to PR #18 (which used a worktree because of a parallel session — this one doesn't need it). Every task starts with `cd F:/Claude/Projects/agent-issue-tracker` and ends with `git log -1` controller-side verification. The subagent CWD discipline rule is the reason these belt-and-suspenders checks exist (project memory `feedback_subagent_cwd_not_worktree`).
- One Phase 2 sub-issue remains after this one: `#15` (skill-currency — write from scratch, not a port). It is unblocked in parallel and can be picked up any time.
- This is the **most-surgery** port of the four (per parent spec §6.2). The bulk of the source skill is preserved verbatim; the four surgical transforms in spec §7 are where the real work happens. The haiku subagent for Task 2 transcribes the verbatim content from Step 2.2 of this plan — interpretive work was done in the brainstorm and locked into the spec.
- This port introduces `templates/epic-body.md` — the most structured template in the plugin (Status block + Phases + Children task-list + Decision log + Resume-from-here). It validates the `templates/*-body.md` non-standard-block pattern for the most complex case after `templates/followup-body.md` (#13) validated it for the medium case.
- The compose-by-reference choice for `templates/sub-issue-body.md` is deliberate divergence from followup-tracking's self-contained pattern, documented in the skill's prose AND the template's preamble. Future-you reading the two templates side-by-side will see the rationale without having to dig.
- The four canonical Status-block field-prefix strings (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) appear in this plan, the design spec §6, the source skill, and will appear in `/resume-initiative` (Phase 3). Any rewording is a load-bearing breaking change.
- No sentinel source file in the workspace this time — the trading-bot source skill is locally readable at `F:/Claude/Projects/Trading/.claude/skills/initiative-tracking/SKILL.md` and the Read tool accepts absolute paths. Subagents read it directly when they need to cross-check.
