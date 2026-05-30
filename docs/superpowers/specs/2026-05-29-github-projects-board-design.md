# Design: GitHub Projects (board) support for initiatives

- **Issue:** [maxdimitrov/agent-issue-tracker#40](https://github.com/maxdimitrov/agent-issue-tracker/issues/40) — `feat(github): GitHub Projects (board) support for initiatives`
- **Branch:** `feat/github-projects-board`
- **Date:** 2026-05-29
- **Status:** approved design — ready for `writing-plans`
- **Builds on:** #39 (N-level nested initiatives, merged)

## Summary

Let the plugin **optionally** mirror an initiative's issue tree onto a GitHub
Projects (v2) board — adding the root epic, every sub-epic, and every leaf child
(including cross-repo `owner/repo#N` children) as Project items, and reflecting
each child's lifecycle in the board's **Status** field. The board is a
**human-facing logistics view**; it never becomes the source of truth. The
`## Children` task-list mirror inside each epic body stays canonical, exactly as
today.

The whole feature is **opt-in and additive**: with no `github.project` configured,
behaviour is byte-identical to today.

## Goal (verbatim from #40)

> The plugin can optionally populate a GitHub Projects (v2) board from an
> initiative's issue tree — adding the epic, its sub-epics, and leaf children
> (including cross-repo `owner/repo#N` children) as Project items — giving
> multi-repo initiatives a human-facing logistics board on top of the
> agent-readable `## Children` mirror, without the board ever becoming the source
> of truth.

## Architecture decision: pure-prose, agent-driven

The plugin ships **zero executable code**. Backends are *documented `gh` / MCP
calls* the agent runs; behaviour lives in skill + command prose. This feature
follows the same shape:

- The literal `gh project` invocations are documented in `backends/github.md`.
- The *when* (file a child → add to board; close a child → set Done; etc.) is
  woven into `skills/initiative-tracking/SKILL.md` and `commands/resume-initiative.md`.

**Rejected alternatives:**

- *A bundled `populate-board.sh` helper* — breaks the no-code architecture; the
  repo has no scripts, only documented CLI.
- *A new `/populate-board` slash command* — #40 wants population as a
  **side-effect** of filing/linking children, not a separate verb. Backfilling an
  existing tree is rare enough to be a documented procedure, not a command.

## Fork resolutions

#40 carried four open design forks (`needs-design`). All resolved:

### (a) Optional capability vs new contract operation → **optional capability**

Projects population is documented as an **OPTIONAL, GitHub-only affordance — NOT a
contract operation.** The seven-operation contract in `backends/_interface.md`
stays seven.

This is forced by the CI `backend-contract` job (`.github/workflows/ci.yml`): it
greps operation headings of the form `` ### `<op>` `` out of `backends/_interface.md`
and asserts each appears in **every** `backends/<backend>.md`. Adding a new
`` ### `op` `` would (1) demand a Jira implementation and (2) break op-parity. So
the Projects section in `github.md` uses a plain `##` heading (e.g.
`## GitHub Projects v2 board (optional)`), never a `` ### `backtick-wrapped` ``
op-name heading, and `_interface.md` gains a short note documenting Projects as an
optional affordance outside the contract.

### (b) Create vs link the Project → **link an existing board**

The operator creates the user/org-level Project v2 board by hand (one-time, in the
browser) and records its URL in `github.project`. The plugin only **adds items**
and **sets Status**. No project-create or field-provisioning GraphQL in v1 —
smallest surface, fewest failure modes, operator owns the board's columns/views.

### (c) Field state to sync → **Status field, three states**

Sync only the **Status** single-select field (GitHub Projects' built-in
`Todo / In Progress / Done`). Three states, each mapped to a *real* plugin
lifecycle event:

| Status | Trigger | Where documented |
|---|---|---|
| **Todo** | child issue filed + linked | `initiative-tracking` (file/link step) |
| **In Progress** | `/resume-initiative --start` enters/creates the child's worktree | `commands/resume-initiative.md` (Mode 3) |
| **Done** | child issue closes | `initiative-tracking` (Maintenance read-modify-write) |

> **Locus note.** The In-Progress hook expands #40's stated Locus to include
> `commands/resume-initiative.md`. This is a deliberate, operator-approved
> expansion during the design pass — and it is faithful to #40's own Sketch,
> which names "Todo / In-Progress / Done". The PR description must call out the
> Locus delta from the issue body.

No other field state is synced in v1 (no assignees, no iteration, no custom
fields). The board's other columns/automations are the operator's to manage.

### (d) Jira parity → **n/a, one-line note**

Projects-board population is a GitHub-specific affordance. `backends/jira.md` gets
a single line: n/a for Jira — use Jira boards. No Jira behaviour change.

## Config schema (new, optional)

One new optional field under the existing `github:` block:

```yaml
github:
  repo: owner/repo
  # Optional. A user- or org-level GitHub Projects (v2) board URL. When set,
  # initiative-tracking mirrors the initiative tree onto this board (best-effort;
  # the ## Children mirror stays canonical). Absent -> no board behaviour.
  project: https://github.com/users/<owner>/projects/<N>
```

- **A single URL field**, not separate owner/number/scope fields. The URL encodes
  everything the `gh project` CLI needs and is copy-pasteable straight from the
  browser address bar.
- Two accepted URL shapes:
  - User board: `https://github.com/users/<login>/projects/<N>` → owner `<login>`, number `<N>`
  - Org board:  `https://github.com/orgs/<org>/projects/<N>` → owner `<org>`, number `<N>`
- **Repo-level project URLs** (`https://github.com/<owner>/<repo>/projects/<N>`)
  are intentionally **not** supported — repo projects can't span repos, which
  defeats the cross-repo use case. `/tracker-doctor` WARNs if a repo-level URL is
  configured.
- **Absent → behaviour identical to today.** This is the load-bearing invariant.

## Behaviour spec

### Resolving board identifiers (once per agent session)

Before any item write, the agent resolves and caches three IDs from the configured
`github.project` URL:

1. Parse `<owner>` and `<number>` from the URL.
2. `gh project view <number> --owner <owner> --format json` → project node `id`.
3. `gh project field-list <number> --owner <owner> --format json` → locate the
   single-select field named `Status` and its option IDs for `Todo`,
   `In Progress`, `Done` (match by name, case-insensitive, tolerating `To do` /
   `Todo`). If the Status field or an expected option is absent, **skip status
   writes** (still add items) and WARN once.

### 1. On file/link a child (Todo)

Extends `initiative-tracking`'s existing "Linking children to the epic" step.
After `link_sub_issue` + the `## Children` mirror append, **if `github.project`
is set**:

```text
gh project item-add <number> --owner <owner> --url <child-issue-url> --format json
  -> capture item.id
gh project item-edit --id <item-id> --project-id <project-id> \
  --field-id <status-field-id> --single-select-option-id <todo-option-id>
```

Applies to **every node** — root epic, sub-epics, and leaves. Cross-repo
`owner/repo#N` children are added by their **full issue URL**, which a
user/org-level board accepts regardless of source repo.

### 2. On `/resume-initiative --start` (In Progress)

Extends `commands/resume-initiative.md` Mode 3. After the worktree for the
next-up leaf is created/entered and **if `github.project` is set**, set that
child's board item Status = `In Progress` (resolve item id via the project's
item list filtered to the child URL; `item-edit` to the In-Progress option).
Best-effort; a failure prints a WARN and does not abort the `--start` handoff to
brainstorming.

