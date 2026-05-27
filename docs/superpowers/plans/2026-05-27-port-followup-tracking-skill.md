# Port followup-tracking skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `skills/followup-tracking/SKILL.md` and `templates/followup-body.md` in this plugin as tracker-agnostic ports of the same-named trading-bot skill, satisfying agent-issue-tracker#13 (Phase 2 sub-issue of trading-bot epic #153).

**Architecture:** Mechanical re-application of the de-trading-bot-ification transforms (parent design spec §6.1) over the source skill, mirroring the bug-tracking + feature-request ports shipped in PRs #16/#17. Two new markdown files plus a CHANGELOG line. The template moves out of the inlined SKILL.md body into its own `templates/followup-body.md` file (self-contained: 5 followup-specific blocks first, separator, then the 7 standard agent-prompt blocks). Behaviour-change-zero invariant: the five-extra-block names, bail criteria, label taxonomy (`followup` + type-shape + area), title-suffix convention (reframed to tracker syntax), body-shape semantics, and lifecycle semantics — byte-equivalent to the trading-bot source.

**Tech Stack:** Markdown only — no code, no scripts. `gh` CLI for the PR; `git` for branch and worktree.

---

## Worktree

All work happens in:

```
F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill
```

on branch `feat/port-followup-tracking-skill` (off `origin/main` @ commit `73a31ca` — the PR #17 / Phase 2 #12 feature-request merge).

**Note on cross-repo session:** the controller session's CWD is typically `F:/Claude/Projects/Trading` (the trading-bot repo) or `F:/Claude/Projects/agent-issue-tracker` (the plugin's primary working tree), NEITHER of which is the worktree itself. Every subagent dispatch in this plan MUST start with the literal first action:

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill && git status
```

After each subagent returns, the controller MUST verify the commit landed on the right branch:

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill log -1 --format='%H %s'
```

For 2+ parallel writing subagents, pass `isolation: "worktree"` on the Agent call instead (per the project's global CLAUDE.md "Parallel agents need isolated workspaces" rule). For the serial-task structure of this plan, that's not needed.

---

## File Structure

All paths relative to the worktree root.

| File | Action | Responsibility |
|---|---|---|
| `docs/superpowers/specs/2026-05-27-port-followup-tracking-skill-design.md` | Already exists | Design spec — committed as `8e4049d` before this plan; ships in the PR alongside the new files. |
| `docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md` | Create (this file) | Implementation plan — committed before Task 1 dispatch; ships in the PR. |
| `templates/followup-body.md` | Create | Self-contained 12-block agent-prompt body skeleton: 5 followup-specific blocks (Parent, What's already done, What's been tried / ruled out, Related issues, Why deferred), separator, then 7 standard blocks (Goal, Locus, Skills to load, task-specific-block pointer, Constraints, Acceptance, Verify) + Notes tail. All-placeholder content (no example values); referenced from SKILL.md. |
| `skills/followup-tracking/SKILL.md` | Create | The followup-tracking methodology — when to file, why structure matters, type-orthogonal framing (sibling cross-links to bug-tracking and feature-request), the block-by-block-why-each-matters table, parent-not-yet-landed handling, label taxonomy, lifecycle. Dispatches to `backends/<backend>.md` for filing / edit / list / close operations. |
| `CHANGELOG.md` | Modify | Append one line under `## [Unreleased]` → `### Added`. |

Pure-addition PR (`+~550 / -0` across 4 new files plus the CHANGELOG one-line append).

---

## Pre-flight (do this once before Task 1)

Run from anywhere thanks to `git -C`:

```bash
# 1. Branch is up to date with origin/main
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill fetch origin
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill rev-list --left-right --count HEAD...origin/main
# Expected: "1\t0"
# LEFT = 1: the spec commit 8e4049d already on the branch.
# RIGHT = 0: origin/main has NOT moved since branch was cut.
# If RIGHT > 0: origin/main has moved. Rebase or report to operator before starting Task 1.
```

If RIGHT > 0, abort and surface to the operator.

The `.followup-tracking-source.md` sentinel file used by the brainstorm stays for now — the agent will reference it during Task 2 to verify byte-equivalent ports of preserved sections. It is NOT git-tracked (untracked file in `git status`); pre-PR cleanup happens at the end of Task 3.

```bash
# Confirm sentinel is present and NOT tracked
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill status --porcelain | grep -F .followup-tracking-source.md
# Expected: "?? .followup-tracking-source.md"  (?? = untracked)
```

---

## Plan-commit step (controller does this BEFORE dispatching Task 1)

The controller commits this plan file on the feature branch first so it ships in the PR alongside the spec, the two new files, and the CHANGELOG entry. Mirrors PR #17's pattern.

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill add docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill commit -m "$(cat <<'EOF'
docs(plan): implementation plan for #13 - port followup-tracking skill

Refs #13. Parent epic: trading-bot#153 (Phase 2).
EOF
)"
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill log -1 --format='%H %s'
# Expected: "<sha> docs(plan): implementation plan for #13 - port followup-tracking skill"
```

---

## Task 1: Write `templates/followup-body.md`

**Files:**
- Create: `templates/followup-body.md`

**Subagent CWD discipline:** the implementer's first action MUST be the `cd` + `git status` pair from the Worktree section above. Controller verifies via `git log -1` after return.

**Blast radius:** one new file. Pure-addition. Rollback: `git restore --staged templates/followup-body.md && rm templates/followup-body.md`.

- [ ] **Step 1.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill
git status
git rev-parse --abbrev-ref HEAD
git log -1 --format='%H %s'
```
Expected:
- `On branch feat/port-followup-tracking-skill`
- Working tree clean except for the untracked `.followup-tracking-source.md`
- `feat/port-followup-tracking-skill`
- HEAD message: `docs(plan): implementation plan for #13 - port followup-tracking skill`

