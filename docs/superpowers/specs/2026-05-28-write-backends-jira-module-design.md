# Write `backends/jira.md` Atlassian Remote MCP Backend — Design

**Date:** 2026-05-28
**Tracker:** [`maxdimitrov/agent-issue-tracker#24`](https://github.com/maxdimitrov/agent-issue-tracker/issues/24)
**Parent epic:** [`maxdimitrov/trading-bot#153`](https://github.com/maxdimitrov/trading-bot/issues/153)
**Parent design spec:** [`docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) on `maxdimitrov/trading-bot` `main` — sections §4 (dispatch decision), §5.5 (seven-operation Jira mapping table), §9 Phase 3 (this deliverable), §9 Phase 6 (the post-merge live-Jira smoke).

## 1. Problem

The plugin's seven-operation backend contract (`backends/_interface.md`) is implemented today only for GitHub via `backends/github.md`. Every plugin skill that was Phase-2-ported (bug-tracking, feature-request, followup-tracking, initiative-tracking, skill-currency) and both Phase-3 slash commands (`/resume-initiative`, `/tracker-init`, `/tracker-doctor`) dispatch through `backends/<backend>.md`. When `.claude/issue-tracker.yaml` says `backend: jira`, those dispatch references have nowhere to land — the agent picks up an issue and there's no file documenting the literal MCP call shape for the configured backend. The Phase 6 second-consumer proof (the operator's work Jira project) is the first end-to-end exercise of the Jira branch; without this module, that whole half of the v1 value proposition is blocked.

## 2. Goal

Ship `backends/jira.md` — a markdown-only dispatch module that implements all seven operations from the contract via the Atlassian Remote MCP tool family. Section structure mirrors `backends/github.md` (the precedent). Every cross-backend invariant from `_interface.md` is satisfied with a numbered paragraph. The Setup-verification block matches `commands/tracker-doctor.md`'s Jira branch verbatim (lines 56-63 + vocabulary lines 87-92) so the validator's three-step probe and this module's documented setup probes agree.

When the module ships, the v1 backend matrix is complete: `backend: github` and `backend: jira` both work end-to-end against the same skills and slash commands.

## 3. Non-goals (explicit)

- **Jira Server / Data Center support.** Day-one follow-on `agent-issue-tracker#3`. The Atlassian Remote MCP is Cloud-only.
- **Bespoke HTTP client or ADF translator.** The MCP owns auth, schema, and ADF rendering. The plugin dispatches; it does not reimplement. Documented as a Cross-backend invariant #1 paragraph.
- **Custom-field support** beyond the classic `customfield_10014` Epic Link toggle. Story points, fixVersion, sprint, etc. are day-one follow-on `agent-issue-tracker#5`.
- **Validating that `jira.issue_types.*` values exist** in the actual project. That's `/tracker-doctor`'s Phase 3 vocabulary-sanity job; the module merely documents what's expected.
- **Auto-creating missing labels / components / issue types.** Operator setup task surfaced by `/tracker-doctor`'s WARN findings.
- **Validating the literal MCP tool names in this session.** The Atlassian Remote MCP is not in the authoring agent's tool surface (verified via `ToolSearch` at session start — no matches). The CHANGELOG entry must mark the names as "conventional pending Phase 6 live smoke" rather than claiming pinning. If a future session has the connector available, a follow-up commit can promote them to "verified".
- **End-to-end test of any operation against a live Jira instance.** Phase 6 (operator's work-Jira project) is where real-Jira correctness is validated. This PR's merge gate is static acceptance + cold-read review.

## 4. Architecture decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| File shape | Markdown only | Mirrors `backends/github.md`; backend modules are prose contracts, not executable. |
| Section structure | Same six sections as `backends/github.md` | Auth, Reference table, Operations, Cross-backend invariants, PR close-on-merge, Setup verification. Order matters — the precedent's order is the reader's mental model. |
| Operation block format | Same as `backends/github.md` | Fenced code block showing the MCP call shape + a "Field mapping" bullet list + a "Per-config indirection" note where applicable. |
| Reference table column count | 3 (Operation, MCP tool, Notes) | Matches GitHub's three-column table; the Notes column carries the input parameter list. |
| Operation order in ## Operations | Same as `_interface.md` and `backends/github.md` | `create_issue`, `add_label`, `link_sub_issue`, `list_open_issues`, `view_issue`, `edit_body`, `close_issue`. Don't innovate. |
| Tool-name verification status | Conventional in this PR; CHANGELOG calls this out | Atlassian MCP not in this session's tool surface. Future Atlassian Remote MCP version updates may rename; document the verification gap honestly. |
| ADF translation | Cross-backend invariant #1 paragraph attributes it to the MCP | The plugin emits markdown only; the MCP handles ADF translation in both directions. Documented once explicitly so future maintainers don't add an ADF dependency. |
| `parent_link_style` branching | Inline in `link_sub_issue` block | Two-way branch documented as nested bullets: `native` (modern Cloud `parent.key`) vs `epic_link` (classic `customfield_10014`). |
| `done_transition` indirection | Inline in `close_issue` block | Reason mapping table: `completed` → `done_transition` (default `Done`), `not_planned` → `"Won't Do"` if available else comment-only, `duplicate` → comment-only. |
| `area_field` indirection | Inline in `create_issue` + `add_label` blocks | `components` (default) vs `labels`. Map `area` input to `fields.components[].name` or `fields.labels[]`. |
| Read-modify-write gotcha | Explicit paragraph in `add_label` and `edit_body` | Parallel to the `-F` vs `-f` gotcha in `backends/github.md`'s `link_sub_issue` — Jira's `editJiraIssue` replaces the labels array; the plugin must fetch current labels, append, write back the full array. |
| Setup-verification block | Mirrors `/tracker-doctor`'s Jira branch verbatim | Three numbered probes (MCP availability → cloud_id round-trip → `getJiraIssue` reachability) + WARN-level vocabulary sanity via `getJiraProjectMetadata`. The two files must agree. |
| PR close-on-merge | Plugin does NOT enforce | Jira lacks GitHub's `Fixes #N` keyword convention. Consumer-declared `jira.close_on_merge_hint` is advisory text rendered into PR descriptions; the plugin does not auto-close. |

## 5. The seven operations

Tool name + input shape + per-config indirection per operation. Tool names are conventional (see §4 verification-status decision).

### 5.1 `create_issue`
- **Tool:** `createJiraIssue`
- **Inputs:** `{cloudId, projectKey, summary, description (markdown), issueTypeName, labels, components?, parent?}`
- **Field mapping:**
  - `type` → `issueTypeName` via consumer's `jira.issue_types.<type>` mapping
  - `title` → `summary`
  - `body` → `description` (markdown; MCP translates to ADF)
  - `labels` → `labels[]`
  - `area` → `components[].name` if `jira.area_field: components`, else appended to `labels[]` if `area_field: labels`
  - `subsystem` → inline in `description` body (Locus block) — same as GitHub
  - `parent` → `parent.key` at create time when present (Cloud's unified parent works at creation for Sub-task types; for Story → Epic linkage use `link_sub_issue` post-create per `parent_link_style`)
- **Output:** Jira issue key (e.g. `TRADE-42`); the skill captures this as the ref.

### 5.2 `add_label`
- **Tool:** `editJiraIssue` setting `fields.labels`
- **Read-modify-write gotcha (explicit paragraph):** `editJiraIssue` replaces the entire `labels` array. The plugin must first `getJiraIssue` to fetch the current labels, append the new label in memory, then write the full array back via `editJiraIssue({fields: {labels: [...existing, newLabel]}})`. Parallel to the `-F` vs `-f` gotcha in `backends/github.md`'s `link_sub_issue`.

### 5.3 `link_sub_issue`
- **Tool:** `editJiraIssue` on the child
- **Branch on `jira.parent_link_style`:**
  - `native` (modern Cloud, recommended) — set `fields.parent.key = <parent_ref>`. Works for any issue-type pair (Epic → Story, Story → Sub-task).
  - `epic_link` (classic, pre-2022 projects) — set `fields.customfield_10014 = <parent_ref>`. Only meaningful for Epic → Story; Sub-tasks always use `parent.key` regardless of toggle. `jira.epic_link_field` overrides the default `customfield_10014`.

### 5.4 `list_open_issues`
- **Tool:** `searchJiraIssuesUsingJql`
- **JQL:** `project = "<jira.project>" AND statusCategory != Done`
- **Filter assembly:**
  - `type` filter → append ` AND issuetype = "<jira.issue_types.<type>>"`
  - `label` filter → append ` AND labels = "<label>"`
- **Returns:** a list of issue keys + summaries + statuses; backend translates to `[{ref, title, status}]` matching the contract output shape.

### 5.5 `view_issue`
- **Tool:** `getJiraIssue({cloudId, issueIdOrKey: <ref>})`
- **Field unwrapping:**
  - `key` → `ref`
  - `fields.summary` → `title`
  - `fields.description` → `body` (ADF-translated to markdown by MCP)
  - `fields.status.name` → `status`
  - `fields.labels[]` → `labels`
  - `fields.parent?.key` → `parent` (present only for sub-issues / children)

### 5.6 `edit_body`
- **Tool:** `editJiraIssue({cloudId, issueIdOrKey, fields: {description: <new_markdown>}})`
- **Destructive whole-body replace.** Plugin pattern: `getJiraIssue` → modify in memory → `editJiraIssue`. Same shape as `gh issue view --json body` → modify → `gh issue edit --body-file`. Cross-backend invariant #2 made concrete.

### 5.7 `close_issue`
- **Tool:** `transitionJiraIssue({cloudId, issueIdOrKey, transitionName: <jira.done_transition>})` + optional `comment`
- **Reason mapping:**
  - `completed` → `transitionJiraIssue` with `jira.done_transition` (default `Done`)
  - `not_planned` → `transitionJiraIssue` with `"Won't Do"` if that transition exists in the project workflow; otherwise fall back to `done_transition` and put the reason in the comment
  - `duplicate` → no native transition; close with the project's done transition and reference the duplicate's ref in the comment

## 6. The five cross-backend invariants (how Jira satisfies them)

Each numbered to match `_interface.md`:

1. **Body format is markdown.** The MCP's `createJiraIssue` and `editJiraIssue` tools accept markdown `description` strings and translate to ADF (Atlassian Document Format) internally; `getJiraIssue` returns ADF that the MCP translates back to markdown. The plugin NEVER touches ADF. Translation is lossless for the agent-prompt body shapes the plugin uses (headings, lists, code fences, tables, links, bold/italic).
2. **Whole-body edits are destructive.** `editJiraIssue` replaces `fields.description` in one call; there is no append-only API. Same shape as GitHub's `gh issue edit --body-file` — read-modify-write is the canonical pattern.
3. **Sub-issue linkage.** Jira Cloud's modern unified `parent.key` (set via `editJiraIssue` on the child) is the recommended path. The classic Epic Link customfield (`customfield_10014` by convention) is a fallback for older Jira projects that pre-date the unified parent field. Branched by `jira.parent_link_style` in `.claude/issue-tracker.yaml`.
4. **Issue refs are opaque.** Jira refs are `<PROJECT>-<N>` (e.g. `TRADE-42`). Skills treat refs as opaque strings; only this backend module knows the syntax. `commands/resume-initiative.md` accepts both `#N` (GitHub) and `<PROJECT>-<N>` (Jira) per `skills/initiative-tracking/SKILL.md`'s Status-block format.
5. **`/tracker-doctor` reachability.** `view_issue({ref: "<jira.project>-1"})` (default smoke ref; `--smoke-issue <ref>` overrides) dispatches to `getJiraIssue`. PASS if returns; PASS-WITH-NOTE on 404 (project reachable but probe issue absent); FAIL on 401/403 (auth wrong or `cloud_id` doesn't match `site`).

## 7. Setup verification (the `/tracker-doctor` Jira branch contract)

Must match `commands/tracker-doctor.md` Phase 2 (Jira branch, lines 56-63) and Phase 3 (Jira vocabulary, lines 87-92). Document in this order:

1. **Atlassian MCP availability.** Agent's tool surface includes the family (`createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`, etc.). If absent, the operator must enable the Atlassian connector at claude.ai → Settings → Connectors → Atlassian.
2. **`cloud_id` round-trip.** Invoke `getAccessibleAtlassianResources`; confirm `jira.cloud_id` is in the returned list and matches `jira.site`. Mismatch is FAIL — `/tracker-doctor` reports the accessible cloud_ids in that case.
3. **`getJiraIssue` reachability.** Canonical reachability probe per cross-backend invariant #5. PASS / PASS-WITH-NOTE (404) / FAIL (401/403).
4. **Vocabulary sanity (WARN-level).** `getJiraProjectMetadata` (conventional name — verify at implementation time) returns project's configured issue types + components. WARN for any `jira.issue_types.*` value missing from the project's issue type list.

## 8. PR close-on-merge convention

Jira does NOT auto-close issues from PR keywords the way GitHub does with `Fixes #N` / `Closes #N`. Auto-close on Jira typically requires the Jira-GitHub or Jira-Bitbucket DVCS integration (configured outside the plugin) — when configured, PRs with a Jira issue key in the branch name or commit message can auto-transition the issue on merge.

The plugin does NOT enforce or configure this behaviour. Consumers declare their PR-merge close convention in `.claude/issue-tracker.yaml` via the `jira.close_on_merge_hint` field. Skill prose (feature-request, bug-tracking) renders the hint string into PR description templates as advisory text — telling reviewers what convention the consumer uses without binding the plugin to a specific integration. Empty `close_on_merge_hint` → no advisory line rendered.

## 9. Failure modes (consolidated)

- **Atlassian MCP unavailable in the dispatch context** → the seven operations all fail; surface via `/tracker-doctor`'s Phase 2 step 1 with the connector setup link. Not a runtime concern of this module per se — the module assumes a working MCP.
- **`cloud_id` mismatched with `site`** → `getAccessibleAtlassianResources` round-trip catches this; surfaced by `/tracker-doctor`. Module documents the relationship.
- **Missing issue type / component in project** → `create_issue` fails; `/tracker-doctor`'s Phase 3 surfaces this preemptively.
- **`done_transition` not in project workflow** → `close_issue` fails at runtime; document that consumers MUST set `jira.done_transition` to a transition name that exists.
- **MCP tool renames between Atlassian releases** → CHANGELOG note documents the conventional-pending-verification status; future maintainers can run `ToolSearch` and promote to verified.

## 10. Invariants

- All seven contract operations get their own subsection under `## Operations`.
- All five cross-backend invariants get their own numbered paragraph under `## Cross-backend invariants — how Jira satisfies them`.
- Section structure matches `backends/github.md` (Auth → Reference table → Operations → Cross-backend invariants → PR close-on-merge → Setup verification) in that order.
- Markdown-only file. No bash heredocs, no JSON example blocks beyond what MCP tool calls naturally use.
- The plugin emits markdown only; ADF is the MCP's problem. Cross-backend invariant #1 paragraph makes this explicit.
- No bespoke HTTP — every operation is an MCP tool call.
- No `gh ` shell-out commands (this is the Jira backend; bare `gh` lines would be a leak).
- No literal `maxdimitrov/trading-bot` string (extracted-plugin discipline).

## 11. Cross-references

- `backends/_interface.md` — the seven-operation contract + five cross-backend invariants this module implements + satisfies.
- `backends/github.md` — the precedent. Mirror its section structure.
- `examples/issue-tracker.yaml.example` lines 66-108 — the `jira:` config block field vocabulary this module dereferences.
- `commands/tracker-init.md` — `/tracker-init`'s Jira branch (Phase 4) writes configs this module reads at runtime.
- `commands/tracker-doctor.md` — `/tracker-doctor`'s Jira branch is the validator that this module's Setup-verification block documents the contract for.

## 12. Acceptance

The PR closes when **all** are true:

- [ ] `backends/jira.md` exists; renders cleanly.
- [ ] No literal `maxdimitrov/trading-bot` string.
- [ ] No bare `gh ` shell-out commands.
- [ ] All seven contract operations have their own `### <op>` subsection (matches `_interface.md` and `backends/github.md` ordering).
- [ ] All five Atlassian MCP tool families named in the prose: `createJiraIssue`, `editJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `transitionJiraIssue`.
- [ ] Plus the two setup-verification tools: `getAccessibleAtlassianResources`, `getJiraProjectMetadata`.
- [ ] All five cross-backend invariants addressed in a `## Cross-backend invariants — how Jira satisfies them` section, numbered 1-5 matching `_interface.md`.
- [ ] ADF translation acknowledged as MCP's responsibility under invariant #1.
- [ ] `parent_link_style` toggle documented in `link_sub_issue` (native vs epic_link); `customfield_10014` named.
- [ ] `done_transition` and reason mapping documented in `close_issue`.
- [ ] `area_field` indirection (components vs labels) documented in `create_issue` and `add_label`.
- [ ] PR close-on-merge section explicitly states the plugin does NOT enforce auto-close; `close_on_merge_hint` is advisory only.
- [ ] Setup-verification section's three-step probe + vocabulary-sanity step match `/tracker-doctor`'s Jira branch byte-for-byte on the operation names.
- [ ] CHANGELOG.md `[Unreleased] → Added` carries the Phase 3 entry in `Phase 3 (#24): backends/jira.md — ...` format AND marks the MCP tool names as "conventional pending Phase 6 live smoke" (honest about the verification gap).

## 13. Verification

```bash
test -f backends/jira.md
grep -F "maxdimitrov/trading-bot" backends/jira.md && echo "LEAK" || echo "clean"
grep -nE "^gh " backends/jira.md && { echo "FAIL: bare gh"; exit 1; } || echo "OK"

# All seven contract operations
for op in create_issue add_label link_sub_issue list_open_issues view_issue edit_body close_issue; do
  grep -qE "###.*$op" backends/jira.md || { echo "MISSING: $op"; exit 1; }
done

# All seven MCP tool names
for tool in createJiraIssue editJiraIssue getJiraIssue searchJiraIssuesUsingJql transitionJiraIssue getAccessibleAtlassianResources getJiraProjectMetadata; do
  grep -q "$tool" backends/jira.md || { echo "MISSING: $tool"; exit 1; }
done

# Invariants section + key concepts
grep -qE "## Cross-backend invariants" backends/jira.md || exit 1
grep -qiE "ADF|atlassian document format" backends/jira.md || exit 1
grep -qE "parent_link_style" backends/jira.md || exit 1
grep -qE "customfield_10014" backends/jira.md || exit 1
grep -qE "done_transition" backends/jira.md || exit 1
grep -qE "area_field" backends/jira.md || exit 1

# PR auto-close NOT enforced
grep -qiE "(does not|do not|doesn't|never).*(auto-close|enforce|configure)" backends/jira.md || exit 1

# Setup verification section
grep -qE "## Setup verification" backends/jira.md || exit 1
```

## 14. Notes

- This is a write-from-scratch module — no source to byte-diff against. The reference for shape is `backends/github.md`; the contract is `backends/_interface.md`; the field vocabulary is `examples/issue-tracker.yaml.example` lines 66-108.
- **The Atlassian Remote MCP is NOT available in the authoring session's tool surface** (verified via `ToolSearch` against keywords `atlassian jira` — no Atlassian tools returned, only `WebFetch` and `mcp__claude_ai_Notion__notion-search`). Tool names below are CONVENTIONAL per parent design spec §5.5 and sub-issue #24's Sketch. The CHANGELOG entry MUST mark this honestly ("conventional pending Phase 6 live smoke") rather than claiming pinning. If a future session has the connector available, a follow-up commit can promote them to "verified".
- The naming convention used by the design spec is camelCase (`createJiraIssue`, not `jira_create_issue`). Match that.
- This module completes the v1 backend matrix. After it lands, Phase 3 is closed and Phase 4 (examples + workflows + CI + README rewrite + v1.0.0 tag) unblocks.
- Phase 6 (operator's work-Jira second-consumer proof) is the first end-to-end exercise of this module. The trading-bot dogfood (Phase 5) uses GitHub. So merge-gate correctness here is static (acceptance grep + cold-read review); real-Jira correctness is the post-merge proof.
- The ADF invariant (Cross-backend invariant #1) is the most subtle bit. If a future Atlassian Remote MCP version stops doing markdown↔ADF translation, the plugin would need an ADF library — a backward-incompatible plugin change worth a major version bump. Today: this constraint is on Atlassian, not the plugin. Document explicitly so future maintainers don't reach for an ADF dep.
- The `done_transition` indirection is the most under-documented Jira-vs-GitHub difference. GitHub has a single `close` action; Jira has a workflow with named transitions. The plugin can't enumerate them all; `done_transition: Done` is a default that works for ~80% of projects, and consumers override per-project.
- The Setup-verification section MUST match `/tracker-doctor`'s Jira branch verbatim on the operation names. The two files are co-designed; future maintainers should treat that section's tool-name list as the single source of truth (this file + `commands/tracker-doctor.md` must agree on the four-step probe sequence and the conventional tool names used).
