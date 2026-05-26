# Port bug-tracking skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `skills/bug-tracking/SKILL.md` and `templates/bug-body.md` in this plugin as tracker-agnostic ports of the same-named trading-bot skill, satisfying agent-issue-tracker#11 (Phase 2 sub-issue of trading-bot epic #153).

**Architecture:** Apply spec §6.1 transforms (parent design spec on trading-bot main at `docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`) to the source skill. Two new markdown files plus a CHANGELOG line. The body template moves out of the SKILL.md (where it was inlined) into its own `templates/bug-body.md` file referenced from the skill. Behaviour-change-zero invariant: bail criteria, label taxonomy, title format, body shape, lifecycle semantics all byte-identical to the source.

**Tech Stack:** Markdown only — no code, no scripts. `gh` CLI for the PR; `git` for branch and worktree.

---

## Worktree

All work happens in:

```
F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking
```

on branch `feat/issue-11-bug-tracking` (off `origin/main` @ commit `74c1d2e` — the Phase 1 merge).

**Note on cross-repo session:** the controller session's CWD is `F:/Claude/Projects/Trading`, NOT the worktree. Every subagent dispatch in this plan MUST start with the literal first action:

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking && git status
```

After each subagent returns, the controller MUST verify the commit landed on the right branch:

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking log -1 --format='%H %s'
```

---

## File Structure

All paths relative to the worktree root.

| File | Action | Responsibility |
|---|---|---|
| `templates/bug-body.md` | Create | The canonical agent-prompt body skeleton. All-placeholder content (no example values). Referenced from SKILL.md. |
| `skills/bug-tracking/SKILL.md` | Create | The bug-tracking methodology — when to file, why structure matters, label taxonomy, lifecycle. Dispatches to `backends/<backend>.md` for filing operations. |
| `CHANGELOG.md` | Modify | Append one line under `## [Unreleased]` → `### Added`. |

---

## Pre-flight (do this once before Task 1)

Run from the controller session's CWD (works from anywhere thanks to `git -C`):

```bash
# 1. Branch is up to date with origin/main
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking fetch origin
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking rev-list --left-right --count HEAD...origin/main
# Expected: "0\t0"  (branch at the same commit as origin/main — the Phase 1 merge)
# If RIGHT side > 0: origin/main has moved since branch was cut. Rebase or report.
```

If RIGHT > 0, abort and surface to the operator before starting Task 1. The Phase 2 base must be Phase 1 merged.

---

## Plan-commit step (controller does this BEFORE dispatching Task 1)

The controller commits this plan file on the feature branch first so it ships in the PR alongside the two new files and CHANGELOG entry:

```bash
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking add docs/superpowers/plans/2026-05-26-port-bug-tracking-skill.md
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking commit -m "$(cat <<'EOF'
docs(plan): implementation plan for #11 — port bug-tracking skill

Refs #11. Parent epic: trading-bot#153 (Phase 2).
EOF
)"
git -C F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking log -1 --format='%H %s'
```

---

## Task 1: Write `templates/bug-body.md`

**Files:**
- Create: `templates/bug-body.md`

**Subagent CWD discipline:** the implementer's first action MUST be the `cd` + `git status` pair from the Worktree section above. Controller verifies via `git log -1` after return.