- [ ] **Step 1.2: Write `templates/followup-body.md` with this exact content**

Use the Write tool with `file_path: templates/followup-body.md` and this content:

````markdown
# Followup Body Template

This is the canonical agent-prompt body for filing a followup via the
`followup-tracking` skill. Use it verbatim — each section maps to a step
an agent picking up the issue cold will take. The five
**followup-specific** blocks come first (Parent / What's already done /
What's been tried-ruled out / Related issues / Why deferred); a `---`
separator follows; then the seven standard agent-prompt blocks shared
with the `bug-tracking` and `feature-request` siblings.

Sections marked **[required]** are what an agent reads to decide
whether to work the issue or bail.

To file, fill in this template and pass the result as the `body`
argument to your backend's `create_issue` operation. See
`backends/<backend>.md` for the literal invocation.

---

## Parent  **[required]**
What this spun out of. Link the parent PR, the parent issue, the
branch, or the conversation. Use your backend's issue-ref syntax
(`#N` for GitHub, `PROJ-123` for Jira, etc.) — the backend module
renders the syntax; the skill names the intent.
- Spun out of: <parent PR or issue ref, or branch `<branch-name>` if
  not yet merged>
- Discussion: <file:line ref, or "<one-line summary>" if chat-only>
- Date deferred: <YYYY-MM-DD>

## What's already done  **[required]**
Two or three bullets — the load-bearing facts from the parent change
that the next agent needs without re-reading the parent diff.
- <fact 1>
- <fact 2>

## What's been tried / ruled out  **[required]**
Approaches considered in the parent work and discarded, with one-line
reasons. If nothing was tried, write `Nothing tried - design is open`
and tag `needs-design`.
- Tried <X>: rejected because <Y>
- Considered <X>: <reason>

## Related issues
Output of your backend's `list_open_issues` operation filtered to the
same area (optionally by keyword if your backend supports it).
"No related issues found" is a valid entry — it tells the next agent
the search has been done.

## Why deferred  **[required]**
One of:
- **scope** — work was ready, just too large for the parent PR.
- **clarity** — open design question; tag `needs-design`.
- **dependency** — blocked on <issue / PR / external ref>.
- **time** — capacity, not unreadiness.

The next agent uses this to judge whether the deferral was about
capacity (do it now if you have time) or unreadiness (don't touch
until the dependency or design lands).

---

## Goal
<one sentence — the observable outcome after the followup ships. State
the change in terms an outside reader can verify.>

## Locus  **[required]**
- File(s): <repo-relative path(s), e.g. `src/api/foo.py:142`>
- Function/route: <name>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an agent should load before editing. Pick the
ones that codify the touched subsystem.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## <task-specific block>
If the followup is a **bug**: add Symptom / Repro / Expected / Impact
blocks per `templates/bug-body.md`.

If the followup is a **feature**: add What's missing / Sketch blocks
per `templates/feature-body.md`.

## Constraints  **[required]**
- Out of scope: <files/dirs/subsystems the change MUST NOT touch>
- Invariants to preserve: <e.g. "do not change the X algorithm",
  "the Y route must remain mounted">
- Dependencies: <other issues/PRs that must merge first; "none" if
  standalone>
- Style: minimal change; no drive-by refactors; match surrounding code
  style.

## Acceptance  **[required]**
Writable as a test or verifiable observation. An agent will write
tests (or a manual-verify script) that assert each of these BEFORE
changing code; they must pass after the change ships.
- [ ] <criterion 1 - observable, specific, testable>
- [ ] <criterion 2 - observable, specific, testable>

## Verify  **[required]**
Exact commands an agent runs from the clone root to prove the change.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, links to docs the agent should read,
anything that helps it pick up cold but isn't load-bearing. Use your
backend's issue-ref syntax (e.g. `#N` for GitHub, `PROJ-123` for
Jira).>
````

- [ ] **Step 1.3: Verify the template passes the leakage greps**

Run (from the worktree root):
```bash
# Must have no matches (trading-bot path leaks)
grep -E "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" templates/followup-body.md
```
Expected: no output (grep exit code 1 is fine — means no matches).

```bash
# All 5 followup-specific block names present
for block in "Parent" "What's already done" "What's been tried" "Related issues" "Why deferred"; do
  grep -qF "## $block" templates/followup-body.md || echo "MISSING: $block"
done
echo "block-presence check done"
```
Expected: just `block-presence check done` (no MISSING lines).

```bash
# Standard tail section headers present (Goal, Locus, Skills to load, Constraints, Acceptance, Verify, Notes — 7 expected)
grep -E "^## (Goal|Locus|Skills to load|Constraints|Acceptance|Verify|Notes)" templates/followup-body.md | wc -l
```
Expected: `7`.

```bash
# Title-suffix hard-coded check: the literal "(followup #" must NOT appear in the template
# (the skill prose names the convention, the backend module renders the syntax)
grep -F "(followup #" templates/followup-body.md && echo HARD_CODED_TITLE_SUFFIX || echo clean
```
Expected: `clean`.

```bash
# No absolute paths or ~/.claude/ refs
grep -rE "~/\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" templates/followup-body.md && echo BAD_PATH || echo clean
```
Expected: `clean`.

If any check fails, fix the template inline and re-run the suite before committing.

