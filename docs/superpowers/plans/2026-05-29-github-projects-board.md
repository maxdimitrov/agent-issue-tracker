# GitHub Projects (board) support for initiatives — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the plugin optionally mirror an initiative's issue tree onto a GitHub Projects (v2) board — adding root epic, sub-epics, and leaf children (incl. cross-repo) as items and syncing each child's lifecycle to the board's Status field — without the board ever becoming the source of truth.

**Architecture:** Pure-prose, agent-driven (the plugin ships zero code). Literal `gh project` calls are documented in `backends/github.md`; the *when* is woven into `skills/initiative-tracking/SKILL.md` and `commands/resume-initiative.md`. Opt-in via a new optional `github.project` URL; absent → byte-identical to today.

**Tech Stack:** Markdown docs only. `gh` CLI (`gh project` subcommands, GraphQL-backed, `project` scope). CI gates: `backend-contract` op-parity grep, `markdownlint-cli2`, `yamllint`.

**Spec:** `docs/superpowers/specs/2026-05-29-github-projects-board-design.md` (committed `9b86d0a`).

**Issue:** [maxdimitrov/agent-issue-tracker#40](https://github.com/maxdimitrov/agent-issue-tracker/issues/40).

---

## Working context (read before starting any task)

- **Worktree (work from here):** `F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+github-projects-board`
- **Branch:** `feat/github-projects-board` (off `origin/main` @ `c35656e`).
- **Subagent CWD discipline:** every implementer subagent MUST start with `cd "F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+github-projects-board" && git status` as its literal first action, and the controller MUST run `git log -1 --format='%h %s' feat/github-projects-board` after each task to confirm the commit landed on the right branch (not `main`).
- **Commit signing:** this machine signs commits via 1Password's SSH agent. If a commit fails with `1Password: failed to fill whole buffer`, the desktop app is locked — surface to the operator to unlock; do NOT bypass with `--no-gpg-sign`.

## Verification model (no code → no pytest)

This is a **docs-only** change. There is no executable behaviour and no unit-test harness. "Tests" are the repo's real CI gates plus a content checklist per task:

- **G1 — op-parity (the load-bearing automated gate).** Replicates `.github/workflows/ci.yml` `backend-contract`. MUST print nothing:
  ```bash
  contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
  for b in backends/github.md backends/jira.md; do \
    comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done
  ```
  Also assert **no new op heading** crept into `_interface.md`:
  ```bash
  grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u | tr '\n' ' '
  # expect exactly: add_label close_issue create_issue edit_body link_sub_issue list_open_issues view_issue
  ```
- **G2 — markdown lint** (CHANGELOG only among our edits; line-length MD013 is off):
  ```bash
  npx markdownlint-cli2 "README.md" "CONTRIBUTING.md" "CHANGELOG.md" "examples/**/*.md"
  ```
- **G3 — yaml lint** (the config-example edits):
  ```bash
  yamllint -d relaxed .
  ```

Run G1 after every backend/interface task, G2 after the CHANGELOG task, G3 after the examples task. Run all three in the final task.

---

## Task 1: Config schema — optional `github.project` field

**Files:**
- Modify: `examples/issue-tracker.yaml.example` (the `github:` block, currently lines 57-64)
- Modify: `examples/github-config.yaml` (the `github:` block, currently lines 7-8)

- [ ] **Step 1: Add the optional field to the full schema example**

In `examples/issue-tracker.yaml.example`, replace the `github:` block (the lines from `# REQUIRED if \`backend: github\`. GitHub backend config.` through `default_pr_close_syntax: "Fixes #N"`) with:

```yaml
# REQUIRED if `backend: github`. GitHub backend config.
github:
  # REQUIRED. The "owner/repo" of the tracker repo (where issues are filed).
  repo: maxdimitrov/example-project

  # Optional. The PR close-on-merge phrasing rendered into PR description
  # templates by feature-request / bug-tracking. Default: "Fixes #N".
  default_pr_close_syntax: "Fixes #N"

  # Optional. A user- or org-level GitHub Projects (v2) board URL. When set,
  # initiative-tracking mirrors the initiative tree onto this board, and
  # /resume-initiative --start sets a child's Status to In Progress. Best-effort:
  # the `## Children` task-list mirror stays canonical; a board failure never
  # blocks an issue operation. Omit for no board behaviour (default).
  # Needs the `project` token scope: gh auth refresh -s project,read:project
  # Use a user- or org-level board (repo-level projects can't span repos):
  #   project: https://github.com/users/<owner>/projects/<N>
  #   project: https://github.com/orgs/<org>/projects/<N>
```

- [ ] **Step 2: Add a commented example to the minimal config**

In `examples/github-config.yaml`, replace the `github:` block (lines 7-8) with:

```yaml
github:
  repo: your-org/your-repo
  # Optional. Mirror initiatives onto a user/org-level GitHub Projects (v2) board.
  # Needs `gh auth refresh -s project,read:project`. Omit for no board behaviour.
  #   project: https://github.com/orgs/your-org/projects/1
```

- [ ] **Step 3: Verify yaml lint passes (G3)**

Run: `yamllint -d relaxed examples/issue-tracker.yaml.example examples/github-config.yaml`
Expected: no output (exit 0).

- [ ] **Step 4: Verify markdownlint still passes (examples glob includes only .md; these are .yaml, so this just confirms nothing regressed) (G2)**

Run: `npx markdownlint-cli2 "examples/**/*.md"`
Expected: `Summary: 0 error(s)`.

- [ ] **Step 5: Commit**

```bash
git add examples/issue-tracker.yaml.example examples/github-config.yaml
git commit -m "docs(examples): add optional github.project board field to config schema"
```

---

## Task 2: `_interface.md` — document Projects as an optional, non-contract affordance

**Files:**
- Modify: `backends/_interface.md` (insert a new section between the `## Cross-backend invariants` block and `## Adding a new backend`, i.e. after the invariants list ends at the `---` on line 120)

- [ ] **Step 1: Insert the optional-affordance section**

In `backends/_interface.md`, immediately after the `---` that closes the Cross-backend invariants section (line 120) and before `## Adding a new backend`, insert:

```markdown
## Optional backend-specific capabilities

The seven operations above are the entire contract. A backend MAY document
additional, backend-specific affordances that are NOT contract operations and are
NOT required of any other backend. Such affordances live under plain `##` headings
in the backend module — never a `` ### `op` `` operation heading — so the
`backend-contract` CI op-parity check (which greps `` ### `op` `` headings) ignores
them. They are always optional for the consumer; with the relevant config key
unset, behaviour is unchanged.

The first such affordance is **GitHub Projects (v2) board population** — see
`backends/github.md` "GitHub Projects v2 board (optional)". It mirrors an
initiative's issue tree onto a GitHub Projects board as a human-facing view. It is
GitHub-only; `backends/jira.md` records it as n/a. It adds **no** contract
operation: the seven ops stay seven, and op-parity remains green.

---
```

- [ ] **Step 2: Verify op-parity gate stays green (G1)**

Run:
```bash
contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
for b in backends/github.md backends/jira.md; do \
  comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done
grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u | tr '\n' ' '; echo
```
Expected: first loop prints nothing; the heading list prints exactly `add_label close_issue create_issue edit_body link_sub_issue list_open_issues view_issue`.

- [ ] **Step 3: Commit**

```bash
git add backends/_interface.md
git commit -m "docs(interface): document Projects as optional non-contract affordance"
```

---

## Task 3: `backends/github.md` — the GitHub Projects v2 board section

**Files:**
- Modify: `backends/github.md` (append a new top-level section after `## Setup verification`, end of file at line 155)

- [ ] **Step 1: Re-confirm `gh project` flags against the live CLI (verify-tool-contracts)**

Run (no `project` scope needed for `--help`):
```bash
gh project item-add --help   | grep -E '\-\-(owner|url|format)'
gh project item-edit --help  | grep -E '\-\-(id|project-id|field-id|single-select-option-id)'
gh project field-list --help | grep -E '\-\-(owner|format)'
gh project view --help       | grep -E '\-\-(owner|format)'
gh project item-list --help  | grep -E '\-\-(owner|format|limit)'
```
Expected: each flag named below appears. If `gh` renamed a flag, adjust the section content in Step 2 to match the live CLI before committing.

- [ ] **Step 2: Append the section to `backends/github.md`**

At the end of `backends/github.md` (after the `## Setup verification` block), append:

```markdown

## GitHub Projects v2 board (optional)

**Optional, GitHub-only. Not a contract operation** — see
[`_interface.md`](_interface.md) "Optional backend-specific capabilities". When the
consumer's `.claude/issue-tracker.yaml` sets `github.project`, `initiative-tracking`
mirrors the initiative tree onto that GitHub Projects (v2) board: it adds the root
epic, every sub-epic, and every leaf child as items and reflects each child's
lifecycle in the board's built-in **Status** field. The board is a human-facing
view; the epic body's `## Children` task-list mirror stays canonical. With
`github.project` unset, none of this runs.

GitHub Projects v2 is GraphQL-only; the `gh project` subcommands wrap it and need
the `project` token scope:

    gh auth refresh -s project,read:project

### Project config

`github.project` is a **user- or org-level** Projects board URL:

- user board: `https://github.com/users/<owner>/projects/<N>`
- org board:  `https://github.com/orgs/<org>/projects/<N>`

Parse `<owner>` (the path segment after `users/` or `orgs/`) and `<N>` (the
trailing number). Repo-level project URLs (`.../<owner>/<repo>/projects/<N>`) are
NOT supported — repo projects can't span repos, which defeats the cross-repo use
case.

### Resolve board identifiers (once per session, then cache)

    # project node id
    PROJECT_ID=$(gh project view <N> --owner <owner> --format json --jq .id)

    # Status field id + the Todo / In Progress / Done option ids
    gh project field-list <N> --owner <owner> --format json \
      --jq '.fields[] | select(.name=="Status")'
    # -> {"id":"<STATUS_FIELD_ID>", "options":[{"id":"..","name":"Todo"}, ...]}

Match option names case-insensitively, tolerating `Todo` / `To do`. If the board
has no `Status` field or an expected option is missing, skip the status write
(still add the item) and WARN once.

### Add an item + set its Status

    # add (idempotent: an issue already on the board returns its existing item)
    ITEM_ID=$(gh project item-add <N> --owner <owner> \
      --url <issue-url> --format json --jq .id)

    # set Status (non-draft items require --id AND --project-id; one field per call)
    gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" \
      --field-id "$STATUS_FIELD_ID" --single-select-option-id "$OPTION_ID"

`<issue-url>` is the child's full GitHub issue URL. Because the board is
user/org-level, a cross-repo `owner/repo#N` child is added by its own repo's issue
URL — the same call works regardless of which repo the issue lives in.

### Set Status on an item already on the board

When the issue was added earlier (close → `Done`; `--start` → `In Progress`),
resolve its item id by content URL first:

    ITEM_ID=$(gh project item-list <N> --owner <owner> --format json -L 200 \
      --jq '.items[] | select(.content.url=="<issue-url>") | .id')

then `item-edit` as above. (`item-list` defaults to 30 items; pass `-L` generously.
Best-effort: if the item isn't in the fetched page, WARN and skip.)

### Failure semantics

Every `gh project` call here is **best-effort**. Any failure — missing `project`
scope, unreachable board, GraphQL error, absent `Status` field — is a WARN, never a
block: the underlying `create_issue` / `link_sub_issue` / `close_issue` /
`/resume-initiative --start` operation still succeeds. The `## Children` mirror is
the source of truth; a degraded board never blocks an initiative operation.
```

- [ ] **Step 3: Verify op-parity gate stays green (G1)**

Run:
```bash
contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
for b in backends/github.md backends/jira.md; do \
  comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done
# Confirm the new github.md subheadings did NOT register as ops:
grep -oP '^### `\K[a-z_]+(?=`)' backends/github.md | sort -u | tr '\n' ' '; echo
```
Expected: first loop prints nothing; the github.md op list is exactly the seven ops (the `### Project config`, `### Resolve board identifiers …`, etc. headings have no leading backtick and must NOT appear).

- [ ] **Step 4: Commit**

```bash
git add backends/github.md
git commit -m "docs(github): document optional GitHub Projects v2 board population"
```

---

## Task 4: `backends/jira.md` — one-line n/a note

**Files:**
- Modify: `backends/jira.md` (append a short section at end of file)

- [ ] **Step 1: Append the n/a note**

At the end of `backends/jira.md`, append:

```markdown

## GitHub Projects v2 board (optional) — n/a for Jira

Projects-board population is a GitHub-specific affordance (see
`backends/github.md` "GitHub Projects v2 board (optional)" and `_interface.md`
"Optional backend-specific capabilities"). It is **not applicable to Jira** — use
Jira's own boards. No Jira behaviour change; the `github.project` config key is
ignored when `backend: jira`.
```

- [ ] **Step 2: Verify op-parity gate stays green (G1)**

Run:
```bash
contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
for b in backends/github.md backends/jira.md; do \
  comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done
```
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add backends/jira.md
git commit -m "docs(jira): note GitHub Projects board is n/a for Jira"
```

---

## Task 5: `skills/initiative-tracking/SKILL.md` — board population + maintenance + backfill

**Files:**
- Modify: `skills/initiative-tracking/SKILL.md` — (a) append a board cross-ref to the `### Children task-list mirror — the cross-backend index` section (ends line 321), (b) add a Maintenance step 6 in the `## Maintenance` numbered list (lines 328-334), (c) insert a new `## GitHub Projects board (optional)` section before `## Epic lifecycle` (line 375)

- [ ] **Step 1: Add a board cross-ref after the Children-mirror section**

In `skills/initiative-tracking/SKILL.md`, immediately after the paragraph that ends `Per-backend native linkage mechanics … The skill does not encode them.` (the end of the `### Children task-list mirror` subsection, line 321), insert:

```markdown

**Optional board mirror.** If the consumer configures `github.project` (GitHub
backend only), also add each newly filed/linked child to the GitHub Projects (v2)
board and set its Status to `Todo` — root epic, sub-epics, and leaves, including
cross-repo `owner/repo#N` children. This is a human-facing **view**; the
`## Children` mirror stays canonical. Best-effort — a board failure WARNs and never
blocks the file/link. See the `## GitHub Projects board (optional)` section below
and `backends/github.md` for the literal `gh project` calls. With `github.project`
unset, skip this.
```

- [ ] **Step 2: Add Maintenance step 6 (Done on close)**

In the `## Maintenance` numbered list, after step `5. Append to \`Decision log\` …` (line 334), add:

```markdown
6. If `github.project` is set (GitHub backend), set the closed child's board item
   Status to `Done` (best-effort — WARN and continue on failure). See "GitHub
   Projects board (optional)" below.
```

- [ ] **Step 3: Insert the board section before `## Epic lifecycle`**

Immediately before `## Epic lifecycle` (line 375), insert:

```markdown
## GitHub Projects board (optional)

When the consumer's `.claude/issue-tracker.yaml` sets `github.project` (GitHub
backend only), mirror the initiative tree onto that GitHub Projects (v2) board in
addition to the canonical `## Children` task-list mirror. **The board is a
human-facing view; the `## Children` mirror stays the source of truth.** With
`github.project` unset, skip this entire section — behaviour is unchanged.

All board writes are **best-effort**: a failure WARNs and continues, never blocking
the issue operation. See `backends/github.md` "GitHub Projects v2 board (optional)"
for the literal `gh project` calls and scope setup
(`gh auth refresh -s project,read:project`).

Status lifecycle — three states, each a real event:

- **Todo** — when a child is filed + linked (see "Children task-list mirror"
  above), add it to the board and set Status `Todo`. Applies to every node: root
  epic, sub-epics, and leaves, including cross-repo `owner/repo#N` children (added
  by full issue URL).
- **In Progress** — set by `/resume-initiative --start` when a child's worktree is
  entered. See `commands/resume-initiative.md`.
- **Done** — when a child closes (see "Maintenance" step 6), set Status `Done`.

### Backfilling an existing tree onto a board

When `github.project` is newly configured on an in-flight initiative — or an
operator asks to "populate the board" — walk each epic node's `## Children` mirror
top-down (root → sub-epics → leaves) and add every node, setting Status from its
current state (open → `Todo`, closed → `Done`). Idempotent: GitHub Projects v2
stores a content item at most once, so re-adding an already-present issue returns
the existing item — no duplicates. This is a documented procedure, not a slash
command.

```

- [ ] **Step 4: Verify the file still reads coherently (content checklist)**

Run: `grep -nE '## GitHub Projects board|Status to `?Todo|Status `?Done|In Progress|github.project' skills/initiative-tracking/SKILL.md`
Expected: shows the new cross-ref, the Maintenance step 6, and the new section — Todo/In Progress/Done all present, all gated on `github.project`.

- [ ] **Step 5: Commit**

```bash
git add skills/initiative-tracking/SKILL.md
git commit -m "docs(initiative-tracking): mirror initiative tree to optional Projects board"
```

---

## Task 6: `commands/resume-initiative.md` — In Progress on `--start`

**Files:**
- Modify: `commands/resume-initiative.md` (Mode 3 step 4, after the worktree path is reported — current line 123)

- [ ] **Step 1: Insert the board-status action in Mode 3 step 4**

In `commands/resume-initiative.md`, in Mode 3 step 4, immediately after the sentence ending `do NOT stop and ask the operator to open a new window.` (line 123) and before the `Invoke \`view_issue({ref: leaf-ref})\`` sentence (line 124), insert:

```markdown
   **(Optional board sync.)** If the consumer's `.claude/issue-tracker.yaml` sets
   `github.project` (GitHub backend), set this leaf's GitHub Projects board item
   Status to `In Progress` now — best-effort: a failure WARNs and does NOT abort
   the handoff. See `backends/github.md` "GitHub Projects v2 board (optional)" for
   the `gh project item-list` (resolve item id by issue URL) + `item-edit` calls.
   With `github.project` unset, skip this.
```

- [ ] **Step 2: Add a one-line note to the Mode-3 description table row (discoverability)**

In the "Invocation modes" table, the row for `/resume-initiative <ref> --start` (line 23) currently ends `… and hand off to \`superpowers:brainstorming\` inline.` Append to that cell: ` (Sets the leaf's GitHub Projects board Status to In Progress if \`github.project\` is configured.)`

- [ ] **Step 3: Verify (content checklist)**

Run: `grep -nE 'In Progress|github.project|board sync' commands/resume-initiative.md`
Expected: the new step-4 paragraph and the table-row note both appear; both gate on `github.project`.

- [ ] **Step 4: Commit**

```bash
git add commands/resume-initiative.md
git commit -m "docs(resume-initiative): set board Status In Progress on --start"
```

---

## Task 7: `commands/tracker-doctor.md` — WARN-only project scope + reachability check

**Files:**
- Modify: `commands/tracker-doctor.md` — add a conditional probe to the GitHub branch of Phase 2 (after probe 3, before the `#### Jira branch` heading, line 54), and a one-line mention in the Phase-2 intro

- [ ] **Step 1: Add probe 4 to the GitHub branch of Phase 2**

In `commands/tracker-doctor.md`, in `#### GitHub branch` of Phase 2, after probe `3. **Canonical reachability:** …` (the block ending at line 52) and before `#### Jira branch` (line 55), insert:

```markdown
4. **GitHub Projects board (only if `github.project` is set; skip otherwise).**
   Parse `<owner>` + `<N>` from the configured `github.project` URL, then run
   `gh project view <N> --owner <owner>`.
   - `PASS` if it returns the project (board reachable + scope present).
   - `WARN` (never `FAIL`) if `gh` reports a missing scope / permission error —
     the board is optional. Print the paste-able fix in a fenced block:

     ```bash
     gh auth refresh -s project,read:project
     ```

   - `WARN` if `github.project` is a **repo-level** URL
     (`.../<owner>/<repo>/projects/<N>`) — repo projects can't span repos; suggest
     a user/org-level board.
```

- [ ] **Step 2: Note it in the Phase-2 intro sentence**

In the Phase 2 intro paragraph (line 41, beginning `Branch on \`backend:\` value …`), append one sentence: ` The GitHub branch adds a fourth, WARN-only probe when \`github.project\` is configured (Projects board reachability).`

- [ ] **Step 3: Verify the always-exits-0 / WARN-only invariant is preserved (content checklist)**

Run: `grep -nE 'github.project|gh project view|auth refresh -s project|FAIL' commands/tracker-doctor.md | grep -iE 'project board|github.project|auth refresh'`
Expected: the new probe references `WARN` (never `FAIL`) and prints the `gh auth refresh -s project,read:project` fix. Confirm the `## Invariants` "Always exits 0" line is untouched.

- [ ] **Step 4: Commit**

```bash
git add commands/tracker-doctor.md
git commit -m "docs(tracker-doctor): WARN-check github.project scope + reachability"
```

---

## Task 8: `commands/tracker-init.md` — optional Projects board URL prompt

**Files:**
- Modify: `commands/tracker-init.md` — (a) Phase 3 GitHub branch: add an optional prompt after the repo prompt (after line 47), (b) Phase 6 assembly: emit `project:` when provided (in the `github:` block bullet list, after line 121), (c) Phase 8 next-steps: scope reminder when a project was configured

- [ ] **Step 1: Add the optional prompt to Phase 3**

In `commands/tracker-init.md`, in `### Phase 3 — GitHub branch`, after `**3c. Repo prompt.**` and its `Store the answer as \`github.repo\`.` line (line 47), insert a new sub-step before `Skip Phase 4 and proceed to Phase 5.`:

```markdown
**3d. Projects board prompt (optional).** Invoke `AskUserQuestion` once
(single-select with "Other" for free-form):
- Question: "Mirror initiatives onto a GitHub Projects (v2) board? Paste a
  user/org-level board URL, or skip."
- Header: `Project board`
- Options: `Skip — no board` (recommended) | (the operator uses "Other" to paste a
  URL like `https://github.com/users/<owner>/projects/<N>`).
- If the operator skips, record that `github.project` will be omitted. If they
  paste a URL, store it as `github.project` (accept as-is; reject blank "Other"
  with a re-prompt).
```

- [ ] **Step 2: Emit the field in Phase 6 assembly**

In `### Phase 6 — Assemble the YAML`, in the `- \`github:\` block — emit ONLY if \`backend: github\`. Include:` list (lines 119-121), after the `default_pr_close_syntax` bullet, add:

```markdown
  - `project: <value from Phase 3d>` — emit ONLY if the operator pasted a board
    URL in Phase 3d; omit the key entirely if they skipped.
```

- [ ] **Step 3: Add the scope reminder to Phase 8**

In `### Phase 8 — Next-steps panel`, after the existing `**For GitHub:**` appended line (line 158), add:

```markdown
**For GitHub with a board configured:** Append: "You configured a Projects board.
Grant the token scope once with `gh auth refresh -s project,read:project`, then
`/tracker-doctor` will verify the board is reachable."
```

- [ ] **Step 4: Verify (content checklist)**

Run: `grep -nE 'Phase 3d|Project board|github.project|project,read:project' commands/tracker-init.md`
Expected: the new prompt (3d), the Phase-6 emit bullet, and the Phase-8 scope reminder all present; all treat the board as optional (omit when skipped).

- [ ] **Step 5: Commit**

```bash
git add commands/tracker-init.md
git commit -m "docs(tracker-init): optional GitHub Projects board URL prompt"
```

---

## Task 9: `CHANGELOG.md` — Unreleased entry

**Files:**
- Modify: `CHANGELOG.md` (the `## [Unreleased]` → `### Added` list, after the existing "Nested initiatives" bullet)

- [ ] **Step 1: Add the Added entry**

In `CHANGELOG.md`, under `## [Unreleased]` → `### Added`, after the existing "Nested initiatives (N-level trees)." bullet block, add:

```markdown
- **GitHub Projects (board) support for initiatives (optional).**
  `initiative-tracking` can optionally mirror an initiative's issue tree onto a
  user/org-level GitHub Projects (v2) board — adding the root epic, sub-epics, and
  leaf children (including cross-repo `owner/repo#N` children) as items and syncing
  each child's lifecycle to the board's **Status** field (`Todo` on file,
  `In Progress` on `/resume-initiative --start`, `Done` on close). Opt-in via a new
  optional `github.project` URL in `.claude/issue-tracker.yaml`; with it unset,
  behaviour is byte-identical to before. The board is a human-facing **view** — the
  `## Children` task-list mirror stays canonical, and every board write is
  best-effort (a board failure never blocks an issue operation). GitHub-only (n/a
  for Jira); **no** backend-contract change — the seven operations are untouched.
  `/tracker-doctor` gains a WARN-only board reachability/scope check; `/tracker-init`
  gains an optional board-URL prompt. Needs the `project` token scope
  (`gh auth refresh -s project,read:project`).
```

- [ ] **Step 2: Verify markdown lint passes (G2)**

Run: `npx markdownlint-cli2 "CHANGELOG.md"`
Expected: `Summary: 0 error(s)`.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add GitHub Projects board entry under Unreleased"
```

---

## Task 10: Final verification + open the PR

**Files:** none (verification + PR only)

- [ ] **Step 1: Run all three CI gates locally**

```bash
# G1 — op-parity (expect NO output, then the exact 7-op list)
contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
for b in backends/github.md backends/jira.md; do \
  comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done
grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u | tr '\n' ' '; echo

# G2 — markdown lint
npx markdownlint-cli2 "README.md" "CONTRIBUTING.md" "CHANGELOG.md" "examples/**/*.md"

# G3 — yaml lint
yamllint -d relaxed .
```
Expected: G1 first loop empty + list = `add_label close_issue create_issue edit_body link_sub_issue list_open_issues view_issue`; G2 `0 error(s)`; G3 exit 0.

- [ ] **Step 2: Acceptance-criteria content review (from #40)**

Confirm by inspection that each is satisfied:
- [ ] `github.project` unset → no new behaviour (every new doc block is explicitly gated on `github.project`).
- [ ] set → file/link adds children (incl. sub-epics + cross-repo) to the board (Task 3 + Task 5).
- [ ] closing a child sets Status `Done`; `## Children` stays canonical (Task 5 step 2 + the "view, not source of truth" rule).
- [ ] `/tracker-doctor` WARNs (never FAILs) on missing scope / unreachable board (Task 7).
- [ ] `_interface.md` documents Projects as optional / github-only; seven-op contract + CI parity unchanged (Task 2 + G1).
- [ ] docs updated: `github.md`, `initiative-tracking`, config examples, `CHANGELOG.md` (Tasks 1,3,5,9).

- [ ] **Step 3: Confirm branch staleness + history**

```bash
git fetch origin --quiet
git rev-list --left-right --count HEAD...origin/main   # expect "9  0" (9 task commits ahead incl. spec, 0 behind)
git log --oneline origin/main..HEAD
```
Expected: ahead-only (0 behind). If behind > 0, rebase onto `origin/main` before opening the PR.

- [ ] **Step 4: Push + open the PR (per superpowers:finishing-a-development-branch)**

```bash
git push -u origin feat/github-projects-board
gh pr create --repo maxdimitrov/agent-issue-tracker \
  --base main --head feat/github-projects-board \
  --title "feat(github): optional GitHub Projects (board) support for initiatives" \
  --body-file <(cat <<'EOF'
Closes #40.

Optional, GitHub-only mirroring of an initiative's issue tree onto a GitHub
Projects (v2) board. Opt-in via a new `github.project` URL; unset = byte-identical
to today. The board is a view — the `## Children` mirror stays canonical; all board
writes are best-effort (never block an issue op). No backend-contract change (seven
ops untouched; CI op-parity green).

**Locus delta from the issue:** #40's Locus omitted `commands/resume-initiative.md`;
the operator approved adding the In-Progress hook there during the design pass
(faithful to #40's "Todo / In-Progress / Done" wording).

Design spec: `docs/superpowers/specs/2026-05-29-github-projects-board-design.md`.
Plan: `docs/superpowers/plans/2026-05-29-github-projects-board.md`.

## Test evidence
- op-parity gate (CI `backend-contract` replica): no missing ops; seven ops intact.
- `markdownlint-cli2` on README/CONTRIBUTING/CHANGELOG/examples: 0 errors.
- `yamllint -d relaxed .`: clean.
- `gh project {item-add,item-edit,field-list,view,item-list}` flags verified against the live CLI.

## Acceptance (#40)
- [x] `github.project` unset → identical to today.
- [x] set → file/link adds children (incl. sub-epics + cross-repo) to the board.
- [x] close → Status `Done`; `## Children` canonical.
- [x] `/tracker-doctor` WARNs (never FAILs) on missing scope / unreachable board.
- [x] `_interface.md` documents Projects as optional/github-only; seven-op contract + CI parity unchanged.
- [x] docs updated: github.md, initiative-tracking, config examples, CHANGELOG.md.
EOF
)
```

- [ ] **Step 5: Confirm the PR is open and links #40**

```bash
gh pr view --repo maxdimitrov/agent-issue-tracker feat/github-projects-board --json number,title,url,state
```
Expected: a single OPEN PR whose body contains `Closes #40`.

---

## Notes for the executor

- **Manual smoke is out-of-band.** A live `gh project item-add` against a real board needs the `project` scope and an operator-owned board; it is a release-gate smoke (per `CONTRIBUTING.md`), not part of this docs PR's CI. Don't block the PR on it.
- **Out of scope (deferred, do NOT add):** auto-creating a board; syncing fields beyond Status; a webhook CI job for status; Jira board parity.
- **One source-of-truth invariant above all:** every new doc block must read as *optional + best-effort + board-is-a-view*. If a sentence could be read as "the board is authoritative" or "a board failure blocks the op", fix it.