- [ ] **Step 1.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking
git status
git rev-parse --abbrev-ref HEAD
```
Expected output:
- `On branch feat/issue-11-bug-tracking`
- `nothing to commit, working tree clean` (or empty, before changes)
- `feat/issue-11-bug-tracking`

- [ ] **Step 1.2: Write `templates/bug-body.md` with this exact content**

Use the Write tool with `file_path: templates/bug-body.md` and this content:

````markdown
# Bug Body Template

This is the canonical agent-prompt body for filing a bug via the
`bug-tracking` skill. Use it verbatim — each section maps to a step an
issue-fix agent will take. Sections marked **[required]** are what an agent
reads to decide auto-fix vs bail.

To file, fill in this template and pass the result as the `body` argument to
your backend's `create_issue` operation. See `backends/<backend>.md` for the
literal invocation.

---

## Goal
<one sentence — the observable outcome after the fix. State the change in
terms an outside reader can verify, e.g. "POST /api/foo returns 200 with a
`bar` field instead of 502 when called with X.">

## Locus  **[required]**
- File(s): <repo-relative path(s), e.g. `src/api/foo.py:142`>
- Function/route: <name>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an issue-fix agent should load before editing.
Pick the ones that codify the touched subsystem.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## Symptom  **[required]**
<What you see go wrong. One or two sentences.>

## Repro  **[required]**
Exact command(s) or steps. Paste verbatim error output in a fenced block.
```bash
<exact command>
```
```
<verbatim error output>
```

## Expected
<What should happen instead. Be specific — "returns 200 with field X" beats
"works correctly".>

## Impact  **[required]**
One of your project's impact categories (e.g. `blocks-release` /
`blocks-deploy` / `degrades-UX` / `cosmetic` / `data-loss-risk`). Add one
sentence of context.

## Root cause hypothesis (optional)
<If you have a guess, write it. An issue-fix agent uses this as a starting
hypothesis but will verify before changing code.>

## Constraints
- Out of scope: <files/dirs/subsystems the fix MUST NOT touch>
- Invariants to preserve: <e.g. "do not change the X algorithm",
  "the Y route must remain mounted">
- Style: minimal fix; no drive-by refactors; match surrounding code style.

## Acceptance  **[required]**
Writable as a regression test. An issue-fix agent will write a test that
asserts each of these BEFORE changing code; the test must FAIL on the base
branch and PASS after the fix.
- [ ] <criterion 1 — observable, specific, testable>
- [ ] <criterion 2 — observable, specific, testable>

## Verify  **[required]**
Exact commands an issue-fix agent runs from the clone root to prove the fix.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, anything that helps an agent pick up cold but
isn't load-bearing. Use your backend's issue-ref syntax (e.g. `#N` for
GitHub, `PROJ-123` for Jira).>
````

- [ ] **Step 1.3: Verify the template passes the leakage greps**

Run (from the worktree root):
```bash
# Must have no matches
grep -E "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture" templates/bug-body.md
```
Expected: no output (grep exit code 1 is fine — means no matches).

```bash
# Required sections present
grep -E "^## (Goal|Locus|Skills to load|Symptom|Repro|Expected|Impact|Root cause hypothesis|Constraints|Acceptance|Verify|Notes)" templates/bug-body.md | wc -l
```
Expected: `12` (all twelve section headers present).

- [ ] **Step 1.4: Commit**

```bash
git add templates/bug-body.md
git commit -m "$(cat <<'EOF'
feat(templates): add bug-body skeleton

Tracker-agnostic agent-prompt body for the bug-tracking skill.
All-placeholder content (no example values); referenced from
skills/bug-tracking/SKILL.md (Task 2).

Refs #11 (Phase 2 of trading-bot epic #153).
EOF
)"
```

Verify:
```bash
git log -1 --format='%H %s'
# Expected: "<sha> feat(templates): add bug-body skeleton"
git rev-parse --abbrev-ref HEAD
# Expected: "feat/issue-11-bug-tracking"
```

---

## Task 2: Write `skills/bug-tracking/SKILL.md` + CHANGELOG entry

**Files:**
- Create: `skills/bug-tracking/SKILL.md`
- Modify: `CHANGELOG.md`

**Subagent CWD discipline:** same as Task 1.

- [ ] **Step 2.1: Confirm cwd and branch**

Run:
```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking
git status
git log -1 --format='%H %s'
```
Expected: `On branch feat/issue-11-bug-tracking` + the Task 1 commit message at HEAD.

- [ ] **Step 2.2: Write `skills/bug-tracking/SKILL.md` with this exact content**

Create the directory (if not already present) and write the file.

```bash
mkdir -p skills/bug-tracking
```

Then write `skills/bug-tracking/SKILL.md` with this exact content:

````markdown
---
name: bug-tracking
description: >-
  How bugs, defects, and regressions are tracked — they go in the configured
  issue tracker (see `.claude/issue-tracker.yaml`) with the `bug` label, not
  in chat. Issues here are consumed by Claude Code agents (e.g. via an
  issue-fix loop), which means the body is an **agent prompt**, not a human
  note — it must give a clear locus, small blast radius, no open design
  question, and writable regression test, or an agent picking it up cold
  will refuse to work it. Use this skill whenever a real defect, regression,
  or broken behaviour surfaces; whenever filing, triaging, labelling, or
  closing a bug; when opening a PR that resolves a bug; and any time the
  user mentions bug tracking, defects, the known-broken list, or "we should
  track this" in a defect context. The siblings feature-request (new
  capabilities) and followup-tracking (scope deferred from in-flight work)
  cover the other two issue shapes. Covers the configured tracker as
  canonical, the label taxonomy, the agent-execution issue body template,
  the backend dispatch contract from `backends/_interface.md`, PR linkage
  via the backend's close-on-merge convention, and the issue lifecycle.
