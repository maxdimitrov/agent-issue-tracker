---
description: Interactive scaffolder — writes `.claude/issue-tracker.yaml` for the consumer project. Refuses to overwrite without --force.
---

# /tracker-init [--force]

Write a valid `.claude/issue-tracker.yaml` to the consumer project's root. This command walks you through an `AskUserQuestion`-driven flow to gather backend choice, backend-specific credentials and config, and project vocabulary. It assembles the YAML in memory, validates it against the schema, and writes it atomically. Refuses to overwrite an existing config unless `--force` is passed. After init completes, run `/tracker-doctor` to validate the config end-to-end. The schema reference is [`examples/issue-tracker.yaml.example`](../examples/issue-tracker.yaml.example).

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/tracker-init` | Interactive flow. Refuses to overwrite an existing `.claude/issue-tracker.yaml`. |
| `/tracker-init --force` | Interactive flow. Overwrites an existing `.claude/issue-tracker.yaml`. |

## What you should do

### Phase 1 — Pre-flight: existing-config guard

1. Check whether `.claude/issue-tracker.yaml` exists in the consumer's CWD.
2. If the file does not exist → continue to Phase 2.
3. If the file exists and `--force` was NOT passed → report the file's path, suggest running `/tracker-doctor` (to validate the existing config) or re-invoking `/tracker-init --force` (to overwrite). Stop. Do not prompt further.
4. If the file exists and `--force` was passed → note that an overwrite is happening; surface this in the final summary (Phase 8); continue to Phase 2.

### Phase 2 — Backend selection

Invoke `AskUserQuestion` once (single-select):
- Question: "Which issue tracker does this project use?"
- Header: `Backend`
- Options: `GitHub` | `Jira`
- "Other" response → reject and re-prompt the same question. Only `github` and `jira` are valid in v1.

Store the answer as `backend`. Branch on it: if `github`, proceed to Phase 3; if `jira`, skip Phase 3 and proceed to Phase 4.

### Phase 3 — GitHub branch (skip if backend is jira)

**3a. Auth probe (STOP-IF-FAIL).** Run `gh auth status`. If it exits non-zero or output contains "not logged" → instruct the operator: "You are not authenticated with GitHub. Run `gh auth login` and re-invoke `/tracker-init`." Exit. Do not continue.

**3b. Repo default extraction.** Run `gh repo view --json nameWithOwner --jq .nameWithOwner` against the consumer's CWD. If the command succeeds, capture the `owner/repo` string as the default. If it fails (the CWD is not a GitHub-cloned repo), record that no default exists.

**3c. Repo prompt.** Invoke `AskUserQuestion` once (single-select):
- Question: "Which GitHub repo will issues be filed against?"
- Header: `Repo`
- Options: If a default was extracted in 3b, present it first as `<owner/repo> (this repo)` and mark it "(Recommended)". If no default, present no recommended option; the operator will use "Other" for free-form input.
- "Other" response → accept as-is (user can type `owner/repo`). Reject blank input with a re-prompt.

Store the answer as `github.repo`. Skip Phase 4 and proceed to Phase 5.

### Phase 4 — Jira branch (skip if backend is github)

**4a. Atlassian MCP availability (STOP-IF-FAIL).** Search the agent's tool surface for the Atlassian Remote MCP tool family (conventional names: `createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`). If no Atlassian tools are found → instruct the operator: "The Atlassian connector is not enabled. Go to claude.ai → Settings → Connectors → Atlassian, enable it, and re-invoke `/tracker-init`." Exit. Do not continue.

**4b. Site + cloud_id (combined).** Invoke the MCP's site-discovery tool (conventional name `getAccessibleAtlassianResources`) to fetch the list of `{cloudId, url, ...}` entries the connector grants access to. Branch on the result count:
- Zero sites → STOP-IF-FAIL. The connector's scope does not include any Jira sites. Instruct: "The Atlassian connector has no Jira site access. Update the connector scope at claude.ai and re-invoke `/tracker-init`." Exit.
- Exactly one site → use it without prompting. Extract `url` (strip `https://` prefix and trailing slash) and store as `jira.site`. Extract `cloudId` and store as `jira.cloud_id`.
- Multiple sites → invoke `AskUserQuestion` once (single-select): "Which Atlassian site will issues be filed against?", header `Site`, options are the accessible sites' URLs (up to 4; if more than 4 sites, list the first 4 and rely on "Other" for typing one not listed). Reject "Other" with a re-prompt if the typed value does not match any accessible site's URL exactly. Extract `cloudId` from the chosen site and store both `jira.site` and `jira.cloud_id`.

