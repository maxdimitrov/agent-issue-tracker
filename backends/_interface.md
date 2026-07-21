# Backend Operation Contract

Every backend module in `backends/<name>.md` implements this contract. The skill prose dispatches through these operations; the backend module documents the literal CLI / MCP calls for the specific tracker.

The contract is THE source of truth. If a backend module diverges from this contract — different operation name, different input shape, different return shape — the divergence is a bug in the backend module, not the contract.

## Operations

Eight operations. Inputs are tracker-agnostic field names; the backend module translates them into tracker-specific fields (label vs component vs custom field, etc.).

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

**Nesting:** the operation is depth-agnostic — it takes any two opaque refs and never inspects their type. The same one-hop call composes transitively, so an issue that is itself a child (a "sub-epic" in `initiative-tracking`) can be the `parent_ref` of its own children. How deep native linkage actually goes is a per-backend capability (see invariant 6); the call signature does not change with depth.

---

### `list_open_issues`

**Purpose:** Filter open issues by type or label.

**Inputs:**
- `type` (optional) — filter to one of `bug | feature | followup | epic | sub`
- `label` (optional) — filter to a specific label

**Output:** list of `{ref, title, status}` entries.

---

### `list_child_issues`

**Purpose:** List the children of a parent issue — the read-inverse of `link_sub_issue`. Used by `initiative-tracking` to adopt a pre-existing epic (one whose body has no `## Children` mirror yet, or a stale one) and to reconcile the mirror against the tracker's actual parent-child linkage. This is the operation that lets the skill answer "what are this epic's children?" from the tracker instead of trusting the epic body's prose.

**Inputs:**
- `parent_ref` — the parent issue ref

**Output:** list of `{ref, title, status}` entries — the parent's **direct** children only. Includes **both open and closed** children, which is the deliberate difference from `list_open_issues`: adoption needs the closed ones to render them in the `## Children` mirror as `[x] … — closed`. Depth is the skill's concern, not this op's — `initiative-tracking` recurses over each node's `## Children` mirror per invariant 6, calling this op once per node.

**Nesting (invariant 6):** native parent queries reach exactly as far as the backend's linkage ceiling (e.g. Jira's three-level Epic → Story/Task → Sub-task cap). Below that ceiling there are no *native* children to enumerate by construction — deeper nesting lives in the body mirror alone — so this op is reliable precisely where adoption needs it: reconciling one node's direct children at a time. A backend whose native ceiling is shallower than a given tree is NOT in violation; the `## Children` body mirror remains the depth-of-record.

---

### `view_issue`

**Purpose:** Read the full state of an issue.

**Inputs:**
- `ref` — issue ref

**Output:** `{ref, title, body, labels[], status, parent?}`. `parent` is present only when the issue is a sub-issue / child, and only on backends whose native API exposes the parent on a plain issue read (GitHub's `gh issue view` does not — see `backends/github.md`). Because of that asymmetry, `initiative-tracking` does NOT rely on `parent?` to identify root vs nested epics; the cross-backend signal is the presence of a `## Parent epic` block in the `body` (a root epic has none). `parent?` is a secondary, best-effort confirmation where the backend supplies it.

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

6. **Initiative nesting lives in the body, not the native hierarchy.** `initiative-tracking` supports initiatives nested more than one level deep (an epic whose child is itself an epic — a "sub-epic" — with its own children). The depth-of-record is the recursive `## Children` task-list mirror inside each epic node's body, parsed by `/resume-initiative`. Native `link_sub_issue` linkage is best-effort *augmentation*, applied as deep as the backend's hierarchy allows and then silently capped — GitHub sub-issues nest arbitrarily; Jira Cloud's standard hierarchy stops at Epic → Story/Task → Sub-task (three levels). A backend that cannot link a deep edge natively is NOT in violation: the body mirror still expresses the full tree, so the skill and command keep working uniformly. Backend modules MUST document where their native linkage ceiling sits.

---

## Optional backend-specific capabilities

The eight operations above are the entire contract. A backend MAY document
additional, backend-specific affordances that are NOT contract operations and are
NOT required of any other backend. Such affordances live under plain `##` headings
in the backend module — never a `` ### `op` `` operation heading — so the
`backend-contract` CI op-parity check (which greps `` ### `op` `` headings) ignores
them. They are always optional for the consumer; with the relevant config key
unset, behaviour is unchanged.

The first such affordance is **GitHub Projects (v2) board population** — see
`backends/github.md` "GitHub Projects v2 board (optional)". It mirrors an
initiative's issue tree onto a GitHub Projects board as a human-facing view. It is
GitHub-only; `backends/jira.md` records it as n/a. It adds **no** contract
operation: the eight ops stay eight, and op-parity remains green.

The second is **in-progress status marking** — the "this issue is being worked"
signal a driver sets when work starts (`/work-issue` Step 3 today;
`/resume-initiative --start` via follow-up #88). It is an affordance, not a ninth
operation, because it cannot be uniformly implemented: GitHub has no native
issue-level status (its mechanism is the Projects-board Status field above), while
Jira's is a workflow transition (`jira.in_progress_transition` — see
`backends/jira.md` "In-progress transition (optional)"). With neither configured,
the fallback signal is the parent epic's Status block `Current branch` line,
written by `/work-issue`'s start-side sync; a parentless issue with nothing
configured gets no marker — a documented no-op. Every such write is best-effort —
WARN, never block.

---

## Adding a new backend

To add a new backend (GitLab, Linear, Jira Server, plain-file, etc.):

1. Create `backends/<name>.md`.
2. For each of the eight operations above, document the literal CLI command, MCP tool call, or API request that implements it. Use the same field names as the contract; translate to tracker-specific fields inside the documentation.
3. Document how the six cross-backend invariants are satisfied — including invariant 6 (where the new backend's native parent-child linkage ceiling sits, so `initiative-tracking` knows how deep native augmentation goes before the body mirror is the sole record).
4. Add a `<name>` block to the config schema in `examples/issue-tracker.yaml.example` with all required + optional fields.
5. Ship a minimal `examples/<name>-config.yaml`.
6. Update `/tracker-init` and `/tracker-doctor` to recognise `backend: <name>` as a valid choice.
7. Update `CHANGELOG.md`.

The contract itself does NOT change to accommodate a new backend. If a backend cannot satisfy the contract as written, the divergence is a backend bug, not a contract bug.