---

# Bug Tracking — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the seven operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the literal
CLI / MCP invocation for each operation.

A bug noted only in chat is lost the moment the session ends. A bug filed
as a well-formed issue can be picked up by an issue-fix agent (if your
project has one) — typically a headless agent that clones the repo, writes
a failing regression test, makes a minimal fix, runs the full verification
suite, and opens a draft PR. So **the body of every issue is an agent
prompt**, not a human note.

## Why structure matters

An agent picking the issue up cold will **bail** (refuse to work it, leave
a comment, no PR) on any of:

- No clear locus — body doesn't name a file/function/route.
- Large blast radius — the change would span many files or subsystems.
- Open design question — there's a real choice to make.
- No writable regression test — no measurable signal that "fixed" means
  fixed.

A vague body wastes an agent run. A structured body gets a draft PR back.

## When to file

File an issue when:

- A real defect, regression, or broken behaviour surfaces — even mid-task,
  even if it isn't what you were working on.
- A known gap or limitation needs to be tracked.

Do **not** file an issue when:

- You are fixing it right now in the current change — just fix it, and
  describe it in the PR.
- It is pure speculation, not an observed problem.
- It already exists — search the tracker (your backend's
  `list_open_issues` operation, optionally filtered by keyword) first.
- It is feature-shaped (missing capability) — that goes through
  `feature-request`.
- It is scope deferred from an in-flight change — that goes through
  `followup-tracking`.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:` in
`.claude/issue-tracker.yaml`. Pass:

- `type`: `bug`
- `title`: `<component>: <symptom>` (see Title format below)
- `labels`: `[bug, <area>]` where `<area>` is one of your configured
  `areas:` enum
- `body`: the filled-in `templates/bug-body.md` template

**Title format:** `<component>: <symptom>`. Component is the path-like
locus (e.g. `worker/queue`, `cli/auth`, `services/payments`). Examples:
`worker/queue: retry returns 500 on dead-letter messages`,
`cli/auth: login fails when token is whitespace-padded`.

## Agent-execution issue body template

The body template lives at `templates/bug-body.md` in this plugin. Use it
verbatim — each section maps to a step an issue-fix agent will take.
Sections marked **[required]** are what an agent reads to decide auto-fix
vs bail.

See `templates/bug-body.md` for the canonical skeleton with placeholders.

### What each required field unlocks

- **Locus** — satisfies "clear, identified locus" (bail criterion #1).
- **Skills to load** — gets the agent the subsystem conventions before the
  first edit, prevents stylistic drift.
- **Symptom + Repro + Impact** — lets the agent reproduce the bug and
  prioritize.
- **Constraints** — bounds the blast radius (bail criterion #2). An issue
  that can't list "out of scope" usually has an unstated design question
  (bail criterion #3).
- **Acceptance** — must be writable as a failing test (bail criterion #4).
  If the acceptance is fuzzy, rewrite it until it isn't.
- **Verify** — the exact commands the agent runs at the end; matches the
  issue-fix agent's verification step.

If you cannot fill in all five required fields, the issue is probably not
auto-fixable yet — file it anyway (so it's tracked), but tag it
`needs-triage` and expect a human pass before any agent can work it.

## Labels

| Type | Meaning |
|---|---|
| `bug` | A defect, regression, or known gap. |
| `enhancement` | (sibling skill) New capability or redesign. |

**Area labels** are project-specific. The consumer's
`.claude/issue-tracker.yaml` lists the project's valid `areas:` enum (e.g.
`dashboard / backend / frontend / infra`, or whatever the consumer chose).
Pick the matching area from that enum when filling the `area` label.

Optional triage flag: `needs-triage` if any required field is missing. An
issue-fix agent will skip `needs-triage` issues.

## Closing the loop

A PR that resolves a bug must follow the backend's close-on-merge
convention — see `backends/<backend>.md` PR close-on-merge section.

For example, on the `github` backend the convention is to include `Fixes
#N` (or `Closes #N`) in the PR title or body so GitHub auto-closes the
issue when the PR merges to the default branch. Other backends document
their own conventions (e.g. Jira may auto-close via a PR-integration hook
configured outside the plugin).

