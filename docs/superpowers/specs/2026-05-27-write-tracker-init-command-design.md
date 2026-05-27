# Write `/tracker-init` Command — Design

**Date:** 2026-05-27
**Tracker:** [`maxdimitrov/agent-issue-tracker#22`](https://github.com/maxdimitrov/agent-issue-tracker/issues/22)
**Parent epic:** [`maxdimitrov/trading-bot#153`](https://github.com/maxdimitrov/trading-bot/issues/153)
**Parent design spec:** [`docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) on `maxdimitrov/trading-bot` main — sections §5.6 (slash commands list), §7 (config schema), §7.1 (the seven-step flow).

## 1. Problem

The plugin's installation story is `claude plugin install agent-issue-tracker` plus a hand-edited `.claude/issue-tracker.yaml`. The hand-edit path is a friction wall: the YAML schema has ~15 fields (~11 of them Jira-specific), backend-conditional required blocks, and three Jira-specific enums (`issue_types` mapping, `area_field`, `parent_link_style`) that have no obvious default for a fresh project. Operators bounce off the schema before reaching `/tracker-doctor`. The first failure mode of a mis-configured `cloud_id` or `issue_types` is a 404 / 401 from the Atlassian MCP at the moment the operator files their first real issue — the worst place to discover the config is broken.

## 2. Goal

Ship `commands/tracker-init.md` — a markdown-only slash command that walks the operator through an interactive `AskUserQuestion`-driven flow and writes a valid `.claude/issue-tracker.yaml` to the consumer's repo root. The command:

- Probes the environment (`gh auth status` for GitHub, Atlassian MCP availability for Jira) and pre-fills defaults where it can (`gh repo view` for `owner/repo`; MCP site-discovery for `cloud_id`).
- Refuses to overwrite an existing config without `--force`.
- Emits only the YAML blocks the operator answered for (no orphan `jira:` block when `backend: github`).
- Prints a next-steps panel pointing at `/tracker-doctor`.

When the command exits cleanly, `/tracker-doctor` against the written config returns PASS for Phase 1 (schema validation) and at minimum PASS for Phase 2 step 1 (auth probe) — i.e. the config is structurally and credential-wise valid out of the box.

## 3. Non-goals (explicit)

- **Validating that the operator's answers are internally consistent** (e.g. a Jira `parent_link_style: epic_link` without `epic_link_field` — defaults apply; the validator's job).
- **Probing whether configured `areas:` labels exist on the GitHub repo or whether `jira.issue_types.*` exist in the project.** That is `/tracker-doctor`'s vocabulary-sanity phase. `/tracker-init` writes what the operator answered; the validator catches mistakes against the actual tracker.
- **Auto-creating missing labels / issue types / components.** Operator's responsibility, surfaced by `/tracker-doctor`.
- **Migrating a v0 config.** No such thing exists — schema v1 is the first version.
- **Storing Atlassian or GitHub credentials.** `gh` and the Atlassian MCP own auth. The command checks reachability, surfaces failure with next-step commands, and exits.
- **A "review the answers and confirm" step before writing.** Each prompt is its own confirmation point; the YAML is written immediately after the last prompt. (If the operator wants to redo, they re-run `/tracker-init --force`.)
- **Cross-platform branching for `gh` invocations.** The command's prose names `gh auth status` and `gh repo view`; the harness executes them; OS-specific quoting is the agent's problem, not the command spec's.

## 4. Architecture decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| File shape | Markdown + YAML frontmatter | Mirrors `commands/resume-initiative.md`. Slash commands are markdown only; the agent EXECUTES the prose. |
| Interactive surface | `AskUserQuestion` | Spec §7.1 mandates this; offers structured single/multi-select with optional "Other" affordance for free-form. |
| Prompt batching | Batch within a logical phase | Jira field-mappings (3 questions) → 1 call; areas + subsystems-yes/no (2 questions) → 1 call. Backend select + repo/site/project remain 1-per-call (they gate downstream branches). |
| Pre-flight auth/MCP probes | Fire immediately after backend select | Failure-mode short-circuit — surface the missing dependency before the operator has answered any other prompt. |
| Closed-enum prompts | Reject "Other" with re-prompt | Backend, `area_field`, `parent_link_style` have closed v1 enums; the tool always offers "Other" but the agent treats it as invalid and re-prompts. |
| Free-form input | Use "Other" affordance | Subsystem list arrives via "Other" with newline-separated text; agent parses into a YAML list. |
| YAML emission | Only blocks the operator answered for | Skip the `jira:` block when `backend: github`, omit `subsystems:` when operator said No, omit `types:` entirely (defaults apply unless overridden — but v1 doesn't prompt for type customisation). |
| `--force` semantics | The ONLY way to overwrite an existing config | No `-y`, no env var, no "we noticed an old config — replacing" silent path. |
| Write timing | Single Write call at the very end | No partial writes. Operator interruption mid-flow leaves the existing config (if any) untouched. |
| Header comment in written YAML | Pinned verbatim with the ISO date | Reviewers + future operators can see where the file came from and what schema version applies. |

## 5. Flow

Eight phases. Pre-flight checks are tagged **(STOP-IF-FAIL)** — they short-circuit the rest of the flow on failure.

### Phase 1 — Pre-flight: existing-config guard

1. Detect `.claude/issue-tracker.yaml` in the consumer's CWD.
2. If absent → continue to Phase 2.
3. If present and `--force` NOT passed → report the existing path, suggest running `/tracker-doctor` (to validate) or re-invoking with `--force` (to overwrite). **(STOP-IF-FAIL)**
4. If present and `--force` passed → record that an overwrite is happening; surface that in the final summary; continue.

### Phase 2 — Backend selection

1 × `AskUserQuestion` (single-select):
- Question: "Which issue tracker does this project use?"
- Header: `Backend` (≤12 chars per the tool's schema)
- Options: `GitHub` | `Jira`
- "Other" → reject, re-prompt (only `github` and `jira` are valid in v1)

Branch on the answer for Phase 3.

### Phase 3 — GitHub branch (skip if `backend: jira`)

**3a. Auth probe (STOP-IF-FAIL).** Run `gh auth status`. On non-zero exit or output containing "not logged" → instruct the operator to run `gh auth login` and re-invoke `/tracker-init`. Exit.

**3b. Repo default extraction.** Run `gh repo view --json nameWithOwner --jq .nameWithOwner` against the consumer's CWD. If it succeeds, capture the `owner/repo` as the default. If it fails (cwd isn't a GitHub-cloned repo), no default.

**3c. Repo prompt.** 1 × `AskUserQuestion` (single-select):
- Question: "Which GitHub repo will issues be filed against?"
- Header: `Repo`
- Options:
  - If default extracted: `<owner/repo> (this repo)` — first, marked "(Recommended)".
  - Otherwise no recommended option; operator uses "Other" to type the value.

Capture as `github.repo`. (Reject blank "Other"; re-prompt.)

Skip to Phase 5.

### Phase 4 — Jira branch (skip if `backend: github`)

**4a. Atlassian MCP availability (STOP-IF-FAIL).** Check the agent's tool surface for the Atlassian Remote MCP tool family — conventional names `createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`. If `ToolSearch` against keywords like `jira atlassian` returns nothing, instruct the operator to enable the Atlassian connector at claude.ai → Settings → Connectors → Atlassian and re-invoke. Exit.

**4b. Site + cloud_id (combined).** Invoke the MCP's site-discovery tool (conventional name `getAccessibleAtlassianResources`; the agent should query `ToolSearch` against `accessible atlassian resources` if uncertain) to get the list of `{cloudId, url, ...}` entries the connector grants access to.

Branch on the result count:
- **Zero sites accessible** → **(STOP-IF-FAIL)** the connector's scope doesn't include any Jira sites; instruct the operator to fix the connector scope at claude.ai and re-invoke.
- **Exactly one site** → use it without prompting (capture `url` → `jira.site` after stripping `https://` + trailing slash; capture `cloudId` → `jira.cloud_id`).
- **Multiple sites** → 1 × `AskUserQuestion` (single-select): "Which Atlassian site will issues be filed against?", header `Site`, options are the accessible sites' URLs (up to 4 per the tool schema; if more than 4, list the first 4 and rely on the operator hitting "Other" to type one not shown). Reject "Other" with a re-prompt if the typed value doesn't match an accessible site. Capture as `jira.site` + `jira.cloud_id`.

This collapses the conceptual "ask for site → resolve cloud_id" two-step into a single prompt sourced from MCP discovery, removing one operator turn and the ambiguity of an empty-recommended Site prompt.

**4c. Project key prompt.** 1 × `AskUserQuestion` (single-select with "Other" for free-form):
- Question: "Which Jira project key will issues be filed under?"
- Header: `Project`
- Options: no recommended option (project keys are too project-specific); operator uses "Other" with a brief example annotation in the description field ("e.g. `TRADE`, `INFRA`").

Capture as `jira.project`.

**4d. Field-mapping batch.** 1 × `AskUserQuestion` (multi-question form — 3 questions in a single call):

1. Question: "What is the Jira issue type for plugin-type `feature`?"
   Header: `Feature type`
   Options: `Story` (recommended) | `Task`
2. Question: "Where does the `<area>` value live in Jira?"
   Header: `Area field`
   Options: `components` (recommended) | `labels`
3. Question: "How do epics link to children?"
   Header: `Parent link`
   Options: `native (modern Cloud parent field)` (recommended) | `epic_link (classic customfield_10014)`

All three reject "Other" with re-prompt. Capture as `jira.issue_types.feature`, `jira.area_field`, `jira.parent_link_style`. (Note: phase letter is `4d` per the cloud-id collapse in 4b; this is the fourth Jira-branch step, not the fifth.)

The other four plugin-type → Jira issue-type mappings are written verbatim with no prompt (overridable post-hoc by hand-editing the YAML):
- `bug → Bug`
- `epic → Epic`
- `sub → Sub-task`
- `followup → Task`

### Phase 5 — Vocabulary batch (both backends)

1 × `AskUserQuestion` (multi-question form — 2 questions in a single call):

1. Question: "Which area labels does this project use?"
   Header: `Areas`
   multiSelect: true
   Options: `dashboard`, `backend`, `frontend`, `infra` — all four pre-selected as the recommended default. Operator deselects unwanted; uses "Other" to add custom values.
2. Question: "Does this project have a subsystem vocabulary to include?"
   Header: `Subsystems`
   Options: `Yes — let me list them` (recommended) | `No — leave subsystems unset`

If the subsystems answer was "Yes", 1 × follow-up `AskUserQuestion` (single-select with "Other" for free-form):
- Question: "Enter subsystem names, one per line."
- Header: `Subsystem list`
- Options: one literal "Enter via Other" with the actual input arriving via the "Other" textbox.

Parse the multi-line response into a YAML list.

### Phase 6 — Assemble the YAML

Build the YAML string in memory. Header comment block (verbatim):

```yaml
# .claude/issue-tracker.yaml — agent-issue-tracker schema v1
#
# Written by /tracker-init on YYYY-MM-DD. Schema reference:
# https://github.com/maxdimitrov/agent-issue-tracker/blob/main/examples/issue-tracker.yaml.example
#
# Run /tracker-doctor to validate this config.

schema_version: 1
```

YYYY-MM-DD is substituted with the current date at invocation time.

Followed by:

```yaml
backend: <github | jira>
```

Then conditionally:

- `areas:` block — only if the multi-select returned a non-empty list.
- `subsystems:` block — only if the subsystems-yes/no returned Yes AND the follow-up parsed a non-empty list.
- `github:` block — only if `backend: github`. Contains `repo:` and the schema default `default_pr_close_syntax: "Fixes #N"` (rendered explicitly so it's visible).
- `jira:` block — only if `backend: jira`. Contains:
  - `site:`, `cloud_id:`, `project:`
  - `issue_types:` mapping (the prompted `feature` plus the four verbatim defaults)
  - `area_field:`, `parent_link_style:`
  - `epic_link_field: customfield_10014` — only if `parent_link_style: epic_link`
  - `done_transition: Done` (the schema default, rendered explicitly)
  - `close_on_merge_hint: ""` (empty default; advisory text)

`types:` block omitted entirely (v1 doesn't prompt for type customisation; plugin defaults apply).
`triage:` block omitted entirely (v1 doesn't prompt for label name customisation; plugin defaults apply).

### Phase 7 — Write

Single Write call to `.claude/issue-tracker.yaml` at the consumer's CWD (relative path acceptable; Write resolves against CWD).

### Phase 8 — Next-steps panel

Print to the operator:

```
Wrote .claude/issue-tracker.yaml (backend: <github | jira>).

Next steps:
  1. Run /tracker-doctor to validate the config end-to-end.
  2. Try filing a smoke-test issue: invoke the bug-tracking skill
     (e.g. "file a bug: README has a typo") and confirm it lands in your tracker.
```

For GitHub: append "If `/tracker-doctor` reports missing area labels on the repo, it will print `gh label create` commands you can paste."
For Jira: append "If `/tracker-doctor` reports missing issue types in the project, it will print the next-step `getJiraProjectMetadata` call you can run."

For `--force` overwrites: prepend "(Overwrote existing config at `.claude/issue-tracker.yaml`.)" to the output.

## 6. Failure modes (consolidated)

Explicit, in the command's "Failure modes" section at the bottom of the file:

1. **Existing config + no `--force`** → refuse, report path, suggest `/tracker-doctor` or `--force`.
2. **GitHub: `gh` missing / unauthenticated** → instruct `gh auth login` and exit.
3. **Jira: Atlassian MCP not in tool surface** → instruct connector setup at claude.ai and exit.
4. **Jira: `site` doesn't match any MCP-accessible site** → list accessible sites; let operator pick; if none acceptable, exit (do NOT write a config with `cloud_id: ""`).
5. **Areas multi-select returned empty** → omit `areas:` entirely (free-form area at skill prose level).
6. **Operator interrupts mid-flow** → no partial write; YAML only written in Phase 7.
7. **"Other" returned for a closed enum** → re-prompt with the same question (do NOT silently accept; do NOT default).

## 7. Invariants

- `schema_version: 1` is always the first non-comment line.
- Every emitted field corresponds to a field documented in `examples/issue-tracker.yaml.example`. No silent extensions.
- `--force` is the only overwrite path.
- Markdown-only command file. The agent EXECUTES the prose; embedded shell strings (`gh auth status`, `gh repo view`) are agent-instruction text, not bash heredocs.
- No partial writes — Phase 7 is atomic.
- The agent uses the Write tool for the YAML emission (NOT shell redirection), so the harness sees the file diff in a follow-up tool result and the operator can audit.

## 8. Cross-references

- `commands/resume-initiative.md` — the markdown shape precedent (frontmatter, "What you should do" section, Failure modes block).
- `examples/issue-tracker.yaml.example` — the schema v1 every emitted field maps onto.
- `backends/github.md` "Setup verification" — the `gh auth status` + `gh repo view` probe shape Phase 3 borrows.
- `backends/jira.md` (sibling Phase 3 sub-issue, not yet landed) — the Atlassian MCP availability probe and `getAccessibleAtlassianResources` site-discovery shape Phase 4 borrows.
- `commands/tracker-doctor.md` (sibling Phase 3 sub-issue, not yet landed) — the file `/tracker-doctor` validates is the file `/tracker-init` writes. Schema invariants must agree.

## 9. Acceptance

The PR closes when **all** are true:

- [ ] `commands/tracker-init.md` exists; renders cleanly; carries YAML frontmatter `description:`.
- [ ] No literal `maxdimitrov/trading-bot` string anywhere in the new file.
- [ ] At least 4 `AskUserQuestion` invocations referenced in the prose (backend select; areas multi-select; subsystems yes/no; plus at least one more per branch — covered by GitHub repo, OR by the 3-question Jira field-mapping batch).
- [ ] Both backend branches fully documented (GitHub: auth probe + repo default + repo prompt; Jira: MCP availability + site + `cloud_id` round-trip + project + 3 field-mappings).
- [ ] Existing-config guard documented (`--force` semantics).
- [ ] Failure-modes section enumerates the seven scenarios from §6.
- [ ] The header comment block written to `.claude/issue-tracker.yaml` is shown verbatim in the prose.
- [ ] YAML emission only includes blocks relevant to the chosen backend (no orphan `jira:` when `github`; no orphan `github:` when `jira`).
- [ ] CHANGELOG.md `[Unreleased] → Added` carries the Phase 3 entry in the same `Phase X (#Y): <name> — ...` format as the four Phase 2 entries and the `/resume-initiative` entry.

## 10. Verification

The verification grep block from issue #22 binds the acceptance. Re-stated here for the spec record:

```bash
test -f commands/tracker-init.md
grep -F "maxdimitrov/trading-bot" commands/tracker-init.md && echo "LEAK" || echo "clean"

COUNT=$(grep -c "AskUserQuestion" commands/tracker-init.md)
[ "$COUNT" -ge 4 ] || { echo "MISSING AskUserQuestion invocations (got $COUNT, need >=4)"; exit 1; }

grep -qE "gh auth status" commands/tracker-init.md || exit 1
grep -qE "gh repo view" commands/tracker-init.md || exit 1
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-init.md || exit 1
grep -qE "cloud_id|cloudId" commands/tracker-init.md || exit 1
grep -qE "\-\-force" commands/tracker-init.md || exit 1
grep -qE "schema_version:\s*1" commands/tracker-init.md || exit 1
```

## 11. Notes

- The plugin's first real consumer running `/tracker-init` is the work Jira project in Phase 6 (the second-consumer proof). The Jira branch's UX is gated by that consumer's experience. The first failure mode in production will be the Atlassian MCP cloud-id round-trip — make that prompt's failure surface name the literal scope (`read:jira-work`) the connector needs.
- `AskUserQuestion` has a hard limit of 4 options per question (plus auto-"Other"). The `areas` multi-select uses exactly 4 default options (`dashboard`, `backend`, `frontend`, `infra`); if the v1 default vocabulary grows, the prompt schema needs splitting. Today it fits.
- The Jira flow collapses the conceptual "ask for site → resolve cloud_id" two-step into a single prompt sourced from `getAccessibleAtlassianResources` (see Phase 4b). This removes one operator turn and avoids the bad ergonomics of an empty-recommended Site prompt where the only meaningful action is "Other". The single-site case is auto-resolved; the multi-site case is a normal single-select.
- This is the first plugin command that writes a file. Resume-initiative is read-only (queries; no writes). Establishing the Write-tool-at-end-of-flow pattern here matters for future commands (`/tracker-fix-areas`, hypothetical migration commands, etc.).
- The header comment's `YYYY-MM-DD` substitution: the agent gets the current date from the system; in Claude Code, `$(date +%Y-%m-%d)` or reading `Today's date is ...` from the system reminder both work. Document a single canonical source in the prose.