**4c. Project key prompt.** Invoke `AskUserQuestion` once (single-select with "Other" for free-form):
- Question: "Which Jira project key will issues be filed under?"
- Header: `Project`
- Options: no recommended option. The description suggests examples like `TRADE`, `INFRA` so the operator knows the format.
- "Other" response → accept as-is. Reject blank input with a re-prompt.

Store the answer as `jira.project`.

**4d. Field-mapping batch.** Invoke `AskUserQuestion` once with three questions (multi-question form):
1. "What is the Jira issue type for plugin-type `feature`?", header `Feature type`, options `Story` (recommended) | `Task`. Reject "Other" with a re-prompt.
2. "Where does the `<area>` value live in Jira?", header `Area field`, options `components` (recommended) | `labels`. Reject "Other" with a re-prompt.
3. "How do epics link to children?", header `Parent link`, options `native (modern Cloud parent field)` (recommended) | `epic_link (classic customfield_10014)`. Reject "Other" with a re-prompt.

Store the answers as `jira.issue_types.feature`, `jira.area_field`, and `jira.parent_link_style`.

The four remaining plugin-type → Jira issue-type mappings are written verbatim without prompting (overridable by hand-editing the YAML post-hoc):
- `bug → Bug`
- `epic → Epic`
- `sub → Sub-task`
- `followup → Task`

### Phase 5 — Vocabulary batch (both backends)

Invoke `AskUserQuestion` once with two questions (multi-question form):

1. "Which area labels does this project use?", header `Areas`, multi-select with options `dashboard` | `backend` | `frontend` | `infra`. All four are pre-selected as the recommended default. The operator deselects unwanted; uses "Other" to add custom values.

2. "Does this project have a subsystem vocabulary to include?", header `Subsystems`, options `Yes — let me list them` (recommended) | `No — leave subsystems unset`.

If the subsystems answer is "Yes", invoke `AskUserQuestion` a second time (single-select with "Other" for free-form):
- Question: "Enter subsystem names, one per line."
- Header: `Subsystem list`
- Parse the multi-line "Other" response into a YAML list (one item per line).

If the subsystems answer is "No", record that `subsystems:` will be omitted from the YAML.

### Phase 6 — Assemble the YAML

Build the YAML string in memory. Start with the header comment block (VERBATIM, with the current ISO date substituted for `YYYY-MM-DD`):

```yaml
# .claude/issue-tracker.yaml — agent-issue-tracker schema v1
#
# Written by /tracker-init on YYYY-MM-DD. Schema reference:
# https://github.com/maxdimitrov/agent-issue-tracker/blob/main/examples/issue-tracker.yaml.example
#
# Run /tracker-doctor to validate this config.

schema_version: 1
```

Followed by:

```yaml
backend: <github | jira>
```

Emit the following blocks conditionally:

- `areas:` — emit ONLY if Phase 5's multi-select returned a non-empty list. Each item as a list entry.
- `subsystems:` — emit ONLY if Phase 5's subsystems answer was "Yes" AND the follow-up list parsed to non-empty. Each item as a list entry.
- `github:` block — emit ONLY if `backend: github`. Include:
  - `repo: <value from Phase 3c>`
  - `default_pr_close_syntax: "Fixes #N"` (render explicitly so it is visible; this is the schema default)