### 3. On child close (Done)

Extends `initiative-tracking`'s "Maintenance" read-modify-write. After flipping
the `## Children` checkbox to `[x] ... — closed YYYY-MM-DD` and updating the
parent's Status block, set the child's board item Status = `Done`. One-hop,
best-effort.

### 4. Backfill an existing tree (documented procedure, not a command)

When an operator newly sets `github.project` on an in-flight initiative, the agent
(prompted by "populate the board" / on next initiative-tracking touch) walks each
epic node's `## Children` mirror **top-down** (root → sub-epics → leaves) and runs
the file/link path's `item-add` for every node, setting Status from each issue's
current open/closed state (open → Todo, closed → Done). Idempotent: GitHub
Projects v2 stores a content item at most once, so re-adding an already-present
issue returns the existing item — no duplicates.

## Failure semantics — best-effort, never blocking

Any `gh project` failure — missing `project` scope, unreachable board, GraphQL
error, absent Status field — results in a **WARN and continue**. It never blocks
or rolls back the underlying `create_issue` / `link_sub_issue` / `close_issue` /
`--start` operation. Rationale: the board is a convenience view; the `## Children`
mirror is the source of truth (the issue's hard invariant). A degraded board is
always preferable to a blocked initiative operation.

## `/tracker-doctor` — new WARN-only check

In the GitHub branch of Phase 2, **only when `github.project` is set**, add a
reachability + scope probe (WARN-level; `/tracker-doctor` still always exits 0):

- `gh project view <number> --owner <owner>` — PASS if reachable.
- On `gh` error mentioning scope / permission → WARN with the paste-able fix:

  ```bash
  gh auth refresh -s project,read:project
  ```

- If `github.project` is a **repo-level** URL → WARN ("repo projects can't span
  repos; use a user/org-level board for cross-repo initiatives").

Never FAIL — matches the command's informational discipline (`PASS / WARN / FAIL /
PASS-WITH-NOTE` taxonomy; the board is optional, so its absence/unreachability is
never structurally broken config).

## `/tracker-init` — one optional prompt

In Phase 3 (GitHub branch), after the repo prompt, add **one optional**
`AskUserQuestion`: "Paste a GitHub Projects board URL to mirror initiatives onto
(optional)." Accept a pasted URL via "Other"; skipping (blank) omits
`github.project` from the emitted YAML. No new STOP-IF-FAIL — a board is never
required. Phase 8's next-steps panel gains a conditional line when a project was
configured, reminding the operator to grant scopes with
`gh auth refresh -s project,read:project`.

## `_interface.md` note

Add a short subsection documenting that GitHub Projects population is an
**optional, backend-specific capability — explicitly NOT one of the seven contract
operations**. This keeps fork (a) honest and the `backend-contract` CI job green
(seven ops stay seven; no new `` ### `op` `` heading anywhere).

## Files touched

Matches #40's Locus **plus** the approved `commands/resume-initiative.md` addition:

| File | Change |
|---|---|
| `backends/github.md` | new `## GitHub Projects v2 board (optional)` section — URL parsing, ID resolution, `item-add` / `item-edit`, scopes, idempotency, cross-repo URL note |
| `backends/_interface.md` | optional-affordance note (NOT a new op) |
| `backends/jira.md` | one-line n/a note |
| `skills/initiative-tracking/SKILL.md` | Todo-on-file, Done-on-close, backfill procedure; "the board is a view, the `## Children` mirror stays canonical" |
| `commands/resume-initiative.md` | Mode 3: In-Progress on `--start` (best-effort) |
| `commands/tracker-doctor.md` | WARN-only project scope + reachability check |
| `commands/tracker-init.md` | optional Project-URL prompt + next-steps scope reminder |
| `examples/issue-tracker.yaml.example` | optional `github.project` field, documented |
| `examples/github-config.yaml` | show the optional `github.project` field (commented) |
| `CHANGELOG.md` | `## [Unreleased]` → Added entry |

## Invariants preserved

1. **No `github.project` → byte-identical to today.** Pure opt-in.
2. **Seven-op contract unchanged**; CI `backend-contract` op-parity stays green
   (no new `` ### `op` `` in `_interface.md`).
3. **`## Children` mirror stays canonical**; the board is a derived view.
4. **markdownlint + yamllint stay green** (only README/CONTRIBUTING/CHANGELOG/
   examples are markdown-linted; the new spec doc lives in `docs/` and is outside
   the lint globs, but is kept clean regardless).
5. **No Jira behaviour change** beyond the one-line n/a note.

## Verification plan

```bash
# 1. CI op-parity must stay green (no new contract op) — expect NO output
contract=$(grep -oP '^### `\K[a-z_]+(?=`)' backends/_interface.md | sort -u)
for b in backends/github.md backends/jira.md; do \
  comm -23 <(echo "$contract") <(grep -oP '^### `\K[a-z_]+(?=`)' "$b" | sort -u); done

# 2. Markdown + YAML lint (CI parity)
npx markdownlint-cli2 "README.md" "CONTRIBUTING.md" "CHANGELOG.md" "examples/**/*.md"
yamllint -d relaxed .

# 3. Manual smoke (needs the scopes first)
gh auth refresh -s project,read:project
gh project item-add <N> --owner <owner> --url <issue-url> --format json
gh project field-list <N> --owner <owner> --format json   # confirm Status options
```

Acceptance (from #40), all satisfied by the above:

- [ ] `github.project` unset → identical to today.
- [ ] set → filing/linking children adds them (incl. sub-epics + cross-repo
  `owner/repo#N`) to the board.
- [ ] closing a child sets its Status `Done`; `## Children` stays canonical.
- [ ] `/tracker-doctor` WARNs (never FAILs) on missing scope / unreachable board.
- [ ] `_interface.md` documents Projects as optional / github-only; seven-op
  contract + CI parity unchanged.
- [ ] docs updated: `backends/github.md`, `initiative-tracking`, config examples,
  `CHANGELOG.md`.

## Out of scope / follow-ups

- **Auto-creating** a Project board (fork b's other branch) — deferred; operator
  creates the board.
- **Syncing fields beyond Status** (assignees, iteration, custom) — deferred.
- **A CI job** that sets Status on `issue.closed` webhook events without an agent
  in the loop — candidate follow-up (mirrors the existing "optional CI job for
  Status-block maintenance" note in `initiative-tracking`).
- **Jira board parity** — out of scope by decision (d).

## Open questions

None — all four forks resolved above. The only scope judgement (3-state +
In-Progress, expanding the Locus to `commands/resume-initiative.md`) was made
explicitly by the operator during this design pass.
