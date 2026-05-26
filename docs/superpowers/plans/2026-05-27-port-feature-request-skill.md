# Port feature-request skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `skills/feature-request/SKILL.md` and `templates/feature-body.md` in this plugin as tracker-agnostic ports of the same-named trading-bot skill, satisfying agent-issue-tracker#12 (Phase 2 sub-issue of trading-bot epic #153).

**Architecture:** Mechanical re-application of the de-trading-bot-ification transforms (parent design spec §6.1, in trading-bot main at `docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`) over the source skill, mirroring the bug-tracking port shipped in PR #16. Two new markdown files plus a CHANGELOG line. The body template moves out of the SKILL.md (where it was inlined) into its own `templates/feature-body.md` file referenced from the skill. Behaviour-change-zero invariant: bail criteria, label taxonomy (`enhancement` + area), title format (`<component>: <capability>`), body shape, lifecycle semantics — byte-identical to the trading-bot source.

**Tech Stack:** Markdown only — no code, no scripts. `gh` CLI for the PR; `git` for branch and worktree.

---

## Worktree

All work happens in:

```
F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill
```

on branch `feat/port-feature-request-skill` (off `origin/main` @ commit `9fd3d66` — the PR #16 / Phase 2 bug-tracking merge).

**Note on cross-repo session:** the controller session's CWD is `F:/Claude/Projects` (and the IDE workspace is `agent-issue-tracker`), NOT the worktree itself. Every subagent dispatch in this plan MUST start with the literal first action:

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill && git status
```

After each subagent returns, the controller MUST verify the commit landed on the right branch:

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill log -1 --format='%H %s'
```

---

## File Structure

All paths relative to the worktree root.

| File | Action | Responsibility |
|---|---|---|
| `templates/feature-body.md` | Create | The canonical agent-prompt body skeleton for features. All-placeholder content (no example values). Referenced from SKILL.md. |
| `skills/feature-request/SKILL.md` | Create | The feature-request methodology — when to file, why structure matters, bug-vs-feature disambig table (canonical home), label taxonomy, lifecycle. Dispatches to `backends/<backend>.md` for filing operations. |
| `CHANGELOG.md` | Modify | Append one line under `## [Unreleased]` → `### Added`. |

---

## Pre-flight (do this once before Task 1)

Run from the controller session's CWD (works from anywhere thanks to `git -C`):

```bash
# 1. Branch is up to date with origin/main
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill fetch origin
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill rev-list --left-right --count HEAD...origin/main
# Expected: "0\t0"  (branch at the same commit as origin/main — the PR #16 merge 9fd3d66)
# If RIGHT side > 0: origin/main has moved since branch was cut. Rebase or report.
```

If RIGHT > 0, abort and surface to the operator before starting Task 1.

Also clean up the source-skill sentinel file used during brainstorming (not part of the PR):

```bash
rm -f F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill/.feature-request-source.md
# Verify it's not git-tracked:
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill status --porcelain | grep -F .feature-request-source.md && echo TRACKED || echo "untracked - safe"
```

---

## Plan-commit step (controller does this BEFORE dispatching Task 1)

The controller commits this plan file on the feature branch first so it ships in the PR alongside the two new files and CHANGELOG entry:

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill add docs/superpowers/plans/2026-05-27-port-feature-request-skill.md
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill commit -m "$(cat <<'EOF'
docs(plan): implementation plan for #12 — port feature-request skill

Refs #12. Parent epic: trading-bot#153 (Phase 2).
EOF
)"
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill log -1 --format='%H %s'
```

---

## Task 1: Write `templates/feature-body.md`

**Files:**
- Create: `templates/feature-body.md`

**Subagent CWD discipline:** the implementer's first action MUST be the `cd` + `git status` pair from the Worktree section above. Controller verifies via `git log -1` after return.

- [ ] **Step 1.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill
git status
git rev-parse --abbrev-ref HEAD
```
Expected output:
- `On branch feat/port-feature-request-skill`
- Working tree clean (plan commit at HEAD)
- `feat/port-feature-request-skill`

- [ ] **Step 1.2: Write `templates/feature-body.md` with this exact content**

Use the Write tool with `file_path: templates/feature-body.md` and this content:

````markdown
# Feature Body Template

