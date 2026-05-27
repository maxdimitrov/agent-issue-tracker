# Write `/tracker-doctor` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `commands/tracker-doctor.md` from scratch — a markdown-only read-only slash command that runs three check phases (schema validation, backend reachability, vocabulary sanity) against `.claude/issue-tracker.yaml` and the configured backend. Always exits 0; emits `PASS / WARN / FAIL` per check with literal next-step commands; dispatches reachability through `view_issue` per cross-backend invariant #5.

**Architecture:** Single new markdown file under `commands/` plus a one-line `CHANGELOG.md` append. No skills, no templates, no backend modules — Phase 1 (`#9`) landed the schema this command validates against; Phase 2 (`#11-#14`) landed the skills that consume the same config; PR #21 (`#20`) landed the slash-command shape precedent; PR #25 (`#22`) landed the sibling `/tracker-init` whose YAML output is this command's input.

**Tech Stack:** Markdown only (slash-command convention), YAML frontmatter, `grep` for static acceptance gates. No code, no tests, no build step. The command's prose tells the agent to use `Read`, backend-dispatched `view_issue`, `ToolSearch`, and to invoke `gh` / Atlassian MCP probes at runtime; those are tool-level concerns, not implementation surface.

**Spec:** `docs/superpowers/specs/2026-05-27-write-tracker-doctor-command-design.md` (committed pre-Task-1 on this branch alongside this plan).

**Source:** None — write-from-scratch. The shape precedent is `commands/resume-initiative.md` and `commands/tracker-init.md` on this plugin's `main` (committed via PRs #21 and #25). The conceptual flow is parent design spec §7.2 on `maxdimitrov/trading-bot` `main`.

**Issue:** `agent-issue-tracker#23`. **Parent epic:** `maxdimitrov/trading-bot#153` (Phase 3).

---

## Pre-task setup (controller, not a subagent task)

Before dispatching Task 1, the controller MUST:

1. Verify CWD is the worktree `.claude/worktrees/feat+issue-23-tracker-doctor-validator/`.
2. Verify the branch is `feat/issue-23-tracker-doctor-validator`.
3. Verify the spec is committed: `git log --oneline -3` should show the design spec + this plan landing on the branch as the first two commits ahead of `main`.

No source-bytes retrieval step — this is write-from-scratch, not a port. The subagent receives the spec sections inline in the dispatch prompt; it does NOT have to read the spec end-to-end.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `commands/tracker-doctor.md` | NEW (~180-260 lines) | The slash command — markdown with YAML frontmatter, three-phase flow plus summary, both backend branches documented, output-format example, failure modes block, invariants section |
| `CHANGELOG.md` | MODIFY (+1 line) | Append a Phase 3 entry under `[Unreleased]` → `Added` |

---

## Task 1: Author `commands/tracker-doctor.md`

**Files:**
- Create: `commands/tracker-doctor.md`
- Reference (read-only, for the design): `docs/superpowers/specs/2026-05-27-write-tracker-doctor-command-design.md`
- Reference (read-only, for the shape precedent): `commands/resume-initiative.md`
- Reference (read-only, for the sibling shape + schema agreement): `commands/tracker-init.md`
- Reference (read-only, for the schema this command validates against): `examples/issue-tracker.yaml.example`
- Reference (read-only, for the GitHub probe shape): `backends/github.md`
- Reference (read-only, for the contract that pins `view_issue` as the reachability probe): `backends/_interface.md`

**Subagent model recommendation:** `haiku` is fine — the work is rule-driven authoring against an explicit phase-by-phase design. No design decisions delegated (those are locked in the spec).

**Subagent context to include in prompt verbatim:** the spec's §3 Non-goals, §4 Decisions table, §5 Flow phases (all three plus summary), §6 Output format example, §7 Failure modes, §8 Invariants. The subagent should NOT have to read the spec end-to-end — paste the binding sections inline.

### Step 1.1: Read the shape precedent

