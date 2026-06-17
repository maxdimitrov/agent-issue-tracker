# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.0] - 2026-06-17

### Added

- **Four explicit filing slash commands — `/file-bug`, `/file-feature`,
  `/file-followup`, `/file-epic`** (#8). Discoverable command-palette
  entry-points that wrap the four issue-filing skills (`bug-tracking`,
  `feature-request`, `followup-tracking`, `initiative-tracking`
  respectively). Each is a one-screen wrapper that invokes its skill with
  any post-command text as starting context, then lets the skill run its
  normal flow unchanged — gather the agent-prompt body, apply the bail
  criteria, and dispatch `create_issue` through the backend resolved from
  `.claude/issue-tracker.yaml`. **No behavioural divergence:** the commands
  are pure UX entry-points, the skills remain the source of truth; filing by
  intent ("file a bug") is byte-for-byte equivalent. Originally deferred from
  v1 per spec §5.6 as a reopen-on-demand candidate (#8 carried
  `needs-design`); built now that the discoverability demand materialised, so
  the design gate is resolved and the label dropped. Each filing skill gained
  a reciprocal **"Slash-command entry-point"** note so the skill ↔ command
  mapping is bidirectional. Component count swept five → nine slash commands
  (six skills + nine commands) across `marketplace.json`, `plugin.json`, and
  `README.md`. **No** backend-contract change — the eight operations are
  untouched and the commands add no `` ### `op` `` heading, so the CI
  `backend-contract` op-parity check stays green.

### Release-gate smokes

Per `CONTRIBUTING.md` "Release process". This release adds **four new slash
commands** (`commands/file-bug.md`, `commands/file-feature.md`,
`commands/file-followup.md`, `commands/file-epic.md`) plus doc updates (the
four filing skills, `README.md`, `plugin.json`, `marketplace.json`,
`CHANGELOG.md`). No backend operation logic and no backend-contract change —
the eight operations are untouched and the `backends/*.md` modules are
unedited, so backend-dispatch risk is confined to the create / label / link /
close paths smoke 1 exercises directly.

- **1. GitHub backend smoke — PASS.** Filed bug (#78), feature (#79),
  followup (#80), and an epic (#81) with a linked sub-issue (#82) against
  this repo. Verified labels (`bug`; `enhancement`; `enhancement`+`followup`;
  `epic`; `enhancement`) and native sub-issue linkage (#81 → #82 via the
  `-F` typed-integer `sub_issues` API). All five closed after verification.
- **2. Jira backend smoke — DEFERRED.** Atlassian connector not configured
  this session; no backend-module change (`backends/jira.md` unedited), so
  Jira dispatch is identical to 1.4.0.
- **3–5. `/tracker-init`, `/tracker-doctor`, `/resume-initiative` —
  DEFERRED (unchanged).** None of the existing command flows changed this
  release; the four new `/file-*` commands are additive filing entry-points
  that do not alter scaffolding, validation, or initiative-walk logic.
- **New-command static check — PASS.** Each `commands/file-*.md` dispatches
  only by invoking its paired filing skill (no direct backend calls), adds
  **no** `` ### `op` `` heading (the CI `backend-contract` op-parity check
  stays green), and references only existing skills and commands (all
  relative links resolve). The four reciprocal "Slash-command entry-point"
  notes in the filing skills link back correctly.
- **6. Clean-machine install — DEFERRED.** No clean machine available this
  session (same deferral as prior releases).
- **7. Post-install component count — PASS (static slice).** The manifest
  now ships **fifteen components** — six skills + nine commands
  (`/tracker-init`, `/tracker-doctor`, `/resume-initiative`, `/work-issue`,
  `/audit-skills`, `/file-bug`, `/file-feature`, `/file-followup`,
  `/file-epic`), verified against the repo tree and the swept
  `plugin.json` / `marketplace.json` descriptions. Full clean-machine
  `claude plugin details` confirmation deferred with smoke 6.

## [1.4.0] - 2026-06-10

### Added

- **`/audit-skills` slash command + stdlib-only detector library — the
  `skill-currency` enforcement helper** (#2). `scripts/audit_skills.py`
  (Python 3.10+, zero third-party deps) parses the branch diff vs a base
  ref (`git diff --unified=0 --find-renames`) and reports agent-readable
  docs whose references to changed files may have gone stale, using
  three match forms (path / basename / 3+-char stem) and dual-layout
  default globs covering both consumer projects (`CLAUDE.md`,
  `AGENTS.md`, `.claude/{skills,agents,commands}/`) and plugin-dev repos
  (`skills/`, `commands/`, `backends/`, `templates/`). The
  trading-bot-specific DB-canonical detector generalized into optional
  config-driven **paired rules** (`{watch, pattern, expect, message}`,
  zero defaults) configured under a new optional `skill_currency:` block
  in `.claude/issue-tracker.yaml` — the slash command translates YAML to
  CLI flags so the Python stays YAML-free. Informational discipline
  throughout: exit 0 always on success, the PR is never blocked. The
  command carries a prose fallback for consumers without Python on PATH.
  Tested by a pytest suite (45 tests) including a hermetic frozen-diff
  replay of the motivating miss (trading-bot PR #139) and the documented
  short-stem false-positive guard; CI gains a `python-tests` job.

### Changed

- `skills/skill-currency/SKILL.md` — the "Verification" section now
  points at the shipped `/audit-skills` helper instead of describing the
  honor-system as the only option. The rule prose is unchanged.

## [1.3.0] - 2026-06-10

### Added

- **`/work-issue` slash command — single-issue execution driver.** The
  missing counterpart to `/resume-initiative`. Where `/resume-initiative`
  is epic/initiative-oriented (walks an initiative tree, picks the next
  workable leaf), `/work-issue <ref> [--start] [--draft]` takes ONE named
  issue and drives it end-to-end through the full mandated agent pipeline:
  `view_issue` the ref → scope assessment (trivial-work test) → isolated
  worktree on a label-derived `feat/` | `fix/` | `docs/` branch → the
  workflow (brainstorm → plan → execute for non-trivial, or
  TDD-implement-verify for trivial) → `verification-before-completion` with
  real output → `finishing-a-development-branch` opening a PR that links the
  issue via the backend's close-on-merge convention. A **slash command, not
  a subagent**, by deliberate design — the driver runs in the main session
  so it can create worktrees and dispatch `subagent-driven-development`
  implementer subagents, the same reason `/resume-initiative` is a
  main-session command. Backend-agnostic: dispatches only through existing
  contract operations (`view_issue` always; optional `add_label` /
  `close_issue`), resolves the backend from `.claude/issue-tracker.yaml`,
  and never reaches past `backends/_interface.md`. The defining contrast
  with a consumer's trivial-only headless auto-fixer: a non-trivial scope
  verdict does **NOT** bail — it *escalates rigor* to the longer
  brainstorm → plan → execute path. `/work-issue` never refuses an issue
  for being too big, and never auto-merges (the PR is the human gate).
  `--start` runs the pipeline inline without pausing after worktree
  creation (mirrors `/resume-initiative --start`); `--draft` opens a draft
  PR. **No** backend-contract change — the eight operations are untouched,
  the CI `backend-contract` op-parity check stays green (no new
  `` ### `op` `` heading). Reuses `/resume-initiative` Mode-3's worktree
  mechanics verbatim (prefer `EnterWorktree`, rename the sanitized branch in
  place to the convention, idempotent re-entry of an existing worktree).
  Component count updated three → four slash commands (six skills + four
  commands) across `marketplace.json`, `plugin.json`, and `README.md`.
  Specced in the consumer project's 2026-06-09 autonomous-issue-batch
  design.

### Release-gate smokes

Per `CONTRIBUTING.md` "Release process". This release adds **one new
slash command** (`commands/work-issue.md`) plus doc updates (`README.md`,
`CHANGELOG.md`, `plugin.json`, `marketplace.json`). No backend operation
logic, no command-dispatch change to the existing three commands, and no
backend-contract change — the eight operations are untouched and the
`backends/*.md` modules are unedited, so backend-dispatch risk is confined
to the paths smoke 1 already exercises.

- **1. GitHub backend smoke — PASS.** Filed bug (#69), feature (#70),
  followup (#71), and an epic (#72) with a linked sub-issue (#73) against
  this repo. Verified labels (`bug`; `enhancement`; `enhancement`+`followup`;
  `epic`; `enhancement`) and native sub-issue linkage (#72 → #73 via the
  `-F` typed-integer `sub_issues` API). All five closed after verification.
- **2. Jira backend smoke — DEFERRED.** No backend-module change; the
  `jira.md` close-on-merge convention `/work-issue` Step 6 relies on is
  unchanged from 1.2.2. Atlassian connector not configured this session.
- **3–5. `/tracker-init`, `/tracker-doctor`, `/resume-initiative` —
  DEFERRED (unchanged).** None of the three existing commands' flows changed
  this release; `/work-issue` reuses `/resume-initiative` Mode-3's worktree
  mechanics by reference without editing the command.
- **New-command static check — PASS.** `commands/work-issue.md` dispatches
  only the `view_issue` contract op (plus optional `add_label` /
  `close_issue`), adds **no** `` ### `op` `` heading (the CI `backend-contract`
  op-parity check stays green), and references only existing `superpowers:*`
  skills (`brainstorming`, `writing-plans`, `subagent-driven-development`,
  `test-driven-development`, `verification-before-completion`,
  `finishing-a-development-branch`, `requesting-code-review`,
  `using-git-worktrees`).
- **6. Clean-machine install — DEFERRED.** No clean machine available this
  session (same deferral as 1.2.1 / 1.2.2).
- **7. Post-install component count — PASS (static slice).** The plugin
  manifest now ships **ten components** — six skills + four commands
  (`/tracker-init`, `/tracker-doctor`, `/resume-initiative`, `/work-issue`),
  verified against the repo tree. Full clean-machine `claude plugin details`
  confirmation deferred with smoke 6.

## [1.2.2] - 2026-06-05

### Fixed

Skill-currency fixes surfaced by the 2026-06-03 live-Jira test of
`initiative-tracking` (epic #59, Phases 1-2). All are doc/skill-prose
corrections to match observed Atlassian Remote MCP behaviour — no
backend operation, command, or API-surface change.

- **`backends/jira` tool-reference drifted from the live Atlassian
  Remote MCP (#53).** The Reference table, `create_issue` /
  `close_issue` invocation blocks, and Setup-verification step 4 now
  match the connector verified live (project MP, 2026-06-03):
  labels/components go in the `additional_fields` object on create (a
  top-level `labels` arg silently no-ops); `close_issue` resolves a
  workflow-scoped transition id via `getTransitionsForJiraIssue` and
  applies `transition: {id}` (no `comment` param — reasons post via
  `addCommentToJiraIssue({commentBody})`); the vocabulary probe uses
  `getJiraProjectIssueTypesMetadata({projectIdOrKey})` (the old
  `getJiraProjectMetadata` does not exist). The "conventional pending
  Phase 6 live smoke" disclaimer is replaced with a verified-live
  note; transition ids are documented as workflow-scoped, never
  hardcoded.
- **`backends/jira` did not warn against Jira wiki markup (#52).**
  Added an explicit `create_issue` callout: issue bodies MUST be
  GitHub-Flavored Markdown, never wiki markup (`h1.`→`#`, `{{x}}`→
  `` `x` ``, wiki `#`/`*` lists → `1.`/`-`), flagging the
  `#`-at-line-start-is-a-heading trap that garbled a real issue
  (MP-5740). Cloud is Markdown-only; Jira Server (#3) is the wiki
  exception.
- **`backends/jira` `list_child_issues` documented pagination but not
  search-index lag (#57).** Added a sibling note:
  `searchJiraIssuesUsingJql` reads the eventually-consistent search
  index, so a just-filed child can be absent from the first query even
  when `pageInfo.hasNextPage` is `false`; re-query until the count is
  stable and/or cross-check via the strongly-consistent
  `getJiraIssue(child).fields.parent`.
- **Jira three-level cap documented as hard-enforced on create
  (#54).** `backends/jira.md` invariant 6 and `initiative-tracking`
  §"Depth and backend ceilings" now state the cap is enforcement-soft:
  the MCP create path silently accepts a Sub-task parented directly
  under an Epic, so the skill — not the tracker — enforces "a direct
  leaf of the root Epic is a Story, never a Sub-task." (Same-level
  Story → Story parenting IS rejected; enforcement is non-uniform.)
- **Status-block parse contract documented as keyed on a literal
  `-` bullet (#55).** `initiative-tracking` SKILL, `/resume-initiative`, the
  epic-body template, and `backends/jira.md` invariant 1 now match the
  four Status-block fields on the **bold field label**, tolerant of
  the leading list-bullet character (`-`/`*`/`+`) — the Atlassian
  Remote MCP rewrites a leading `-` bullet to `*` on the ADF
  round-trip (task-list `- [ ]` lines are exempt), so the old
  "character-for-character" contract was silently false on Jira.
- **`templates/epic-body.md` sub-epic marker placement was
  self-contradictory (#58).** The prose now agrees with the worked
  example: the `▸ sub-epic` marker goes after the `(Phase N)` suffix
  and before any `— closed YYYY-MM-DD` tail. Added a closed-sub-epic
  worked-example line.

### Release-gate smokes

Per `CONTRIBUTING.md` "Release process". This release is
doc/skill/command **prose only** — no backend operation logic, command
flow, or API-surface change. The GitHub backend module
(`backends/github.md`) is untouched, so backend-dispatch risk is
confined to the GitHub create/link/close paths, which smoke 1
exercises directly.

- **1. GitHub backend smoke — PASS.** Filed bug (#62), feature (#63),
  followup (#64), and an epic (#65) with a linked sub-issue (#66)
  against this repo. Verified labels (`bug`; `enhancement`;
  `enhancement`+`followup`; `epic`; `enhancement`), the epic
  Status-block shape, and native sub-issue linkage (#65 → #66 via the
  `-F` typed-integer `sub_issues` API). All five closed after
  verification.
- **2. Jira backend smoke — DEFERRED.** Atlassian Remote MCP connector
  not configured in the release session (same deferral as 1.2.1). The
  `backends/jira.md` changes in this release *document* live behaviour
  captured by the 2026-06-03 initiative-tracking Jira test (epic #59);
  they are not newly-authored conventions.
- **3. `/tracker-init` — DEFERRED (prose-only edit).** The only change
  was the Jira next-step panel text (`getJiraProjectMetadata` →
  `getJiraProjectIssueTypesMetadata`); scaffolder flow unchanged, and no
  consumer `.claude/issue-tracker.yaml` exists in this repo to scaffold
  against non-destructively. Statically verified.
- **4. `/tracker-doctor` — PASS (GitHub slice).** GitHub-branch
  reachability + vocabulary checks run live: `gh` authenticated, repo
  reachable (`view_issue` dispatch surface), all plugin vocabulary
  labels present (`bug`/`enhancement`/`epic`/`followup`/`needs-design`).
  The Jira-branch vocabulary probe (the file edited here) needs a live
  MCP session — DEFERRED, tracked by #61.
- **5. `/resume-initiative` — PASS.** Parsed the real epic #59: all
  four Status-block fields matched on the bold field label (the new
  bullet-tolerant contract from #55), the `## Children` mirror counted
  5 closed / 1 open, and next-up resolved to #56. Separately proved the
  #55 contract directly — the bold-label match succeeds on `*`-bulleted
  Status lines (the Jira ADF `-`→`*` round-trip case).
- **6–7. Clean-machine install + post-install load — DEFERRED.** No
  `marketplace.json` / `plugin.json` dependency change beyond the
  version bump; clean machine not available this session (same deferral
  as 1.2.1).

## [1.2.1] - 2026-06-03

### Fixed

- **`skill-currency` skill-path ambiguity.** The rule, a new "Where
  the skills live" note, and both `grep` instructions now name both
  locations — `skills/*/SKILL.md` when developing the plugin and
  `.claude/skills/*/SKILL.md` once installed in a consumer — so an
  agent working in the plugin repo no longer greps an empty
  `.claude/skills/`.
- **`bug-tracking` required-field miscount.** "all five required
  fields" corrected to "all of the required fields above" (the list
  enumerates six; the body template marks seven `[required]`).
- **Worked-example rendering.** The `bug-tracking`, `feature-request`,
  and `followup-tracking` worked examples wrapped a markdown body in
  an outer code fence that the inner fenced blocks closed early,
  mis-rendering on GitHub. Switched each outer fence to four backticks
  so the inner blocks nest correctly.

### Changed

- **`initiative-tracking` GitHub Projects board section** moved into
  `skills/initiative-tracking/references/github-projects-board.md`
  (progressive disclosure for the optional, `github.project`-gated
  feature); `SKILL.md` keeps a concise pointer and the trigger rules
  stay inline.

### Release-gate smokes

Per `CONTRIBUTING.md` "Release process". This is a docs/skill-prose-only
patch — no backend operation, command, or API-surface change — so the
functional command smokes (3-5) and clean-machine install smokes (6-7)
exercise code paths unchanged in 1.2.1.

- **1. GitHub backend smoke — PASS.** Filed bug (#46), feature (#47),
  followup (#48), and an epic (#49) with a linked sub-issue (#50)
  against this repo. Verified labels (`bug`; `enhancement`;
  `enhancement`+`followup`; `epic`), body shapes (Parent / Parent epic
  blocks), and native sub-issue linkage (#49 → #50 via the `-F`
  typed-integer `sub_issues` API). All five closed after verification.
  Also created the previously-missing `followup` and `epic` repo labels.
- **2. Jira backend smoke — DEFERRED.** Atlassian connector not
  configured in the release session.
- **3–5. `/tracker-init`, `/tracker-doctor`, `/resume-initiative` —
  DEFERRED.** Command implementations unchanged in this release.
- **6–7. Clean-machine install + post-install load — DEFERRED.** No
  `marketplace.json` / `plugin.json` dependency change beyond the
  version bump; clean machine not available this session.

## [1.2.0] - 2026-06-03

### Added

- **`list_child_issues` backend operation + "adopting an existing
  epic" workflow.** `initiative-tracking` can now bring a
  pre-existing epic — one not created through the skill, with no
  `## Children` mirror yet or a stale one — under the template by
  enumerating its **actual** children from the tracker instead of
  trusting the epic body's prose. Adds an eighth contract operation
  `list_child_issues(parent_ref) → [{ref, title, status}]` to
  `backends/_interface.md` (the read-inverse of `link_sub_issue`;
  returns a parent's **direct** children, open **and** closed —
  adoption needs the closed ones to render `[x] … — closed` mirror
  lines), implemented for both backends (Jira: `parent = <ref>` JQL
  with pagination; GitHub: a paginated GET on the native `sub_issues`
  endpoint). New **"Adopting an existing epic into the template"**
  section in `skills/initiative-tracking/SKILL.md` carrying the
  load-bearing guard: **never infer the child set from body prose —
  query the tracker.** Op-count references swept 7 → 8 across
  `_interface.md`, both backend modules, all four tracker skills,
  `README.md`, and `CONTRIBUTING.md`; the CI `backend-contract`
  op-parity check stays green (the new `list_child_issues` heading
  appears in both backends). No config or schema change. Motivated by
  a live miss: an agent reformatting an epic that already had ten
  children read "child tickets to be filed when prioritized" from the
  stale body and concluded there were none.

- **`tracker-contribute` skill — report a plugin problem (or a fix)
  upstream.** A sixth skill for the case the plugin's own thesis
  implies but nothing covered: when agent-issue-tracker *itself*
  misbehaves or falls short while you're using it, file a well-formed
  issue — or open a PR — against the plugin's own repo
  (`maxdimitrov/agent-issue-tracker`) in the plugin's agent-prompt
  body shape. It is the **one** skill that ignores
  `.claude/issue-tracker.yaml`: plugin problems always route to the
  upstream GitHub repo via `gh`, never into the consumer's configured
  tracker (where the maintainer would never see them). Covers the
  issue-vs-PR decision, the `CONTRIBUTING.md` body shape, and the
  repo's own conventions (skill-currency, op-parity CI, no version
  bump). Component count updated 8 → 9 (six skills + three commands)
  across `marketplace.json`, `plugin.json`, `README.md`, and
  `CONTRIBUTING.md` smoke 7. Motivated by hitting exactly this gap —
  needing a sanctioned path to file the `list_child_issues` miss back
  upstream.

### Release-gate smokes

Per CONTRIBUTING.md Release process; operator-approved runnable-subset scope for
this release.

- **Smoke 1 (GitHub backend against `maxdimitrov/agent-issue-tracker`)** — PASS.
  `#42` and `#43` were both filed and closed through the plugin's GitHub backend
  (agent-prompt-shaped bodies, area/type labels, PR-close-on-merge); this release
  PR exercises the same path end-to-end.
- **Smokes 6 + 7 (install path; loads enabled with all 9 components)** — run
  against the published `v1.2.0` tag in a clean session (they require the tag to
  exist first); outcome recorded in the GitHub release notes rather than this
  block, which is fixed at tag time.
- **Smokes 2, 3, 4, 5 (Jira backend; `/tracker-init`; `/tracker-doctor`;
  `/resume-initiative`)** — DEFERRED. No live Atlassian connector in the release
  session; structural cold-read only, matching the v1.0.0–v1.0.2 gating
  discipline. `#42` touched `initiative-tracking` + the backend contract and `#43`
  added `tracker-contribute`; a live `/resume-initiative` + `/tracker-doctor`
  pass against a real epic is the recommended post-release validation.

## [1.1.0] - 2026-06-01

### Added

- **Nested initiatives (N-level trees).** `initiative-tracking` now
  supports initiatives nested more than one level deep — a child of
  an epic can itself be an epic (a "sub-epic") with its own
  children, to any depth — and `/resume-initiative` walks the whole
  tree. The design is **fully backwards-compatible**: an existing
  two-level epic is the degenerate case (a root with no
  `## Parent epic` block and no sub-epic-marked children) and keeps
  parsing unchanged. No backend-contract change (the seven
  operations are untouched), no config/schema change, no new issue
  type — a sub-epic is just an epic that has a parent. Decisions:
  reuse the `epic` label + a `## Parent epic` block to mark interior
  nodes; count direct children per node with rolled-up leaf totals
  computed by the command on read (one-hop maintenance preserved);
  command-enforced depth cap (`MAX_DEPTH = 10`) + visited-ref cycle
  guard.

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

### Changed

- `commands/resume-initiative.md` — Mode 1 filters `list_open_issues`
  to **roots** (no `## Parent epic` block) and rolls up leaf
  progress; Mode 2 recursively enumerates the child subtree, renders
  it as an indented tree, and resolves `Next up` down to the next
  workable **leaf** (reporting the drill path); Mode 3 `--start`
  drills past sub-epics to a leaf and guards against handing a
  sub-epic body to `superpowers:brainstorming`. New "Tree traversal
  (shared rules)" section (node/root detection, depth cap, cycle
  guard, read-only rollup).
- `skills/initiative-tracking/SKILL.md` — new "Nested initiatives"
  section (root vs sub-epic vs leaf, per-node Status block +
  `## Children` mirror, leaf-promotion mechanics); triage gate gains
  the one-level-down rule (a child that decomposes into 3+
  sub-issues is promoted to a sub-epic under its existing parent);
  Maintenance clarified as one-hop (close edits only the immediate
  parent); Status-block spec and lifecycle updated for sub-epics.
- `skills/followup-tracking/SKILL.md` — new "When a follow-up
  compounds" rule: a compounded follow-up spun from work already
  inside an initiative becomes a **sub-epic under that parent**, not
  a new root.
- `templates/epic-body.md` — doubles as the sub-epic body; optional
  `## Parent epic` block; `## Children` documents the `▸ sub-epic`
  marker and per-node (direct-children) semantics.
- `templates/sub-issue-body.md` — composes from feature/bug **or**
  epic base; `## Parent epic` generalized to name the immediate
  parent (which may be a sub-epic).
- `backends/_interface.md`, `backends/github.md`, `backends/jira.md`
  — new cross-backend invariant 6 (nesting lives in the body
  `## Children` mirror; native `link_sub_issue` is best-effort to
  each backend's hierarchy ceiling). Documents GitHub's arbitrary
  sub-issue depth and Jira's three-level cap (Epic → Story/Task →
  Sub-task; deeper nesting is body-mirror-only, and requires
  `parent_link_style: native`). `view_issue.parent?` clarified as a
  best-effort secondary signal; root detection uses the
  `## Parent epic` body block.

### Release-gate smokes

Smoke gate per CONTRIBUTING.md "Release process" **waived by operator
decision** at release time — smokes 1–7 were not run for this release.

## [1.0.2] - 2026-05-29

Patch release. Makes the plugin actually **load** after install — `v1.0.1` (`#35`) fixed the marketplace-add + install steps, but `claude plugin list` post-install reported `Status: ✘ failed to load` with `Dependency "superpowers@maxdimitrov-agent-issue-tracker" is not installed`. The runtime resolver scopes bare names in `plugin.json.dependencies` to the **current plugin's** marketplace, so `"superpowers"` resolved to `superpowers@maxdimitrov-agent-issue-tracker` (which doesn't exist) instead of `superpowers@claude-plugins-official` (where the dep actually lives). Adopters saw a green install but every plugin component failed to surface: `/tracker-doctor` returned "No matching commands", skills didn't fire.

### Fixed

- `(#37)` `.claude-plugin/plugin.json` `dependencies` qualified with the marketplace: `["superpowers"]` → `["superpowers@claude-plugins-official"]`. The Anthropic-blessed `claude-plugins-official` marketplace is where [`superpowers`](https://github.com/obra/superpowers) ships. With this change, `claude plugin list` reports `Status: ✔ enabled` and `claude plugin details agent-issue-tracker` reports 8 components (5 skills + 3 commands) in a fresh session against the install.
- `(#37)` `.claude-plugin/plugin.json` `version` bumped `1.0.1` → `1.0.2` (and matching entry in `.claude-plugin/marketplace.json`).
- `(#37)` `CONTRIBUTING.md` Release process gains **smoke 7** ("plugin loads `enabled` post-install"), retroactively adds **smoke 6** ("install path against the published repo", introduced in `#35`'s `[1.0.1]` block but not actually written into CONTRIBUTING.md at the time). The release-gate is now seven scenarios; smokes 1-5 unchanged. Closes a `skill-currency`-style gap where the methodology section ("joins the gate") shipped without the methodology-document change.

### Release-gate smokes

- **Smoke 1 (GitHub backend against `maxdimitrov/agent-issue-tracker`)** — PASS via `#37` + this PR exercising the GitHub backend end-to-end (agent-prompt-shaped bug body via the plugin methodology; `bug` label; PR-close on merge).
- **Smoke 6 (install path)** — PASS in the post-tag release session: `claude plugin marketplace add maxdimitrov/agent-issue-tracker` + `claude plugin install agent-issue-tracker` both exit 0; install records `version: 1.0.2`. Smoke 6's first canonical run as part of the gate.
- **Smoke 7 (loads enabled post-install)** — PASS in the post-tag release session: `claude plugin list` shows `Status: ✔ enabled` for `agent-issue-tracker@maxdimitrov-agent-issue-tracker`; `claude plugin details agent-issue-tracker` reports 8 components (5 skills + 3 commands); a fresh CC session resolves the three slash commands. Smoke 7's first canonical run; was the failing smoke that motivated this release.
- Smokes 2, 3, 4, 5 carry forward from `v1.0.0` and `v1.0.1` unchanged — no skill, command, backend, or methodology surface changed in this release.

## [1.0.1] - 2026-05-29

Patch release. Makes the documented install path actually work — `v1.0.0` shipped without `.claude-plugin/marketplace.json`, so `claude plugin marketplace add maxdimitrov/agent-issue-tracker` failed at the first step for every adopter. The plugin's `dependencies = ["superpowers"]` resolution, the skills, the slash commands, and the backend modules were all correct at `v1.0.0`; the only thing missing was the marketplace manifest that surfaces the plugin to the Claude Code plugin system.

### Fixed

- `(#35)` `.claude-plugin/marketplace.json` added — declares this repo as a self-contained single-plugin marketplace named `maxdimitrov-agent-issue-tracker`, with one entry pointing at `./` (the repo root, where `.claude-plugin/plugin.json` lives). Schema reference: `https://anthropic.com/claude-code/marketplace.schema.json`. Modeled on the single-plugin marketplaces in the existing Claude Code plugin ecosystem (`affaan-m/everything-claude-code` `marketplace.json` shape).
- `(#35)` `.claude-plugin/plugin.json` `version` bumped from `1.0.0-pre` to `1.0.1`. The `1.0.0-pre` literal was a Phase 4 oversight — the version bump from pre-release to release was supposed to land alongside the `v1.0.0` tag, but never did, so the installed plugin would have reported `1.0.0-pre` even at the `v1.0.0` tag. Fix-forward via patch release (the `v1.0.0` git tag is not moved).

### Release-gate smokes

- **Smoke 1 (GitHub backend against `maxdimitrov/agent-issue-tracker`)** — PASS via #35 + this PR exercising the GitHub backend end-to-end (agent-prompt-shaped bug body via the plugin methodology; the `bug` label; PR-close on merge).
- **Smoke 6 (install path against the published repo, new for `v1.0.1`)** — PASS in the post-tag release session: `claude plugin marketplace add maxdimitrov/agent-issue-tracker` succeeds, `claude plugin install agent-issue-tracker` succeeds, `superpowers` resolves transitively, the installed plugin reports `"version": "1.0.1"` in `~/.claude/plugins/installed_plugins.json`. This smoke joins the five-scenario gate codified in `CONTRIBUTING.md` Release process — every future release must rerun it.
- Smokes 2, 3, 4, 5 carry forward from `v1.0.0` unchanged — no skill, command, backend, or methodology surface changed in this release.

## [1.0.0] - 2026-05-28

First public release. Five skills (`bug-tracking`, `feature-request`, `followup-tracking`, `initiative-tracking`, `skill-currency`), three slash commands (`/tracker-init`, `/tracker-doctor`, `/resume-initiative`), two backends (`github` via the `gh` CLI; `jira` via the Atlassian Remote MCP), full CI (markdown-lint, yaml-validate, backend-contract checker), and three operator-facing walkthroughs. Release-gate smoke status: smokes 1 + 5 PASS in the release session; smokes 2 + 3 + 4 DEFERRED to Phase 5/6 dogfood cutovers — see "Release-gate smokes" below.

### Added

- Phase 0 bootstrap: plugin manifest, LICENSE, README/CONTRIBUTING/CHANGELOG placeholders, directory skeleton from spec §5.1.
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from the originating project; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-project-specific-ification pattern for #12/#13/#14/#15.
- Phase 2 (#12): feature-request skill — tracker-agnostic port, mechanical re-application of the #11 transforms. Houses the canonical bug-vs-feature disambig table referenced by `bug-tracking`. New `templates/feature-body.md` skeleton consumed by the skill's body-template section.
- Phase 2 (#13): followup-tracking skill — tracker-agnostic port. Type-orthogonal sibling to bug-tracking + feature-request; covers origination (work deferred from in-flight effort), not type. New `templates/followup-body.md` skeleton — first non-standard body template in the plugin, with five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) preceding the standard tail. Validates the templates/*-body.md pattern for `templates/epic-body.md` (#14).
- Phase 2 (#14): initiative-tracking skill — tracker-agnostic port, the most-surgery port of the four. Four surgical transforms: native sub-issue API block → `link_sub_issue` indirection; Status-block parser extension (Next-up accepts both `#N` and `PROJ-123`); read-modify-write warning generalized via the destructive-edit cross-backend invariant from `backends/_interface.md`; per-backend fallback section reframed as a cross-backend invariant (the `## Children` task-list mirror is the canonical index; native linkage is per-backend native plumbing). New `templates/epic-body.md` carries the four canonical Status-block field prefixes (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) literally — Phase 3 `/resume-initiative` parses them character-for-character. New `templates/sub-issue-body.md` is a thin compose-by-reference wrapper around feature-body.md / bug-body.md plus a `## Parent epic` block (deliberate divergence from followup-body.md's self-contained pattern).
- Phase 3 (#20): `/resume-initiative` slash command — tracker-agnostic port. First plugin command whose dispatch must work cross-repo + cross-backend; dispatches through `list_open_issues` / `view_issue` from `backends/_interface.md` rather than calling `gh` directly. Parses both `#N` and `PROJ-123` Status-block refs per the format codified in `skills/initiative-tracking/SKILL.md`. Handles three child ref shapes in the `## Children` task-list mirror (`#N` same-repo, `owner/repo#N` cross-repo GitHub, `PROJ-123` Jira) — the mirror is the canonical cross-backend child-discovery path, with native sub-issue API queries demoted to optional augmentation. Mode 3 (`--start`) worktree creation lands in the consumer's CWD even when the next-up child is a cross-repo ref. Mixed-backend mismatched refs trigger a soft warning and skip, not a crash.
- Phase 3 (#22): `commands/tracker-init.md` — interactive scaffolder. Eight-phase `AskUserQuestion`-driven flow writes a valid `.claude/issue-tracker.yaml` for the consumer project. Both backend branches (GitHub: `gh auth status` + `gh repo view` default; Jira: Atlassian MCP availability + combined site/`cloud_id` from `getAccessibleAtlassianResources` + project key + 3-question field-mapping batch), vocabulary multi-select with custom-value affordance, atomic single-`Write` emission, refuses to overwrite without `--force`.
- Phase 3 (#23): `commands/tracker-doctor.md` — read-only validator. Three check phases (schema validation, backend reachability, vocabulary sanity) plus a summary line; emits `[PASS]` / `[WARN]` / `[FAIL]` per check with literal next-step commands; always exits 0 (informational discipline, mirrors `/audit-skills` + `/audit-pii`). Reachability dispatches through `view_issue` per cross-backend invariant #5 in `backends/_interface.md` — GitHub: `gh auth status` → `gh repo view` → `view_issue(#<N>)`; Jira: Atlassian MCP availability → `getAccessibleAtlassianResources` `cloud_id` round-trip → `view_issue(<PROJECT>-<N>)` via `getJiraIssue`. `PASS-WITH-NOTE` handles the 404-on-probe-ref case (greenfield repo / project) without failing the run. `--smoke-issue <ref>` overrides the default probe ref.
- Phase 2 (#15): skill-currency skill — written from scratch (only new skill in v1, not a port). Codifies the rule that when a PR changes API surface (new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file), the affected `.claude/skills/*.md` files MUST update in the same PR. Cross-links the three filing-shape siblings (`bug-tracking`, `feature-request`, `followup-tracking`); references the v1.1 enforcement helper (`agent-issue-tracker#2`, port of `/audit-skills` + detector library) as the deferred automated path — until then, the rule is honor-system. Closes Phase 2 (all five skills shipped).
- Phase 3 (#24): `backends/jira.md` — Atlassian Remote MCP dispatch for all seven contract operations from `backends/_interface.md`. Second backend implementation completing the v1 backend matrix. Seven MCP tools used: `createJiraIssue`, `editJiraIssue` (drives `add_label`, `link_sub_issue`, `edit_body`), `getJiraIssue`, `searchJiraIssuesUsingJql`, `transitionJiraIssue`, plus `getAccessibleAtlassianResources` + `getJiraProjectMetadata` for `/tracker-doctor`'s Jira-branch setup verification. Three Jira-specific gotchas documented: read-modify-write for `add_label` (full-array replace), `parent_link_style` toggle (`native` Cloud `parent.key` vs `epic_link` classic `customfield_10014`), `done_transition` workflow indirection in `close_issue` with reason mapping (`completed` / `not_planned` / `duplicate`). ADF translation attributed to the MCP under cross-backend invariant #1 — plugin never touches ADF. Tool names are CONVENTIONAL pending Phase 6 live-Jira smoke (Atlassian Remote MCP was not in the authoring session's tool surface; verified via `ToolSearch` at session start). Closes Phase 3 (all four siblings shipped).
- Phase 4 (#29): examples + workflows + CI — minimal `examples/jira-config.yaml` sibling to `examples/github-config.yaml` (Jira-backed adopters now have a copy-paste starting point matching the GitHub minimal config's shape). Three operator-facing walkthroughs under `examples/workflows/` showing the end-to-end trigger → skill activation → body draft → backend dispatch → tracker result shape: `file-a-bug.md` (the `bug-tracking` skill against a GitHub project), `file-an-epic.md` (the `initiative-tracking` skill including the canonical four-line Status block and the cross-backend `## Children` task-list mirror with all three ref shapes — `#N`, `owner/repo#N`, `PROJ-123`), `resume-an-initiative.md` (the three modes of `/resume-initiative` end-to-end). `.github/workflows/ci.yml` with three jobs (markdown-lint via `markdownlint-cli2-action@v16`; yaml-validate via `yamllint -d relaxed`; backend-contract as inline shell asserting every ``### `<op>` `` heading in `backends/_interface.md` appears in every `backends/<backend>.md`) — first automated check on this repo, catches the contract-drift failure mode the Phase 3 work twice nearly hit. Action versions pinned (`@v4` and `@v16`); no secrets required; all three jobs run on `pull_request` and `push` to `main`. `.github/ISSUE_TEMPLATE/` deliberately left empty — the plugin's whole methodology files issues via skills, not via web-UI templates. First ~half of Phase 4; sibling sub-issue (#30) ships README rewrite + smoke-test gate + v1.0.0 tag.
- Phase 4 (#30): README rewrite + CONTRIBUTING release-process section + v1.0.0 release tag. `README.md` rewritten from Phase-0 placeholder into the canonical adopter-facing front page — 12 sections from "What this is" through "License", with compact 5-skill + 3-command tables, GitHub + Jira backend setup sub-sections, configuration story, walkthrough links, a methodology deep-dive (agent-prompt body shape, bail criteria, type taxonomy, epic + sub-issue indexing, `## Children` task-list mirror as cross-backend source of truth, skill-currency rule), `superpowers` dependency rationale, adding-a-backend pointer, and roadmap. `CONTRIBUTING.md` extended with a "Release process" section codifying the five-scenario smoke gate from design spec §8.3 as a numbered checklist (with smoke 2 deferral language for the Atlassian-connector-unavailable case) and tag-annotation discipline, plus an "Adding a backend" section pointing at `backends/_interface.md` (the seven-operation contract) and the CI `backend-contract` job. CHANGELOG `[1.0.0]` release block with full chronological Added section + Release-gate smokes sub-section recording smoke outcomes. Capstone Phase 4 sub-issue.

### Release-gate smokes

Per the design spec §8.3 five-scenario gate, now codified in `CONTRIBUTING.md` Release process. Outcomes for the v1.0.0 release session:

- **Smoke 1 (GitHub backend against `maxdimitrov/agent-issue-tracker`)** — PASS. This session's own #29 + #30 + PR #31 exercised the GitHub backend end-to-end: agent-prompt-shaped bodies, `bug`/`epic`/`enhancement` labels, GitHub native sub-issue linkage via the `link_sub_issue` API path documented in `backends/github.md`, `edit_body` flow on the epic Status block. Issue refs: #29 (Phase 4 sub-issue), #30 (Phase 4 capstone sub-issue), #31 (Phase 4 examples + workflows + CI PR). All filed via the plugin's methodology; all closed via the release pipeline.
- **Smoke 2 (Jira backend against a real Jira project)** — DEFERRED to Phase 6 (work-Jira second-consumer proof). Atlassian Remote MCP connector was not in the v1.0.0 release session's tool surface (verified via `ToolSearch` at session start). Tool names in `backends/jira.md` remain CONVENTIONAL pending Phase 6 live smoke; if drift surfaces, fix lands as a `vX.Y.Z` patch release.
- **Smoke 3 (`/tracker-init` from blank state)** — DEFERRED to Phase 5 (dogfood cutover on the originating consumer). The `commands/tracker-init.md` flow was cold-read for structural correctness against the schema in `examples/issue-tracker.yaml.example` + the minimal targets in `examples/{github,jira}-config.yaml`, but the eight-phase `AskUserQuestion`-driven scaffolder was not executed live against a blank-state repo in this session — and per CONTRIBUTING.md Release process, cold-read review is not execution. Live verification gates Phase 5: the cutover PR scaffolds its own `.claude/issue-tracker.yaml` via `/tracker-init`, providing first live evidence. If the scaffolder fails there, a patch release (`v1.0.1`) lands the fix before Phase 5 merges.
- **Smoke 4 (`/tracker-doctor` PASS / WARN / FAIL routing)** — DEFERRED to Phase 5 (dogfood cutover). Same structural cold-read against `commands/tracker-doctor.md`'s three-phase validator (schema check; backend reachability via `view_issue` per cross-backend invariant #5; vocabulary sanity) confirmed correct routing semantics + literal next-step commands — but PASS / WARN / FAIL routing against a real `.claude/issue-tracker.yaml` was not executed live. The Phase 5 cutover runs `/tracker-doctor` against its real config as the live PASS evidence; intentional malformed-config + missing-labels variants exercise the WARN + FAIL routing.
- **Smoke 5 (`/resume-initiative` against the v1 launch epic)** — PASS via in-session execution. The release session navigated the launch epic to confirm the four-line Status block parses (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`), the `## Children` task-list mirror enumerates all sub-issues with correct ref shapes, and the Decision log + Resume-from-here sections render correctly. The session itself used `/resume-initiative` semantics implicitly (read the epic, identified Phase 4 as the next-up phase, filed #29 + #30 against this repo).

## Pre-history

This plugin extracts methodology that originated as project-local skills in a private GitHub repository. v1.0.0 is the first public release; earlier work lived in that repo as `.claude/skills/{bug-tracking,feature-request,followup-tracking,initiative-tracking}/SKILL.md` plus a local `/resume-initiative` slash command.