This is the canonical agent-prompt body for filing a feature request via
the `feature-request` skill. Use it verbatim — each section maps to a
step an agent picking up the issue cold will take. Sections marked
**[required]** are what an agent reads to decide whether to work the
issue or bail.

To file, fill in this template and pass the result as the `body` argument
to your backend's `create_issue` operation. See `backends/<backend>.md`
for the literal invocation.

---

## Goal
<one sentence — the capability after the change exists. State it as an
observable outcome an outside reader can verify, e.g. "`cli/list`
supports `--json` output and emits one JSON object per row as NDJSON,
matching the existing table output's field set.">

## Locus  **[required]**
- File(s) to add/modify: <repo-relative paths, e.g. `cli/list.py:42`>
- New file(s): <if any, e.g. `cli/_format_json.py`>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an agent should load before editing. Pick the
ones that codify the touched subsystem and any cross-cutting conventions
(output formatting, persistence, UI design) the change touches.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## What's missing  **[required]**
<What does the project not do today? One sentence. Be specific —
"`cli/list` cannot emit machine-readable output" beats "needs better
output support".>

## Why
<The workflow this unblocks or the question it answers. Without this
context, future-you cannot judge whether the idea is still worth
building.>

## Sketch  **[required]**
The shape of the solution. Bullet points are fine. If you don't have a
sketch, write `Open — needs design pass` and tag `needs-design` — an
agent will not work the issue until a sketch exists.

- <step or component 1>
- <step or component 2>

## Constraints  **[required]**
- Out of scope: <files/dirs/subsystems the change MUST NOT touch>
- Invariants to preserve: <e.g. "default behaviour byte-identical when
  the new flag is not passed", "existing route X stays mounted">
- Dependencies: <other issues/PRs that must merge first; "none" if
  standalone>
- Style: minimal change; no drive-by refactors; match surrounding code
  style.

## Acceptance  **[required]**
Writable as a test or a verifiable observation. An agent will write
tests (or a manual-verify script) that assert each of these BEFORE
changing code; they must pass after the change ships.
- [ ] <criterion 1 — observable, specific, testable>
- [ ] <criterion 2 — observable, specific, testable>

## Verify  **[required]**
Exact commands an agent runs from the clone root to prove the change.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, links to docs the agent should read, anything
that helps it pick up cold but isn't load-bearing. Use your backend's
issue-ref syntax (e.g. `#N` for GitHub, `PROJ-123` for Jira).>
````

- [ ] **Step 1.3: Verify the template passes the leakage greps**

Run (from the worktree root):
```bash
# Must have no matches
grep -E "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" templates/feature-body.md
```
Expected: no output (grep exit code 1 is fine — means no matches).

```bash
# Required section headers present (10 expected: Goal, Locus, Skills to load, What's missing, Why, Sketch, Constraints, Acceptance, Verify, Notes)
grep -E "^## (Goal|Locus|Skills to load|What's missing|Why|Sketch|Constraints|Acceptance|Verify|Notes)" templates/feature-body.md | wc -l
```
Expected: `10`.

- [ ] **Step 1.4: Commit**

```bash
git add templates/feature-body.md
git commit -m "$(cat <<'EOF'
feat(templates): add feature-body skeleton

Tracker-agnostic agent-prompt body for the feature-request skill.
All-placeholder content (no example values); referenced from
skills/feature-request/SKILL.md (Task 2).

Refs #12 (Phase 2 of trading-bot epic #153).
EOF
)"
```

Verify:
```bash
git log -1 --format='%H %s'
# Expected: "<sha> feat(templates): add feature-body skeleton"
git rev-parse --abbrev-ref HEAD
# Expected: "feat/port-feature-request-skill"
```

---

## Task 2: Write `skills/feature-request/SKILL.md` + CHANGELOG entry

**Files:**
- Create: `skills/feature-request/SKILL.md`
- Modify: `CHANGELOG.md`

**Subagent CWD discipline:** same as Task 1.

