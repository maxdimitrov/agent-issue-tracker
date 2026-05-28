# Write `backends/jira.md` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `backends/jira.md` from scratch — the Jira Cloud dispatch module for the agent-issue-tracker plugin. Implements all seven operations from the contract in `backends/_interface.md` via the Atlassian Remote MCP tool family; satisfies the five cross-backend invariants; mirrors `backends/github.md`'s section structure; matches `commands/tracker-doctor.md`'s Jira-branch setup-verification block on the literal tool names.

**Architecture:** Single new markdown file under `backends/` plus a one-line `CHANGELOG.md` append. No skills, no commands, no templates — Phase 1 (#9) landed the contract this module implements, Phase 2 (#11-#15) landed the skills that dispatch through it, Phase 3 (#20, #22, #23) landed the slash commands that reference it. The module is the last Phase 3 deliverable; everything it interfaces with already exists.

**Tech Stack:** Markdown only. No code, no tests, no build step. The prose tells the agent which MCP tool to call and what input shape; the agent uses the actual MCP at runtime.

**Spec:** `docs/superpowers/specs/2026-05-28-write-backends-jira-module-design.md` (committed pre-Task-1 on this branch alongside this plan).

**Source:** None — write-from-scratch. Shape precedent: `backends/github.md` on `main`. Contract: `backends/_interface.md`. Field vocabulary: `examples/issue-tracker.yaml.example` lines 66-108. Setup-verification consumer: `commands/tracker-doctor.md` Jira branch (lines 56-63 + lines 87-92).

**Issue:** `agent-issue-tracker#24`. **Parent epic:** `maxdimitrov/trading-bot#153` (Phase 3 — this is the third and final Phase 3 sibling).

---

## Pre-task setup (controller, not a subagent task)

Before dispatching Task 1, the controller MUST:

1. Verify CWD is the worktree `.claude/worktrees/write-backends-jira-module/`.
2. Verify the branch is `feat/backends-jira-module`.
3. Verify the spec is committed: `git log --oneline -3` should show the design spec + this plan landing on the branch as the first two commits ahead of `main`.
4. Run `ToolSearch` against keywords `atlassian jira create issue` and capture whether the Atlassian Remote MCP is in the agent's tool surface. The expectation in this session is **no Atlassian tools** (verified at session start); pass that determination into Task 1's prompt so the subagent uses the conventional names and marks them as "conventional pending Phase 6 live smoke" in the CHANGELOG entry.

No source-bytes retrieval step — this is write-from-scratch, not a port. The subagent receives spec sections inline in the dispatch prompt; it should not have to read the spec end-to-end.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `backends/jira.md` | NEW (~200-300 lines) | The dispatch module — markdown, six top-level sections matching `backends/github.md`, seven operation blocks, five cross-backend invariant paragraphs, setup-verification block |
| `CHANGELOG.md` | MODIFY (+1 line) | Append a Phase 3 (#24) entry under `[Unreleased]` → `Added` |

---

## Task 1: Author `backends/jira.md`

**Files:**
- Create: `backends/jira.md`
- Reference (read-only): `backends/github.md` — the precedent. Read end-to-end so the section structure, prose tone, table shape, gotcha-paragraph convention, and "Cross-backend invariants" + "Setup verification" section placement match exactly.
- Reference (read-only, for the contract): `backends/_interface.md` (seven operations + five invariants — every operation block must match the contract's input/output shape; every invariant must be addressed numbered 1-5).
- Reference (read-only, for the field vocabulary): `examples/issue-tracker.yaml.example` lines 66-108 (the `jira:` block — every config field this module reads).
- Reference (read-only, for setup-verification consistency): `commands/tracker-doctor.md` Phase 2 Jira-branch (lines 56-63) + Phase 3 Jira-branch (lines 87-92). The tool names used here must match.

**Subagent model recommendation:** `haiku` — the work is rule-driven authoring against an explicit spec. No design decisions delegated.

**Subagent context to include in prompt verbatim:** §3 Non-goals, §4 Decisions table, §5 The seven operations, §6 The five cross-backend invariants, §7 Setup verification, §8 PR close-on-merge, §10 Invariants, §14 Notes (especially the "Atlassian MCP not in tool surface" caveat).

### Step 1.1: Read the precedent

Read `backends/github.md` end-to-end. It's ~155 lines. Note especially:
- The intro paragraph (one sentence + a cite to `_interface.md`)
- The `## Auth` section (terse — three short paragraphs)
- The `## Reference: gh issue and gh api commands` 3-column table
- The `## Operations` section with seven `### <op>` subsections, each containing a fenced shell block + a "Field mapping" bullet list (where the operation has nontrivial mapping)
- The explicit-paragraph gotcha callout in `link_sub_issue` (the `-F` vs `-f` typed-int gotcha)
- The `## Cross-backend invariants — how GitHub satisfies them` section with five numbered paragraphs
- The `## PR close-on-merge convention` section
- The `## Setup verification` section listing the literal probe commands `/tracker-doctor` runs

The Jira backend mirrors this exactly. Same headings, same section order, same paragraph density.

### Step 1.2: Author the new file — section by section

Write `backends/jira.md` from scratch with this exact structure:

1. **Title line:** `# Jira Backend`

2. **Intro paragraph** (1-2 sentences). Name the Atlassian Remote MCP as the dispatch surface; cite `_interface.md` as the contract; name `backends/github.md` as the sibling implementation.

3. **`## Auth`** — 2-3 paragraphs:
   - Atlassian Remote MCP is a connector enabled per-user at claude.ai → Settings → Connectors → Atlassian.
   - No per-project credentials in the plugin or `.claude/issue-tracker.yaml`.
   - MCP handles OAuth refresh, scopes, rate limiting transparently.
   - If `/tracker-doctor`'s Phase 2 step 1 reports the family missing, the operator enables the connector and re-invokes.

4. **`## Reference: Atlassian Remote MCP tool family`** — 3-column table (Operation | MCP tool | Notes). Rows for create, add label, sub-issue link, list open, view, edit body, close — same order as `backends/github.md`. The Notes column carries the input parameter list + key gotchas. Add a one-line caveat below the table: "Tool names below are CONVENTIONAL — see CHANGELOG for the verification status."

5. **`## Operations`** — seven `### <op>` subsections in this exact order:
   - `### create_issue`
   - `### add_label`
   - `### link_sub_issue`
   - `### list_open_issues`
   - `### view_issue`
   - `### edit_body`
   - `### close_issue`

   Each operation block follows this template (filled in from spec §5):
   ```
   ### <op>

   <Brief 1-sentence purpose statement>

   <Fenced block showing the MCP call shape>

   **Field mapping:**
   - `<contract input>` → `<Jira field>`
   ...

   <Optional explicit-paragraph gotcha or per-config indirection note>
   ```

   Per-operation specifics from spec §5.1-5.7:
   - **5.1 `create_issue`**: tool `createJiraIssue`, full input shape, mapping table including `area_field` indirection (components vs labels), `parent` note about Cloud's unified parent vs `link_sub_issue` post-create for Epic Link.
   - **5.2 `add_label`**: tool `editJiraIssue` setting `fields.labels`. **Explicit gotcha paragraph** about read-modify-write — `editJiraIssue` replaces the entire array, plugin must `getJiraIssue` first, append in memory, write back the full array. Cite the parallel to `backends/github.md`'s `-F` vs `-f` gotcha.
   - **5.3 `link_sub_issue`**: branch on `jira.parent_link_style`. Nested bullets for native (modern Cloud `parent.key`) vs epic_link (classic `customfield_10014`); `jira.epic_link_field` overrides default `customfield_10014`.
   - **5.4 `list_open_issues`**: tool `searchJiraIssuesUsingJql`. Document the base JQL and how `type` and `label` filters append clauses.
   - **5.5 `view_issue`**: tool `getJiraIssue`. Document the field unwrapping from `fields.summary` / `fields.description` / `fields.status.name` / etc. to the contract output shape.
   - **5.6 `edit_body`**: tool `editJiraIssue({fields: {description: ...}})`. **Destructive**. Document the read-modify-write pattern; cite cross-backend invariant #2.
   - **5.7 `close_issue`**: tool `transitionJiraIssue` with `transitionName = jira.done_transition`. Reason mapping: `completed` → done_transition (default `Done`); `not_planned` → `"Won't Do"` if exists, else comment; `duplicate` → comment-only.

6. **`## Cross-backend invariants — how Jira satisfies them`** — five numbered paragraphs, content from spec §6:
   1. Body format is markdown — ADF translation is the MCP's responsibility; plugin never touches ADF.
   2. Whole-body edits are destructive — `editJiraIssue` replaces `fields.description` in one call; read-modify-write is canonical.
   3. Sub-issue linkage — modern unified `parent.key` is recommended; `customfield_10014` is fallback; branched by `parent_link_style`.
   4. Issue refs are opaque — `<PROJECT>-<N>` syntax; only this module parses; `commands/resume-initiative.md` accepts both `#N` and `<PROJECT>-<N>` per `skills/initiative-tracking/SKILL.md`.
   5. `/tracker-doctor` reachability — `view_issue` against `<jira.project>-1` (or `--smoke-issue` override); PASS / PASS-WITH-NOTE (404) / FAIL (401/403).

7. **`## PR close-on-merge convention`** — content from spec §8. Three paragraphs:
   - Jira does NOT auto-close from PR keywords like GitHub's `Fixes #N` / `Closes #N`.
   - Auto-close typically requires the Jira-GitHub or Jira-Bitbucket DVCS integration (configured outside the plugin).
   - Consumers declare convention in `.claude/issue-tracker.yaml` via `jira.close_on_merge_hint` (advisory text only; plugin does NOT enforce); empty hint → no advisory line rendered.

8. **`## Setup verification`** — content from spec §7. Numbered 1-4, matching `commands/tracker-doctor.md`'s Jira branch verbatim on tool names:
   1. Atlassian MCP availability — agent's tool surface includes `createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`. Setup link if missing.
   2. `cloud_id` round-trip — `getAccessibleAtlassianResources` confirms `jira.cloud_id` matches `jira.site`.
   3. `getJiraIssue({issueIdOrKey: "<jira.project>-1"})` — canonical reachability probe per invariant #5.
   4. Vocabulary sanity (WARN-level) — `getJiraProjectMetadata` returns issue types + components; warn for any `jira.issue_types.*` missing from project.

### Step 1.3: Tool-name verification status (must include in the file)

The Atlassian Remote MCP is **not available in the authoring session's tool surface**. Tool names used are conventional per parent design spec §5.5. Include a one-line caveat under the `## Reference: Atlassian Remote MCP tool family` table:

> Tool names listed are conventional per the parent design spec §5.5. The Atlassian Remote MCP was not available in the authoring session for direct verification; the CHANGELOG entry for this PR marks the names as "conventional pending Phase 6 live smoke." Future sessions with the connector available may run `ToolSearch` against `atlassian jira` and promote any drifted name in a follow-up commit.

### Step 1.4: Style guidance

- **Prose tone:** terse, table-heavy, gotcha-callouts-via-explicit-paragraph. Match `backends/github.md`.
- **Fenced blocks:** show MCP call shapes as inline pseudo-syntax (e.g. `createJiraIssue({cloudId, projectKey, summary, ...})`). No bash heredocs.
- **No emojis.**
- **No `gh `** shell-out commands. This is the Jira backend.

### Step 1.5: Self-verify against the static acceptance gates

Run every gate AFTER writing, BEFORE committing. EVERY line must print `OK:`; if any prints `FAIL:`, fix and re-run:

```bash
test -f backends/jira.md && echo "OK: file" || echo "FAIL: file"

grep -F "maxdimitrov/trading-bot" backends/jira.md && echo "FAIL: trading-bot leak" || echo "OK: no leak"
grep -nE "^gh " backends/jira.md && echo "FAIL: bare gh" || echo "OK: no gh"

# Seven contract operations as ### headings
for op in create_issue add_label link_sub_issue list_open_issues view_issue edit_body close_issue; do
  grep -qE "^### .*$op" backends/jira.md && echo "OK: ### $op" || echo "FAIL: ### $op"
done

# Seven MCP tool names
for tool in createJiraIssue editJiraIssue getJiraIssue searchJiraIssuesUsingJql transitionJiraIssue getAccessibleAtlassianResources getJiraProjectMetadata; do
  grep -q "$tool" backends/jira.md && echo "OK: $tool" || echo "FAIL: $tool"
done

# Cross-backend invariants section
grep -qE "^## Cross-backend invariants" backends/jira.md && echo "OK: invariants section" || echo "FAIL: invariants section"

# Key concepts
grep -qiE "ADF|atlassian document format" backends/jira.md && echo "OK: ADF" || echo "FAIL: ADF"
grep -qE "parent_link_style" backends/jira.md && echo "OK: parent_link_style" || echo "FAIL: parent_link_style"
grep -qE "customfield_10014" backends/jira.md && echo "OK: customfield_10014" || echo "FAIL: customfield_10014"
grep -qE "done_transition" backends/jira.md && echo "OK: done_transition" || echo "FAIL: done_transition"
grep -qE "area_field" backends/jira.md && echo "OK: area_field" || echo "FAIL: area_field"

# PR auto-close NOT enforced (one of: does not / do not / doesn't / never)
grep -qiE "(does not|do not|doesn't|never).*(auto-close|enforce|configure)" backends/jira.md && echo "OK: no-auto-close stated" || echo "FAIL: no-auto-close stated"

# Setup verification + key probe tool names from /tracker-doctor's Jira branch
grep -qE "^## Setup verification" backends/jira.md && echo "OK: setup verification section" || echo "FAIL: setup verification section"

# Top-level sections in correct order (six sections per the precedent)
for section in "^## Auth" "^## Reference" "^## Operations" "^## Cross-backend invariants" "^## PR close-on-merge convention" "^## Setup verification"; do
  grep -qE "$section" backends/jira.md && echo "OK: $section" || echo "FAIL: $section"
done

# Conventional-pending caveat present
grep -qiE "conventional|pending.*verification|verification status" backends/jira.md && echo "OK: verification caveat" || echo "FAIL: verification caveat"
```

If any gate fails, fix and re-run before committing.

### Step 1.6: Commit

After ALL gates pass:

```bash
git add backends/jira.md
git commit -m "$(cat <<'EOF'
feat(backends): write jira.md Atlassian Remote MCP backend (#24)

The second backend implementing the seven-operation contract from
backends/_interface.md, dispatching via the Atlassian Remote MCP
tool family. Mirrors backends/github.md's section structure:
Auth, Reference table, Operations, Cross-backend invariants, PR
close-on-merge convention, Setup verification.

Seven operations dispatch to seven MCP tools: createJiraIssue,
editJiraIssue (used by add_label, link_sub_issue, edit_body),
getJiraIssue, searchJiraIssuesUsingJql, transitionJiraIssue, plus
the two setup-verification tools getAccessibleAtlassianResources
and getJiraProjectMetadata.

Three Jira-specific gotchas documented inline as explicit
paragraphs: read-modify-write for add_label (editJiraIssue
replaces the full labels array); parent_link_style toggle in
link_sub_issue (modern Cloud parent.key vs classic
customfield_10014); done_transition workflow indirection in
close_issue (default "Done", consumer-overridable, plus reason
mapping for completed / not_planned / duplicate).

ADF translation acknowledged as the MCP's responsibility under
cross-backend invariant #1 — the plugin never touches ADF.

Setup-verification block matches commands/tracker-doctor.md's
Jira branch verbatim on tool names: MCP availability →
getAccessibleAtlassianResources cloud_id round-trip →
getJiraIssue reachability → getJiraProjectMetadata vocabulary
sanity.

Tool names are CONVENTIONAL pending Phase 6 live-Jira smoke —
the Atlassian Remote MCP was not in the authoring session's tool
surface (verified via ToolSearch). A follow-up commit can
promote names to "verified" once a session with the connector
runs the smoke tests.

Spec: docs/superpowers/specs/2026-05-28-write-backends-jira-module-design.md.
Parent epic: maxdimitrov/trading-bot#153 (Phase 3 — last sibling).
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'
git show --stat HEAD     # must show only backends/jira.md changed
```

---

## Task 2: CHANGELOG.md update + final static verify

**Files:**
- Modify: `CHANGELOG.md` (append one bullet under `[Unreleased]` → `Added`)

**Subagent model recommendation:** `haiku` — single-line append + grep verification.

### Step 2.1: Read the current CHANGELOG.md

The CHANGELOG follows Keep-a-Changelog format. The most-recent entries under `[Unreleased]` → `Added`:
- Phase 3 (#22): `commands/tracker-init.md`
- Phase 3 (#23): `commands/tracker-doctor.md`
- Phase 2 (#15): `skills/skill-currency/SKILL.md`

The new bullet appends after the most-recent (#15) line.

### Step 2.2: Append the Phase 3 (#24) entry

Use the Edit tool. The `old_string` is the last existing `Added` bullet (the #15 line — find it via Read first). The `new_string` is that same bullet PLUS a newline PLUS the new bullet:

```
- Phase 3 (#24): `backends/jira.md` — Atlassian Remote MCP dispatch for all seven contract operations from `backends/_interface.md`. Second backend implementation completing the v1 backend matrix. Seven MCP tools used: `createJiraIssue`, `editJiraIssue` (drives `add_label`, `link_sub_issue`, `edit_body`), `getJiraIssue`, `searchJiraIssuesUsingJql`, `transitionJiraIssue`, plus `getAccessibleAtlassianResources` + `getJiraProjectMetadata` for `/tracker-doctor`'s Jira-branch setup verification. Three Jira-specific gotchas documented: read-modify-write for `add_label` (full-array replace), `parent_link_style` toggle (`native` Cloud `parent.key` vs `epic_link` classic `customfield_10014`), `done_transition` workflow indirection in `close_issue` with reason mapping. ADF translation attributed to the MCP under cross-backend invariant #1 — plugin never touches ADF. Tool names are CONVENTIONAL pending Phase 6 live-Jira smoke (Atlassian Remote MCP was not in the authoring session's tool surface; verified via `ToolSearch` at session start).
```

Use the em-dash `—` (U+2014) for the bullet separator — NOT ASCII `--`. Pre-PR-19 and pre-PR-25 history shows this is a repeatable byte-regression hazard; the controller will run a post-Edit grep to confirm the bullet is using `—`.

### Step 2.3: Run the full static acceptance checklist

EVERY line must print `OK:`; if any prints `FAIL:`, do NOT commit:

```bash
# Task 1 regression gates (no breakage)
test -f backends/jira.md && echo "OK: file" || echo "FAIL: file"
grep -F "maxdimitrov/trading-bot" backends/jira.md && echo "FAIL: trading-bot leak" || echo "OK: no leak"
grep -nE "^gh " backends/jira.md && echo "FAIL: bare gh" || echo "OK: no gh"

for op in create_issue add_label link_sub_issue list_open_issues view_issue edit_body close_issue; do
  grep -qE "^### .*$op" backends/jira.md && echo "OK: ### $op" || echo "FAIL: ### $op"
done

for tool in createJiraIssue editJiraIssue getJiraIssue searchJiraIssuesUsingJql transitionJiraIssue getAccessibleAtlassianResources getJiraProjectMetadata; do
  grep -q "$tool" backends/jira.md && echo "OK: $tool" || echo "FAIL: $tool"
done

grep -qE "^## Cross-backend invariants" backends/jira.md && echo "OK: invariants section" || echo "FAIL: invariants section"
grep -qiE "ADF|atlassian document format" backends/jira.md && echo "OK: ADF" || echo "FAIL: ADF"
grep -qE "parent_link_style" backends/jira.md && echo "OK: parent_link_style" || echo "FAIL: parent_link_style"
grep -qE "customfield_10014" backends/jira.md && echo "OK: customfield_10014" || echo "FAIL: customfield_10014"
grep -qE "done_transition" backends/jira.md && echo "OK: done_transition" || echo "FAIL: done_transition"
grep -qE "area_field" backends/jira.md && echo "OK: area_field" || echo "FAIL: area_field"
grep -qiE "(does not|do not|doesn't|never).*(auto-close|enforce|configure)" backends/jira.md && echo "OK: no-auto-close stated" || echo "FAIL: no-auto-close stated"
grep -qE "^## Setup verification" backends/jira.md && echo "OK: setup verification section" || echo "FAIL: setup verification section"
grep -qiE "conventional|pending.*verification|verification status" backends/jira.md && echo "OK: verification caveat" || echo "FAIL: verification caveat"

# CHANGELOG entry
grep -qE "Phase 3 \(#24\):.*backends/jira" CHANGELOG.md && echo "OK: CHANGELOG entry" || echo "FAIL: CHANGELOG entry"

# CHANGELOG bullet uses em-dash (catch the byte regression from PR #25)
NEW_BULLET=$(grep -F "Phase 3 (#24)" CHANGELOG.md)
echo "$NEW_BULLET" | grep -P "—" > /dev/null && echo "OK: em-dash in CHANGELOG bullet" || echo "FAIL: em-dash missing — likely downgraded to ASCII --"
```

### Step 2.4: Commit

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore(changelog): note Phase 3 #24 (backends/jira.md)

Append a Phase 3 entry to [Unreleased] → Added for the
backends/jira.md Atlassian Remote MCP backend landed in the
previous commit. Marks tool names as "conventional pending Phase 6
live-Jira smoke" since the authoring session did not have the
Atlassian connector in its tool surface.
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'
git show --stat HEAD     # must show only CHANGELOG.md changed
git log --oneline -5     # 4 commits ahead of main: spec, plan, backend, changelog
```

---

## Post-task: open the PR

After Task 2 commits cleanly:

1. Push the branch:
   ```bash
   git push -u origin feat/backends-jira-module
   ```

2. Create the PR against `maxdimitrov/agent-issue-tracker` `main`. Title: `Phase 3 (#24): write backends/jira.md (Atlassian Remote MCP)`. Body matches the shape of PR #25's body (Summary, Files, Decisions settled in brainstorm, Reviewer process, Test plan, `Closes #24`, `Parent epic`).

3. Wait for merge. The post-merge epic #153 update is controller's concern (the user's pipeline step 7), NOT a subagent task.

---

## Self-review (controller, after writing this plan)

**Spec coverage:**
- §1 Problem — context only; no implementation surface.
- §2 Goal — covered by Task 1 Step 1.2 (output file structure).
- §3 Non-goals — out-of-scope items NOT addressed (correct).
- §4 Decisions table — all 13 decisions reflected in Task 1 Step 1.2 (structure) + Step 1.3 (verification caveat) + Step 1.4 (style).
- §5 Seven operations — Task 1 Step 1.2 item 5 with per-operation specifics 5.1-5.7.
- §6 Five cross-backend invariants — Task 1 Step 1.2 item 6.
- §7 Setup verification — Task 1 Step 1.2 item 8.
- §8 PR close-on-merge — Task 1 Step 1.2 item 7.
- §9 Failure modes — implicit in operation blocks + setup verification.
- §10 Invariants — Task 1 grep gates (Step 1.5 + Step 2.3).
- §11 Cross-references — informational; no implementation surface.
- §12 Acceptance — Step 1.5 + Step 2.3 grep gates.
- §13 Verification — Step 1.5 + Step 2.3.
- §14 Notes — Task 1 Step 1.3 (verification caveat) + Step 1.6 commit message body.

**Placeholder scan:** none — every section has explicit content rules, every grep is fully written, every commit message is in HEREDOC form.

**Type consistency:** N/A — markdown-only. The seven contract operation names and seven MCP tool names appear consistently across spec, this plan, and Step 1.5 / Step 2.3 grep gates.

**No drift:** Task 1 commit message matches the spec wording; Task 2 commit message matches the appended CHANGELOG line; both reference issue #24 and parent epic #153.

---

## Execution mode

Per `~/.claude/CLAUDE.md` "Plan execution" section, execution is always via `superpowers:subagent-driven-development`. Fresh subagent per task, two-stage spec-then-quality review.

For this plan: two subagent dispatches (Task 1 = haiku, Task 2 = haiku), then one quality-review subagent (sonnet, cold read of `backends/jira.md` against the spec). The controller verifies `git log -1 --format='%H %s'` and `git show --stat HEAD` after each subagent returns; reads the produced `backends/jira.md` end-to-end before declaring Task 1 done.

The sonnet quality reviewer checks: spec compliance per phase, issue #24 acceptance bullets, spec §10 invariants, prose style + cold-read clarity, cross-reference accuracy against `backends/github.md` and `commands/tracker-doctor.md`, byte-level audit on the verbatim setup-verification probe sequence (must match `commands/tracker-doctor.md` lines 56-63 + 87-92 on tool names).
