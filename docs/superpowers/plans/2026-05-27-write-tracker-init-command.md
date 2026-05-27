# Write `/tracker-init` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `commands/tracker-init.md` from scratch — a markdown-only slash command that walks the operator through an `AskUserQuestion`-driven flow and writes a valid `.claude/issue-tracker.yaml` to the consumer's repo root. Both backend branches (GitHub + Jira), environment probes, atomic single-Write emission, refuses to overwrite without `--force`.

**Architecture:** Single new markdown file under `commands/` plus a one-line `CHANGELOG.md` append. No skills, no templates, no backend modules — Phase 1 (#9) landed the schema this command's output conforms to, Phase 2 (#11-#14) landed the skills that consume the written config, and PR #21 landed the slash-command shape precedent. The command is the deliverable; everything it interfaces with already exists.

**Tech Stack:** Markdown only (slash-command convention), YAML frontmatter, `grep` for static acceptance gates. No code, no tests, no build step. The command's prose tells the agent to use `AskUserQuestion`, `Write`, and `ToolSearch` at runtime; those are tool-level concerns, not implementation surface.

**Spec:** `docs/superpowers/specs/2026-05-27-write-tracker-init-command-design.md` (committed pre-Task-1 on this branch alongside this plan).

**Source:** None — write-from-scratch. The shape precedent is `commands/resume-initiative.md` on this plugin's `main` (committed via PR #21). The conceptual flow is parent design spec §7.1 on `maxdimitrov/trading-bot` `main`.

**Issue:** `agent-issue-tracker#22`. **Parent epic:** `maxdimitrov/trading-bot#153` (Phase 3).

---

## Pre-task setup (controller, not a subagent task)

Before dispatching Task 1, the controller MUST:

1. Verify CWD is the worktree `.claude/worktrees/write-tracker-init-command/`.
2. Verify the branch is `feat/tracker-init-command`.
3. Verify the spec is committed: `git log --oneline -3` should show the design spec + this plan landing on the branch as the first two commits ahead of `main`.

No source-bytes retrieval step — this is write-from-scratch, not a port. The subagent receives the spec sections inline in the dispatch prompt; it does NOT have to read the spec end-to-end.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `commands/tracker-init.md` | NEW (~200-280 lines) | The slash command — markdown with YAML frontmatter, eight-phase flow, both backend branches documented, failure modes block |
| `CHANGELOG.md` | MODIFY (+1 line) | Append a Phase 3 entry under `[Unreleased]` → `Added` |

---

## Task 1: Author `commands/tracker-init.md`

**Files:**
- Create: `commands/tracker-init.md`
- Reference (read-only, for the design): `docs/superpowers/specs/2026-05-27-write-tracker-init-command-design.md`
- Reference (read-only, for the shape precedent): `commands/resume-initiative.md`
- Reference (read-only, for the schema this command's output conforms to): `examples/issue-tracker.yaml.example`
- Reference (read-only, for the GitHub probe shape): `backends/github.md`

**Subagent model recommendation:** `haiku` is fine — the work is rule-driven authoring against an explicit phase-by-phase design. No design decisions delegated (those are locked in the spec).

**Subagent context to include in prompt verbatim:** the spec's §3 Non-goals, §4 Decisions table, and §5 Flow phases (all eight). The subagent should NOT have to read the spec end-to-end — paste the binding sections inline.

### Step 1.1: Read the shape precedent

Read `commands/resume-initiative.md` end-to-end (~110 lines). It's the only existing plugin slash command and the source of truth for:

- YAML frontmatter shape (single-line `description:`)
- Section headings (`# /command-name [args]`, `## Invocation modes`, `## What you should do`, `## Failure modes`)
- Numbered subsection structure inside "What you should do"
- Prose tone (terse, dispatch-through-contract, name files not commands)

Do NOT read the design spec end-to-end — the dispatch prompt carries the binding sections inline.

### Step 1.2: Author the new file — section by section

Write `commands/tracker-init.md` from scratch, following this exact ordered structure (one section per spec phase):

1. **YAML frontmatter.** Single key:
   ```yaml
   ---
   description: Interactive scaffolder — writes `.claude/issue-tracker.yaml` for the consumer project. Refuses to overwrite without --force.
   ---
   ```

2. **Title line.** `# /tracker-init [--force]` (note the `--force` flag in the title).

3. **Overview paragraph.** Two-to-four sentences. Name the goal (writes a valid `.claude/issue-tracker.yaml`), the surface (`AskUserQuestion`-driven flow), the gate (`--force` to overwrite), and the closing handoff (`/tracker-doctor` validates the result). Cite `examples/issue-tracker.yaml.example` as the schema reference.

4. **`## Invocation modes` table.** Two rows:
   | Invocation | Behaviour |
   |---|---|
   | `/tracker-init` | Interactive flow. Refuses to overwrite an existing `.claude/issue-tracker.yaml`. |
   | `/tracker-init --force` | Interactive flow. Overwrites an existing `.claude/issue-tracker.yaml`. |

5. **`## What you should do`** — eight `### Phase N — <name>` subsections, one per spec §5 phase. Mirror the spec's structure inside each:

   - **Phase 1 — Pre-flight: existing-config guard.** Detect `.claude/issue-tracker.yaml`. Branch on absent / present-no-force (STOP, refuse) / present-with-force (continue, record overwrite). Verbatim from spec §5 Phase 1.
   - **Phase 2 — Backend selection.** Single `AskUserQuestion` invocation (single-select, header `Backend`, options `GitHub | Jira`). "Other" rejected → re-prompt.
   - **Phase 3 — GitHub branch** (skip if `backend: jira`). Three steps from spec §5 Phase 3 (auth probe STOP-IF-FAIL, repo default extraction via `gh repo view`, repo prompt via `AskUserQuestion` with the extracted default as recommended).
   - **Phase 4 — Jira branch** (skip if `backend: github`). Four steps from spec §5 Phase 4 (MCP availability STOP-IF-FAIL, site+cloud_id combined prompt from MCP discovery, project key prompt, 3-question field-mapping batch). NB: ONLY four steps (4a/4b/4c/4d), not five — site+cloud_id is collapsed into a single MCP-sourced prompt per spec §5 Phase 4b.
   - **Phase 5 — Vocabulary batch.** 2-question `AskUserQuestion` (areas multi-select with 4 pre-selected defaults + Other; subsystems Yes/No). Conditional follow-up `AskUserQuestion` if Yes (parse multi-line input via "Other" affordance).
   - **Phase 6 — Assemble the YAML.** Build the YAML string in memory. Include the verbatim header comment block (with `YYYY-MM-DD` substituted from the system date). Then `schema_version: 1` and `backend:`. Then conditional blocks per spec §5 Phase 6.
   - **Phase 7 — Write.** Single `Write` tool call to `.claude/issue-tracker.yaml`. Atomic.
   - **Phase 8 — Next-steps panel.** Print the operator-facing output block from spec §5 Phase 8.

6. **`## Failure modes`** — seven bullet points covering the seven scenarios in spec §6.

7. **(Optional) `## Conventions assumed`** — short paragraph naming the schema reference (`examples/issue-tracker.yaml.example`), the consumer-project's `.claude/issue-tracker.yaml` path, and the sibling `/tracker-doctor` command as the post-init validator. Style-matches `commands/resume-initiative.md`'s "Conventions assumed" block.

### Step 1.3: Verbatim text from the spec to preserve

The following passages MUST appear verbatim in the command file (the spec authored them with intent; reviewers will diff against this list):

- The header comment block from spec §5 Phase 6 (the four-line `# .claude/issue-tracker.yaml — agent-issue-tracker schema v1` comment + the schema reference URL).
- The next-steps panel text from spec §5 Phase 8 (the "Wrote .claude/issue-tracker.yaml" + numbered steps + the per-backend `/tracker-doctor` hint suffix).
- The four `AskUserQuestion` headers — `Backend`, `Repo`, `Site`, `Project`, `Feature type`, `Area field`, `Parent link`, `Areas`, `Subsystems`, `Subsystem list` — all ≤12 chars (verify when authoring).

### Step 1.4: Style guidance

- **Prose tone:** terse, instructional, second-person ("invoke `AskUserQuestion` with...", "check whether the file exists at..."). Match `commands/resume-initiative.md`.
- **Code fences:** YAML examples in fenced ```yaml blocks; shell-style command names (`gh auth status`, `gh repo view`) in backticks inline; `AskUserQuestion` references in backticks.
- **No bash heredocs.** The prose tells the agent what to do; the agent uses the actual tools. No `set -e` or `if [[ ... ]]` blocks.
- **No emojis.** Match the existing plugin file style.

### Step 1.5: Self-verify against the static acceptance gates

Before committing, the subagent runs every gate from spec §10 + the acceptance-table grep checks from issue #22, and reports any failure to the controller (does NOT commit until all pass):

```bash
test -f commands/tracker-init.md || { echo "MISSING file"; exit 1; }

# Leakage gates
grep -F "maxdimitrov/trading-bot" commands/tracker-init.md \
  && { echo "LEAK: trading-bot string"; exit 1; } || echo "clean: no trading-bot"

# At least 4 AskUserQuestion invocations
COUNT=$(grep -c "AskUserQuestion" commands/tracker-init.md)
[ "$COUNT" -ge 4 ] || { echo "MISSING AskUserQuestion invocations (got $COUNT, need >=4)"; exit 1; }
echo "AskUserQuestion references: $COUNT"

# Both backend branches present
grep -qE "gh auth status" commands/tracker-init.md \
  || { echo "MISSING GitHub auth probe"; exit 1; }
grep -qE "gh repo view" commands/tracker-init.md \
  || { echo "MISSING GitHub repo default extraction"; exit 1; }
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-init.md \
  || { echo "MISSING Atlassian MCP availability probe"; exit 1; }
grep -qE "cloud_id|cloudId" commands/tracker-init.md \
  || { echo "MISSING cloud_id resolution"; exit 1; }

# Existing-config guard
grep -qE "\-\-force" commands/tracker-init.md \
  || { echo "MISSING --force flag for overwrite"; exit 1; }

# Schema version pinned
grep -qE "schema_version:\s*1" commands/tracker-init.md \
  || { echo "MISSING schema_version: 1 in written YAML"; exit 1; }

# All eight phases present (using --- block to disambiguate against the spec's "Phase N" entries)
for n in 1 2 3 4 5 6 7 8; do
  grep -qE "^### Phase $n " commands/tracker-init.md \
    || { echo "MISSING Phase $n subsection"; exit 1; }
done
echo "all eight phases present"

# Failure modes section
grep -qE "^## Failure modes" commands/tracker-init.md \
  || { echo "MISSING Failure modes section"; exit 1; }

# Write tool referenced for atomic emission
grep -qE "\\bWrite\\b" commands/tracker-init.md \
  || { echo "MISSING Write-tool reference for YAML emission"; exit 1; }
```

If any gate fails, fix and re-run before committing.

### Step 1.6: Commit

```bash
git add commands/tracker-init.md
git commit -m "$(cat <<'EOF'
feat(commands): write /tracker-init interactive scaffolder (#22)

New plugin slash command that walks the operator through an
AskUserQuestion-driven flow and writes a valid
.claude/issue-tracker.yaml to the consumer's repo root.

Eight phases: existing-config guard (--force overwrite), backend
select, GitHub branch (gh auth probe + gh repo view default +
repo prompt), Jira branch (Atlassian MCP availability + combined
site/cloud_id from getAccessibleAtlassianResources + project key
+ 3-question field-mapping batch), vocabulary batch (areas
multi-select + subsystems yes/no + optional follow-up list),
YAML assembly emitting only blocks relevant to the chosen
backend, single atomic Write to .claude/issue-tracker.yaml,
next-steps panel pointing at /tracker-doctor.

Closed-enum prompts reject "Other" with re-prompt. Pre-flight
auth/MCP probes fire immediately after backend select so failure
short-circuits before further prompts. No partial writes — YAML
is built in memory and emitted once in Phase 7.

Spec: docs/superpowers/specs/2026-05-27-write-tracker-init-command-design.md.
Parent epic: maxdimitrov/trading-bot#153 (Phase 3).
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'    # confirm commit landed
git show --stat HEAD           # confirm only commands/tracker-init.md changed
```

---

## Task 2: CHANGELOG.md update + final static verify

**Files:**
- Modify: `CHANGELOG.md` (append one bullet under `[Unreleased]` → `Added`)

**Subagent model recommendation:** `haiku` — single-line append + grep verification.

### Step 2.1: Read the current CHANGELOG.md

The CHANGELOG follows Keep-a-Changelog format. The Phase 3 (#20) entry currently lives under `[Unreleased]` → `Added` as the most-recent bullet. Locate it; the new bullet appends immediately after.

### Step 2.2: Append the Phase 3 entry

Use the Edit tool. The `old_string` is the last existing `Added` bullet (the Phase 3 (#20) line — find it with Read first). The `new_string` is that same line PLUS a newline PLUS the new bullet:

```markdown
- `commands/tracker-init.md` — interactive scaffolder. Eight-phase `AskUserQuestion`-driven flow writes a valid `.claude/issue-tracker.yaml` for the consumer project. Both backend branches (GitHub: `gh auth status` + `gh repo view` default; Jira: Atlassian MCP availability + combined site/`cloud_id` from `getAccessibleAtlassianResources` + project key + 3-question field-mapping batch), vocabulary multi-select with custom-value affordance, atomic single-`Write` emission, refuses to overwrite without `--force`. Phase 3 (#22).
```

### Step 2.3: Re-run the full static acceptance checklist from spec §10 + the Task 1 gates

Same grep block as Step 1.5 plus a CHANGELOG gate. The subagent runs every line and reports the full output to the controller:

```bash
# (Same gates as Step 1.5)
test -f commands/tracker-init.md && echo "OK: file exists" || echo "FAIL: file"
grep -F "maxdimitrov/trading-bot" commands/tracker-init.md && echo "FAIL: trading-bot leak" || echo "OK: no leak"

COUNT=$(grep -c "AskUserQuestion" commands/tracker-init.md)
[ "$COUNT" -ge 4 ] && echo "OK: AskUserQuestion x$COUNT" || echo "FAIL: AskUserQuestion (got $COUNT)"

grep -qE "gh auth status" commands/tracker-init.md && echo "OK: gh auth status" || echo "FAIL: gh auth status"
grep -qE "gh repo view" commands/tracker-init.md && echo "OK: gh repo view" || echo "FAIL: gh repo view"
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-init.md && echo "OK: Atlassian MCP" || echo "FAIL: Atlassian MCP"
grep -qE "cloud_id|cloudId" commands/tracker-init.md && echo "OK: cloud_id" || echo "FAIL: cloud_id"
grep -qE "\-\-force" commands/tracker-init.md && echo "OK: --force" || echo "FAIL: --force"
grep -qE "schema_version:\s*1" commands/tracker-init.md && echo "OK: schema_version" || echo "FAIL: schema_version"

for n in 1 2 3 4 5 6 7 8; do
  grep -qE "^### Phase $n " commands/tracker-init.md && echo "OK: Phase $n" || echo "FAIL: Phase $n"
done

grep -qE "^## Failure modes" commands/tracker-init.md && echo "OK: Failure modes" || echo "FAIL: Failure modes"
grep -qE "\\bWrite\\b" commands/tracker-init.md && echo "OK: Write tool" || echo "FAIL: Write tool"

# CHANGELOG gate
grep -qE "commands/tracker-init|Phase 3 \(#22\)" CHANGELOG.md && echo "OK: CHANGELOG entry" || echo "FAIL: CHANGELOG entry"
```

Every line should print `OK: ...`. If any prints `FAIL: ...`, do NOT commit — return to the controller for triage.

### Step 2.4: Commit

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore(changelog): note Phase 3 #22 (/tracker-init scaffolder)

Append a Phase 3 entry to [Unreleased] → Added for the
commands/tracker-init.md interactive scaffolder landed in the
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

1. Push the branch:
   ```bash
   git push -u origin feat/tracker-init-command
   ```

2. Create the PR via `gh pr create` against `maxdimitrov/agent-issue-tracker` `main`. Title: `Phase 3 (#22): write /tracker-init interactive scaffolder`. Body follows the shape of PR #21 (summary, files, decisions settled in brainstorm, behaviour-change-zero N/A for write-from-scratch, test plan with the static acceptance checklist marked, `Closes #22`, `Parent epic: maxdimitrov/trading-bot#153`).

3. Wait for merge. The post-merge epic update is the controller's concern (the user's pipeline step 3), NOT a subagent task.

---

## Self-review (controller, after writing this plan)

**Spec coverage:**
- §1 Problem — context for Task 1 only; no implementation surface.
- §2 Goal — covered by Task 1 Step 1.2 (output file structure).
- §3 Non-goals — out-of-scope items NOT addressed (correct).
- §4 Decisions table — all 10 decisions reflected in Task 1 Step 1.2 (phase structure) + Step 1.3 (verbatim text) + Step 1.4 (style).
- §5 Flow phases 1-8 — each maps to a `### Phase N — <name>` subsection inside Task 1 Step 1.2 item 5.
- §6 Failure modes — Task 1 Step 1.2 item 6.
- §7 Invariants — implicit in the spec sections the subagent receives; the grep gates in Step 1.5 cover the testable ones (`schema_version: 1`, `--force`, atomic Write).
- §8 Cross-references — informational; no implementation surface.
- §9 Acceptance — Step 1.5 + Step 2.3 grep gates.
- §10 Verification — Step 1.5 + Step 2.3.
- §11 Notes — informational; the Phase 4 site+cloud_id collapse is binding and is restated explicitly in Task 1 Step 1.2 Phase 4.

**Placeholder scan:** none — every section has explicit content rules, every grep is fully written, every commit message is in HEREDOC form, no "implement appropriately."

**Type consistency:** N/A — markdown-only, no types. The eight `Phase N` headings appear consistently across the spec, this plan, and Step 1.5's grep gates.

**No drift:** Task 1 commit message matches the spec wording; Task 2 commit message matches the appended CHANGELOG line; both reference issue #22 and parent epic #153.

---

## Execution mode

Per project CLAUDE.md (`~/.claude/CLAUDE.md` "Plan execution" section), execution is always via `superpowers:subagent-driven-development`. Fresh subagent per task, two-stage spec-then-quality review.

For this plan: two subagent dispatches (Task 1, Task 2). Both can use the `haiku` model — the work is rule-driven authoring against an explicit phase-by-phase spec, no design decisions delegated. The controller verifies `git log -1 --format='%H %s'` and `git show --stat HEAD` after each subagent returns; reads the produced `commands/tracker-init.md` end-to-end before declaring Task 1 done.

After both tasks complete, the controller invokes one more subagent (sonnet, full file) as a quality-review pass — same shape as PR #21's Task 3 reviewer subagent. The reviewer reads `commands/tracker-init.md` cold against the spec and reports any drift (silent enum substitutions, missing failure modes, vocabulary that doesn't match the spec).