- `jira:` block — emit ONLY if `backend: jira`. Include:
  - `site: <value from Phase 4b, stripped of https:// and trailing slash>`
  - `cloud_id: <value from Phase 4b>`
  - `project: <value from Phase 4c>`
  - `issue_types:` mapping with:
    - `feature: <value from Phase 4d>`
    - `bug: Bug` (verbatim)
    - `epic: Epic` (verbatim)
    - `sub: Sub-task` (verbatim)
    - `followup: Task` (verbatim)
  - `area_field: <value from Phase 4d>`
  - `parent_link_style: <value from Phase 4d>`
  - `epic_link_field: customfield_10014` — emit ONLY if `parent_link_style: epic_link`
  - `done_transition: Done` (render explicitly; this is the schema default)
  - `close_on_merge_hint: ""` (render explicitly with empty string; advisory text for the operator)

Omit `types:` block entirely (v1 does not prompt for this; plugin defaults apply).
Omit `triage:` block entirely (same reason).

### Phase 7 — Write

Invoke `Write` tool once with the consumer's CWD path `./.claude/issue-tracker.yaml` and the YAML string assembled in Phase 6. This is the sole point at which the file is written to disk — atomic, no intermediate files.

### Phase 8 — Next-steps panel

Print to the operator (VERBATIM template, substituting `<github | jira>` with the chosen backend):

```
Wrote .claude/issue-tracker.yaml (backend: <github | jira>).

Next steps:
  1. Run /tracker-doctor to validate the config end-to-end.
  2. Try filing a smoke-test issue: invoke the bug-tracking skill
     (e.g. "file a bug: README has a typo") and confirm it lands in your tracker.
```

**For GitHub:** Append: "If `/tracker-doctor` reports missing area labels on the repo, it will print `gh label create` commands you can paste."

**For Jira:** Append: "If `/tracker-doctor` reports missing issue types in the project, it will print the next-step `getJiraProjectMetadata` call you can run."

**For `--force` overwrites:** Prepend the entire output with: "(Overwrote existing config at `.claude/issue-tracker.yaml`.)"

## Failure modes

- Existing config + no `--force` → refuse to overwrite. Report the file's path; suggest `/tracker-doctor` (to validate the existing config) or `--force` (to overwrite). Stop.
- GitHub: `gh` missing or unauthenticated (Phase 3a) → instruct operator to run `gh auth login` and re-invoke `/tracker-init`. Stop.
- GitHub: CWD is not a GitHub repo (Phase 3b) → no default extracted. Operator enters repo manually via "Other" in Phase 3c. Continue.
- Jira: Atlassian MCP not found in tool surface (Phase 4a) → instruct operator to enable the Atlassian connector at claude.ai and re-invoke. Stop.
- Jira: `getAccessibleAtlassianResources` returns zero sites (Phase 4b) → instruct operator to update connector scope. Stop.
- Jira: typed site in Phase 4b does not match any accessible site → reject with re-prompt. Do not proceed with a `cloud_id: ""`.
- Areas multi-select returned empty → omit `areas:` entirely from the YAML. No error; this is a valid state.
- Operator interrupts mid-flow (before Phase 7) → no file written. YAML is assembled only in Phase 6 and written in Phase 7; partial state is never persisted.
- "Other" response for a closed enum (Backend in Phase 2, Feature type / Area field / Parent link in Phase 4d) → reject with a re-prompt. Do NOT silently accept "Other"; do NOT default to an unlisted value.

## Conventions assumed

- The `.claude/issue-tracker.yaml` file lives at the consumer's repo root and is committed to version control.
- The schema is defined in [`examples/issue-tracker.yaml.example`](../examples/issue-tracker.yaml.example) (v1 only).
- After init, `/tracker-doctor` is the validation entrypoint — it runs `gh auth status` + `gh repo view` (GitHub) or Atlassian MCP site discovery (Jira) and warns about missing labels or issue types.
- For Jira, the Atlassian Remote MCP is the sole auth mechanism; no API tokens are stored in the plugin or the config file.