- [ ] **Step 2.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill
git status
git log -1 --format='%H %s'
```
Expected: `On branch feat/port-feature-request-skill` + the Task 1 commit message at HEAD.

- [ ] **Step 2.2: Write `skills/feature-request/SKILL.md` with this exact content**

Create the directory (if not already present) and write the file.

```bash
mkdir -p skills/feature-request
```

Then write `skills/feature-request/SKILL.md` with this exact content:

````markdown
---
name: feature-request
description: >-
  How feature requests, enhancements, new capabilities, and redesigns are
  tracked — they go in the configured issue tracker (see
  `.claude/issue-tracker.yaml`) with the `enhancement` label, not in chat
  and not as `// TODO` code comments. Issues here are consumed by Claude
  Code agents, which means the body is an **agent prompt**, not a human
  note — it must give a clear locus, scope boundaries, and writable
  acceptance criteria or no agent can pick it up. Use this skill whenever
  a new capability, missing feature, redesign idea, "it would be nice
  if...", "we should add...", or planned improvement surfaces; whenever
  filing, triaging, labelling, or closing enhancement issues; when
  opening a PR that ships a requested feature; and any time the user
  says "feature request", "add this to the backlog", "we should build
  X", or asks what is planned vs. shipped. The siblings bug-tracking
  (defects) and followup-tracking (scope deferred from in-flight work)
  cover the other two issue shapes. Covers the capability-vs-defect
  framing, the `enhancement` label + area labels, the agent-execution
  issue body template, the backend dispatch contract from
  `backends/_interface.md`, PR linkage via the backend's close-on-merge
  convention, and the enhancement lifecycle.
---

# Feature Requests — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the seven operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the literal
CLI / MCP invocation for each operation.

A feature idea noted only in chat is forgotten the moment the session
ends. A `// TODO` rots — no one re-reads them. An idea filed as a
well-formed issue can be picked up by a Claude Code agent: the agent
loads the relevant project skills, writes the change, runs the
verification suite, and opens a draft PR. So **the body of every issue
is an agent prompt**, not a human note.

This skill is the enhancement-side counterpart to `bug-tracking`. Same
tracker, same backend dispatch, same lifecycle — different shape of body
(no symptom/repro, but a sketch and an acceptance contract).

## Why structure matters

A vague feature request burns an agent run on guesswork. A structured
one bounds the work and ships a draft PR. An agent (an issue-fix agent
if your project has one, or any agent picking the issue up cold) will
**bail** (refuse to work it, leave a comment, no PR) on:

- No clear locus — body doesn't name where the feature lives.
- Open design question — there's a real choice the agent can't make
  unilaterally.
- No writable acceptance signal — no measurable "done when".
- Unbounded scope — body lists "and also..." for several pages.

If the feature has a real open design question, that's fine — file it
anyway, tag `needs-design`, and accept that a human pass (likely a
brainstorm) happens before any agent works it.

## Bug vs. feature — quick disambig

| Signal | Bug | Feature |
|---|---|---|
| Existing behaviour is wrong | yes | no |
| Component crashes / returns wrong value | yes | no |
| Capability does not exist yet | no | yes |
| "It would be nice if..." | no | yes |
| User-visible regression | yes | no |
| Refactor / redesign of working code | no | yes |

If it's scope spun out of an in-flight PR, use `followup-tracking` instead.

## When to file

File a feature request when:

- You want a capability the project does not have yet — a new command,
  a new UI panel, a new endpoint, a new automation.
- An existing feature works correctly but could be materially better —
  a redesign, a UX improvement, a new flag, a performance pass.
- The user says "we should also add X" or "let's track that for later"
  and the thing is genuinely new capability.

Do **not** file when:

- You are building it right now in the current change.
- It is pure speculation with no clear user value.
- It already exists — search the tracker first (your backend's
  `list_open_issues` operation, optionally filtered by keyword). If a
  similar issue exists, comment on it with the new context instead of
  duplicating.
- The thing is broken — that's a bug; use `bug-tracking`.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:` in
`.claude/issue-tracker.yaml`. Pass:

- `type`: `feature`
- `title`: `<component>: <capability>` (see Title format below)
- `labels`: `[enhancement, <area>]` where `<area>` is one of your
  configured `areas:` enum
- `body`: the filled-in `templates/feature-body.md` template

**Title format:** `<component>: <capability>`. Component is the
path-like locus (e.g. `cli/list`, `worker/queue`, `dashboard/overview`).
Examples: `cli/list: support --json output format`,
`worker/queue: add dead-letter retention policy`,
`dashboard/overview: per-environment status panel`.

## Agent-execution issue body template

The body template lives at `templates/feature-body.md` in this plugin.
Use it verbatim — each section maps to a step an agent picking up the
issue cold will take. Sections marked **[required]** are what an agent
reads to decide whether to work the issue or bail.