- [ ] **Step 1.4: Commit**

```bash
git add templates/followup-body.md
git commit -m "$(cat <<'EOF'
feat(templates): add followup-body skeleton

Self-contained 12-block agent-prompt body for the followup-tracking
skill. Five followup-specific blocks (Parent / What's already done /
What's been tried-ruled out / Related issues / Why deferred) precede
the standard seven (Goal / Locus / Skills to load / task-specific
block pointer / Constraints / Acceptance / Verify) plus the optional
Notes tail. All-placeholder content; referenced from
skills/followup-tracking/SKILL.md (Task 2).

Block ordering preserves the trading-bot source (followup-context
before target state); deliberate divergence from issue #13's section 6
which ordered Goal first. Behaviour-change-zero invariant.

Refs #13 (Phase 2 of trading-bot epic #153).
EOF
)"
```

Verify:
```bash
git log -1 --format='%H %s'
# Expected: "<sha> feat(templates): add followup-body skeleton"
git rev-parse --abbrev-ref HEAD
# Expected: "feat/port-followup-tracking-skill"
git log --oneline -3
# Expected (most recent first):
#   <sha> feat(templates): add followup-body skeleton
#   <sha> docs(plan): implementation plan for #13 - port followup-tracking skill
#   8e4049d docs(spec): port followup-tracking skill design (#13)
```

---

## Task 2: Write `skills/followup-tracking/SKILL.md` + CHANGELOG entry

**Files:**
- Create: `skills/followup-tracking/SKILL.md`
- Modify: `CHANGELOG.md`

**Subagent CWD discipline:** same as Task 1.

**Blast radius:** one new file + one one-line append. Pure-addition. Rollback: `git reset --hard HEAD~1` (after committing) or `git restore --staged <files> && rm skills/followup-tracking/SKILL.md && git restore CHANGELOG.md` (before committing).

- [ ] **Step 2.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill
git status
git log -1 --format='%H %s'
```
Expected: `On branch feat/port-followup-tracking-skill` + the Task 1 commit message at HEAD.

- [ ] **Step 2.2: Create the skill directory and write `skills/followup-tracking/SKILL.md`**

```bash
mkdir -p skills/followup-tracking
```

Then write `skills/followup-tracking/SKILL.md` with this exact content:

````markdown
---
name: followup-tracking
description: >-
  How follow-ups, scope-deferrals, "later phase" work, and spun-out tasks
  are tracked — they go in the configured issue tracker (see
  `.claude/issue-tracker.yaml`) as enriched issues with the parent
  PR/branch, what has already been done in the spawning change, what has
  been tried or ruled out, related existing issues, and the reason for
  deferral. Issues here are consumed by Claude Code agents, which means
  the body is an **agent prompt**, not a human note - on top of the
  parent/prior-work blocks, the body must satisfy the same locus /
  constraints / writable-acceptance requirements as a plain bug or
  feature issue or no agent can pick it up. Use this skill whenever you
  are about to write "follow-up", "later phase", "out of scope for this
  PR", "we'll handle X in a separate change", "TODO: also do Y",
  "leaving Z for next pass", or otherwise carve scope off an in-flight
  piece of work; whenever the user says "follow-up for that", "track
  that for later", "spin that out", or "do that in a separate PR"; and
  whenever a reviewer's comment surfaces a real-but-out-of-scope
  concern. The siblings bug-tracking (defects) and feature-request (new
  capabilities) cover the type framing - this skill covers the
  *origination* (work deferred from in-flight effort) which is
  orthogonal: a follow-up can be either bug-shaped or feature-shaped.
---

# Follow-up Tracking — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the seven operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the
literal CLI / MCP invocation for each operation.

Follow-ups are not a different *tracker* — they are a different *shape
of issue*. The shape exists because a follow-up exists *because of*
another change: a PR that left scope on the floor, a review comment
that surfaced an adjacent concern, a bug fix that revealed a related
defect.

That parent context is the whole value of filing a follow-up as a
structured issue instead of a code comment or a chat message. **And
it's also what makes a follow-up agent-executable** — when the next
agent picks it up cold weeks later, the parent + prior-work + ruled-out
blocks prevent them from re-deriving discarded approaches.

## Type-orthogonal

A follow-up is either bug-shaped or feature-shaped. This skill adds
five extra blocks (Parent / What's already done / What's been tried-
ruled out / Related issues / Why deferred) on top of the appropriate
sibling skill's body:

- Deferred thing is **broken behaviour** → `bug` label, follow
  `skills/bug-tracking/` for the Symptom / Repro / Expected / Impact
  blocks.
- Deferred thing is a **missing capability or redesign** →
  `enhancement` label, follow `skills/feature-request/` for the
  What's missing / Sketch blocks.

Always add the `followup` label so the configured backend's
`list_open_issues` operation, filtered by `label: followup`, finds
them cleanly.

## Why structure matters

Same bail criteria as the sibling skills: an agent picking the issue
up cold will **bail** (refuse to work it, leave a comment, no PR) on a
fuzzy locus, unbounded scope, an open design question, or no writable
acceptance. The parent / prior-work blocks help, but they don't
substitute — they're *additional* context, not a replacement.

If the follow-up has a real open design question (common for follow-ups
spun out under time pressure), tag `needs-design` and accept that a
human brainstorm runs before any agent works it.

## When to file

File when, mid-task or mid-PR, you find yourself wanting to defer real
work and the deferral is **decision-shaped** — i.e. you have context
the next agent will not, and that context will not survive in chat or
in a code comment.

Strong triggers:

- "Out of scope for this PR but we should also..."
- "Leaving X for a follow-up — the design is unclear."
- "We tried Y, it didn't work because of Z. Should revisit when..."
- Review comment surfaces a real concern that doesn't block merge.
- A bug fix exposes a related-but-distinct defect.
- A feature ships in a minimal form and the next slice has obvious
  work.

Do **not** file when:

- You are doing the work in the current change.
- The "deferral" is a vague maybe.
- The thing is already tracked — use the backend's `list_open_issues`
  operation (optionally filtered by keyword) first. Comment on the
  existing issue with the new context.
- The thing is purely a tactical reminder for the current task — that
  belongs in your task tracker or PR description, not a permanent
  issue.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:`
