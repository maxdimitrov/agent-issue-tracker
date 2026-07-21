# Jira Backend

Backend module for the [Atlassian Remote MCP](https://www.atlassian.com/blog/announcements/remote-mcp-server) — the dispatch surface for the `jira` backend. Implements the eight operations from [`_interface.md`](_interface.md). Sibling implementation: [`github.md`](github.md).

## Auth

Jira reaches the tracker via the Atlassian Remote MCP — a connector enabled per-user at claude.ai → Settings → Connectors → Atlassian. No per-project credentials live in the plugin or in `.claude/issue-tracker.yaml`.

The MCP handles OAuth refresh, token scopes, and rate limiting transparently. The plugin's only auth concern is whether the family is present in the agent's tool surface — checked via `ToolSearch` against keywords like `jira create issue` / `jira get issue`.

If `/tracker-doctor`'s Phase 2 step 1 reports the Atlassian MCP missing from the tool surface, the operator must enable the connector at claude.ai → Settings → Connectors → Atlassian and reload the session.

## Reference: Atlassian Remote MCP tool family

| Operation | MCP tool | Notes |
|---|---|---|
| Create | `createJiraIssue` | top-level: `cloudId`, `projectKey`, `issueTypeName`, `summary`, `description` (markdown), `parent`?; `labels` / `priority` / area-component / custom fields go in the `additional_fields` object — a top-level `labels` arg silently no-ops |
| Add label | `editJiraIssue` | set `fields.labels` (read-modify-write — fetch current labels first) |
| Sub-issue link | `editJiraIssue` | set `fields.parent.key` (modern Cloud) or `customfield_10014` (classic Epic Link); branch on `jira.parent_link_style` |
| List open | `searchJiraIssuesUsingJql` | JQL: `project = <key> AND statusCategory != Done` plus optional `issuetype` / `labels` filters |
| View | `getJiraIssue` | returns `{key, summary, description, status, labels, components, parent}` |
| Edit body | `editJiraIssue` | set `fields.description` to markdown string; MCP translates to ADF |
| Close | `transitionJiraIssue` | `transition: {id}` — numeric id resolved via `getTransitionsForJiraIssue` (ids are workflow-scoped, not global); no `comment` param — post a reason via `addCommentToJiraIssue({commentBody})` |

Tool names and call shapes verified live against the Atlassian Remote MCP (project MP, 2026-06-03). Transition ids are **workflow-scoped**, not global — the numeric id for a given transition name differs between workflows (e.g. the Story/Sub-task/Bug workflow vs the Epic workflow), so resolve them per-issue via `getTransitionsForJiraIssue` rather than hardcoding any numeric id. (Illustrative datum from that run: id `131` = "In Code Review" in MP's Story/Sub-task/Bug workflow — an example of *why* ids must be resolved at runtime, not a value to reuse.)

---

## Operations

### `create_issue`

File a new issue in the configured Jira project.

```
createJiraIssue({
  cloudId: <jira.cloud_id>,
  projectKey: <jira.project>,
  summary: <title>,
  issueTypeName: <jira.issue_types.<type>>,
  description: <body — markdown; MCP translates to ADF>,
  parent: <optional, for sub-issues created at file-time>,
  additional_fields: { labels: <labels[]>, components: <derived from area + area_field — see below> }
})
```

**Field mapping:**
- `type` → `issueTypeName` via the consumer's `jira.issue_types.<type>` mapping
- `title` → `summary`
- `body` → `description` (markdown; MCP handles ADF translation)
- `labels` → `additional_fields.labels[]` — a top-level `labels` arg silently no-ops, so labels MUST go inside the `additional_fields` object
- `area` → `additional_fields.components[].name` if `jira.area_field: components`, else appended to `additional_fields.labels[]` if `area_field: labels`
- `subsystem` → inline in `description` body (Locus block) — same convention as the GitHub backend
- `parent` → `parent.key` at create time when the operation supplies one (Cloud's unified parent works at creation for Sub-task types; for Story → Epic linkage use `link_sub_issue` post-create per the consumer's `jira.parent_link_style`)

Returns the Jira issue key (e.g. `TRADE-42`); the skill captures this as the ref.

**Body format — GitHub-Flavored Markdown ONLY, never Jira wiki markup.** The Atlassian Cloud MCP's `description` field is Markdown→ADF: it expects GitHub-Flavored Markdown and passes Jira **wiki-markup** tokens through as *literal text* (no API error — the issue just renders garbled). Do NOT reach for wiki markup even though "Jira" primes it. Token substitutions:

- `h1.` / `h2.` headings → `#` / `##`
- `{{monospace}}` → `` `monospace` `` (backticks)
- wiki ordered `#` / bullet `*` list markers → Markdown `1.` / `-`

Critical trap: a `#` at line-start is a Markdown **heading**, not an ordered-list item — wiki `#`-prefixed lists render as giant H1s. Because the `bug-tracking` thesis is "the body is an agent prompt," garbled headings and broken fences corrupt the very Locus / Acceptance / Verify structure an issue-fix agent parses. (Jira **Server / Data Center** legitimately uses wiki markup — see issue #3 — but this Cloud backend is Markdown-only; do not conflate them.)

---

### `add_label`

Apply an additional label to an existing issue.

```
# Read current labels
current = getJiraIssue({cloudId, issueIdOrKey: <ref>}).fields.labels

# Write back the full array (read-modify-write)
editJiraIssue({
  cloudId,
  issueIdOrKey: <ref>,
  fields: {labels: [...current, <new_label>]}
})
```

**Critical gotcha:** `editJiraIssue` REPLACES the entire `labels` array. The plugin MUST first `getJiraIssue` to fetch the current labels, append the new one in memory, then write the full array back. Forgetting the read step silently drops every other label on the issue. This is the Jira-side equivalent of the `-F` vs `-f` typed-int gotcha documented in [`github.md`](github.md)'s `link_sub_issue` block — same shape (a per-tracker API quirk that bites every operator once), same mitigation (document the canonical pattern inline).

**Area-field indirection:** When `jira.area_field: components`, an area-derived label does NOT pass through this operation — area is managed via `fields.components[].name`, set at `create_issue` time (see `create_issue`'s field mapping). Only non-area labels use `add_label`. When `area_field: labels`, area-derived labels are indistinguishable from any other label and use this operation normally.

---

### `link_sub_issue`

Attach a child issue to a parent. Branches on `jira.parent_link_style`:

- **`native`** (modern Cloud, recommended) — `editJiraIssue({cloudId, issueIdOrKey: <child_ref>, fields: {parent: {key: <parent_ref>}}})`. Works for any issue-type pair: Epic → Story, Story → Sub-task, etc.
- **`epic_link`** (classic) — `editJiraIssue({cloudId, issueIdOrKey: <child_ref>, fields: {customfield_10014: <parent_ref>}})`. Only meaningful for Epic → Story; Sub-tasks always use `parent.key` regardless of toggle. The `jira.epic_link_field` config field overrides the default `customfield_10014` for projects that use a non-standard Epic Link customfield id.

---

### `list_open_issues`

Filter open issues by type or label.

```
searchJiraIssuesUsingJql({
  cloudId: <jira.cloud_id>,
  jql: 'project = "<jira.project>" AND statusCategory != Done [AND issuetype = "<...>"] [AND labels = "<...>"]'
})
```

**Filter assembly:**
- `type` filter → append ` AND issuetype = "<jira.issue_types.<type>>"`
- `label` filter → append ` AND labels = "<label>"`

Returns a list of issue keys + summaries + statuses; the backend module translates the MCP response to `[{ref, title, status}]` matching the contract output shape.

---

### `list_child_issues`

List the direct children of a parent issue (open **and** closed).

```
searchJiraIssuesUsingJql({
  cloudId: <jira.cloud_id>,
  jql: 'parent = "<parent_ref>" ORDER BY key ASC'
})
```

**Field mapping:** `parent_ref` → the JQL `parent = "<ref>"` clause. Note there is deliberately **no** `statusCategory != Done` filter — unlike `list_open_issues`, this op returns closed children too, because adoption needs them to render `[x] … — closed` mirror lines. Translate each returned issue to `{ref: key, title: summary, status: status.name}`.

**Pagination:** `searchJiraIssuesUsingJql` pages its results (`nextPageToken` / `pageInfo.hasNextPage`). Follow the token until exhausted — a truncated page silently drops children from the adopted `## Children` mirror. Request only the fields you need (`["summary", "status"]`) so a many-child epic's descriptions don't blow the response size.

**Search-index lag (eventual consistency):** `searchJiraIssuesUsingJql` reads Jira's **search index**, which is *eventually* consistent — a child created or re-parented seconds earlier can be absent from the FIRST query even though it already exists. This is distinct from pagination: a child can be missing even when `pageInfo.hasNextPage` is `false`. Adoption is exactly when this bites (you query an epic's children right after filing them), so when children were just filed, re-query until the child count is stable, and/or cross-check membership via `getJiraIssue(child).fields.parent` — `getJiraIssue` is strongly consistent, while the JQL search index is not.

**Hierarchy ceiling (invariant 6):** the JQL `parent` field resolves the unified parent linkage Jira Cloud maintains down to its three-level cap (Epic → Story/Task → Sub-task). On `jira.parent_link_style: native` this returns a node's direct children at every level the native hierarchy reaches; nesting deeper than the cap is body-mirror-only and is neither returned nor required here. On classic `jira.parent_link_style: epic_link` projects, where Epic → Story linkage lives in the Epic Link customfield rather than `parent`, fall back to `'"Epic Link" = <parent_ref>'` (or the configured `jira.epic_link_field`).

---

### `view_issue`

Read the full state of an issue.

```
getJiraIssue({cloudId, issueIdOrKey: <ref>})
```

**Field unwrapping (MCP response → contract output):**
- `key` → `ref`
- `fields.summary` → `title`
- `fields.description` → `body` (ADF-translated to markdown by the MCP)
- `fields.status.name` → `status`
- `fields.labels[]` → `labels`
- `fields.parent?.key` → `parent` (present only for sub-issues / children)

---

### `edit_body`

Replace the body of an existing issue.

```
# Read current description first (cross-backend invariant #2)
current = getJiraIssue({cloudId, issueIdOrKey: <ref>}).fields.description

# Modify in memory, then write back
editJiraIssue({
  cloudId,
  issueIdOrKey: <ref>,
  fields: {description: <new_markdown>}
})
```

**Destructive whole-body replace.** The `description` field is overwritten in one call; there is no append-only API on the MCP. Read-modify-write is the canonical pattern: `getJiraIssue` to fetch current description → modify in memory → `editJiraIssue` to write the full body back. Same shape as GitHub's `gh issue view --json body` → modify → `gh issue edit --body-file`. Cross-backend invariant #2 documented once across both backends.

---

### `close_issue`

Mark an issue resolved by transitioning to the project's done state.

```
# Resolve the workflow-scoped transition id (ids differ per workflow — Story/Bug vs Epic)
transitions = getTransitionsForJiraIssue({cloudId, issueIdOrKey: <ref>})
id = <the transition whose name matches jira.done_transition>

transitionJiraIssue({cloudId, issueIdOrKey: <ref>, transition: {id: <id>}})

# Reason, if any, is a SEPARATE call (transitionJiraIssue has no comment param):
addCommentToJiraIssue({cloudId, issueIdOrKey: <ref>, commentBody: <reason>})
```

**Reason mapping:** `done_transition` is resolved by NAME to a workflow-scoped transition id at runtime via `getTransitionsForJiraIssue` (never hardcode the numeric id — ids are workflow-scoped, not global), then applied as `transition: {id}`. Any reason string is a SEPARATE `addCommentToJiraIssue({commentBody: <reason>})` call — `transitionJiraIssue` has no `comment` param.
- `completed` → transition via `jira.done_transition` (default `Done`); no comment needed
- `not_planned` → transition via `"Won't Do"` if that transition exists in the project workflow (resolve its id the same way); otherwise fall back to `done_transition` and post the reason via `addCommentToJiraIssue({commentBody})`
- `duplicate` → no native equivalent; transition via the project's `done_transition` and reference the duplicate's ref via `addCommentToJiraIssue({commentBody})`

`done_transition` defaults to `Done` but is overridable per consumer via `.claude/issue-tracker.yaml`. Different Jira projects use different transition names for "this issue is finished" (`Done`, `Closed`, `Resolved`, etc.), and the plugin cannot enumerate them all — consumers set the value that matches their workflow.

---

## Cross-backend invariants — how Jira satisfies them

1. **Body format is markdown** — the Atlassian Remote MCP's `createJiraIssue` and `editJiraIssue` tools accept markdown `description` strings and translate to ADF (Atlassian Document Format) internally. The plugin NEVER emits or parses ADF; `getJiraIssue` returns ADF that the MCP translates back to markdown for the plugin. Translation is lossless for the agent-prompt body shapes the plugin uses (headings, lists, code fences, tables, links, bold/italic), with one **bullet normalization to be aware of: a leading `-` unordered-list bullet is rewritten to `*` on the markdown→ADF→markdown round-trip** (e.g. a Status-block line written `- **Phase:** …` reads back as `* **Phase:** …`; the bold labels and values are byte-identical — only the bullet glyph flips). Task-list lines (`- [ ]` / `- [x]`) are **exempt** and stay `-`. This is why `/resume-initiative` matches Status-block lines on the bold field label rather than a literal `- ` bullet (see `skills/initiative-tracking/SKILL.md` "Status block — exact field spec"). If a future Atlassian Remote MCP version stops doing this translation, the plugin would need an ADF library — that would be a backward-incompatible plugin change, worth a major version bump. Today this constraint is on Atlassian, not the plugin.
2. **Whole-body edits are destructive** — `editJiraIssue` replaces the `fields.description` value in one call; there is no append-only API. Plugin pattern: `getJiraIssue` → modify in memory → `editJiraIssue`. Same shape as GitHub's `gh issue view --json body` → modify → `gh issue edit --body-file`. The Status-block-update path in `initiative-tracking` uses exactly this read-modify-write shape on both backends.
3. **Sub-issue linkage** — Jira Cloud's modern unified `parent` field (set via `editJiraIssue` on the child) is the recommended path. The classic Epic Link customfield (`customfield_10014` by convention) is a per-project fallback for older Jira projects that pre-date the unified parent field. Branched by `jira.parent_link_style` in `.claude/issue-tracker.yaml` — `native` (recommended) vs `epic_link` (classic compatibility).
4. **Issue refs are opaque** — Jira refs are `<PROJECT>-<N>` (e.g. `TRADE-42`). Skills treat refs as opaque strings; only this backend module knows the syntax. The plugin's `commands/resume-initiative.md` accepts both `#N` (GitHub) and `<PROJECT>-<N>` (Jira) in the Status block's `Next up:` line per `skills/initiative-tracking/SKILL.md`.
5. **`/tracker-doctor` reachability** — `view_issue({ref: "<jira.project>-1"})` (the default smoke ref; `--smoke-issue <ref>` overrides) dispatches to `getJiraIssue`. PASS if the call returns a structured response; PASS-WITH-NOTE on 404 (project reachable but no `<PROJECT>-1` filed yet — common in greenfield projects); FAIL on 401 / 403 (auth wrong, or `cloud_id` doesn't match `site`).
6. **Initiative nesting** — Jira's standard issue hierarchy spans **three levels**: Epic → Story/Task → Sub-task, and a Sub-task has no children of its own. So when `initiative-tracking` nests a "sub-epic" under a parent epic, the **interior nodes (root epic + sub-epics) map to issue types that can parent** — Epic at the root, Story/Task for sub-epics — linked via the unified `parent` field (`jira.parent_link_style: native`); only the **leaves** map to Sub-task. **This cap is enforcement-soft on the create/parent path: the MCP `createJiraIssue` `parent` path silently accepts a Sub-task parented directly under an Epic — the Epic → Sub-task level-skip is NOT bounced on create** (verified live, project MP, 2026-06-03: a Sub-task created with `parent` an Epic succeeded and the parent stuck). Do not rely on a rejection — the **skill**, not the tracker, must enforce the leaf-of-Epic = Story convention (see `initiative-tracking` §"Depth and backend ceilings"). Enforcement is also non-uniform: the *same-level* Story → Story `parent` link IS rejected (`"Given parent work item does not belong to appropriate hierarchy"`), while the Epic → Sub-task level-skip is not. Native linkage reaches as far as that three-level cap, after which the recursive `## Children` body mirror is the **sole** record of any deeper nesting (per cross-backend invariant 6) and `/resume-initiative` still traverses it correctly. Classic projects on `jira.parent_link_style: epic_link` can only express Epic → Story (the Epic Link field is meaningful only there); they cannot represent sub-epics natively at all and MUST use `native` parent linkage to get past one level — for `epic_link` projects, deep nesting is body-mirror-only. Teams needing native linkage beyond three levels need Jira Premium's Advanced Roadmaps custom hierarchy, which is outside this plugin's scope. `getJiraIssue` returns `fields.parent.key`, so root-vs-nested detection MAY use it here — but the portable signal remains the `## Parent epic` block in the body.

---

## PR close-on-merge convention

Jira does NOT auto-close issues from PR keywords the way GitHub does with `Fixes #N` / `Closes #N`. Auto-close on Jira typically requires the Jira-GitHub or Jira-Bitbucket DVCS integration (configured outside the plugin) — when configured, PRs with a Jira issue key in the branch name or commit message can auto-transition the issue on merge.

The plugin does NOT enforce or configure this behaviour. Consumers declare their PR-merge close convention in `.claude/issue-tracker.yaml`:

```yaml
jira:
  close_on_merge_hint: "Closes TRADE-N (DVCS-triggered auto-close)"
```

The skill prose (`feature-request`, `bug-tracking`) renders `jira.close_on_merge_hint` into PR description templates as advisory text — telling reviewers what convention the consumer uses without binding the plugin to a specific integration. If `close_on_merge_hint` is empty, no advisory line is rendered.

---

## Setup verification

`/tracker-doctor` runs these probes (in order) on its Jira branch:

1. **Atlassian MCP availability** — the agent's tool surface includes the Atlassian Remote MCP family (`createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`). If absent, `/tracker-doctor` reports the connector setup link (claude.ai → Settings → Connectors → Atlassian).
2. **`cloud_id` round-trip** — invoke `getAccessibleAtlassianResources`; confirm the configured `jira.cloud_id` appears in the returned site list and matches the configured `jira.site`. If not, `/tracker-doctor` reports the accessible cloud_ids and the operator picks the right one.
3. **`getJiraIssue({cloudId, issueIdOrKey: "<jira.project>-1"})`** — the canonical reachability probe per cross-backend invariant #5. PASS if returns; PASS-WITH-NOTE on 404 (project reachable but `<PROJECT>-1` doesn't exist); FAIL on 401 / 403 (auth wrong, or `cloud_id` doesn't match `site`).
4. **Vocabulary sanity (WARN-level):** `getJiraProjectIssueTypesMetadata({cloudId, projectIdOrKey})` returns the project's configured issue types (the visible-project list itself comes from `getVisibleJiraProjects`). WARN if any value in `jira.issue_types.*` (the consumer's mappings for the five plugin type keys — `bug`, `feature`, `epic`, `sub`, `followup` — to their Jira issue type names, e.g. `Bug`, `Story`, `Epic`, `Sub-task`, `Task`) is missing from the project's issue type list. No FAIL — vocabulary mismatches are operator setup tasks surfaced informationally; the plugin still works without them (the next `create_issue` will fail noisily at the MCP layer, with a more actionable error message than the plugin could compose preemptively).

## In-progress transition (optional)

**Optional, Jira-only. Not a contract operation** — see [`_interface.md`](_interface.md)
"Optional backend-specific capabilities". When the consumer's
`.claude/issue-tracker.yaml` sets `jira.in_progress_transition`, a driver that
starts work on an issue (`/work-issue` Step 3 today; `/resume-initiative --start`
once parity follow-up #88 lands) marks the issue in progress by firing the named
workflow transition:

```
# Resolve the workflow-scoped transition id at runtime (same rule as close_issue --
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

## GitHub Projects v2 board (optional) -- n/a for Jira

Projects-board population is a GitHub-specific affordance (see
`backends/github.md` "GitHub Projects v2 board (optional)" and `_interface.md`
"Optional backend-specific capabilities"). It is **not applicable to Jira** -- use
Jira's own boards. No Jira behaviour change; the `github.project` config key is
ignored when `backend: jira`. The Jira-side in-progress affordance is the
workflow transition above ("In-progress transition (optional)"), not a board.