See `templates/feature-body.md` for the canonical skeleton with
placeholders.

### What each required field unlocks

- **Locus** — names where the feature lives so the agent knows what to
  open first. New files should be named.
- **Skills to load** — gets the agent the subsystem conventions; without
  this it may invent patterns that conflict with existing code.
- **What's missing + Why** — frames the problem so an agent can judge
  whether its draft solves it.
- **Sketch** — bounds the solution space. An empty Sketch with
  `needs-design` tag is honest; a missing Sketch is bait-and-switch.
- **Constraints** — bounds the blast radius. Most "small features"
  sprawl because no one wrote down what's out of scope.
- **Acceptance** — must be testable. Vague acceptance is the most common
  reason agent drafts get rejected at review.
- **Verify** — the exact commands the agent runs at the end.

## Labels

| Type | Meaning |
|---|---|
| `enhancement` | A new capability, redesign, or improvement. |
| `bug` | (sibling skill) A defect, regression, or known gap. |

**Area labels** are project-specific. The consumer's
`.claude/issue-tracker.yaml` lists the project's valid `areas:` enum
(e.g. `dashboard / backend / frontend / infra`, or whatever the consumer
chose). Pick the matching area from that enum when filling the `area`
label.

Triage flags:
- `needs-design` — open design question, no sketch yet.
- `needs-triage` — body is missing required fields.

Agents skip both.

## Closing the loop

A PR that ships a feature must follow the backend's close-on-merge
convention — see `backends/<backend>.md` PR close-on-merge section.

For example, on the `github` backend the convention is to include the
literal line `Closes #N` in the PR title or body so GitHub auto-closes
the issue when the PR merges to the default branch. Prefer `Closes`
over `Fixes` for feature PRs — the thing wasn't broken; the linguistic
distinction is a recommendation, not a backend-enforced rule. Other
backends document their own conventions (e.g. Jira may auto-close via a
PR-integration hook configured outside the plugin).

