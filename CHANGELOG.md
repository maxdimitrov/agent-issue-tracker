# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
