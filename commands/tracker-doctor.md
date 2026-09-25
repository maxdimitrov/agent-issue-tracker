---
description: Validate `.claude/issue-tracker.yaml`: schema, backend reachability, vocabulary sanity. Read-only. Always exits 0.
---

# /tracker-doctor [--smoke-issue <ref>]

Validate the consumer project's `.claude/issue-tracker.yaml`. Runs four sequential check phases: schema validation (file exists, parses, version and backend present, required fields set per backend, type enum check); backend reachability (proof-of-dispatch via `view_issue` per cross-backend invariant #5 in `backends/_interface.md`); vocabulary sanity (warning-level warnings about missing labels or issue types); session-title hook prerequisites (WARN-only, never FAILs). Always exits 0 (informational discipline, same pattern as `/audit-skills`). Sibling pair: `/tracker-init` writes the config; `/tracker-doctor` validates it.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/tracker-doctor` | Run all four check phases against the current config. Use the default probe ref (`#1` on GitHub / `<jira.project>-1` on Jira). |
| `/tracker-doctor --smoke-issue <ref>` | Run all four check phases. Override the default reachability probe ref with `<ref>` (useful when the conventional first-issue ref doesn't exist or is restricted). |

## What you should do

### Phase 1 — Schema validation

Read `.claude/issue-tracker.yaml` from the consumer's CWD. Apply these checks in order; each is its own line in the output:

| Check | PASS condition | FAIL output |
|---|---|---|
| File exists | the file is present at `.claude/issue-tracker.yaml` | "no config found; run `/tracker-init`" |
| YAML parses | the file loads as a valid YAML document | "YAML parse error: `<line>:<col>: <message>`" |
| `schema_version: 1` | top-level key present with value `1` | "missing or wrong schema_version (only `1` is supported in v1)" |
| `backend:` present | top-level key present with value `github` or `jira` | "missing or unrecognized backend (must be `github` or `jira`)" |
| Backend-conditional required block | if `backend: github`, the `github:` block exists with `github.repo` set; if `backend: jira`, the `jira:` block exists with `jira.site`, `jira.cloud_id`, `jira.project`, `jira.issue_types` all set | "missing required `<backend>.<field>` for backend `<backend>`" |
| `types.*` only contains known keys | each key under `types:` (if present) is one of `bug`, `feature`, `followup`, `epic`, `sub` | "unknown type key under `types:`: `<list>`" |
| Jira-only: `jira.issue_types` covers all five plugin types | mapping has keys `bug`, `feature`, `epic`, `sub`, `followup` | "missing issue_types mapping for: `<list>`" |
| `loops.*` well-formed (only when `loops:` is present) | `interval` matches `^[0-9]+[smhd]$`; `max_iterations`, `max_hours`, `idle_stop_after`, `max_concurrent` are positive integers; `pr_mode` is `draft` or `ready`; no unknown keys | "invalid loops config: `<key>`: `<value>` (expected `<rule>`)" |

WARN-only items (bullet list):

- `areas:` empty or missing — optional, but warn so skills know to fall back to free-form.
- `subsystems:` empty or missing — optional, but worth surfacing.
- Jira-only: `jira.parent_link_style: epic_link` but `epic_link_field` not set — defaults to `customfield_10014`; warn but use the default.
- Jira-only: `jira.in_progress_transition` not set — the in-progress affordance is opt-in (`backends/jira.md` "In-progress transition (optional)"), so every driver that starts work leaves the issue in whatever status it already had. That is the documented default, but it is silent at the moment it matters, so surface it here, where the operator is looking at their config:

  ```
  [WARN] jira.in_progress_transition unset — issues keep their current status when work
         starts (/work-issue Step 3, /resume-initiative --start). Set it to opt in:
  ```

  ```yaml
  jira:
    in_progress_transition: "In Progress"   # must match a transition name in your workflow
  ```

- Jira-only, INFO-level: `jira.in_progress_sprint` not set — reported as an
  `[INFO]` line, not `[WARN]` and not `[PASS]`; it counts toward neither in
  the summary. Active-sprint assignment is opt-in on top of the transition
  above, so leaving it unset is an ordinary, unremarkable default — worth one
  line so the operator knows the affordance exists, but not worth a warning:

  ```
  [INFO] jira.in_progress_sprint unset — issues stay out of the active sprint when
         work starts. Set it to opt in:
  ```

  ```yaml
  jira:
    in_progress_sprint: active
    # sprint_board_id: 123            # optional; disambiguates multiple active sprints
    # sprint_field: customfield_10020 # optional; defaults to customfield_10020
  ```

  When `jira.in_progress_sprint` IS set, validate its shape (still Phase 1,
  still WARN-level — never FAIL):
  - `in_progress_sprint` must be the literal string `active` (the only
    supported value today) — WARN otherwise.
  - `sprint_board_id`, if set, must be a positive integer — WARN otherwise.
  - `sprint_field`, if set, must match `^customfield_\d+$` — WARN otherwise.

- Jira-only, INFO-level: `jira.merged_transition` not set — the same
  render-only `[INFO]` shape as `in_progress_sprint` above. Moving a ticket to
  a merged-not-released status on `/work-issue --finish` is opt-in
  (`backends/jira.md` "Merged transition (optional)"):

  ```
  [INFO] jira.merged_transition unset — /work-issue --finish leaves the ticket's
         status alone after a merge. Set it to opt in:
  ```

  ```yaml
  jira:
    merged_transition: "Ready for Release"   # must match a transition name in your workflow
  ```

- `merge_method` set to anything but `merge`, `squash` or `rebase` — WARN
  "`merge_method: <value>` is not one of `merge` / `squash` / `rebase`";
  `/work-issue --merge` and `/tracker-loop babysit` would pass it straight to
  `gh pr merge`. Unset is fine (default `squash`) and prints nothing.

- `loops:` absent — fine; `/tracker-loop` uses its built-in defaults (`examples/issue-tracker.yaml.example` documents them). Surfaced only so an operator who expected a custom `poll_label` notices it is not set.
- `skill_currency:` malformed (only when the block is present; absent is fine and prints nothing). The block is optional and `/audit-skills` never blocks a PR, so every problem here is a `WARN`, never a `FAIL` — but without these rows a typo stays silent until `/audit-skills` exits 1 with a parse error. Check the shape `examples/issue-tracker.yaml.example` documents and emit one `WARN` line per problem, naming it:
  - `skill_currency:` present but not a mapping — "`skill_currency` must be a mapping with `doc_globs` / `paired_rules`".
  - `doc_globs:` present but not a list of strings — "`skill_currency.doc_globs` must be a list of glob strings".
  - a `paired_rules:` entry (by index) missing any of `watch`, `pattern`, `expect`, `message` — "`skill_currency.paired_rules[<i>]` missing keys: `<list>`" (the same four keys `scripts/audit_skills.py`'s `parse_rule` requires).
  - a `paired_rules:` entry whose `pattern` is not a valid regular expression — "`skill_currency.paired_rules[<i>].pattern` is not a valid regex: `<error>`". Test it the way the detector does (`python -c "import re, sys; re.compile(sys.argv[1])" '<pattern>'`), or reason about it when no Python is on PATH.
  - a `paired_rules:` entry that is not a mapping, or `paired_rules:` itself not a list — same `WARN` shape, naming the offending index.

  A valid block, or no block, adds no output. `skill_currency` problems never stop Phases 2-3: they are informational, exactly like the `/audit-skills` run they pre-empt.

If any check `FAIL`s in Phase 1, **stop here**. Do NOT run Phase 2 or Phase 3. The config is structurally broken; reachability probes against it would just compound the noise. The summary line still prints with the Phase 1 counts.

### Phase 2 — Backend reachability

Branch on `backend:` value from the schema. Phase 2 always runs `view_issue` (per cross-backend invariant #5 in `backends/_interface.md`) as the canonical reachability proof — different backends have different setup-prerequisite checks before it and conditional WARN-only probes after it. The GitHub branch adds two unconditional probes before `view_issue` (issues-enabled, write probe) plus a conditional, WARN-only probe when `github.project` is configured (Projects board reachability); the Jira branch adds a conditional, WARN-only probe when `jira.in_progress_sprint` is configured (sprint-field and active-sprint sanity). After the backend-specific branch, both backends run the upstream-contribution check (WARN-only, below) against the plugin's own repo.

#### GitHub branch

Five sequential probes numbered 1-5, plus a sixth, conditional, WARN-only Projects-board probe when `github.project` is set.

1. `gh auth status` — `PASS` if exits 0; `FAIL` with "run `gh auth login` and retry" otherwise. Report the credential source and token type from this call's own output: the line naming `GH_TOKEN`/`GITHUB_TOKEN` (env) or `keyring`, and the token's non-secret prefix — `github_pat_` (fine-grained), `ghp_` (classic), `gho_` (OAuth). Never print more of the token than the prefix.
2. `gh repo view <github.repo>` — `PASS` if exits 0; `FAIL` with the literal `gh` error (typically "Could not resolve to a Repository") + suggestion to fix `github.repo` in the YAML.
3. **Issues enabled:** `gh repo view <github.repo> --json hasIssuesEnabled --jq .hasIssuesEnabled`. `FAIL` with "issues are disabled on `<repo>` (common on forks) — enable them in Settings → Features, or point `github.repo` at the upstream repo" if `false`.
4. **Write probe:** confirm the token can *create* issues, not just read them — on a public repo, probes 1-3 all pass for a read-only token, so `create_issue` failing is otherwise discovered only at filing time. Non-destructive: POST an issue with an empty body. `title` is required, so nothing is ever created, and GitHub checks the token's permission before it validates the request body:

   ```bash
   gh api -X POST "repos/<github.repo>/issues" --input - <<< '{}'
   ```

   | HTTP status | Observed message | Meaning | Result |
   |---|---|---|---|
   | 422 | `Invalid request. "title" wasn't supplied.` | token may create issues; nothing created | `PASS` |
   | 403 | `Resource not accessible by personal access token` | token can read but not write issues here | `FAIL` |
   | 401 | `Bad credentials` | token invalid, expired, or revoked | `FAIL` |

   Remediation on `FAIL`, tailored to the token type named in step 1:
   - `github_pat_` (fine-grained) on 403: whoever owns the token (the
     operator, or the org for an org-owned token) must grant it "Issues:
     Read and write" on this repo, or re-auth with a classic/OAuth token via
     `gh auth login`.
   - `ghp_` (classic) or `gho_` (OAuth) on 403: the token itself lacks the
     `repo` scope — `gh auth refresh -s repo` or `gh auth login` again.
   - Any type on 401: the token is invalid, expired, or revoked — `gh auth
     login` for a fresh one.

   **Expiry.** Re-run the same probe with `-i` (`gh api -i -X POST ...`) to
   read response headers. If `github-authentication-token-expiration` is
   present, print the date; `WARN` when it is under 14 days away or already
   past. Absent means the token does not expire (observed for the OAuth
   `gho_` token this was verified against).

5. **Canonical reachability:** invoke `view_issue({ref: "#<smoke-ref-or-1>"})` against the configured backend (which dispatches to `gh issue view <N> --repo <github.repo> --json body,labels,state,title`). `<smoke-ref>` is the `--smoke-issue` flag value if passed (accept either `#7` or `7` — strip a leading `#` before composing the ref); otherwise default to `1`.
   - `PASS` if the call returns a structured response (issue exists).
   - `PASS-WITH-NOTE` if the call returns 404 — the repo is reachable, but the issue doesn't exist (greenfield repo). The dispatch path is proven.
   - `FAIL` only on 401 / 403 (auth wrong despite Step 1 passing — token scope mismatch) or connection error.

6. **GitHub Projects board (only if `github.project` is set; skip otherwise).**
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

#### Jira branch

Three sequential probes numbered 1/2/3, plus a fourth when configured.

1. **Atlassian MCP availability** — confirm the agent's tool surface includes the Atlassian Remote MCP family (`createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`). `FAIL` with "enable the Atlassian connector at claude.ai → Settings → Connectors → Atlassian" otherwise. The agent uses `ToolSearch` against keywords like `jira atlassian` if uncertain.
2. **`cloud_id` round-trip** — invoke `getAccessibleAtlassianResources`; confirm the configured `jira.cloud_id` appears in the returned site list and matches the configured `jira.site`. `FAIL` with the list of accessible cloud_ids otherwise.
3. **Canonical reachability:** invoke `view_issue({ref: "<smoke-ref-or-PROJECT-1>"})` where `<smoke-ref>` is the value of `--smoke-issue` if passed, otherwise the default `<jira.project>-1` (e.g. `TRADE-1`). The configured backend dispatches to `getJiraIssue(cloudId, issueKey)`.
   - `PASS` if the call returns a structured response.
   - `PASS-WITH-NOTE` if the call returns 404 — the project is reachable, but the probe issue doesn't exist (project may have started from a higher seed, or `<PROJECT>-1` is restricted). The dispatch path is proven.
   - `FAIL` only on 401 / 403 (auth wrong, or `cloud_id` doesn't match `site`) or connection error.

4. **Active-sprint assignment sanity (only if `jira.in_progress_sprint` is set; skip otherwise).**
   Two live checks, both `WARN`-only (never `FAIL` — the affordance is optional):
   - `getJiraIssue({cloudId, issueIdOrKey: <smoke-ref-or-PROJECT-1>, expand: "names"})` — confirm `jira.sprint_field` (default `customfield_10020`) maps to a field named `Sprint` in the returned `names` map. `WARN` naming the field it actually maps to (or "not present") otherwise.
   - `searchJiraIssuesUsingJql({cloudId, jql: "project = <jira.project> AND sprint in openSprints()", fields: [<sprint_field>]})` — collect distinct sprint objects with `state == "active"`, filtered by `boardId == jira.sprint_board_id` when that key is set. `WARN` naming the count found unless exactly one qualifies.

#### Upstream contribution check (both backends, WARN-only)

Runs after the backend-specific branch above, **for both backends** — `tracker-contribute` always uses `gh` to file upstream, regardless of `backend:`. Reuses the same non-destructive write probe as the GitHub branch's step 4, aimed instead at the repository named in the plugin's own `.claude-plugin/plugin.json` `repository` field (parse `<owner>/<repo>` from that URL; today `maxdimitrov/agent-issue-tracker`). Honour `GH_TOKEN` / `GITHUB_TOKEN` when set — same precedence `gh` itself uses — so this checks the token an operator will actually file with, not just the keyring default. Document to the operator: run `/tracker-doctor` with the same environment you plan to file with.

```bash
gh api -X POST "repos/maxdimitrov/agent-issue-tracker/issues" --input - <<< '{}'
```

- `422` — `PASS`.
- `403` with a fine-grained token (`github_pat_`) — `WARN`, quoting the limitation: GitHub does not support fine-grained PATs contributing to public repos where the token owner is not a member, and each fine-grained token is scoped to a single resource owner. Remediation: `gh auth login` (OAuth), or set `GH_TOKEN` to a classic/OAuth token for this one call.
- `401` — `WARN`: "token expired or revoked; rotate it."
- `gh` missing or unauthenticated — `WARN`, never `FAIL`: contributing upstream is optional.

If any check `FAIL`s in Phase 2, **continue to Phase 3** — vocabulary sanity is independent of reachability (the labels-list probe in Phase 3's GitHub branch hits `gh label list` which has its own auth path). But document: Phase 3 results may be empty or 401 if reachability is broken. Phase 2 `FAIL` is the actionable finding; Phase 3 is informational in that case.

### Phase 3 — Vocabulary sanity

Branch on `backend:` value. Each check is `WARN`-level (the plugin works without these — but the operator's first `create_issue` will fail noisily if they're missing). Never `FAIL`.

#### GitHub branch

For each value in the consumer's `areas:` list (skip if `areas:` is empty or missing — already `WARN`ed in Phase 1), check whether the label exists on the configured repo with:

```bash
gh label list --repo "<github.repo>" --search "<area>" --json name --jq '.[].name'
```

If the label is missing, `WARN` with the literal next-step command in a fenced block the operator can paste:

```bash
gh label create "<area>" --repo "<github.repo>" --description "Area: <area>" --color BFD4F2
```

Print one such command per missing area.

#### Jira branch

Two checks, numbered:

1. For each value in `jira.issue_types.*` (the five mapped issue type names — `Bug`, `Story`, etc.), check whether the issue type exists in the configured Jira project. MCP call (verified live against the Atlassian Remote MCP): `getJiraProjectIssueTypesMetadata({cloudId, projectIdOrKey})` returns the project's configured issue types (the visible-project list itself comes from `getVisibleJiraProjects`); the agent can `ToolSearch` against `jira project metadata` if the tool name has shifted in the current MCP version. `WARN` with "missing issue type `<name>` in project `<projectKey>`; check your Jira project settings or remap in `.claude/issue-tracker.yaml`" for any missing type.
2. If `jira.area_field: components`, list the project's configured Components and surface them as a `WARN-info` line so the operator knows what areas they can use. MCP call (verified live against the Atlassian Remote MCP, 2026-07-28): the tool family has **no dedicated project-components tool** — enumerate them via `getJiraIssueTypeMetaWithFields({cloudId, projectIdOrKey, issueTypeId, requiredFieldsOnly: false})`, where `issueTypeId` is any non-subtask issue type id already returned by check 1's `getJiraProjectIssueTypesMetadata` call; the project's components are the `allowedValues[].name` entries on the response field whose `fieldId` is `components`. A project with no Components configured returns `allowedValues: []` — surface that as the same `WARN-info` line ("no Components configured; `area_field: components` has nothing to match"). No `FAIL` — `area_field` defaults to free-form when components don't match.

### Phase 4 — session-title hook prerequisites (WARN-only)

The SessionStart session-title hook is cosmetic; nothing here may FAIL.

1. `jq` on PATH → `[PASS] jq found`. Missing → `[WARN] session-title hook
   inactive: jq not found` + install hint (`brew install jq` / `apt install jq`).
2. State dir `${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles/`
   creatable/writable → `[PASS]`; else `[WARN]` with the path.
3. Config sets `session_titles: false` → `[PASS-WITH-NOTE] session titles
   disabled by config`.

### Phase 5 — Summary

Always exit 0. The final line aggregates counts:

```
Summary: <F> FAIL · <W> WARN · <P> PASS
```

`<F>`, `<W>`, `<P>` are the integer counts of `FAIL` / `WARN` / `PASS` lines across Phases 1-4. `PASS-WITH-NOTE` counts as `PASS` for the summary but renders inline as `[PASS] ... (note: <reason>)`. `[INFO]` lines are not counted.

## Output format

Verbatim example block:

```
=== /tracker-doctor — agent-issue-tracker schema v1 ===

Phase 1 — schema validation
  [PASS] file exists
  [PASS] YAML parses
  [PASS] schema_version: 1
  [PASS] backend: github
  [PASS] github.repo: maxdimitrov/example-project
  [WARN] areas: unset (skills will use free-form area)

Phase 2 — backend reachability
  [PASS] gh auth status (keyring; ghp_ classic PAT)
  [PASS] gh repo view maxdimitrov/example-project
  [PASS] hasIssuesEnabled: true
  [PASS] write probe: 422 — token may create issues
  [PASS] token expiry: 2027-03-01 (154 days out)
  [PASS] view_issue(#1) — issue exists

Upstream contribution check
  [PASS] write probe (maxdimitrov/agent-issue-tracker): 422 — token may create issues

Phase 3 — vocabulary sanity
  (no areas configured; skipping)

Summary: 0 FAIL · 1 WARN · 12 PASS
```

Example for a write-probe `FAIL` (403 on the consumer repo — a fine-grained token that can read but not write issues here):

```
Phase 2 — backend reachability
  [PASS] gh auth status (keyring; github_pat_ fine-grained PAT)
  [PASS] gh repo view maxdimitrov/example-project
  [PASS] hasIssuesEnabled: true
  [FAIL] write probe: 403 — Resource not accessible by personal access token
```

```bash
# Fine-grained PAT lacks "Issues: Read and write" on this repo.
# Grant it in the token's settings (org admin for an org-owned token),
# or re-auth with a classic/OAuth token:
gh auth login
```

For `FAIL` / `WARN` lines, render the literal next-step command in a fenced block under the line. Example for a missing-label `WARN` in Phase 3a:

```
Phase 3 — vocabulary sanity
  [WARN] area label `dashboard` missing on maxdimitrov/example-project
```

```bash
gh label create "dashboard" --repo "maxdimitrov/example-project" --description "Area: dashboard" --color BFD4F2
```

Example for a malformed `skill_currency:` block in Phase 1 (WARN-only; Phases 2-3 still run):

```
Phase 1 — schema validation
  [PASS] file exists
  [PASS] YAML parses
  [PASS] schema_version: 1
  [PASS] backend: github
  [PASS] github.repo: maxdimitrov/example-project
  [WARN] skill_currency.doc_globs must be a list of glob strings (got a string)
  [WARN] skill_currency.paired_rules[0] missing keys: expect, message
  [WARN] skill_currency.paired_rules[1].pattern is not a valid regex: missing ), unterminated subpattern at position 12
```

Under each `WARN`, point at the shape: "see the `skill_currency:` block in `examples/issue-tracker.yaml.example`". `/audit-skills` would otherwise exit 1 on the first bad rule with the same message.

## Failure modes

- **Config missing.** Report "no config found; run `/tracker-init`" as a Phase 1 `FAIL`. Exit 0.
- **Phase 1 FAIL (any).** Do not run Phase 2 or 3 — the YAML is structurally broken; further probes would compound noise. Summary line still prints with Phase 1 counts.
- **Backend probe timeout / network error.** Render as `FAIL` with the literal command the operator should retry by hand. Exit 0 (informational).
- **Atlassian MCP not in tool surface (Jira).** Phase 2 step 1 = `FAIL` with the connector setup link. Phase 2 steps 2/3 + Phase 3 skip with a note ("Atlassian MCP unavailable; skipping").
- **Write probe FAIL (403 / 401 on the consumer repo).** 403 = token can read but not write issues here — a fine-grained PAT needs "Issues: Read and write" on this repo granted by the token's owner (the org, for an org-owned token), or re-auth (`gh auth login`) with a classic/OAuth token; a classic/OAuth token needs `gh auth refresh -s repo`. 401 = token invalid, expired, or revoked — `gh auth login` for a fresh one. Doctor still continues past it (Phase 2 `FAIL` doesn't short-circuit Phase 3).
- **Upstream contribution check WARN (403 on the plugin repo with a fine-grained token).** GitHub does not support fine-grained PATs contributing to public repos where the token owner is not a member. Remediation: `gh auth login` (OAuth), or set `GH_TOKEN` to a classic/OAuth token for that one call. Never `FAIL`s — contributing upstream is optional.
- **Operator interrupts mid-validation.** No side effects — the command is read-only. The harness's interrupt handling closes the session; no partial state on disk or in the tracker.

## Invariants

- **Always exits 0.** Informational discipline. Mirrors `/audit-skills`. The operator decides whether `WARN` matters; the validator never gates.
- **Read-only, with one narrow, verified exception.** No `create_issue`, no `edit_body`, no `add_label`, no `close_issue`. No modifications to `.claude/issue-tracker.yaml`. The GitHub write probe (Phase 2 GitHub branch step 4, reused by the upstream contribution check) is the one write-*shaped* call, and it can never mutate anything: it POSTs an issue body with `title` omitted, `title` is a required field, and GitHub checks the token's permission before it validates the request body — so the best case the probe can produce is a 422 rejection, never a created issue.
- **Never use `viewerPermission` or `permissions.*` as evidence of write access.** Both reflect the authenticated *account's* role on the repo, not what the *token* was granted — a fine-grained PAT scoped to read-only can sit on an account with `viewerPermission: WRITE` and still fail every `create_issue`. Only the write probe's actual HTTP status is evidence.
- **Never print or log a token.** The non-secret prefix (`github_pat_`, `ghp_`, `gho_`) is the only token-derived output, ever.
- **Canonical reachability probe is `view_issue`.** Cross-backend invariant #5 from `backends/_interface.md`. Every backend's Phase 2 final step dispatches through that contract operation, not the backend's raw CLI / MCP.
- **PASS / WARN / FAIL / PASS-WITH-NOTE is fixed.** `FAIL` = dispatch path is broken; `WARN` = dispatch works but vocabulary is incomplete; `PASS` = green; `PASS-WITH-NOTE` = dispatch works but the probe artifact is absent (404). The only other line shape is `[INFO]`: a render-only note about an unset opt-in key (today: `jira.in_progress_sprint` and `jira.merged_transition`) that is neither a check result nor counted in the summary.
- **Markdown-only file.** Slash commands are markdown. No embedded shell scripts beyond what `backends/<backend>.md` already documents as probe commands.
- **Phase 1 short-circuits Phases 2-3; Phase 2 does NOT short-circuit Phase 3.** A broken schema makes downstream probes meaningless. A broken reachability still leaves vocabulary findings actionable.

## Conventions assumed

The schema reference is `examples/issue-tracker.yaml.example`. The consumer-project's `.claude/issue-tracker.yaml` lives at the repo root. The sibling `/tracker-init` is the writer of the file `/tracker-doctor` validates; the two share schema invariants. The configured backend is dispatched via `backends/<backend>.md`; raw CLI / MCP calls appear only in the per-backend setup-verification probes documented there.