Read `commands/resume-initiative.md` and `commands/tracker-init.md` end-to-end. They are the existing plugin slash commands and the source of truth for:

- YAML frontmatter shape (single-line `description:`)
- Section headings (`# /command-name [args]`, `## Invocation modes`, `## What you should do`, `## Failure modes`, optional `## Conventions assumed`)
- Numbered subsection structure inside "What you should do"
- Prose tone (terse, dispatch-through-contract, name files not commands, second-person instructional)
- Code-fence conventions: YAML in ```yaml; shell command names inline in backticks; contract operations in backticks
- Verbatim text discipline (PRs #21 and #25 caught en-dash regressions; preserve any quoted output blocks character-for-character)

Do NOT read the design spec end-to-end — the dispatch prompt carries the binding sections inline.

### Step 1.2: Author the new file — section by section

Write `commands/tracker-doctor.md` from scratch, following this exact ordered structure:

1. **YAML frontmatter.** Single key:
   ```yaml
   ---
   description: Validate `.claude/issue-tracker.yaml`: schema, backend reachability, vocabulary sanity. Read-only. Always exits 0.
   ---
   ```

2. **Title line.** `# /tracker-doctor [--smoke-issue <ref>]` (note the optional `--smoke-issue` flag in the title).

3. **Overview paragraph.** Three-to-five sentences. Name the goal (read-only validator for `.claude/issue-tracker.yaml`), the three phases (schema validation → backend reachability → vocabulary sanity), the dispatch model (`view_issue` per cross-backend invariant #5 from `backends/_interface.md`), the discipline (always exits 0, mirrors `/audit-skills` / `/audit-pii`), and the sibling-pair statement (`/tracker-init` writes; `/tracker-doctor` validates).

4. **`## Invocation modes` table.** Two rows:
   | Invocation | Behaviour |
   |---|---|
   | `/tracker-doctor` | Run all three check phases against the current config. Use the default probe ref (`#1` GitHub / `<jira.project>-1` Jira). |
   | `/tracker-doctor --smoke-issue <ref>` | Run all three check phases. Override the default reachability probe ref with `<ref>` (useful when the conventional first-issue ref doesn't exist or is restricted). |

5. **`## What you should do`** — three `### Phase N — <name>` subsections plus a `### Phase 4 — Summary` subsection, one per spec §5 phase. Mirror the spec's structure inside each:

   - **Phase 1 — Schema validation.** Verbatim from spec §5 Phase 1. The seven `PASS / FAIL` checks from the table, plus the three `WARN` items. End with the "If any check `FAIL`s, **stop here**" short-circuit rule.
   - **Phase 2 — Backend reachability.** Branch-on-`backend:` opening. Sub-sections `2a. GitHub branch` (three probes — `gh auth status`, `gh repo view`, canonical `view_issue` with `PASS / PASS-WITH-NOTE / FAIL` semantics) and `2b. Jira branch` (three probes — Atlassian MCP availability via `ToolSearch`, `cloud_id` round-trip via `getAccessibleAtlassianResources`, canonical `view_issue` via `getJiraIssue`). End with the "Phase 2 `FAIL` does NOT short-circuit Phase 3" continuation rule.
   - **Phase 3 — Vocabulary sanity.** Branch-on-`backend:` opening. Sub-sections `3a. GitHub branch` (per-area `gh label list --search` check + fenced `gh label create` next-step block) and `3b. Jira branch` (issue-types check via `getJiraProjectMetadata` + optional components surfacing for `area_field: components`). All `WARN`-only — never `FAIL`.
   - **Phase 4 — Summary.** The aggregated `Summary: <F> FAIL · <W> WARN · <P> PASS` line. `PASS-WITH-NOTE` counts as `PASS` in the aggregate; renders inline as `[PASS] ... (note: <reason>)`.

6. **`## Output format`** — verbatim example block from spec §6. The 17-line clean-run example plus the missing-label `WARN` example with fenced `gh label create` next-step block. Reviewers will diff against this; preserve character-for-character.

7. **`## Failure modes`** — five bullet points covering the five scenarios in spec §7.

8. **`## Invariants`** — six bullet points covering the six invariants in spec §8 (always-exit-0; read-only; `view_issue` as canonical probe; PASS / WARN / FAIL / PASS-WITH-NOTE classification; markdown-only; Phase 1 short-circuits). Reviewers will diff against this; each invariant explicit and named.

9. **`## Conventions assumed`** — short paragraph naming the schema reference (`examples/issue-tracker.yaml.example`), the consumer-project's `.claude/issue-tracker.yaml` path, and the sibling `/tracker-init` as the writer of the file this validator validates. Style-matches the existing commands' Conventions blocks.

### Step 1.3: Verbatim text from the spec to preserve

The following passages MUST appear verbatim in the command file (the spec authored them with intent; reviewers will diff against this list):

- The Phase 1 PASS/FAIL table (seven rows) — column structure and FAIL output strings exactly as in spec §5 Phase 1.
- The full output example block from spec §6 — the 17-line clean-run example plus the missing-label fenced next-step block. Em-dashes (`—`) preserved; ASCII hyphens (`-`) preserved as-is; no Unicode drift. Lesson from PR #19: when the spec says "verbatim", paste source bytes through a non-lossy path.
- The `gh label create` next-step command from spec §5 Phase 3a — flags + color hex (`BFD4F2`) exact.
- The cross-backend invariant #5 citation — the literal phrase "cross-backend invariant #5" or "invariant #5 in `backends/_interface.md`" so the verification grep matches.

### Step 1.4: Style guidance

- **Prose tone:** terse, instructional, second-person ("invoke `view_issue({ref: <smoke-ref>})`", "branch on `backend:` value"). Match `commands/resume-initiative.md` + `commands/tracker-init.md`.
- **Code fences:** YAML examples in fenced ```yaml blocks; shell commands (`gh auth status`, `gh repo view`) in backticks inline; contract operations (`view_issue`, `list_open_issues`) in backticks; fenced ```bash blocks for the next-step commands the operator pastes.
- **No bash heredocs.** The prose tells the agent what to do; the agent uses the actual tools. No `set -e` or `if [[ ... ]]` blocks.
- **No emojis.** Match the existing plugin file style.
- **PASS / WARN / FAIL spelling.** Always uppercase, always bracketed (`[PASS]` / `[WARN]` / `[FAIL]` / `[PASS-WITH-NOTE]`) when rendered in example output. Reviewers will diff against this.

### Step 1.5: Self-verify against the static acceptance gates

Before committing, the subagent runs every gate from spec §11 + the acceptance-table grep checks from issue #23, and reports any failure to the controller (does NOT commit until all pass):

```bash
test -f commands/tracker-doctor.md || { echo "MISSING file"; exit 1; }

# Leakage gates
grep -F "maxdimitrov/trading-bot" commands/tracker-doctor.md \
  && { echo "LEAK: trading-bot string"; exit 1; } || echo "clean: no trading-bot"

# Three phases named in prose
for phase in "schema validation" "backend reachability" "vocabulary sanity"; do
  grep -qiE "$phase" commands/tracker-doctor.md \
    || { echo "MISSING phase: $phase"; exit 1; }
done

# Cross-backend invariant #5 cited (view_issue as the canonical reachability probe)
grep -qE "view_issue" commands/tracker-doctor.md \
  || { echo "MISSING view_issue as canonical reachability probe"; exit 1; }
grep -qiE "invariant.*5|smoke test" commands/tracker-doctor.md \
  || { echo "MISSING cross-backend invariant #5 citation"; exit 1; }

# Both backend branches present
grep -qE "gh auth status" commands/tracker-doctor.md \
  || { echo "MISSING GitHub auth probe"; exit 1; }
grep -qE "gh repo view" commands/tracker-doctor.md \
  || { echo "MISSING GitHub repo probe"; exit 1; }
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-doctor.md \
  || { echo "MISSING Atlassian MCP availability probe"; exit 1; }
grep -qE "getJiraIssue|getAccessibleAtlassianResources" commands/tracker-doctor.md \
  || { echo "MISSING Jira MCP probe tool names"; exit 1; }

# --smoke-issue flag documented
grep -qE "\-\-smoke-issue" commands/tracker-doctor.md \
  || { echo "MISSING --smoke-issue flag"; exit 1; }

# PASS / WARN / FAIL classification used
for cls in "PASS" "WARN" "FAIL"; do
  grep -q "$cls" commands/tracker-doctor.md \
    || { echo "MISSING classification: $cls"; exit 1; }
done

# Always-exit-0 invariant stated
grep -qiE "exit 0|always exit 0|exits 0" commands/tracker-doctor.md \
  || { echo "MISSING always-exit-0 invariant"; exit 1; }

# Read-only invariant stated
grep -qiE "read-only" commands/tracker-doctor.md \
  || { echo "MISSING read-only invariant"; exit 1; }

# Three phases AND a summary section present (subsection headings)
for n in 1 2 3 4; do
  grep -qE "^### Phase $n " commands/tracker-doctor.md \
    || { echo "MISSING Phase $n subsection"; exit 1; }
done

# Required top-level sections
for sec in "## Invocation modes" "## What you should do" "## Output format" "## Failure modes" "## Invariants"; do
  grep -qF "$sec" commands/tracker-doctor.md \
    || { echo "MISSING section: $sec"; exit 1; }
done
```

If any gate fails, fix and re-run before committing.

### Step 1.6: Commit

```bash
git add commands/tracker-doctor.md
git commit -m "$(cat <<'EOF'
feat(commands): write /tracker-doctor validator (#23)

New plugin slash command — read-only validator that runs three
check phases against .claude/issue-tracker.yaml and the configured
backend, emits PASS/WARN/FAIL per check with literal next-step
commands, and always exits 0 (informational discipline, mirrors
/audit-skills + /audit-pii).

Three phases: schema validation (file exists, parses,
schema_version: 1, backend-conditional required fields, types
enum, Jira issue_types coverage); backend reachability
(GitHub: gh auth status -> gh repo view -> view_issue(#N);
Jira: Atlassian MCP availability -> getAccessibleAtlassianResources
cloud_id round-trip -> view_issue(<PROJECT>-N) via getJiraIssue);
vocabulary sanity (GitHub: per-area gh label list with literal
gh label create next-steps; Jira: per-issue-type
getJiraProjectMetadata check). Summary line aggregates counts.

view_issue is the canonical reachability probe per cross-backend
invariant #5 in backends/_interface.md. PASS-WITH-NOTE handles
the 404-on-probe-ref case (greenfield repo / project) without
failing the run. --smoke-issue flag overrides the default probe
ref. Phase 1 FAIL short-circuits Phases 2-3; Phase 2 FAIL does
NOT short-circuit Phase 3 (vocabulary findings remain actionable).

Spec: docs/superpowers/specs/2026-05-27-write-tracker-doctor-command-design.md.
Parent epic: maxdimitrov/trading-bot#153 (Phase 3).
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'    # confirm commit landed
git show --stat HEAD           # confirm only commands/tracker-doctor.md changed
```

---

## Task 2: CHANGELOG.md update + final static verify

**Files:**
- Modify: `CHANGELOG.md` (append one bullet under `[Unreleased]` → `Added`)

**Subagent model recommendation:** `haiku` — single-line append + grep verification.

### Step 2.1: Read the current CHANGELOG.md

The CHANGELOG follows Keep-a-Changelog format. The Phase 3 (#22) entry currently lives under `[Unreleased]` → `Added` as the most-recent bullet. Locate it; the new bullet appends immediately after.

### Step 2.2: Append the Phase 3 entry

Use the Edit tool. The `old_string` is the last existing `Added` bullet (the Phase 3 (#22) line — find it with Read first). The `new_string` is that same line PLUS a newline PLUS the new bullet:

```markdown
- Phase 3 (#23): `commands/tracker-doctor.md` — read-only validator. Three check phases (schema validation, backend reachability, vocabulary sanity) plus a summary line; emits `[PASS]` / `[WARN]` / `[FAIL]` per check with literal next-step commands; always exits 0 (informational discipline, mirrors `/audit-skills` + `/audit-pii`). Reachability dispatches through `view_issue` per cross-backend invariant #5 in `backends/_interface.md` — GitHub: `gh auth status` → `gh repo view` → `view_issue(#<N>)`; Jira: Atlassian MCP availability → `getAccessibleAtlassianResources` `cloud_id` round-trip → `view_issue(<PROJECT>-<N>)` via `getJiraIssue`. `PASS-WITH-NOTE` handles the 404-on-probe-ref case (greenfield repo / project) without failing the run. `--smoke-issue <ref>` overrides the default probe ref.
```

### Step 2.3: Re-run the full static acceptance checklist from spec §11 + the Task 1 gates

Same grep block as Step 1.5 plus a CHANGELOG gate. The subagent runs every line and reports the full output to the controller:

```bash
# (Same gates as Step 1.5)
test -f commands/tracker-doctor.md && echo "OK: file exists" || echo "FAIL: file"
grep -F "maxdimitrov/trading-bot" commands/tracker-doctor.md && echo "FAIL: trading-bot leak" || echo "OK: no leak"

for phase in "schema validation" "backend reachability" "vocabulary sanity"; do
  grep -qiE "$phase" commands/tracker-doctor.md && echo "OK: phase $phase" || echo "FAIL: phase $phase"
done

grep -qE "view_issue" commands/tracker-doctor.md && echo "OK: view_issue" || echo "FAIL: view_issue"
grep -qiE "invariant.*5|smoke test" commands/tracker-doctor.md && echo "OK: invariant #5" || echo "FAIL: invariant #5"
grep -qE "gh auth status" commands/tracker-doctor.md && echo "OK: gh auth status" || echo "FAIL: gh auth status"
grep -qE "gh repo view" commands/tracker-doctor.md && echo "OK: gh repo view" || echo "FAIL: gh repo view"
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-doctor.md && echo "OK: Atlassian MCP" || echo "FAIL: Atlassian MCP"
grep -qE "getJiraIssue|getAccessibleAtlassianResources" commands/tracker-doctor.md && echo "OK: Jira MCP tools" || echo "FAIL: Jira MCP tools"
grep -qE "\-\-smoke-issue" commands/tracker-doctor.md && echo "OK: --smoke-issue" || echo "FAIL: --smoke-issue"

for cls in "PASS" "WARN" "FAIL"; do
  grep -q "$cls" commands/tracker-doctor.md && echo "OK: $cls" || echo "FAIL: $cls"
done

grep -qiE "exit 0|always exit 0|exits 0" commands/tracker-doctor.md && echo "OK: exit 0 invariant" || echo "FAIL: exit 0 invariant"
grep -qiE "read-only" commands/tracker-doctor.md && echo "OK: read-only invariant" || echo "FAIL: read-only invariant"

for n in 1 2 3 4; do
  grep -qE "^### Phase $n " commands/tracker-doctor.md && echo "OK: Phase $n" || echo "FAIL: Phase $n"
done

for sec in "## Invocation modes" "## What you should do" "## Output format" "## Failure modes" "## Invariants"; do
  grep -qF "$sec" commands/tracker-doctor.md && echo "OK: section $sec" || echo "FAIL: section $sec"
done

# CHANGELOG gate
grep -qE "commands/tracker-doctor|Phase 3 \(#23\)" CHANGELOG.md && echo "OK: CHANGELOG entry" || echo "FAIL: CHANGELOG entry"
```

Every line should print `OK: ...`. If any prints `FAIL: ...`, do NOT commit — return to the controller for triage.

### Step 2.4: Commit

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore(changelog): note Phase 3 #23 (/tracker-doctor validator)

Append a Phase 3 entry to [Unreleased] -> Added for the
commands/tracker-doctor.md read-only validator landed in the
previous commit.
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'    # confirm commit landed
git show --stat HEAD           # confirm only CHANGELOG.md changed
git log --oneline -5           # full branch state — spec, plan, command, changelog (4 commits ahead of main)
```

---

## Post-task: open the PR

After Task 2 commits cleanly:

1. Pre-push branch-staleness check:
   ```bash
   git fetch origin
   git rev-list --left-right --count HEAD...origin/main
   # RIGHT must be 0; if not, rebase before pushing
   ```

2. Push the branch:
   ```bash
   git push -u origin feat/issue-23-tracker-doctor-validator
   ```

3. Create the PR via `gh pr create --body-file <temp>` against `maxdimitrov/agent-issue-tracker` `main`. Title: `Phase 3 (#23): write /tracker-doctor validator`. Body follows the shape of PRs #21 and #25 (summary, files, decisions settled in spec/brainstorm, behaviour-change-zero N/A for write-from-scratch, test plan with the static acceptance checklist marked, `Closes #23`, `Parent epic: maxdimitrov/trading-bot#153`).

4. Wait for merge. The post-merge epic update (parent epic #153 Status block) is the controller's concern (the user's pipeline step 5), NOT a subagent task.

---

## Self-review (controller, after writing this plan)

**Spec coverage:**
- §1 Problem — context for Task 1 only; no implementation surface.
- §2 Goal — covered by Task 1 Step 1.2 (output file structure).
- §3 Non-goals — out-of-scope items NOT addressed (correct).
- §4 Decisions table — all 11 decisions reflected in Task 1 Step 1.2 (phase structure + sections) + Step 1.3 (verbatim text) + Step 1.4 (style).
- §5 Flow phases 1-4 (incl. Summary) — each maps to a `### Phase N — <name>` subsection inside Task 1 Step 1.2 item 5.
- §6 Output format — Task 1 Step 1.2 item 6 (verbatim block).
- §7 Failure modes — Task 1 Step 1.2 item 7.
- §8 Invariants — Task 1 Step 1.2 item 8.
- §9 Cross-references — implicit (the subagent references the listed files when authoring); no implementation surface.
- §10 Acceptance — Step 1.5 + Step 2.3 grep gates.
- §11 Verification — Step 1.5 + Step 2.3.
- §12 Notes — informational; the asymmetry between Phase 1 short-circuit (yes) and Phase 2 short-circuit (no) is binding and is restated explicitly in Task 1 Step 1.2 Phase 2 and Phase 3.

**Placeholder scan:** none — every section has explicit content rules, every grep is fully written, every commit message is in HEREDOC form, no "implement appropriately."

**Type consistency:** N/A — markdown-only, no types. The four `Phase N` headings (1 through 4 incl. Summary) appear consistently across the spec, this plan, and Step 1.5's grep gates.

**No drift:** Task 1 commit message matches the spec wording; Task 2 commit message matches the appended CHANGELOG line; both reference issue #23 and parent epic #153.

---

## Execution mode

Per project CLAUDE.md (`~/.claude/CLAUDE.md` "Plan execution" section), execution is always via `superpowers:subagent-driven-development`. Fresh subagent per task, two-stage spec-then-quality review.

For this plan: two subagent dispatches (Task 1, Task 2). Both can use the `haiku` model — the work is rule-driven authoring against an explicit phase-by-phase spec, no design decisions delegated. The controller verifies `git log -1 --format='%H %s'` and `git show --stat HEAD` after each subagent returns; reads the produced `commands/tracker-doctor.md` end-to-end before declaring Task 1 done.

After both tasks complete, the controller invokes one more subagent (sonnet, full file) as a quality-review pass — same shape as PRs #21 and #25's reviewer subagent. The reviewer reads `commands/tracker-doctor.md` cold against the spec and reports any drift (silent enum substitutions, missing failure modes, missing invariants, vocabulary that doesn't match the spec, PASS-WITH-NOTE semantics misstated).