Manual closures follow the same convention — use the backend's
`close_issue` operation with a one-line reason if a bug turns out to be
resolved another way (config, upstream fix, won't-fix).

## At the start of work

The backend's `list_open_issues` operation filtered by `{type: bug}` shows
the auto-fixable backlog — useful before proposing new work in an area.
Filter additionally by the `needs-triage` label to see what agents can't
pick up yet.

## Example — a well-formed bug

```markdown
## Goal
POST /api/queues/<name>/retry returns 200 with the requeued message id
when the message is in the dead-letter queue, instead of 500.

## Locus
- File: `services/queue/retry_handler.py:87`
- Function: `retry_dead_letter`
- Subsystem: queue   # from your configured `subsystems:` enum

## Skills to load
- <your-queue-architecture-skill>
- <your-retry-policy-skill>

## Symptom
Calling the retry endpoint on a known-dead-letter message returns HTTP
500 with a generic stack trace. The expected behaviour is HTTP 200 with
a structured response naming the requeued id.

## Repro
```bash
curl -X POST http://localhost:8080/api/queues/payments/retry \
  -H 'Content-Type: application/json' \
  -d '{"message_id": "abc-123"}'
```
```
HTTP/1.1 500 Internal Server Error
KeyError: 'requeue_target'
```

## Expected
HTTP 200 with body `{"requeued_id": "<uuid>", "queue": "payments"}`.

## Impact
degrades-UX — operators cannot recover failed messages from the
dashboard. Does not block message ingestion.

## Root cause hypothesis
`retry_dead_letter` reads `requeue_target` from the message envelope
without checking for the dead-letter-specific shape, where that key is
namespaced under `dlq.requeue_target`.

## Constraints
- Out of scope: the queue driver itself (`services/queue/driver.py`).
- Invariants: dead-letter retention policy unchanged; no new queue states.
- Style: minimal fix; no drive-by refactors.

## Acceptance
- [ ] Calling retry on a dead-letter message returns HTTP 200.
- [ ] Response body matches `{"requeued_id": "<uuid>", "queue": "<name>"}`.
- [ ] The dead-letter row is removed atomically with the requeue insert.

## Verify
```bash
pytest -q tests/test_queue_retry.py::test_retry_dead_letter
pytest -q
```
```

---

See also: `feature-request` (new capabilities), `followup-tracking` (scope
deferred from in-flight work), `initiative-tracking` (multi-issue epics).
````

- [ ] **Step 2.3: Edit `CHANGELOG.md`**

The current `CHANGELOG.md` has a `## [Unreleased]` section with a `### Added` block listing Phase 0 and Phase 1 entries. Append the Phase 2 (#11) line to that `### Added` list.

Use the Edit tool. `old_string` matches the last existing `### Added` entry; `new_string` keeps that entry and appends a newline + the new line.

`old_string`:
```
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
```

`new_string`:
```
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from trading-bot; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-trading-bot-ification pattern for #12/#13/#14/#15.
```

Verify:
```bash
grep -E "Phase 2 \(#11\): bug-tracking" CHANGELOG.md
# Expected: one matching line
```

- [ ] **Step 2.4: Run the full acceptance grep suite**

```bash
# AC1 + AC2: files exist
test -f skills/bug-tracking/SKILL.md && echo OK_SKILL || echo MISSING_SKILL
test -f templates/bug-body.md && echo OK_TEMPLATE || echo MISSING_TEMPLATE
# Both must echo OK_*

# AC3 + AC4: no trading-bot leakage
grep -rE "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture" skills/bug-tracking templates/bug-body.md && echo LEAK || echo clean
# Expected: "clean"  (grep returns no matches → exit 1 → `|| echo clean` fires)

# AC5: skill dispatches to backend via operation contract
grep -E "create_issue|backends/<backend>\\.md|configured backend" skills/bug-tracking/SKILL.md | wc -l
# Expected: ≥1 (and the line `Invoke the configured backend's \`create_issue\` operation` should appear)

# AC6: template has all required section headers
grep -E "^## (Goal|Locus|Skills to load|Symptom|Repro|Expected|Impact|Constraints|Acceptance|Verify|Notes)" templates/bug-body.md | wc -l
# Expected: ≥11

# AC7: no absolute paths or ~/.claude/ refs in skill or template
grep -rE "~/\\.claude/|^/[A-Za-z]+/|^[A-Z]:[/\\]" skills/bug-tracking templates/bug-body.md && echo BAD_PATH || echo clean
# Expected: "clean"

# AC8: CHANGELOG entry
grep -E "Phase 2 \\(#11\\): bug-tracking" CHANGELOG.md
# Expected: one matching line
```

If any check fails, fix in place and re-run the suite before committing.

- [ ] **Step 2.5: Markdownlint (conditional)**

```bash
[ -f .markdownlint.json ] && npx --yes markdownlint-cli skills/bug-tracking/SKILL.md templates/bug-body.md
[ -f .markdownlint.json ] || echo "no markdownlint config; deferred to Phase 4 per design spec"
```

The plugin does not ship a markdownlint config today (deferred to Phase 4). Skip and report.

- [ ] **Step 2.6: Commit**

```bash
git add skills/bug-tracking/SKILL.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat(skills): port bug-tracking from trading-bot

Tracker-agnostic prose; dispatches to backends/<backend>.md via the
seven-operation contract. Body template extracted to
templates/bug-body.md (Task 1). CHANGELOG entry added.

Behaviour-change-zero: bail criteria, label taxonomy, title format,
body shape, and lifecycle semantics all preserved from the trading-bot
source. Trigger phrases in the description preserved verbatim.

Closes #11.
Refs trading-bot#153 (Phase 2).
EOF
)"
```

Verify:
```bash
git log -2 --format='%H %s'
# Expected first line: "<sha> feat(skills): port bug-tracking from trading-bot"
# Expected second line: Task 1's commit ("<sha> feat(templates): add bug-body skeleton")
git status
# Expected: "On branch feat/issue-11-bug-tracking" + "nothing to commit, working tree clean"
```

---

## Task 3: Push branch + create PR

**Files:** none — git/gh operations only.

**Subagent CWD discipline:** same as Task 1.

- [ ] **Step 3.1: Confirm cwd, branch, and staleness**

```bash
cd F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+issue-11-bug-tracking
git status
git log --oneline -5
# Expected: two new commits on top of the Phase 1 merge (74c1d2e)

git fetch origin
git rev-list --left-right --count HEAD...origin/main
# LEFT side (HEAD) should be exactly 2 (our two commits)
# RIGHT side (origin/main) MUST be 0 — if not, origin/main moved during the work; report to operator
```

If RIGHT > 0, STOP and report. Do not push.

- [ ] **Step 3.2: Push branch with upstream tracking**

```bash
git push -u origin feat/issue-11-bug-tracking
```

Expected: branch created on origin, tracking set up.

- [ ] **Step 3.3: Create the PR**

```bash
gh pr create \
  --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/issue-11-bug-tracking \
  --title "Phase 2 (#11): port bug-tracking skill" \
  --body "$(cat <<'EOF'
## Summary
- Ports the `bug-tracking` skill from `maxdimitrov/trading-bot` to this plugin in tracker-agnostic prose.
- Extracts the agent-prompt body template into `templates/bug-body.md`; the skill now references it instead of inlining.
- Dispatches to `backends/<backend>.md` via the seven-operation contract landed in Phase 1 (#9).
- Updates CHANGELOG under `[Unreleased]` → `Added`.

## Files
- `skills/bug-tracking/SKILL.md` — new (≈ 175 lines)
- `templates/bug-body.md` — new (≈ 80 lines)
- `CHANGELOG.md` — one line appended

## Transforms applied (parent spec §6.1)
- `GitHub Issues on maxdimitrov/trading-bot` → "the configured tracker (see `.claude/issue-tracker.yaml`)"
- `gh issue create ...` block → `create_issue` operation dispatch paragraph (spec §5.2)
- `memory/PENDING-FIXES.md` paragraph — deleted
- `/fix-issue <N>` → "an issue-fix agent (if your project has one)"
- `gh issue list --label bug` → `list_open_issues` operation reference
- `Fixes #N` lifecycle → "the backend's close-on-merge convention"
- area / subsystem enums → consumer-configured (`.claude/issue-tracker.yaml`)
- trading-bot domain skill cross-links — deleted
- Trigger phrases in the frontmatter `description:` — preserved verbatim (behaviour-change-zero invariant)

## Behaviour-change-zero
Per §8.2 of the parent design spec, the issue body shape, bail criteria, label taxonomy, title format, and lifecycle semantics are byte-identical to the trading-bot source. The Phase 5 cutover PR (against trading-bot) is the explicit gate where trigger-phrase regression is verified end-to-end; this PR only ships the plugin-side port.

## Test plan
Static acceptance from issue #11 (no code, no pytest — markdown-only):

- [x] `skills/bug-tracking/SKILL.md` exists
- [x] `templates/bug-body.md` exists with every `[required]` section header
- [x] `grep -rE "maxdimitrov/trading-bot|PENDING-FIXES|/fix-issue|ic-memo-framework|dca-router|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture" skills/bug-tracking templates/bug-body.md` returns no matches
- [x] `grep -E "create_issue|backends/<backend>\\.md|configured backend" skills/bug-tracking/SKILL.md` returns ≥ 1 match
- [x] CHANGELOG.md has the Phase 2 (#11) line under `[Unreleased]` → `Added`
- [ ] Markdownlint — deferred to Phase 4 (no `.markdownlint.json` yet)
- [ ] Cold-read review by operator

Closes #11.
Parent epic: maxdimitrov/trading-bot#153.
Plan: `docs/superpowers/plans/2026-05-26-port-bug-tracking-skill.md` (in this PR).
EOF
)"
```

- [ ] **Step 3.4: Report PR URL and final state to controller**

Capture the PR URL emitted by `gh pr create` and surface it to the operator. Also report:

```bash
git log --oneline -5
# Expected: 3 commits on top of 74c1d2e — plan (controller pre-step), template (Task 1), skill+CHANGELOG (Task 2)
```

---

## Acceptance (mirrors issue #11)

The PR is mergeable when ALL of these hold:

- [ ] `skills/bug-tracking/SKILL.md` exists; opens; renders cleanly.
- [ ] `templates/bug-body.md` exists; contains every `[required]` section the skill names (Goal, Locus, Skills to load, Symptom, Repro, Expected, Impact, Constraints, Acceptance, Verify — Notes is optional but present as a placeholder).
- [ ] No literal `maxdimitrov/trading-bot` anywhere in `skills/bug-tracking/` or `templates/bug-body.md`.
- [ ] No literal `memory/PENDING-FIXES.md`, no `/fix-issue` reference, no trading-bot-specific skill cross-link (`ic-memo-framework`, `dca-router-mechanics`, `dashboard-maintenance`, `atr-stops`, `reserve-ledger`, `execution-service-architecture`, `proposal-service-architecture`, …).
- [ ] Skill prose dispatches to the backend via the operation contract — at least one of `create_issue` + `backends/<backend>.md` reference is present.
- [ ] `templates/bug-body.md` is markdown-syntactically valid (no rendering errors when viewed via `gh issue view` previews or any standard markdown renderer).
- [ ] Skill cross-links use plugin-relative paths only — no `~/.claude/skills/`, no absolute paths, no Windows drive letters.
- [ ] `CHANGELOG.md` gains an `## [Unreleased]` → `### Added` entry noting the bug-tracking skill landed.
- [ ] Plan file committed to the branch as part of this PR.
- [ ] PR title is `Phase 2 (#11): port bug-tracking skill` and body includes `Closes #11` plus parent epic ref `trading-bot#153`.
- [ ] Branch staleness check before push showed `0` on the RIGHT side (origin/main did not move during the work).

---

## Notes

- The smoke test from the issue's Verify section ("file a real bug against THIS repo using the new skill") is deferred — per brainstorm decision #2, this PR ships with static-checks-only verification. Phase 5 is the explicit gate where the trigger-phrase regression is verified against trading-bot.
- The cross-repo controller / worktree dance is the unusual part of this plan. Every task starts with `cd <worktree>` and ends with `git log -1` controller-side verification. The subagent CWD discipline rule (project CLAUDE.md "Subagent CWD discipline" section) is the reason these belt-and-suspenders checks exist — a Task 3-style accidental commit-to-main has happened before in this project.
- Three Phase 2 sub-issues remain after this one (#12 feature-request, #13 followup-tracking, #14 initiative-tracking, #15 skill-currency). The transform table and the file-structure conventions established here are the model for those.
