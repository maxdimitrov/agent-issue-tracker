# Phase 1 — Backend Interface Contract + GitHub Backend + Config Schema

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the load-bearing seam of the agent-issue-tracker plugin: the seven-operation backend contract (`backends/_interface.md`), the GitHub reference implementation (`backends/github.md`), the canonical config schema (`examples/issue-tracker.yaml.example`), and a minimal GitHub setup example (`examples/github-config.yaml`). After this plan ships, Phase 2 (skill rewrites) and Phase 3 (Jira backend) are both unblocked.

**Architecture:** All v1 content is prose markdown + YAML. No code, no runtime. The contract documents *what* every backend must implement; the GitHub backend documents *how* `gh` CLI satisfies it. The schema YAML is what each consuming project commits to declare its tracker. Spec sections being implemented: §5.3 (contract), §5.4 (GitHub backend), §7 (config schema).

**Tech Stack:** Markdown + YAML. Verification via `python3 -c "import yaml"`, `grep`, `test -f`.

**Spec:** [`maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) §5.3, §5.4, §7.

**Issue:** [`maxdimitrov/agent-issue-tracker#9`](https://github.com/maxdimitrov/agent-issue-tracker/issues/9).

**Branch:** `feat/issue-9-backend-interface-and-github` on `maxdimitrov/agent-issue-tracker`.

**Working directory:** `F:/Claude/Projects/agent-issue-tracker`.

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `docs/superpowers/plans/2026-05-26-phase-1-backend-interface-and-github.md` | this file | The plan itself, lands alongside the implementation. |
| `backends/_interface.md` | create | The seven-operation contract every backend must implement. Tracker-agnostic inputs/outputs. Cross-backend invariants documented inline. |
| `backends/github.md` | create | The literal `gh` CLI invocations + `gh api` calls for each of the seven operations. Bakes in the `-F`-vs-`-f` gotcha for sub-issue linkage. |
| `examples/issue-tracker.yaml.example` | create | Heavily-commented schema sample. Required vs optional fields marked. Defaults shown. Both `github:` and `jira:` blocks present (consumer fills in the one they use). |
| `examples/github-config.yaml` | create | Minimal real-world GitHub setup. Parses as valid YAML. |
| `CHANGELOG.md` | modify | Append a Phase 1 line under `[Unreleased] > Added`. |

---

## Task 1: Write `backends/_interface.md`

**Files:**
- Create: `backends/_interface.md`

### Step 1.1: Write the contract file

Create `backends/_interface.md` with the structure below. Every section is REQUIRED.

````markdown
# Backend Operation Contract

Every backend module in `backends/<name>.md` implements this contract. The skill prose dispatches through these operations; the backend module documents the literal CLI / MCP calls for the specific tracker.

The contract is THE source of truth. If a backend module diverges from this contract — different operation name, different input shape, different return shape — the divergence is a bug in the backend module, not the contract.

## Operations

Seven operations. Inputs are tracker-agnostic field names; the backend module translates them into tracker-specific fields (label vs component vs custom field, etc.).

### `create_issue`

**Purpose:** File a new issue.

**Inputs:**
- `type` — one of `bug | feature | followup | epic | sub`
- `title` — short single-line summary
- `labels` — list of label strings to apply (always includes the type-driven default per config)
- `body` — markdown body string (the agent-prompt template, filled in)
- `parent` (optional) — parent issue ref, for sub-issues
- `area` (optional) — value from the consumer's `areas:` enum (config)
- `subsystem` (optional) — value from the consumer's `subsystems:` enum (config)

**Output:** issue ref — an opaque string in the tracker's syntax. `#42` on GitHub, `PROJ-123` on Jira. Skills never parse this; only backend modules do.

---

### `add_label`

**Purpose:** Apply an additional label to an existing issue.

**Inputs:**
- `ref` — issue ref
- `label` — label name

**Output:** (void)

---

### `link_sub_issue`

**Purpose:** Attach a child issue to a parent issue, creating the native parent-child relationship the tracker provides.

**Inputs:**
- `parent_ref` — parent issue ref
- `child_ref` — child issue ref

**Output:** (void)

---

### `list_open_issues`

**Purpose:** Filter open issues by type or label.

**Inputs:**
- `type` (optional) — filter to one of `bug | feature | followup | epic | sub`
- `label` (optional) — filter to a specific label

**Output:** list of `{ref, title, status}` entries.

---

### `view_issue`

**Purpose:** Read the full state of an issue.

**Inputs:**
- `ref` — issue ref

**Output:** `{ref, title, body, labels[], status, parent?}`. `parent` is present only when the issue is a sub-issue / child.

---

### `edit_body`

**Purpose:** Replace the body of an existing issue (destructive whole-body replace). Used by `initiative-tracking` to update the epic's Status block after a child closes.

**Inputs:**
- `ref` — issue ref
- `new_body` — new markdown body string

**Output:** (void)

**Note:** This operation is destructive. Both GitHub and Jira's edit-issue APIs replace the description in one call; there is no append-only API on either tracker. The skill is responsible for read-modify-write — fetch current body, modify in memory, write back the whole thing.

---

### `close_issue`

**Purpose:** Mark an issue resolved.

**Inputs:**
- `ref` — issue ref
- `comment` (optional) — closing comment string
- `reason` (optional) — `completed | not_planned | duplicate` (mapped per-tracker by backend module)

**Output:** (void)

---

## Cross-backend invariants

Every backend module MUST satisfy these. They are not negotiable.

1. **Body format is markdown.** GitHub natively renders markdown bodies; Jira accepts markdown via the Atlassian Remote MCP's ADF-translation layer. Skills produce markdown only — never ADF, never wiki markup, never HTML.

2. **Whole-body edits are destructive.** Both trackers' description fields are replaced entirely on edit. The skill reads the current body, modifies it in memory, then writes back. There is no append-only API.

3. **Sub-issue linkage is uniform from the skill's POV.** `link_sub_issue(parent_ref, child_ref)` works the same regardless of backend. The backend module handles the per-tracker mechanism — GitHub's native sub-issue API (`POST repos/.../issues/<parent>/sub_issues`); Jira's `parent` field on the sub-task or the legacy Epic Link customfield.

4. **Issue refs are opaque strings.** The skill never parses them. Only backend modules render or parse refs. This is what lets the same template produce `#42` on GitHub and `PROJ-123` on Jira without the skill prose knowing the difference.

5. **`/tracker-doctor` is the smoke test.** Every backend module MUST work end-to-end against `/tracker-doctor`'s reachability check. `/tracker-doctor` calls `view_issue` against a known-existent ref to prove the backend dispatch path works.

---

## Adding a new backend

To add a new backend (GitLab, Linear, Jira Server, plain-file, etc.):

1. Create `backends/<name>.md`.
2. For each of the seven operations above, document the literal CLI command, MCP tool call, or API request that implements it. Use the same field names as the contract; translate to tracker-specific fields inside the documentation.
3. Document how the five cross-backend invariants are satisfied.
4. Add a `<name>` block to the config schema in `examples/issue-tracker.yaml.example` with all required + optional fields.
5. Ship a minimal `examples/<name>-config.yaml`.
6. Update `/tracker-init` and `/tracker-doctor` to recognise `backend: <name>` as a valid choice.
7. Update `CHANGELOG.md`.

The contract itself does NOT change to accommodate a new backend. If a backend cannot satisfy the contract as written, the divergence is a backend bug, not a contract bug.
````

### Step 1.2: Verify

```bash
test -f backends/_interface.md
grep -c "^### \`" backends/_interface.md           # expect 7 (one per operation)
grep -c "create_issue\|add_label\|link_sub_issue\|list_open_issues\|view_issue\|edit_body\|close_issue" backends/_interface.md   # expect >= 7
grep -c "^## Cross-backend invariants\|^## Adding a new backend\|^## Operations" backends/_interface.md   # expect 3
```

Expected: file exists, 7 H3 operation sections, all 7 op names mentioned, all 3 H2 structural sections.

### Step 1.3: Commit

```bash
git add backends/_interface.md
git commit -m "feat(backends): document the seven-operation backend contract (#9)"
```

---

## Task 2: Write `backends/github.md`

**Files:**
- Create: `backends/github.md`

### Step 2.1: Write the GitHub backend file

Create `backends/github.md` with the structure below.

````markdown
# GitHub Backend

Backend module for [`gh` CLI](https://cli.github.com/) — the dispatch surface for the `github` backend. Implements the seven operations from [`_interface.md`](_interface.md).

## Auth

Consumer runs `gh auth login` once per machine. The `gh` CLI manages the credential. No per-project token storage in the plugin.

For GitHub Enterprise, `gh auth login --hostname <enterprise-host>`. The `github.repo` field in `.claude/issue-tracker.yaml` is qualified by host implicitly because `gh` resolves `owner/repo` against whichever host the CLI is currently authed to.

## Reference: `gh issue` and `gh api` commands

| Operation | Command shape |
|---|---|
| Create | `gh issue create --repo OWNER/REPO --title TITLE --body-file PATH --label "L1,L2"` |
| Add label | `gh issue edit N --repo OWNER/REPO --add-label LABEL` |
| Sub-issue link (resolve child id) | `gh api repos/OWNER/REPO/issues/N --jq .id` |
| Sub-issue link (attach) | `gh api -X POST repos/OWNER/REPO/issues/PARENT/sub_issues -F sub_issue_id=CHILD_ID` |
| List open | `gh issue list --repo OWNER/REPO --label LABEL --state open --json number,title,state` |
| View | `gh issue view N --repo OWNER/REPO --json body,labels,state` |
| Edit body (destructive) | `gh issue edit N --repo OWNER/REPO --body-file PATH` |
| Close | `gh issue close N --repo OWNER/REPO --comment "REASON"` |

---

## Operations

### `create_issue`

```bash
# Write body to a temp file (gh --body has shell-escaping pitfalls; --body-file is safer)
echo "$BODY" > .tmp_issue_body.md
gh issue create \
  --repo "$GITHUB_REPO" \
  --title "$TITLE" \
  --body-file .tmp_issue_body.md \
  --label "$(IFS=,; echo "${LABELS[*]}")"
rm .tmp_issue_body.md
```

Returns the URL of the created issue; the skill captures the trailing `/N` as the ref.

**Field mapping:**
- `type` → maps to a label from `types.<type>.labels` in config (`bug → bug`, `feature → enhancement`, `epic → epic`, etc.)
- `area` → applied as a label (`github` backend uses labels for areas; no `components` concept)
- `subsystem` → not a label; goes inline in the issue body's Locus block
- `parent` → not used at create-time; sub-issue linkage is a separate `link_sub_issue` call after the child exists

---

### `add_label`

```bash
gh issue edit "$N" --repo "$GITHUB_REPO" --add-label "$LABEL"
```

If `$LABEL` doesn't exist on the repo, `gh` errors. `/tracker-doctor` warns if the consumer's configured `areas:` enum references missing labels and prints the `gh label create` commands to fix.

---

### `link_sub_issue`

Two-step on GitHub. The native `sub_issues` API takes the child's *database id* (integer), not its number.

```bash
# Resolve child database id (NOT the issue number)
CHILD_ID=$(gh api repos/"$GITHUB_REPO"/issues/"$CHILD_N" --jq .id)

# Attach via the sub-issue API
gh api -X POST repos/"$GITHUB_REPO"/issues/"$PARENT_N"/sub_issues \
  -F sub_issue_id="$CHILD_ID"
```

**Critical gotcha:** the `sub_issue_id` field MUST be passed with `-F` (typed integer), not `-f` (string). Wrong flag returns:

```
HTTP 422: Invalid property /sub_issue_id: is not of type integer
```

This bites every operator who reads the GitHub API docs casually. Always `-F`.

---

### `list_open_issues`

```bash
gh issue list \
  --repo "$GITHUB_REPO" \
  --label "$FILTER" \
  --state open \
  --json number,title,state \
  --jq '.[] | "\(.number)\t\(.title)\t\(.state)"'
```

For multi-label AND-filter, repeat `--label`. For type-filter, pass the type-driven label (`bug`, `enhancement`, `epic`).

---

### `view_issue`

```bash
gh issue view "$N" --repo "$GITHUB_REPO" --json body,labels,state,title
```

Returns JSON with the issue's body, labels array, state (`OPEN | CLOSED`), and title. For parent lookup on sub-issues, query `gh api repos/$GITHUB_REPO/issues/$N --jq '.sub_issue_id // empty'` (no native parent field via `gh issue view`).

---

### `edit_body`

```bash
# Read current body first if doing read-modify-write
gh issue view "$N" --repo "$GITHUB_REPO" --json body --jq .body > .tmp_current_body.md
# ... modify .tmp_current_body.md in memory ...
gh issue edit "$N" --repo "$GITHUB_REPO" --body-file .tmp_current_body.md
rm .tmp_current_body.md
```

Destructive replace. There is no append-only API on `gh`. The Status-block-update path in `initiative-tracking` uses exactly this read-modify-write shape.

---

### `close_issue`

```bash
gh issue close "$N" --repo "$GITHUB_REPO" --comment "$COMMENT"
```

For `reason: not_planned`, pass `--reason "not planned"`. For `reason: duplicate`, no native equivalent — close with a `--comment` that references the duplicate's ref instead.

---

## Cross-backend invariants — how GitHub satisfies them

1. **Body format is markdown** — GitHub renders markdown natively. Plugin emits markdown directly.
2. **Whole-body edits are destructive** — `gh issue edit --body-file` replaces the whole description. Plugin pattern: `gh issue view --json body --jq .body` → modify in memory → `gh issue edit --body-file`.
3. **Sub-issue linkage** — GitHub's native sub-issue API (the `sub_issues` endpoint). Implemented per `link_sub_issue` above.
4. **Issue refs are opaque** — GitHub refs are `#N`, where `N` is the per-repo issue number. The skill treats this as opaque; only this backend module knows the syntax.
5. **`/tracker-doctor` reachability** — runs `gh auth status` + `gh repo view "$GITHUB_REPO"`. Both must succeed.

## PR close-on-merge convention

GitHub auto-closes referenced issues when the merging PR's body or title contains `Fixes #N`, `Closes #N`, or `Resolves #N` and the PR merges to the repo's default branch. The plugin's `feature-request` and `bug-tracking` skills tell the agent to include `Closes #<N>` in PR bodies for this backend. Trading-bot's existing convention is `Fixes #N` for bugs and `Closes #N` for features — both work identically.

The consumer's `.claude/issue-tracker.yaml`'s `github.default_pr_close_syntax` field is rendered into PR description templates as the recommended phrasing.

## Setup verification

`/tracker-doctor` runs (in order):

1. `gh auth status` — must succeed (consumer is authed).
2. `gh repo view "$GITHUB_REPO"` — must succeed (repo exists, consumer has access).
3. For each label in `areas:`, `gh label list --repo "$GITHUB_REPO" --search "$LABEL"` — warning if missing, prints `gh label create` next-step.
````

### Step 2.2: Verify

```bash
test -f backends/github.md
grep -c "^### \`" backends/github.md           # expect 7 (one per operation)
grep -c "gh issue create\|gh issue edit\|gh issue view\|gh issue list\|gh issue close\|gh api" backends/github.md   # expect >= 7
grep -c "\-F sub_issue_id\|typed integer" backends/github.md   # expect >= 2 (the gotcha is called out twice)
```

Expected: file exists, 7 H3 operation sections, multiple `gh` invocations, the typed-int gotcha is documented.

### Step 2.3: Commit

```bash
git add backends/github.md
git commit -m "feat(backends): GitHub backend module via gh CLI (#9)"
```

---

## Task 3: Write `examples/issue-tracker.yaml.example`

**Files:**
- Create: `examples/issue-tracker.yaml.example`

### Step 3.1: Write the schema example

Create `examples/issue-tracker.yaml.example` with comments showing every field's role and default.

```yaml
# .claude/issue-tracker.yaml — agent-issue-tracker schema v1
#
# Each consuming project commits one such file at its repo root. The plugin's
# skills + slash commands read this file to know which tracker backend to
# dispatch to and how to fill in tracker-specific fields.
#
# Fields marked REQUIRED have no default. Fields marked optional show the
# default the plugin uses if you omit them.

# REQUIRED. Schema version. The plugin reads this to apply forward-compat
# migrations. v1 is the only version v1 of the plugin understands.
schema_version: 1

# REQUIRED. Backend identifier. Currently supported: github | jira.
backend: github

# Optional. Per-type config (labels and title conventions).
# All five types ship with sensible defaults; override only what you need.
types:
  bug:
    labels: [bug]                # always applied at create_issue time
    title_prefix: ""             # advisory; the skill includes this in the title
  feature:
    labels: [enhancement]
  followup:
    labels: [followup]
  epic:
    labels: [epic]
    title_prefix: "epic: "       # all epics get this prefix in the title
  sub:
    labels: []                   # initiative-tracking adds phase prefix at file time

# Optional. Project vocabulary for the `<area>` label.
# If set, skills nudge the agent to pick from this enum when filling the
# Locus / area block. If omitted, the area field becomes free-form.
areas:
  - dashboard
  - backend
  - frontend
  - infra

# Optional. Project vocabulary for the `<subsystem>` body field.
# Same role as areas, but goes inline in the issue body's Locus block
# rather than as a label.
subsystems:
  - ibkr
  - proposal-service
  - execution-service
  - scheduler
  - scripts

# Optional. Triage label names. Override only if your tracker uses different names.
triage:
  needs_design_label: needs-design   # default
  needs_triage_label: needs-triage   # default

# REQUIRED if `backend: github`. GitHub backend config.
github:
  # REQUIRED. The "owner/repo" of the tracker repo (where issues are filed).
  repo: maxdimitrov/example-project

  # Optional. The PR close-on-merge phrasing rendered into PR description
  # templates by feature-request / bug-tracking. Default: "Fixes #N".
  default_pr_close_syntax: "Fixes #N"

# REQUIRED if `backend: jira`. Jira Cloud backend config.
# Jira reaches the tracker via the Atlassian Remote MCP — no API tokens
# stored in the plugin. /tracker-init resolves cloud_id automatically.
jira:
  # REQUIRED. Your Atlassian site domain (without https://).
  site: example.atlassian.net

  # REQUIRED. Filled by /tracker-init via Atlassian MCP's site-discovery tool.
  cloud_id: ""

  # REQUIRED. The Jira project key under which issues are filed.
  project: TRADE

  # REQUIRED. Map the plugin's 5 type names to your Jira project's
  # issue types. The names on the right must match your project's
  # configured issue types exactly (case-sensitive).
  issue_types:
    bug: Bug
    feature: Story          # or Task — per your team's convention
    epic: Epic
    sub: Sub-task           # or Story for epic-children

  # Optional. Where the `<area>` value goes in Jira. Default: components.
  # Set to `labels` if your project uses labels for area-style tagging
  # instead of Jira's Components feature.
  area_field: components

  # Optional. How epics link to their children. Default: native.
  #   native     — modern Cloud unified parent field (sub-task.parent.key)
  #   epic_link  — classic customfield_10014 Epic Link
  parent_link_style: native

  # Optional. Only used if parent_link_style: epic_link. Default: customfield_10014.
  epic_link_field: customfield_10014

  # Optional. The transition name to "Done" state in your project's workflow.
  # Default: Done.
  done_transition: Done

  # Optional. Advisory text rendered into PR descriptions, telling reviewers
  # how your Jira-PR integration triggers auto-close. Plugin does not enforce
  # auto-close — this is purely advisory text.
  close_on_merge_hint: ""
```

### Step 3.2: Verify

```bash
test -f examples/issue-tracker.yaml.example
python3 -c "import yaml; d=yaml.safe_load(open('examples/issue-tracker.yaml.example')); print('schema_version=', d['schema_version']); print('backend=', d['backend']); print('github.repo=', d['github']['repo']); print('jira.issue_types=', d['jira']['issue_types'])"
```

Expected: file exists, parses as valid YAML, all four top-level keys (`schema_version`, `backend`, `github`, `jira`) present with expected types.

### Step 3.3: Commit

```bash
git add examples/issue-tracker.yaml.example
git commit -m "feat(examples): schema v1 reference YAML with comments (#9)"
```

---

## Task 4: Write `examples/github-config.yaml`

**Files:**
- Create: `examples/github-config.yaml`

### Step 4.1: Write the minimal GitHub example

Create `examples/github-config.yaml` — a minimal real-world setup with no comments.

```yaml
schema_version: 1
backend: github

areas: [dashboard, backend, frontend, infra]
subsystems: [api, worker, scheduler, scripts]

github:
  repo: your-org/your-repo
```

### Step 4.2: Verify

```bash
test -f examples/github-config.yaml
python3 -c "import yaml; d=yaml.safe_load(open('examples/github-config.yaml')); assert d['schema_version']==1; assert d['backend']=='github'; assert d['github']['repo']=='your-org/your-repo'; print('OK')"
```

Expected: `OK`.

### Step 4.3: Commit

```bash
git add examples/github-config.yaml
git commit -m "feat(examples): minimal GitHub backend config (#9)"
```

---

## Task 5: Update `CHANGELOG.md`

**Files:**
- Modify: `CHANGELOG.md`

### Step 5.1: Append the Phase 1 entry

Change the `[Unreleased] > Added` section to include the Phase 1 entry:

```markdown
## [Unreleased]

### Added
- Phase 0 bootstrap: plugin manifest, LICENSE, README/CONTRIBUTING/CHANGELOG placeholders, directory skeleton from spec §5.1.
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
```

### Step 5.2: Verify

```bash
grep "Phase 1" CHANGELOG.md   # expect at least one hit
```

### Step 5.3: Commit

```bash
git add CHANGELOG.md
git commit -m "chore(changelog): Phase 1 entry under Unreleased (#9)"
```

---

## Task 6: Final acceptance check + open PR

### Step 6.1: Run all acceptance checks together

```bash
cd F:/Claude/Projects/agent-issue-tracker
test -f backends/_interface.md && echo "interface-OK" || echo "interface-MISSING"
test -f backends/github.md && echo "github-OK" || echo "github-MISSING"
test -f examples/issue-tracker.yaml.example && echo "schema-example-OK" || echo "schema-example-MISSING"
test -f examples/github-config.yaml && echo "github-config-OK" || echo "github-config-MISSING"
python3 -c "import yaml; yaml.safe_load(open('examples/issue-tracker.yaml.example'))" && echo "schema-yaml-VALID"
python3 -c "import yaml; yaml.safe_load(open('examples/github-config.yaml'))" && echo "github-yaml-VALID"
grep -c "^### \`" backends/_interface.md
grep -c "^### \`" backends/github.md
grep "Phase 1" CHANGELOG.md
```

Expected:
- All 4 `*-OK` markers.
- 2 `*-VALID` markers.
- 7 H3 operation sections in `_interface.md`.
- 7 H3 operation sections in `github.md`.
- A `Phase 1` line in CHANGELOG.

### Step 6.2: Stage the plan + push the branch

```bash
git add docs/superpowers/plans/2026-05-26-phase-1-backend-interface-and-github.md
git commit -m "docs(plan): Phase 1 implementation plan (#9)"
git push -u origin feat/issue-9-backend-interface-and-github
```

### Step 6.3: Branch staleness check before PR

```bash
git fetch origin main && git rev-list --left-right --count HEAD...origin/main
```

Expected: N ahead, 0 behind (pure-addition expectation; only this branch has touched main since Phase 0 merged).

### Step 6.4: Open PR

```bash
gh pr create \
  --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/issue-9-backend-interface-and-github \
  --title "Phase 1: backend interface contract + GitHub backend + config schema" \
  --body "$(cat <<'EOF'
## Summary

- `backends/_interface.md` — the seven-operation contract every backend must implement, plus five cross-backend invariants.
- `backends/github.md` — `gh` CLI invocations for each operation, with the `-F sub_issue_id` typed-int gotcha called out.
- `examples/issue-tracker.yaml.example` — heavily-commented schema v1 reference.
- `examples/github-config.yaml` — minimal real-world GitHub setup.
- `CHANGELOG.md` — Phase 1 entry under Unreleased.
- `docs/superpowers/plans/2026-05-26-phase-1-backend-interface-and-github.md` — the plan that produced this PR.

## Tracking

Closes #9. Part of `maxdimitrov/trading-bot#153` initiative epic.

## Test plan

- [x] `test -f` for all 4 new content files
- [x] `python3 -c "import yaml"` parses both YAML files
- [x] `grep -c '^### \`'` returns 7 for both `_interface.md` and `github.md` (one H3 per operation)
- [x] `_interface.md` documents all 5 cross-backend invariants
- [x] `github.md` documents the `-F` typed-int gotcha for sub-issue linkage
- [x] CHANGELOG `[Unreleased] > Added` has a Phase 1 entry

## Notes

This PR is Phase 1 of the agent-issue-tracker v1 plan. After it merges, Phase 2 (skill rewrites — 5 separate sub-issues) and Phase 3 (Jira backend, which implements the same contract) are unblocked.
EOF
)"
```

### Step 6.5: Capture PR URL + comment on epic

```bash
PR_URL=$(gh pr view --repo maxdimitrov/agent-issue-tracker --json url --jq .url)
gh issue comment 153 --repo maxdimitrov/trading-bot \
  --body "Phase 1 PR opened: $PR_URL — Closes agent-issue-tracker#9."
```

The epic body's Children list gets `[x]` flipped on `agent-issue-tracker#9` AFTER the PR merges (Task 7.3 below).

---

## Task 7: Merge Phase 1 + update epic

### Step 7.1: Merge the Phase 1 PR

After PR review (self-review acceptable for prose-only PRs):

```bash
PR_N=$(gh pr list --repo maxdimitrov/agent-issue-tracker --head feat/issue-9-backend-interface-and-github --json number --jq '.[0].number')
gh pr merge "$PR_N" --repo maxdimitrov/agent-issue-tracker --squash --delete-branch
```

### Step 7.2: Verify issue #9 closed by merge

GitHub auto-closes `#9` because the PR body has `Closes #9`.

```bash
gh issue view 9 --repo maxdimitrov/agent-issue-tracker --json state --jq .state
```

Expected: `CLOSED`.

### Step 7.3: Update epic Status block

Read current epic body, flip `agent-issue-tracker#9` to `[x]`, update Status block to `Phase 2 · 2/15 sub-issues closed`, append Decision log entry.

```bash
gh issue view 153 --repo maxdimitrov/trading-bot --json body --jq .body > .tmp_epic_body.md
# Edit:
#   - Status block "Phase: ..." line → "Phase 2 · 2/15 sub-issues closed"
#   - Status block "Next up: ..." line → "<Phase 2 first sub-issue — to be filed>"
#   - Status block "Last updated:" → today
#   - Children list: [x] mark agent-issue-tracker#9 with close date
#   - Decision log: append a 2026-05-2N entry covering Phase 1 close
gh issue edit 153 --repo maxdimitrov/trading-bot --body-file .tmp_epic_body.md
rm .tmp_epic_body.md
```

---

## Phase 1 done when

- [ ] `backends/_interface.md` exists on `agent-issue-tracker` main, documents 7 operations + 5 invariants + "adding a new backend" guide.
- [ ] `backends/github.md` exists on `agent-issue-tracker` main, documents 7 operations via `gh` CLI with the typed-int gotcha called out.
- [ ] `examples/issue-tracker.yaml.example` + `examples/github-config.yaml` exist on `agent-issue-tracker` main, both parse as valid YAML.
- [ ] `CHANGELOG.md` `[Unreleased] > Added` section has a Phase 1 entry.
- [ ] PR merged on `agent-issue-tracker` (auto-closes #9).
- [ ] Epic #153 Status block reflects Phase 2 next-up, child #9 marked closed in Children list.

---

## Out of scope (for clarity)

This plan deliberately does NOT do:

- **Jira backend** — Phase 3.
- **Skill rewrites** — Phase 2.
- **Slash commands (`/tracker-init`, `/tracker-doctor`, `/resume-initiative`)** — Phase 3.
- **CI workflows** — Phase 4.
- **README rewrite** — Phase 4.
- **Custom-field support, Jira Server, GitLab** — explicit day-one follow-on issues (#1-#8).