in `.claude/issue-tracker.yaml`. Pass:

- `type`: `followup`
- `title`: `<component>: <deferred work>` plus a parent reference in
  your tracker's syntax (see Title format below)
- `labels`: `[<bug or enhancement>, <area>, followup]` where `<area>`
  is one of your configured `areas:` enum and the bug-or-enhancement
  choice follows the type-orthogonal rule above
- `body`: the filled-in `templates/followup-body.md` template

**Title format:** `<component>: <deferred work>`. Optionally append a
parent reference in your tracker's syntax — e.g. `(followup #<parent>)`
on GitHub, `(followup <PROJ-N>)` on Jira. The backend module documents
the literal syntax; the skill names the *intent* (the title should
make the parent linkage visible when scanning a backend's
issue-list view).

Examples: `worker/queue: defer dead-letter retention policy`,
`cli/list: ship schema versioning for --json output`.

If the `followup` label doesn't exist on your tracker yet, your
consumer's setup process creates it once — see your backend's
configuration documentation.

## Agent-execution issue body template

The body template lives at `templates/followup-body.md` in this
plugin. Use it verbatim — each section maps to a step an agent picking
up the issue cold will take. Sections marked **[required]** are what
an agent reads to decide whether to work the issue or bail.

See `templates/followup-body.md` for the canonical skeleton with
placeholders. The template is self-contained: the five
followup-specific blocks come first, a `---` separator follows, then
the standard tail. The `<task-specific block>` pointer in the standard
tail names which sibling-template blocks to compose in
(`templates/bug-body.md` or `templates/feature-body.md`) based on
whether the deferred work is bug-shaped or feature-shaped.

### What each block unlocks

- **Parent** — orients the agent: "this exists because of #N". Lets
  the agent open the parent PR and see what shipped vs. what's open.
- **What's already done** — saves the agent from re-reading the
  entire parent diff. Two bullets of context beat 300 lines of diff.
- **What's been tried / ruled out** — the highest-value block.
  Prevents the agent from rediscovering discarded dead ends.
  *Always* include this even if it's "Nothing tried".
- **Related issues** — `list_open_issues` results frozen at file
  time. Saves the agent a search round-trip.
- **Why deferred** — tells the agent whether to pick it up at all. A
  `clarity` deferral with `needs-design` is a hard skip for
  autonomous agents.
- **Locus + Skills + Constraints + Acceptance + Verify** — same bail
  criteria as plain bugs/features. A great parent block doesn't save
  a follow-up with no acceptance criteria.

## When the parent has not landed yet

Link the follow-up by branch instead of by parent-issue-or-PR
reference — PR/issue refs are unstable until merge on some backends,
and a branch name is always stable. Once the parent merges, edit the
follow-up to swap the branch reference for the merged ref.

Use your backend's `edit_body` operation for this — read the current
body, modify the Parent block in memory, write back the whole body.
The contract documents this as a destructive whole-body replace; the
skill is responsible for the read-modify-write cycle.

## Labels

Every follow-up gets:

- One type-shape label: `bug` or `enhancement`.
- One or more area labels from the consumer's
  `.claude/issue-tracker.yaml` `areas:` enum.
- The **`followup`** label.

Triage flags (agents skip):

- `needs-design` — open design question, sketch missing.
- `needs-triage` — required fields missing.

## Closing the loop

A PR that resolves a follow-up must follow the backend's
close-on-merge convention — see `backends/<backend>.md` PR
close-on-merge section. For example, on the `github` backend the
convention is to include `Fixes #N` (for bug-shaped follow-ups) or
`Closes #N` (for feature-shaped) in the PR title or body so GitHub
auto-closes the issue when the PR merges to the default branch.
`Closes` works for both — pick the verb that matches the type-shape.

Other backends document their own conventions (e.g. Jira may
auto-close via a PR-integration hook configured outside the plugin).

Manual closures follow the same convention — use the backend's
`close_issue` operation with a one-line reason if a follow-up turns
out to be resolved another way (superseded, won't-fix, fixed-by-other-
PR).

**Note:** `link_sub_issue` is NOT used for follow-ups. Follow-ups are
not sub-issues; the parent linkage is the body's Parent block plus
the `followup` label. `link_sub_issue` is reserved for the epic →
sub-issue relationship documented in `initiative-tracking`.

## At the start of work

The backend's `list_open_issues` operation filtered by
`{label: followup}` shows the deferred-scope backlog — useful before
starting a new feature in an area, since a related follow-up may
already exist. Filter additionally by `needs-design` to see the
follow-ups that still need a human brainstorm pass before any agent
can work them.

## Example — a well-formed follow-up

A follow-up spun out of the `cli/list --json` feature (from the
`feature-request` example): the initial PR shipped the `--json` flag
without schema versioning. The next slice — adding a `--schema-version`
flag — was deferred.

```markdown
## Parent
- Spun out of: `#<PR ref>` (cli/list --json feature; merged
  YYYY-MM-DD)
