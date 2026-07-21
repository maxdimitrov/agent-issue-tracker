# /work-issue Start-Side Status Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/work-issue` reflects "work has started" into initiative state on any backend — epic Status block `Current branch`/`Last updated` sync plus a per-backend in-progress affordance — with the close-side half deferred to filed follow-ups.

**Architecture:** Docs-artifact repo — the deliverable is agent-prose. Option A (per-backend optional affordances, no ninth contract op) per the approved spec `docs/superpowers/specs/2026-07-21-work-issue-status-lifecycle-design.md`. `commands/resume-initiative.md` is NOT touched (owned by #85's concurrent session).

**Tech Stack:** Markdown, YAML example config, `gh` CLI (follow-up filing), pytest + CI greps (verification).

## Global Constraints

- `backends/_interface.md` MUST keep exactly eight `` ### `op` `` headings; backend modules add affordances only under plain `##` headings (op-parity CI).
- Every status write documented as best-effort: WARN-and-continue, never blocks run/PR/file-op.
- `edit_body` always documented as read-modify-write (cross-backend invariant 2).
- Do NOT edit `commands/resume-initiative.md` (collision with in-flight #85).
- `skills/initiative-tracking/SKILL.md` is hard-wrapped narrow (~66 cols) — match it. `backends/*.md` and `commands/*.md` use long lines — match those.
- No version bump in this PR; CHANGELOG entry goes under `## [Unreleased]`.
- `<FA>` / `<FB>` denote the two follow-up issue refs created in Task 1 — substitute the real `#N` values everywhere they appear in later tasks.

---

### Task 1: File the two follow-up issues (main session, `gh` CLI)

**Files:** none (tracker writes). Repo: `maxdimitrov/agent-issue-tracker`.

**Interfaces:**
- Produces: `<FA>` (close-side epic maintenance follow-up, labels `enhancement,followup,needs-design`), `<FB>` (`/resume-initiative --start` affordance-parity follow-up, labels `enhancement,followup`). Later tasks cite both refs in doc prose.

- [ ] **Step 1:** Verify labels exist: `gh label list --repo maxdimitrov/agent-issue-tracker --search followup`. If `followup` is missing, file with the remaining labels.
- [ ] **Step 2:** File Follow-up A (close-side, Option C direction, post-#85) with the followup-tracking body shape: Goal = acceptance criterion 3 of #86 (children `[x]` flip, `Phase N/M` increment, `Next up` recompute, `Last updated` bump on next `/resume-initiative` read); Parent = #86 + branch `feat/work-issue-status-lifecycle`; names the open design question (reconcile #85's "no auto-writes on read" with tracker-confirmed close-state write-back) → `needs-design`; Constraints = direct-child-only writes, read-modify-write, best-effort, land after #85 merges.
- [ ] **Step 3:** File Follow-up B (Mode 3 `--start` fires the same affordances as `/work-issue`: board In Progress or `jira.in_progress_transition`); Parent = #86 + branch; Why deferred = `resume-initiative.md` owned by #85's session.
- [ ] **Step 4:** Record both refs; substitute into `<FA>`/`<FB>` for Tasks 2-5.

### Task 2: Jira affordance + contract note + example config

**Files:**
- Modify: `backends/jira.md` (new `## In-progress transition (optional)` section before the n/a-board section; one pointer sentence appended to the n/a-board section)
- Modify: `backends/_interface.md` ("Optional backend-specific capabilities" gains the second-affordance paragraph)
- Modify: `examples/issue-tracker.yaml.example` (commented `in_progress_transition` key after `done_transition`; `github.project` comment generalised)

**Interfaces:**
- Produces: the affordance names later tasks cite — `jira.in_progress_transition` (config key), section title `In-progress transition (optional)`.

- [ ] **Step 1:** In `backends/jira.md`, insert before the `## GitHub Projects v2 board (optional) -- n/a for Jira` heading:

````markdown
## In-progress transition (optional)

**Optional, Jira-only. Not a contract operation** — see [`_interface.md`](_interface.md)
"Optional backend-specific capabilities". When the consumer's
`.claude/issue-tracker.yaml` sets `jira.in_progress_transition`, a driver that
starts work on an issue (`/work-issue` Step 3 today; `/resume-initiative --start`
once parity follow-up <FB> lands) marks the issue in progress by firing the named
workflow transition:

```
# Resolve the workflow-scoped transition id at runtime (same rule as close_issue —
# ids differ per workflow; never hardcode a numeric id)
transitions = getTransitionsForJiraIssue({cloudId, issueIdOrKey: <ref>})
id = <the transition whose name matches jira.in_progress_transition>

transitionJiraIssue({cloudId, issueIdOrKey: <ref>, transition: {id: <id>}})
```

- **Default: unset → no-op.** The plugin never fires a workflow transition the
  consumer didn't opt into. There is deliberately no `In Progress` default —
  `done_transition` defaults to `Done` because `close_issue` is a contract
  operation the skills already invoke; in-progress marking is new, optional
  behaviour.
- **Best-effort.** Any failure — the named transition absent from the issue's
  current workflow state, a permission error, an MCP error — is a WARN, never a
  block: the driver's run continues unaffected.
- If `getTransitionsForJiraIssue` does not offer the named transition (already in
  that state, or the workflow lacks it), WARN and skip — do not hunt for an
  alternative transition.
````

- [ ] **Step 2:** Append to the n/a-board section's paragraph: `The Jira-side in-progress affordance is the workflow transition above ("In-progress transition (optional)"), not a board.`
- [ ] **Step 3:** In `backends/_interface.md`, after the Projects-board paragraph of "Optional backend-specific capabilities", add:

```markdown
The second is **in-progress status marking** — the "this issue is being worked"
signal a driver sets when work starts (`/work-issue` Step 3 today; `/resume-initiative
--start` via follow-up <FB>). It is an affordance, not a ninth operation, because it
cannot be uniformly implemented: GitHub has no native issue-level status (its
mechanism is the Projects-board Status field above), while Jira's is a workflow
transition (`jira.in_progress_transition` — see `backends/jira.md` "In-progress
transition (optional)"). With neither configured, the fallback signal is the parent
epic's Status block `Current branch` line, written by `/work-issue`'s start-side
sync; a parentless issue with nothing configured gets no marker — a documented
no-op. Every such write is best-effort — WARN, never block.
```

- [ ] **Step 4:** In `examples/issue-tracker.yaml.example`, after the `done_transition` block add:

```yaml
  # Optional. The transition name a driver fires to mark an issue "in progress"
  # when work starts on it (/work-issue Step 3). Resolved by name to a
  # workflow-scoped id at runtime, per issue. Unset (default) = never
  # transition — the plugin only fires transitions you opt into. Best-effort:
  # a failure WARNs and never blocks the run.
  # in_progress_transition: "In Progress"
```

and change the `github.project` comment line `# initiative-tracking mirrors the initiative tree onto this board, and` / `# /resume-initiative --start sets a child's Status to In Progress.` to `# initiative-tracking mirrors the initiative tree onto this board, and drivers` / `# that start work on a child (/resume-initiative --start, /work-issue) set its` / `# Status to In Progress.`

- [ ] **Step 5:** Verify: `grep -cP '^### \`' backends/_interface.md` → `8`; same count for `backends/jira.md` → `8`; `yamllint -d relaxed examples/issue-tracker.yaml.example` → clean.
- [ ] **Step 6:** Commit: `git add -A && git commit -m "feat(backends): jira in-progress transition affordance + contract note (#86)"`

### Task 3: GitHub board trigger + board reference + initiative-tracking skill

**Files:**
- Modify: `backends/github.md` ("Set Status on an item already on the board" + "Failure semantics" mention both drivers)
- Modify: `skills/initiative-tracking/references/github-projects-board.md` (In Progress bullet)
- Modify: `skills/initiative-tracking/SKILL.md` (new affordance section; board-lifecycle line; Maintenance automation note cites `<FA>`)

- [ ] **Step 1:** `backends/github.md`: `(close -> `Done`; `--start` -> `In Progress`)` → `(close -> `Done`; work-start -> `In Progress` — set by `/resume-initiative --start` or `/work-issue`)`. In "Failure semantics", `/resume-initiative --start` → `/resume-initiative --start` / `/work-issue`.
- [ ] **Step 2:** `references/github-projects-board.md` In Progress bullet → `**In Progress** — set when a driver starts work on a child and its worktree is entered — `/resume-initiative --start` (see `commands/resume-initiative.md`) or `/work-issue` (see `commands/work-issue.md`).`
- [ ] **Step 3:** `SKILL.md`: in "GitHub Projects board (optional)", `(`Todo` on file/link, `In Progress` on `/resume-initiative --start`, `Done` on close)` → `(`Todo` on file/link, `In Progress` when a driver starts work — `/resume-initiative --start` or `/work-issue` — `Done` on close)`.
- [ ] **Step 4:** `SKILL.md`: insert a new `## In-progress status (optional affordances)` section between "Maintenance" and "GitHub Projects board (optional)" (narrow-wrapped to match the file):

```markdown
## In-progress status (optional affordances)

"This issue is being worked" has no cross-backend primitive —
`close_issue` is the contract's only state-change operation. The
in-progress signal is therefore a per-backend **optional
affordance** (see `backends/_interface.md` "Optional
backend-specific capabilities"), set by a driver when work starts
(`/work-issue` Step 3 today; `/resume-initiative --start` via
follow-up <FB>):

- **GitHub** — `github.project` configured → set the child's board
  item Status to `In Progress` (see `backends/github.md`).
- **Jira** — `jira.in_progress_transition` configured → fire that
  workflow transition (see `backends/jira.md` "In-progress
  transition (optional)").
- **Neither configured** — the parent epic's Status block
  `- **Current branch:**` line (set by `/work-issue`'s start-side
  sync, alongside a `Last updated` bump) is the fallback signal; a
  parentless issue gets no marker. No-op, run proceeds.

Every such write is best-effort: a failure WARNs and never blocks
the run, the worktree, or the file operation. Start-side writes
touch ONLY `Current branch` + `Last updated` — never `Phase`,
`Next up`, or the `## Children` mirror (those are close-side
Maintenance, above).
```

- [ ] **Step 5:** `SKILL.md` Maintenance trailing note: `Optional — a CI job that does steps 1-3 automatically on issue-closed events. Out of scope for this skill; a candidate follow-up feature-request.` → `Optional — a CI job that does steps 1-3 automatically on issue-closed events. Out of scope for this skill; the close-side automation/reconcile work is tracked as follow-up <FA> (coordinated with #85).`
- [ ] **Step 6:** Verify: `grep -cP '^### \`' backends/github.md` → `8`; `grep -n "work-issue" skills/initiative-tracking/SKILL.md` shows the new section.
- [ ] **Step 7:** Commit: `git add -A && git commit -m "docs(initiative-tracking): cross-backend in-progress affordance; board trigger names both drivers (#86)"`

### Task 4: `commands/work-issue.md` — start-side sync

**Files:**
- Modify: `commands/work-issue.md` (header ops sentence L9; siblings-table Backend cell; Step 3 gains the sync block; Conventions bullet; new failure mode)

- [ ] **Step 1:** L9: `— `view_issue` (always) and, where the workflow surfaces a label/close action, `add_label` / `close_issue`.` → `— `view_issue` (always); `edit_body` (start-side epic Status sync, best-effort); and, where the workflow surfaces a label/close action, `add_label` / `close_issue`.`
- [ ] **Step 2:** Siblings-table row 1: `Backend-agnostic (`view_issue`, optional `add_label` / `close_issue`)` → `Backend-agnostic (`view_issue`, best-effort `edit_body`, optional `add_label` / `close_issue`)`
- [ ] **Step 3:** In Step 3, after the branch-rename numbered list and BEFORE the closing `EnterWorktree switches the session's CWD…` paragraph, insert:

```markdown
**Start-side initiative sync (best-effort).** Immediately after the worktree
exists, reflect "work has started" into the initiative state. Every step here is
best-effort: a failure emits a WARN and never blocks the run, the worktree, or the
eventual PR. With no `.claude/issue-tracker.yaml`, skip the whole block (fail-open).

1. **Discover the parent epic — from the body, not the backend.** Parse the issue
   body (fetched at Step 1) for a `## Parent epic` block; the ref opening its first
   non-blank line names the immediate parent (`templates/sub-issue-body.md` pins the
   shape). This is the portable cross-backend signal — do NOT rely on `view_issue`'s
   `parent?` field, which is absent on GitHub plain reads (`backends/_interface.md`).
   No `## Parent epic` block → not an initiative child; skip step 2 (step 3's
   in-progress marking still applies).
2. **Sync the epic Status block.** `view_issue(parent)` → read-modify-write per
   cross-backend invariant 2: set the Status block's `- **Current branch:**` line to
   the new branch name and `- **Last updated:**` to today (`YYYY-MM-DD`), then
   `edit_body(parent, new_body)`. Touch NOTHING else — not `Phase`, not `Next up`,
   not the `## Children` mirror; those are close-side Maintenance
   (`skills/initiative-tracking/SKILL.md`, tracked as follow-up <FA>). Parent
   unfetchable, or its body has no Status block → WARN and skip.
3. **Mark the issue in progress** via the backend's configured affordance — see
   `skills/initiative-tracking/SKILL.md` "In-progress status (optional affordances)":
   GitHub with `github.project` set → board item Status `In Progress`
   (`backends/github.md`); Jira with `jira.in_progress_transition` set → fire that
   workflow transition (`backends/jira.md`). Neither configured → no-op; the
   `Current branch` line from step 2 is the fallback signal.
```

- [ ] **Step 4:** Conventions bullet 2: `` `/work-issue` dispatches `view_issue` (and any `add_label` / `close_issue`) through `backends/<backend>.md`; it never calls a backend's raw CLI / MCP directly.`` → `` `/work-issue` dispatches `view_issue`, the start-side sync's `edit_body`, and any `add_label` / `close_issue` through `backends/<backend>.md`; it never calls a backend's raw CLI / MCP directly.``
- [ ] **Step 5:** Failure modes — append: `- **Start-side initiative sync fails** (parent epic unfetchable, Status block missing, board write or transition rejected) → WARN and continue; status writes never block the run. The epic catches up on the close side (follow-up <FA>).`
- [ ] **Step 6:** Verify: `grep -n "Start-side initiative sync" commands/work-issue.md` → present in Step 3 + failure modes; `grep -c "edit_body" commands/work-issue.md` ≥ 3.
- [ ] **Step 7:** Commit: `git add -A && git commit -m "feat(work-issue): start-side epic sync + in-progress marking in Step 3 (#86)"`

### Task 5: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]` gains an `### Added` entry; Keep-a-Changelog style matching 1.6.0's entry)

- [ ] **Step 1:** Under `## [Unreleased]` add an `### Added` section with one bolded entry: **`/work-issue` start-side initiative status lifecycle (#86)** — start-side epic Status sync (`Current branch` + `Last updated` via read-modify-write `edit_body`), cross-backend in-progress marking as per-backend optional affordances (GitHub Projects board In Progress; new optional `jira.in_progress_transition` config key, default unset = no-op), best-effort WARN-and-continue semantics, eight-op contract untouched (op-parity green), close-side deferred to `<FA>` + `--start` parity to `<FB>` (coordinated with #85).
- [ ] **Step 2:** Verify: `npx markdownlint-cli2 CHANGELOG.md` clean (or the CI action's equivalent).
- [ ] **Step 3:** Commit: `git add CHANGELOG.md && git commit -m "docs(changelog): unreleased entry for #86 start-side status lifecycle"`

### Task 6: Full verification (main session)

- [ ] `python -m pytest -q` → all pass (surface untouched).
- [ ] Op-parity (CI equivalent): contract ops from `_interface.md` == 8 and every op present in both backend modules.
- [ ] `yamllint -d relaxed .` → clean.
- [ ] markdownlint on `README.md CONTRIBUTING.md CHANGELOG.md examples/**/*.md`.
- [ ] `git log --oneline main..HEAD` shows the task commits; diff contains NO changes to `commands/resume-initiative.md`.