If the idea is abandoned (better path found, no longer relevant,
won't-build), close by hand with the backend's `close_issue` operation
and a one-line reason.

## At the start of work

The backend's `list_open_issues` operation filtered by `{type: feature}`
shows the current capability backlog — useful before proposing new
direction. Filter additionally by the `needs-design` label to see the
ideas that still need a human brainstorm pass.

## Example — a well-formed feature request

```markdown
## Goal
`cli/list` supports a `--json` output format that emits each row as a
JSON object on its own line (NDJSON), instead of only the existing
human-formatted table.

## Locus
- File: `cli/list.py:42` (`render_list`)
- New helper: `cli/_format_json.py` (pure functions)
- Subsystem: cli   # from your configured `subsystems:` enum

## Skills to load
- <your-cli-architecture-skill>
- <your-output-format-conventions-skill>

## What's missing
`cli/list` only prints a fixed-width table. Downstream automation has
no machine-readable shape — consumers pipe through `awk` to parse.

## Why
A scriptable `--json` flag unblocks an automation that currently shells
out, parses, and reformats the table. It also lays the groundwork for
a planned `--format=<json|table|csv>` family. Without it, every
consumer reinvents the parser.

## Sketch
- Add `cli/_format_json.py` with `to_ndjson(rows) -> str` — pure, no
  I/O.
- `cli/list.py:render_list` branches on the `--json` flag.
- Default behaviour (no flag) is byte-identical to today.
- No schema versioning yet — out of scope.

## Constraints
- Out of scope: the storage layer that produces `rows` — already stable.
- Invariants: existing table output is byte-identical when `--json` is
  not passed.
- Dependencies: none.
- Style: minimal change; no drive-by refactors.

## Acceptance
- [ ] `cli list --json` prints one JSON object per row, NDJSON-shaped.
- [ ] `cli list` (no flag) output is byte-identical to before.
- [ ] Empty result set with `--json` prints zero lines, exit 0.

## Verify
```bash
pytest -q tests/test_cli_list.py
pytest -q
```
```

---

See also: `skills/bug-tracking/` for the defect-shaped sibling.
`followup-tracking` (scope deferred from in-flight work),
`initiative-tracking` (multi-issue epics).
````

- [ ] **Step 2.3: Edit `CHANGELOG.md`**

The current `CHANGELOG.md` has a `## [Unreleased]` section with a `### Added` block listing Phase 0, Phase 1, and Phase 2 (#11) entries. Append the Phase 2 (#12) line to that `### Added` list.

Use the Edit tool. `old_string` matches the last existing `### Added` entry (the Phase 2 #11 line); `new_string` keeps that entry and appends a newline + the new line.

`old_string`:
```
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from trading-bot; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-trading-bot-ification pattern for #12/#13/#14/#15.
```

`new_string`:
```
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from trading-bot; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-trading-bot-ification pattern for #12/#13/#14/#15.
- Phase 2 (#12): feature-request skill — tracker-agnostic port from trading-bot, mechanical re-application of the #11 transforms. Houses the canonical bug-vs-feature disambig table referenced by `bug-tracking`. New `templates/feature-body.md` skeleton consumed by the skill's body-template section.
```

Verify:
```bash
grep -E "Phase 2 \(#12\): feature-request" CHANGELOG.md
# Expected: one matching line
```

- [ ] **Step 2.4: Run the full acceptance grep suite (issue #12 Verify section)**

```bash
# AC1 + AC2: files exist
test -f skills/feature-request/SKILL.md && echo OK_SKILL || echo MISSING_SKILL
test -f templates/feature-body.md && echo OK_TEMPLATE || echo MISSING_TEMPLATE
# Both must echo OK_*

# AC3 + AC4: no trading-bot leakage
grep -rE "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|quant-atelier-design|twr-benchmarking|position-sizing" skills/feature-request templates/feature-body.md && echo LEAK || echo clean
# Expected: "clean"

# AC5: skill dispatches to backend via operation contract
grep -E "create_issue|backends/<backend>\.md|configured backend" skills/feature-request/SKILL.md | wc -l
# Expected: >=1 (and "Invoke the configured backend's `create_issue` operation" should appear)

# AC6: bug-vs-feature disambig table present in this skill (canonical home)
grep -E "^## Bug vs\. feature" skills/feature-request/SKILL.md
# Expected: one matching line

# AC7: template has all required section headers
grep -E "^## (Goal|Locus|Skills to load|What's missing|Why|Sketch|Constraints|Acceptance|Verify|Notes)" templates/feature-body.md | wc -l
# Expected: 10

# AC8: no absolute paths or ~/.claude/ refs in skill or template
grep -rE "~/\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" skills/feature-request templates/feature-body.md && echo BAD_PATH || echo clean
# Expected: "clean"

# AC9: CHANGELOG entry
grep -E "Phase 2 \(#12\): feature-request" CHANGELOG.md
# Expected: one matching line

# AC10 (issue #12 Verify): bug-vs-feature awk-diff against bug-tracking
# bug-tracking currently does NOT mirror the table (it only has a sibling pointer),
# so this skill is the canonical home. The diff will show feature-request's section
# vs an empty awk output. That is the expected state per issue body design decision.
diff <(awk '/Bug vs\./,/^## /' skills/bug-tracking/SKILL.md) \
     <(awk '/Bug vs\./,/^## /' skills/feature-request/SKILL.md) | head -5
# Expected: a diff showing this skill has the table and bug-tracking does not.
# This is fine — note in the PR body that the canonical copy lives here.
```

If any check fails, fix in place and re-run the suite before committing.

- [ ] **Step 2.5: Markdownlint (conditional)**

```bash
[ -f .markdownlint.json ] && npx --yes markdownlint-cli skills/feature-request/SKILL.md templates/feature-body.md
[ -f .markdownlint.json ] || echo "no markdownlint config; deferred to Phase 4 per design spec"
```

The plugin does not ship a markdownlint config today (deferred to Phase 4). Skip and report.

- [ ] **Step 2.6: Commit**

```bash
git add skills/feature-request/SKILL.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat(skills): port feature-request from trading-bot

Tracker-agnostic prose; dispatches to backends/<backend>.md via the
seven-operation contract. Body template extracted to
templates/feature-body.md (Task 1). CHANGELOG entry added.

Houses the canonical bug-vs-feature disambig table referenced by the
bug-tracking sibling (which uses a name-only pointer rather than
mirroring the table).

Behaviour-change-zero: bail criteria, label taxonomy (enhancement +
area), title format (<component>: <capability>), body shape, and
lifecycle semantics all preserved from the trading-bot source.
Trigger phrases in the description preserved verbatim.

Closes #12.
Refs trading-bot#153 (Phase 2).
EOF
)"
```

Verify:
```bash
git log -3 --format='%H %s'
# Expected (most recent first):
#   <sha> feat(skills): port feature-request from trading-bot
#   <sha> feat(templates): add feature-body skeleton
#   <sha> docs(plan): implementation plan for #12 — port feature-request skill
git status
# Expected: "On branch feat/port-feature-request-skill" + "nothing to commit, working tree clean"
```

---

## Task 3: Push branch + create PR

**Files:** none — git/gh operations only.

**Subagent CWD discipline:** same as Task 1.

- [ ] **Step 3.1: Confirm cwd, branch, and staleness**

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+port-feature-request-skill
git status
git log --oneline -5
# Expected: three new commits on top of the PR #16 merge (9fd3d66)

git fetch origin
git rev-list --left-right --count HEAD...origin/main
# LEFT side (HEAD) should be exactly 3 (plan + template + skill+CHANGELOG)
# RIGHT side (origin/main) MUST be 0 — if not, origin/main moved during the work; report to operator
```

If RIGHT > 0, STOP and report. Do not push.

- [ ] **Step 3.2: Push branch with upstream tracking**

```bash
git push -u origin feat/port-feature-request-skill
```

Expected: branch created on origin, tracking set up.

- [ ] **Step 3.3: Create the PR**

```bash
gh pr create \
  --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/port-feature-request-skill \
  --title "Phase 2 (#12): port feature-request skill" \
  --body "$(cat <<'EOF'
## Summary
- Ports the `feature-request` skill from `maxdimitrov/trading-bot` to this plugin in tracker-agnostic prose.
- Extracts the agent-prompt body template into `templates/feature-body.md`; the skill now references it instead of inlining.
- Dispatches to `backends/<backend>.md` via the seven-operation contract landed in Phase 1 (#9).
- Houses the canonical bug-vs-feature disambig table (referenced by the `bug-tracking` sibling).
- Updates CHANGELOG under `[Unreleased]` → `Added`.

## Files
- `skills/feature-request/SKILL.md` — new (~200 lines)
- `templates/feature-body.md` — new (~90 lines)
- `CHANGELOG.md` — one line appended
- `docs/superpowers/plans/2026-05-27-port-feature-request-skill.md` — implementation plan committed alongside

## Transforms applied (parent spec §6.1, re-applied per #11 precedent)
- `GitHub Issues on maxdimitrov/trading-bot` → "the configured tracker (see `.claude/issue-tracker.yaml`)"
- `gh issue create ...` block → `create_issue` operation dispatch paragraph (spec §5.2)
- `/fix-issue` reference + "auto-fixer v1" caveat → "an agent picking the issue up cold" / "an issue-fix agent (if your project has one)"
- `gh issue list --label enhancement` → `list_open_issues` operation, filtered by `{type: feature}`
- `gh issue close <N>` → `close_issue` operation
- `Closes #N` lifecycle → "the backend's close-on-merge convention"; the `Closes`-vs-`Fixes` linguistic recommendation kept as a soft hint pointing at the backend doc
- Trading-bot subsystem enum (dashboard/executor/ibkr/proposal-service/execution-service/scheduler/claude-runner/scripts/infra/commands/skills) → consumer-configured `.claude/issue-tracker.yaml` `subsystems:` enum
- Trading-bot area enum (dashboard/backend/frontend/infra) → consumer-configured `areas:` enum; example list kept as illustration only
- Trading-bot domain skill cross-links (`quant-atelier-design`, `twr-benchmarking`, `position-sizing`) — dropped or replaced with `<your-...>` placeholders
- Trading-bot worked example (`/portfolio` realised-P&L-by-sleeve) → generic `cli/list: support --json output format` (per issue spec §6.2)
- Trigger phrases in the frontmatter `description:` — preserved verbatim (behaviour-change-zero invariant)

## Bug-vs-feature disambig — canonical home
The source skill ships the disambig table. The sibling `bug-tracking` (PR #16) currently uses a name-only sibling pointer ("goes through `feature-request`") rather than mirroring the table. This PR makes `feature-request` the canonical home: the cross-link from `bug-tracking` is live, and there is no drift because there is no mirror to drift from. The issue #12 Verify section's awk-diff check is expected to show this skill having the table and `bug-tracking` not — flagged in the file so reviewers can confirm the design decision.

## Behaviour-change-zero
Per §8.2 of the parent design spec, the issue body shape, bail criteria, label taxonomy, title format (`<component>: <capability>`), and lifecycle semantics are byte-identical to the trading-bot source. The Phase 5 cutover PR (against trading-bot) is the explicit gate where trigger-phrase regression is verified end-to-end; this PR only ships the plugin-side port.

## Test plan
Static acceptance from issue #12 (no code, no pytest — markdown-only):

- [x] `skills/feature-request/SKILL.md` exists
- [x] `templates/feature-body.md` exists with all 10 section headers (Goal, Locus, Skills to load, What's missing, Why, Sketch, Constraints, Acceptance, Verify, Notes)
- [x] `grep -rE "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|...|quant-atelier-design|twr-benchmarking|position-sizing" skills/feature-request templates/feature-body.md` — no matches
- [x] `grep -E "create_issue|backends/<backend>\\.md|configured backend" skills/feature-request/SKILL.md` — at least 1 match
- [x] Bug-vs-feature disambig table present in this skill
- [x] Plugin-relative cross-links only (no `~/.claude/`, no absolute paths, no Windows drives)
- [x] CHANGELOG.md has the Phase 2 (#12) line under `[Unreleased]` → `Added`
- [ ] Markdownlint — deferred to Phase 4 (no `.markdownlint.json` yet)
- [ ] Cold-read review by operator

Closes #12.
Parent epic: maxdimitrov/trading-bot#153.
Plan: `docs/superpowers/plans/2026-05-27-port-feature-request-skill.md` (in this PR).
EOF
)"
```

- [ ] **Step 3.4: Report PR URL and final state to controller**

Capture the PR URL emitted by `gh pr create` and surface it to the operator. Also report:

```bash
git log --oneline -5
# Expected: 3 commits on top of 9fd3d66 — plan, template, skill+CHANGELOG
```

---

## Acceptance (mirrors issue #12)

The PR is mergeable when ALL of these hold:

- [ ] `skills/feature-request/SKILL.md` exists; opens; renders cleanly.
- [ ] `templates/feature-body.md` exists; contains every section the skill marks `**[required]**` with placeholder prose (plus the optional Goal/Why/Notes).
- [ ] No literal `maxdimitrov/trading-bot` anywhere in `skills/feature-request/` or `templates/feature-body.md`.
- [ ] No literal `PENDING-FIXES`, no `/fix-issue` reference, no trading-bot-specific skill cross-link.
- [ ] Skill prose dispatches to the backend via the operation contract — at least one of `create_issue` + `backends/<backend>.md` reference is present.
- [ ] Bug-vs-feature disambig table appears in this skill (the canonical copy); `bug-tracking` sibling currently uses a name-only pointer — no drift.
- [ ] Skill cross-links use plugin-relative paths only — no `~/.claude/skills/`, no absolute paths, no Windows drive letters.
- [ ] `CHANGELOG.md` gains an `## [Unreleased]` → `### Added` entry noting the feature-request skill landed.
- [ ] Plan file committed to the branch as part of this PR.
- [ ] PR title is `Phase 2 (#12): port feature-request skill` and body includes `Closes #12` plus parent epic ref `trading-bot#153`.
- [ ] Branch staleness check before push showed `0` on the RIGHT side (origin/main did not move during the work).

---

## Notes

- The smoke test from the issue's Verify section (the awk-diff against bug-tracking) is expected to show the table living only in `feature-request`. This is the design decision called out in the issue body ("identical content as the mirror in bug-tracking" — or, per the parenthetical, "one cites the other"). bug-tracking's pointer is the cite.
- The cross-repo controller / worktree dance is identical to PR #16. Every task starts with `cd <worktree>` and ends with `git log -1` controller-side verification. The subagent CWD discipline rule is the reason these belt-and-suspenders checks exist.
- Three Phase 2 sub-issues remain after this one (#13 followup-tracking, #14 initiative-tracking, #15 skill-currency). The transform table established in #11 + re-applied here is the model for those.
- The sentinel `.feature-request-source.md` file at the worktree root is a brainstorming artifact (the raw source fetched via `gh api`); it is NOT committed and should be removed in pre-flight.