- Discussion: review thread on `cli/list.py:render_list`
- Date deferred: 2026-MM-DD

## What's already done
- Initial PR shipped `cli list --json` emitting NDJSON, one JSON
  object per row, matching the existing table field set.
- Default behaviour (no flag) is byte-identical to before.

## What's been tried / ruled out
- Tried embedding a `_schema_version` field in each row: rejected
  because consumers parsing line-by-line shouldn't pay for the
  field on every line.
- Considered a `--schema-version` flag that emits a header line:
  this is the recommended path for the follow-up.

## Related issues
- `list_open_issues` filtered by `cli` area: no other open
  follow-ups in `cli/list`.

## Why deferred
scope — the schema-versioning sub-design was clean enough to ship,
but the initial PR was already at the size limit reviewers prefer.
A separate change keeps the diff readable.

---

## Goal
`cli/list --json` emits an optional header line declaring the schema
version when `--schema-version` is passed, letting downstream
automation lock against a known shape.

## Locus
- File: `cli/list.py:render_list`
- New helper: `cli/_format_json.py:emit_header`
- Subsystem: cli   # from your configured `subsystems:` enum

## Skills to load
- <your-cli-architecture-skill>
- <your-output-format-conventions-skill>

## What's missing
There is no way for a downstream consumer to assert it was given a
shape it understands. `awk` parsers pin against field positions and
break silently when the field set changes.

## Sketch
- Add `cli/_format_json.py:emit_header(version) -> str` returning a
  single NDJSON object like `{"_schema_version": "1"}`.
- `cli/list.py:render_list` emits the header BEFORE the first row
  when `--schema-version` is passed.
- Default behaviour (no `--schema-version` flag) is byte-identical
  to the post-`#<PR ref>` baseline.

