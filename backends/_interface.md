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

1. **Body format is markdown.** GitHub renders markdown bodies natively; Jira accepts markdown via the Atlassian Remote MCP's ADF-translation layer. Skills produce markdown only — never ADF, never wiki markup, never HTML.

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