## Constraints
- Out of scope: changing field names or types in existing rows
  (would be a breaking change to the post-#<PR ref> baseline).
- Invariants: omitting `--schema-version` produces output
  byte-identical to today.
- Style: minimal change; no drive-by refactors.

## Acceptance
- [ ] `cli list --json --schema-version` prints `{"_schema_version":
  "1"}` as the FIRST line, followed by NDJSON rows.
- [ ] `cli list --json` (no `--schema-version`) output is
  byte-identical to the post-#<PR ref> baseline.
- [ ] Header line is valid NDJSON (parses as a single JSON object on
  one line).

## Verify
```bash
pytest -q tests/test_cli_list.py
pytest -q
```
```

---

See also: `skills/bug-tracking/` (defect-shaped sibling),
`skills/feature-request/` (capability-shaped sibling),
`initiative-tracking` (multi-issue epics — when follow-ups compound
into an initiative).
````

- [ ] **Step 2.3: Edit `CHANGELOG.md` to add the Phase 2 (#13) line**

The current `CHANGELOG.md` has a `## [Unreleased]` section with a `### Added` block listing Phase 0, Phase 1, and Phase 2 (#11, #12) entries. Append the Phase 2 (#13) line to that `### Added` list.

Use the Edit tool. `old_string` matches the last existing `### Added` entry (the Phase 2 #12 feature-request line); `new_string` keeps that entry and appends a newline + the new line.

`old_string`:
```
- Phase 2 (#12): feature-request skill — tracker-agnostic port from trading-bot, mechanical re-application of the #11 transforms. Houses the canonical bug-vs-feature disambig table referenced by `bug-tracking`. New `templates/feature-body.md` skeleton consumed by the skill's body-template section.
```

`new_string`:
```
- Phase 2 (#12): feature-request skill — tracker-agnostic port from trading-bot, mechanical re-application of the #11 transforms. Houses the canonical bug-vs-feature disambig table referenced by `bug-tracking`. New `templates/feature-body.md` skeleton consumed by the skill's body-template section.
- Phase 2 (#13): followup-tracking skill — tracker-agnostic port from trading-bot. Type-orthogonal sibling to bug-tracking + feature-request; covers origination (work deferred from in-flight effort), not type. New `templates/followup-body.md` skeleton — first non-standard body template in the plugin, with five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) preceding the standard tail. Validates the templates/*-body.md pattern for `templates/epic-body.md` (#14).
```

If the exact `old_string` does not match (CHANGELOG drift since PR #17), the agent must read `CHANGELOG.md` first, locate the `## [Unreleased]` → `### Added` block, and append the new line as the LAST entry under it.

Verify:
```bash
grep -E "Phase 2 \(#13\): followup-tracking" CHANGELOG.md
# Expected: one matching line
```

- [ ] **Step 2.4: Run the full acceptance grep suite (issue #13 Verify section)**

```bash
# AC1: files exist
test -f skills/followup-tracking/SKILL.md && echo OK_SKILL || echo MISSING_SKILL
test -f templates/followup-body.md && echo OK_TEMPLATE || echo MISSING_TEMPLATE
# Both must echo OK_*

# AC2: no maxdimitrov/trading-bot literal
grep -r "maxdimitrov/trading-bot" skills/followup-tracking templates/followup-body.md && echo LEAK || echo clean
# Expected: "clean"

# AC3: no trading-bot-specific skill or path leaks
grep -rE "PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" skills/followup-tracking templates/followup-body.md && echo LEAK || echo clean
# Expected: "clean"

# AC4: all 5 followup-specific blocks present in template
for block in "Parent" "What's already done" "What's been tried" "Related issues" "Why deferred"; do
  grep -qF "## $block" templates/followup-body.md || echo "MISSING: $block"
done
echo "block-presence check done"
# Expected: just "block-presence check done"

# AC5: standard tail headers present in template (7 expected)
grep -E "^## (Goal|Locus|Skills to load|Constraints|Acceptance|Verify|Notes)" templates/followup-body.md | wc -l
# Expected: 7

# AC6: skill dispatches to backend via operation contract
grep -E "create_issue|backends/<backend>\.md|configured backend" skills/followup-tracking/SKILL.md | wc -l
# Expected: >=3 (Filing section + body-template-pointer section + Closing-the-loop section all cite the backend)

# AC7: skill cross-links bug-tracking AND feature-request as siblings
grep -E "skills/bug-tracking|skills/feature-request" skills/followup-tracking/SKILL.md | wc -l
# Expected: >=2

# AC8: skill explicitly states the orthogonality
grep -iE "orthogonal|origination|not type" skills/followup-tracking/SKILL.md
# Expected: at least one match

# AC9: title-suffix is tracker-neutral in skill prose
# The literal "(followup #" MAY appear in the skill prose as an example of GitHub-syntax, but ONLY
# as part of a phrase that explicitly names it as the per-backend rendering. Allowed: "e.g. `(followup #<parent>)` on GitHub".
# Verify the literal appears with the GitHub qualifier nearby:
grep -F "(followup #" skills/followup-tracking/SKILL.md
# Expected: appears within ~2 lines of the phrase "on GitHub" or "tracker's syntax"
# Manual eyeball check: confirm the appearance is qualified as a per-backend example, not a hard-coded format.

# AC10: link_sub_issue is explicitly called out as NOT used
grep -F "link_sub_issue" skills/followup-tracking/SKILL.md
# Expected: at least one match, contextually negating its use (e.g. "is NOT used for follow-ups")

# AC11: no absolute paths or ~/.claude/ refs
grep -rE "~/\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" skills/followup-tracking templates/followup-body.md && echo BAD_PATH || echo clean
# Expected: "clean"

# AC12: CHANGELOG entry present
grep -E "Phase 2 \(#13\): followup-tracking" CHANGELOG.md
# Expected: one matching line

# AC13: file size sanity
wc -l skills/followup-tracking/SKILL.md templates/followup-body.md
# Expected (approximate, within ±25%):
#   skills/followup-tracking/SKILL.md   -> 260-320 lines
#   templates/followup-body.md          -> 95-130 lines
```

If any check fails, fix in place and re-run the suite before committing.

- [ ] **Step 2.5: Markdownlint (conditional)**

```bash
[ -f .markdownlint.json ] && npx --yes markdownlint-cli skills/followup-tracking/SKILL.md templates/followup-body.md
[ -f .markdownlint.json ] || echo "no markdownlint config; deferred to Phase 4 per design spec"
```

The plugin does not ship a markdownlint config today (deferred to Phase 4). Skip and report.

- [ ] **Step 2.6: Cold-read review**

Open both files in a fresh view (without the source skill nearby) and verify:

1. The skill prose reads as "this is the methodology" without trading-bot pre-knowledge — no orphaned references, no "see the X skill" pointers that don't resolve in this plugin.
2. The five followup-specific blocks appear FIRST in the template (before `---` and before `## Goal`).
3. The example chains off the `cli/list --json` feature-request example coherently — the reader can follow "this feature shipped without schema versioning, and the followup adds it" without re-reading the sibling skill.
4. The title-suffix convention is named (not hard-coded format-only) — the skill says "include a parent reference in your tracker's syntax" with `(followup #<parent>)` shown as a GitHub example.
5. `link_sub_issue` is explicitly NOT used (note in the Closing-the-loop section).

If any cold-read issue surfaces, fix inline and re-run the AC suite before committing.

- [ ] **Step 2.7: Commit**

```bash
git add skills/followup-tracking/SKILL.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat(skills): port followup-tracking from trading-bot

Tracker-agnostic prose; dispatches to backends/<backend>.md via the
seven-operation contract (create_issue / list_open_issues / edit_body
/ close_issue; explicitly NOT link_sub_issue - that's reserved for
initiative-tracking's epic-to-child relation). Self-contained body
template at templates/followup-body.md (Task 1) - first non-standard
body template in the plugin, validating the templates/*-body.md
pattern for templates/epic-body.md (#14).

Behaviour-change-zero: bail criteria, type-orthogonal framing (bug-
shaped or feature-shaped), the five followup-specific blocks and
their order, label taxonomy (followup + type-shape + area), title-
suffix convention (reframed to tracker syntax per spec section 6.2),
parent-not-yet-landed handling, and lifecycle semantics all
preserved from the trading-bot source.

Trigger phrases in the frontmatter description preserved verbatim.

Example chains off feature-request's cli/list --json feature: a
followup that defers JSON schema versioning to the next slice.

Closes #13.
Refs trading-bot#153 (Phase 2).
EOF
)"
```

Verify:
```bash
git log -4 --format='%H %s'
# Expected (most recent first):
#   <sha> feat(skills): port followup-tracking from trading-bot
#   <sha> feat(templates): add followup-body skeleton
#   <sha> docs(plan): implementation plan for #13 - port followup-tracking skill
#   8e4049d docs(spec): port followup-tracking skill design (#13)
git status
# Expected: "On branch feat/port-followup-tracking-skill" + working tree clean except for untracked .followup-tracking-source.md
```

---

## Task 3: Cleanup sentinel + push branch + create PR

**Files:** none committed — git/gh operations plus working-tree cleanup.

**Subagent CWD discipline:** same as Task 1.

**Blast radius:** removes the untracked `.followup-tracking-source.md` sentinel, pushes the branch to origin, opens the PR. Reversible — `git push origin --delete feat/port-followup-tracking-skill` removes the remote branch; `gh pr close <N>` closes the PR.

- [ ] **Step 3.1: Confirm cwd, branch, staleness, and clean sentinel**

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-followup-tracking-skill
git status
git log --oneline -5
# Expected: four new commits on top of the PR #17 merge (73a31ca):
#   - feat(skills): port followup-tracking from trading-bot
#   - feat(templates): add followup-body skeleton
#   - docs(plan): implementation plan for #13 - port followup-tracking skill
#   - docs(spec): port followup-tracking skill design (#13)
# Working tree dirty only with the untracked .followup-tracking-source.md

git fetch origin
git rev-list --left-right --count HEAD...origin/main
# LEFT side (HEAD) should be exactly 4 (spec + plan + template + skill+CHANGELOG)
# RIGHT side (origin/main) MUST be 0 - if not, origin/main moved during the work; report to operator
```

If RIGHT > 0, STOP and report. Do not push.

```bash
# Remove the brainstorm sentinel file (not part of the PR)
rm -f .followup-tracking-source.md
git status
# Expected: "nothing to commit, working tree clean"
```

- [ ] **Step 3.2: Push branch with upstream tracking**

```bash
git push -u origin feat/port-followup-tracking-skill
```

Expected: branch created on origin, tracking set up. Look for `* [new branch]  feat/port-followup-tracking-skill -> feat/port-followup-tracking-skill` in the output.

- [ ] **Step 3.3: Create the PR**

```bash
gh pr create \
  --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/port-followup-tracking-skill \
  --title "Phase 2 (#13): port followup-tracking skill" \
  --body "$(cat <<'EOF'
## Summary
- Ports the `followup-tracking` skill from `maxdimitrov/trading-bot` to this plugin in tracker-agnostic prose.
- Adds `templates/followup-body.md` — the first non-standard body template in the plugin. Self-contained: five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) precede a `---` separator, then the seven standard agent-prompt blocks shared with `bug-tracking` and `feature-request`.
- Dispatches to `backends/<backend>.md` via the seven-operation contract landed in Phase 1 (#9). Uses `create_issue` / `list_open_issues` / `edit_body` / `close_issue`. Explicitly NOT `link_sub_issue` (follow-ups are not sub-issues; parent linkage is body block + `followup` label).
- Updates CHANGELOG under `[Unreleased]` → `Added`.

## Files
- `skills/followup-tracking/SKILL.md` — new (~285 lines)
- `templates/followup-body.md` — new (~110 lines, self-contained 12 blocks)
- `CHANGELOG.md` — one line appended
- `docs/superpowers/specs/2026-05-27-port-followup-tracking-skill-design.md` — design spec (committed pre-Task 1)
- `docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md` — implementation plan (committed pre-Task 1)

## Decisions settled in brainstorm
1. **Template composition** — self-contained 12-block template (not composed with `templates/feature-body.md` / `templates/bug-body.md`). Matches source body monolith; readers fill in one file.
2. **Block ordering** — five followup-specific blocks come FIRST, separator, then `## Goal` and the standard tail. Deliberate divergence from issue #13's §6 ordering (which had Goal first); behaviour-change-zero is the binding invariant, and the source skill puts context BEFORE target state.
3. **Example** — chains off `feature-request`'s `cli/list --json` example with a follow-up deferring JSON schema versioning to the next slice. Reader has just seen the parent feature; cross-skill narrative consistency.

## Transforms applied (parent spec §6.1, re-applied per #11/#12 precedent)
- `GitHub Issues on maxdimitrov/trading-bot` → "the configured tracker (see `.claude/issue-tracker.yaml`)"
- `gh issue create ...` block → `create_issue` operation dispatch paragraph
- `gh issue list --label followup` → `list_open_issues` operation, filtered by `label: followup`
- `gh issue edit ...` (parent-not-yet-landed handling) → `edit_body` operation, with explicit read-modify-write note
- `gh issue close <N>` → `close_issue` operation
- `Closes #N` / `Fixes #N` lifecycle → "the backend's close-on-merge convention"; verb choice kept as soft type-shape recommendation pointing at the backend doc
- Trading-bot subsystem enum (dashboard / executor / ibkr / proposal-service / execution-service / scheduler / claude-runner / scripts / infra / commands / skills) → consumer-configured `.claude/issue-tracker.yaml` `subsystems:` enum
- Trading-bot area enum (dashboard / backend / frontend / infra) → consumer-configured `areas:` enum; not pinned in the skill
- Trading-bot domain skill cross-links (e.g. ibkr/dca/dashboard skills in source example) — dropped or replaced with `<your-...>` placeholders
- Trading-bot worked example (the `feat/ibind-primary-dispatch` partial-fill UI followup) → generic `cli/list: ship schema versioning for --json output` chained off `feature-request`'s example
- Title-suffix `(followup #<parent>)` — reframed: "include a parent reference in your tracker's syntax (e.g. `(followup #<parent>)` on GitHub, `(followup <PROJ-N>)` on Jira). The backend module renders the syntax; the skill names the intent."
- Trigger phrases in the frontmatter `description:` — preserved verbatim (behaviour-change-zero invariant)

## Type-orthogonal framing
The skill explicitly states followups are type-orthogonal: a followup is either bug-shaped or feature-shaped, and the skill points at the appropriate sibling (`skills/bug-tracking/` or `skills/feature-request/`) for the type-specific block set. The `<task-specific block>` slot in `templates/followup-body.md` names which sibling-template blocks to compose in. This is origination, not type.

## Behaviour-change-zero
Per §8.2 of the parent design spec, the issue body shape, bail criteria, label taxonomy, title-suffix convention (reframed to tracker syntax), and lifecycle semantics are byte-equivalent to the trading-bot source. The five followup-specific block names (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) are preserved verbatim. The Phase 5 cutover PR (against trading-bot) is the explicit gate where trigger-phrase regression is verified end-to-end; this PR only ships the plugin-side port.

## Templates/*-body.md pattern validation
This is the first port whose body template adds fields beyond the standard agent-prompt shape. Confirming the self-contained-template pattern works at this scale validates the approach for `templates/epic-body.md` (#14 initiative-tracking), which has more structured content (Status block + Phases + Children + Decision log).

## Test plan
Static acceptance from issue #13 (no code, no pytest — markdown-only):

- [x] `skills/followup-tracking/SKILL.md` exists
- [x] `templates/followup-body.md` exists; contains all 5 followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) + 7 standard tail headers (Goal / Locus / Skills to load / Constraints / Acceptance / Verify / Notes)
- [x] `grep -r "maxdimitrov/trading-bot" skills/followup-tracking templates/followup-body.md` → no matches
- [x] `grep -rE "PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" skills/followup-tracking templates/followup-body.md` → no matches
- [x] Skill dispatches through the backend contract — `create_issue` / `backends/<backend>.md` / `configured backend` cited (≥3 references)
- [x] Skill cross-links `skills/bug-tracking` and `skills/feature-request` as siblings
- [x] Skill explicitly states the orthogonality (followup is origination, not type)
- [x] Title-suffix convention is reframed in tracker-neutral terms (no hard-coded `(followup #N)` format-only literal; backend module renders the syntax)
- [x] `link_sub_issue` is explicitly noted as NOT used for follow-ups
- [x] CHANGELOG.md has the Phase 2 (#13) line under `[Unreleased]` → `Added`
- [x] No absolute paths or `~/.claude/` refs in skill or template
- [ ] Markdownlint — deferred to Phase 4 (no `.markdownlint.json` yet)
- [ ] Cold-read review by reviewer

Closes #13.
Parent epic: maxdimitrov/trading-bot#153.
Spec: `docs/superpowers/specs/2026-05-27-port-followup-tracking-skill-design.md` (in this PR).
Plan: `docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md` (in this PR).
EOF
)"
```

- [ ] **Step 3.4: Report PR URL and final state to controller**

Capture the PR URL emitted by `gh pr create` and surface it to the operator. Also report:

```bash
git log --oneline -5
# Expected: 4 commits on top of 73a31ca — spec, plan, template, skill+CHANGELOG
git status
# Expected: clean working tree
```

---

## Acceptance (mirrors issue #13)

The PR is mergeable when ALL of these hold:

- [ ] `skills/followup-tracking/SKILL.md` exists; opens; renders cleanly.
- [ ] `templates/followup-body.md` exists; contains all five followup-specific required/optional blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) plus the standard agent-prompt fields.
- [ ] No literal `maxdimitrov/trading-bot` anywhere in the new files.
- [ ] No trading-bot-specific skill cross-links or paths (PENDING-FIXES, /fix-issue, ic-memo-framework, dca-router, dashboard-maintenance, reserve-ledger).
- [ ] Skill dispatches through the backend contract — cites `backends/<backend>.md` and at least one operation name (`create_issue`).
- [ ] Skill cross-links `bug-tracking` and `feature-request` as siblings, and explicitly states the orthogonality (followup is origination, not type).
- [ ] Title-suffix convention is reframed in tracker-neutral terms per spec §6.2 (no hard-coded `(followup #N)` GitHub-syntax-only literal in the skill prose; backend module renders the syntax — the GitHub example is qualified).
- [ ] `link_sub_issue` is explicitly noted as NOT used for follow-ups.
- [ ] CHANGELOG.md `## [Unreleased]` → `### Added` notes the followup-tracking skill landed.
- [ ] Plan file committed to the branch as part of this PR.
- [ ] Spec file committed to the branch as part of this PR.
- [ ] PR title is `Phase 2 (#13): port followup-tracking skill` and body includes `Closes #13` plus parent epic ref `trading-bot#153`.
- [ ] Branch staleness check before push showed `0` on the RIGHT side (origin/main did not move during the work).

---

## Notes

- The cross-repo controller / worktree dance is identical to PR #16 and PR #17. Every task starts with `cd <worktree>` and ends with `git log -1` controller-side verification. The subagent CWD discipline rule is the reason these belt-and-suspenders checks exist (project memory `feedback_subagent_cwd_not_worktree`).
- Two Phase 2 sub-issues remain after this one: `#14` (initiative-tracking) and `#15` (skill-currency). Both unblocked in parallel after this lands.
- This is the first port whose body template adds fields beyond the standard agent-prompt shape. The pattern this validates (self-contained template, source-ordering of context-before-target) feeds directly into `#14`'s `templates/epic-body.md` (more structure: Status block + Phases + Children + Decision log).
- The sentinel `.followup-tracking-source.md` file at the worktree root is a brainstorming artifact (the raw source fetched via `gh api`). It is NOT committed and is removed in Step 3.1.
- Block-ordering: this plan locks in source ordering (5 followup blocks before Goal). The issue body §6 ordered `## Goal` first; this is a deliberate, documented divergence captured in the design spec (Decision 2). The brainstorm rationale: behaviour-change-zero is the binding invariant, AND context-before-target is better methodology for an agent reading the body cold.
