# Port /resume-initiative Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `.claude/commands/resume-initiative.md` from `maxdimitrov/trading-bot` to this plugin as `commands/resume-initiative.md` in tracker-agnostic prose — dispatches through the seven-operation contract, accepts both `#N` and `PROJ-123` refs, handles cross-repo `## Children` task-list mirrors, lands Mode 3 worktrees in the consumer's CWD.

**Architecture:** Single new markdown file under `commands/` plus a one-line `CHANGELOG.md` append. No skills, no templates, no backend modules — Phase 1 (#9) landed the dispatch contract and Phase 2 (#14) landed the Status-block format this command parses. The command is the deliverable; dispatch glue already exists.

**Tech Stack:** Markdown only (slash-command convention), YAML frontmatter, `gh` CLI for source retrieval, `grep` for static acceptance gates. No code, no tests, no build step.

**Spec:** `docs/superpowers/specs/2026-05-27-port-resume-initiative-command-design.md` (committed pre-Task-1 on this branch).

**Source:** `.claude/commands/resume-initiative.md` on `maxdimitrov/trading-bot` `main`.

**Issue:** `agent-issue-tracker#20`. **Parent epic:** `maxdimitrov/trading-bot#153` (Phase 3).

---

## Pre-task setup (controller, not a subagent task)

Before dispatching Task 1, the controller MUST:

1. Verify CWD is the worktree `.claude/worktrees/port-resume-initiative-command/`.
2. Verify the branch is `feat/port-resume-initiative-command`.
3. Verify the spec is committed: `git log --oneline -3` should show `docs(spec): port /resume-initiative command — design (#20)` and `docs(plan): port /resume-initiative command — plan (#20)` (this commit, after this file lands).
4. Retrieve the source command bytes and save to a known path the subagent can read:
   ```bash
   gh api repos/maxdimitrov/trading-bot/contents/.claude/commands/resume-initiative.md \
     --jq .content | base64 -d > .resume-initiative-source.md
   ```
   This file is `.gitignore`d (or untracked — it must NOT be committed). The subagent reads it as the source of truth for the port.

5. Pass the source file path explicitly in the subagent's prompt: `"the source command is at .resume-initiative-source.md in the worktree root; read it end-to-end before writing the port"`.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `commands/resume-initiative.md` | NEW (~200-260 lines) | The slash command — markdown with YAML frontmatter, tracker-agnostic prose, dispatches through the operation contract |
| `CHANGELOG.md` | MODIFY (+1 line) | Append a Phase 3 entry under `[Unreleased]` → `Added` |
| `.resume-initiative-source.md` | EPHEMERAL (untracked) | The source bytes from trading-bot; reference-only for the port; never committed |

---

## Task 1: Author `commands/resume-initiative.md`

**Files:**
- Create: `commands/resume-initiative.md`
- Read: `.resume-initiative-source.md` (the source bytes from trading-bot, fetched by the controller pre-task)
- Reference (read-only, for the transform rules): `docs/superpowers/specs/2026-05-27-port-resume-initiative-command-design.md`
- Reference (read-only, for dispatch contract): `backends/_interface.md`
- Reference (read-only, for the Status-block field spec): `skills/initiative-tracking/SKILL.md`
- Reference (read-only, for the `## Children` task-list shape): `templates/epic-body.md`

**Subagent model recommendation:** `haiku` is fine — the work is rule-driven transformation of a known source against an explicit transform table. No design decisions required (those are locked in the spec).

**Subagent context to include in prompt:** the spec's §5 transform tables in full (5.1, 5.2, 5.3, 5.4, 5.5). The subagent should NOT have to read the spec end-to-end — paste the binding sections inline.

### Step 1.1: Read the source command end-to-end

The source is at `.resume-initiative-source.md` in the worktree root. Read it before writing anything. It's ~170 lines: YAML frontmatter, then six sections — overview, invocation modes table, "What you should do" with Mode 1 / Mode 2 / Mode 3 subsections, "Conventions assumed", "Failure modes".

### Step 1.2: Author the new file — apply the transforms section-by-section

Write `commands/resume-initiative.md` from scratch, following the source's section structure but applying every transform from spec §5.1 (standard de-trading-bot-ification) and §5.2 (the four surgical transforms).

The file structure to produce (in this order):

1. **YAML frontmatter** — preserve `description:` modulo dropping any trading-bot-specific phrasing.
2. **Title line** — `# /resume-initiative [epic-ref] [--start]` (note `<ref>` — generic — not `<N>`).
3. **Overview paragraph** — describe what the command does in tracker-agnostic terms. Replace "Reads GitHub Issues for the `epic` label" with "Invokes the configured backend's `list_open_issues({label: 'epic'})` operation". Cite `.claude/issue-tracker.yaml`.
4. **Generic-applicability paragraph** — preserve verbatim ("This command is generic — it works for any initiative tracked via the `initiative-tracking` skill…"). The phrasing is tracker-neutral already.
5. **Inline brainstorm handoff paragraph** — preserve verbatim. The "do NOT stop and tell the operator to open a new window" guarantee is load-bearing.
6. **Naming aside** — preserve verbatim ("Named `/resume-initiative` (not `/resume`) to avoid shadowing Claude Code's built-in `/resume`…").
7. **`## Invocation modes` table** — preserve the three-row shape; column 1 syntax changes from `<N>` to `<ref>`.
8. **`## What you should do`** — three subsections per the source's `### Mode 1`, `### Mode 2`, `### Mode 3`. Apply the transforms per §5.2:
   - Mode 1: replace the `gh issue list ...` block with backend dispatch prose — invoke `list_open_issues({label: "epic"})` then per-result `view_issue({ref})` to fetch the body. Document the N+1 cost is acceptable (typical N < 20).
   - Mode 2: replace the `gh issue view ...` block with `view_issue({ref})`. The Status-block parsing section preserves the four canonical field-prefix strings literally — do NOT reword them; they are parsed character-for-character per `skills/initiative-tracking/SKILL.md`. Replace the children-listing subsection with the cross-backend canonical path (parse `## Children` task-list mirror; native sub-issue API is optional augmentation, not the primary). Document the three ref shapes (§4.4 / §5.2(c) of spec) — `#N`, `owner/repo#N`, `PROJ-123`.
   - Mode 3: preserve worktree creation mechanics + branch-name caveat + inline brainstorm handoff verbatim. Replace the `gh issue view <child-N> ...` body fetch with `view_issue({ref: child-ref})`. Document that the worktree lands in the consumer's CWD even for cross-repo `owner/repo#N` children.
9. **`## Conventions assumed`** — three items preserved; third reframed per spec §5.4 (children link back via `## Children` task-list mirror canonical + native sub-issue linkage optional augmentation + `## Parent epic` block in the child body).
10. **`## Failure modes`** — six bullet points covering the six scenarios in spec §5.3 (four ported from source, two new — mixed-backend ref shape and cross-repo `owner/repo#N` ref).

### Step 1.3: Apply the standard de-trading-bot-ification transforms

For every section above, apply the swap table from spec §5.1. The critical ones in this command:

| Source string | Replacement |
|---|---|
| `gh issue list --repo maxdimitrov/trading-bot --label epic --state open` (with `--json number,title,body,updatedAt --limit 20`) | one paragraph: "invoke `list_open_issues({label: 'epic'})`; for each returned `{ref, title, status}` call `view_issue({ref})` to fetch the body for Status-block parsing. See `backends/<backend>.md` for the literal invocation." |
| `gh issue view <N> --repo maxdimitrov/trading-bot --json number,title,body,labels,comments` | "invoke `view_issue({ref})`; the returned `{ref, title, body, labels[], status, parent?}` carries the body for Status-block parsing." |
| `gh api repos/maxdimitrov/trading-bot/issues/<N>/sub_issues --jq '.[] | {number, title, state}'` | (removed entirely from the primary path; if mentioned, it's as optional augmentation only — "the backend's native sub-issue relation MAY be queried alongside the task-list mirror parse, but the task-list mirror is the canonical cross-backend index. See `backends/<backend>.md` for whether and how native sub-issue queries are exposed.") |
| `gh issue view <child-N> --repo maxdimitrov/trading-bot --json body --jq .body` | "invoke `view_issue({ref: child-ref})` and pass the returned `body` to `superpowers:brainstorming`." |
| `maxdimitrov/trading-bot` (any other occurrence) | DELETE — no replacement; the consumer's `.claude/issue-tracker.yaml` is the source of truth. |
| `gh auth status` (failure-mode advice) | "the configured backend reports a reachability failure → run `/tracker-doctor` and re-invoke. See `backends/<backend>.md` setup section." |
| The bash code block fetching the children list | replaced with prose describing the task-list-mirror parse (no bash block in the canonical path); native augmentation MAY be cited but as a one-line reference, not as executable bash. |

**Acceptance during authoring:** zero literal `maxdimitrov/trading-bot` strings in the output; zero bare `gh ` shell commands (the canonical path uses `view_issue` / `list_open_issues`); the four Status-block field-prefix strings appear verbatim; both `#N` and `PROJ-123` named; cross-repo `owner/repo#N` documented; `## Children` task-list mirror named as canonical.

### Step 1.4: Self-verify against the static acceptance gates

Before committing, the subagent runs these greps and reports any failure to the controller (does NOT commit until all pass):

```bash
test -f commands/resume-initiative.md || echo "MISSING file"

# Leakage gates
grep -F "maxdimitrov/trading-bot" commands/resume-initiative.md \
  && echo "LEAK: trading-bot string" || echo "clean: no trading-bot string"

grep -nE "^gh " commands/resume-initiative.md \
  && echo "LEAK: bare gh command" || echo "clean: no bare gh"

# Canonical Status-block field prefixes — all four must appear
for field in '- \*\*Phase:\*\*' '- \*\*Next up:\*\*' '- \*\*Current branch:\*\*' '- \*\*Last updated:\*\*'; do
  grep -qE "$field" commands/resume-initiative.md \
    || { echo "MISSING field: $field"; exit 1; }
done
echo "all four field prefixes present"

# Both ref shapes
grep -qE '#N|#<N>|`#42`' commands/resume-initiative.md \
  || { echo "MISSING #N ref syntax"; exit 1; }
grep -qE 'PROJ-123|PROJ-<N>|<PROJECT>-<N>' commands/resume-initiative.md \
  || { echo "MISSING Jira ref syntax"; exit 1; }
echo "both ref shapes present"

# Cross-repo case documented
grep -qE 'owner/repo#' commands/resume-initiative.md \
  || { echo "MISSING cross-repo ref shape"; exit 1; }
echo "cross-repo ref documented"

# Task-list mirror cited as canonical
grep -qE '## Children|task-list' commands/resume-initiative.md \
  || { echo "MISSING children task-list mirror citation"; exit 1; }
echo "task-list mirror cited"

# Backend operation dispatch
grep -qE 'view_issue|list_open_issues' commands/resume-initiative.md \
  || { echo "MISSING backend operation dispatch"; exit 1; }
echo "backend operations cited"
```

If any gate fails, fix and re-run before committing.

### Step 1.5: Commit

```bash
git add commands/resume-initiative.md
git commit -m "$(cat <<'EOF'
feat(commands): port /resume-initiative — tracker-agnostic (#20)

Ports .claude/commands/resume-initiative.md from
maxdimitrov/trading-bot to this plugin as
commands/resume-initiative.md in tracker-agnostic prose.

The command dispatches through the seven-operation contract from
backends/_interface.md (list_open_issues, view_issue) rather than
calling gh directly. It parses the Status-block format codified in
skills/initiative-tracking/SKILL.md and accepts both #N (GitHub)
and PROJ-123 (Jira) refs in the Next up: line.

Cross-repo + cross-backend child discovery uses the ## Children
task-list mirror in the epic body — the canonical cross-backend
index per skills/initiative-tracking/SKILL.md. Three ref shapes
documented: #N (same repo), owner/repo#N (cross-repo GitHub),
PROJ-123 (Jira). Native sub-issue API queries demoted to optional
augmentation.

Mode 3 (--start) creates a worktree in the consumer's CWD even
when the next-up child is a cross-repo owner/repo#N ref; the
inline brainstorm handoff is preserved verbatim.

Spec: docs/superpowers/specs/2026-05-27-port-resume-initiative-command-design.md.
Parent epic: maxdimitrov/trading-bot#153 (Phase 3).
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'    # confirm commit landed
git show --stat HEAD           # confirm only commands/resume-initiative.md changed
```

---

## Task 2: CHANGELOG.md update + final static verify

**Files:**
- Modify: `CHANGELOG.md` (append one line under `[Unreleased]` → `Added`)

**Subagent model recommendation:** `haiku` — single-line append + grep verification.

### Step 2.1: Read the current CHANGELOG.md

The CHANGELOG follows Keep-a-Changelog format. The Phase 2 entries currently live under `[Unreleased]` → `Added`. Locate the bottom of that `Added` list — that's where the new entry goes.

### Step 2.2: Append the Phase 3 entry

Append one bullet under `[Unreleased]` → `Added` (after the Phase 2 (#14) line). Use this exact text:

```markdown
- `commands/resume-initiative.md` — tracker-agnostic port of the slash command. Dispatches through `list_open_issues` / `view_issue` from `backends/_interface.md`, parses both `#N` and `PROJ-123` Status-block refs, handles cross-repo `## Children` task-list mirrors with three ref shapes (`#N`, `owner/repo#N`, `PROJ-123`), Mode 3 worktree creation lands in the consumer's CWD. Phase 3 (#20).
```

Use the Edit tool. The `old_string` should be the last existing `Added` bullet (the Phase 2 #14 line) — find it with Read first. The `new_string` is that same line PLUS a newline PLUS the new bullet above.

### Step 2.3: Re-run the full static acceptance checklist from spec §7

The subagent runs every gate and reports the full output to the controller:

```bash
# File exists
test -f commands/resume-initiative.md && echo "OK: file exists"

# Leakage gates
grep -F "maxdimitrov/trading-bot" commands/resume-initiative.md && echo "FAIL: trading-bot leak" || echo "OK: no trading-bot leak"
grep -nE "^gh " commands/resume-initiative.md && echo "FAIL: bare gh" || echo "OK: no bare gh"

# Canonical Status-block field prefixes
for field in '- \*\*Phase:\*\*' '- \*\*Next up:\*\*' '- \*\*Current branch:\*\*' '- \*\*Last updated:\*\*'; do
  grep -qE "$field" commands/resume-initiative.md && echo "OK: $field" || echo "FAIL: $field missing"
done

# Both ref shapes
grep -qE '#N|#<N>|`#42`' commands/resume-initiative.md && echo "OK: #N ref" || echo "FAIL: #N ref missing"
grep -qE 'PROJ-123|PROJ-<N>|<PROJECT>-<N>' commands/resume-initiative.md && echo "OK: PROJ-123 ref" || echo "FAIL: PROJ-123 ref missing"

# Cross-repo case
grep -qE 'owner/repo#' commands/resume-initiative.md && echo "OK: cross-repo ref" || echo "FAIL: cross-repo ref missing"

# Task-list mirror canonical
grep -qE '## Children|task-list' commands/resume-initiative.md && echo "OK: task-list mirror" || echo "FAIL: task-list mirror missing"

# Backend operation dispatch
grep -qE 'view_issue|list_open_issues' commands/resume-initiative.md && echo "OK: backend ops" || echo "FAIL: backend ops missing"

# CHANGELOG updated
grep -qE "commands/resume-initiative|Phase 3 \(#20\)" CHANGELOG.md && echo "OK: CHANGELOG entry" || echo "FAIL: CHANGELOG entry missing"
```

Every line should print `OK: ...`. If any prints `FAIL: ...`, do NOT commit — return to the controller for triage.

### Step 2.4: Commit

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
chore(changelog): note Phase 3 #20 (/resume-initiative port)

Append a Phase 3 entry to [Unreleased] → Added for the
commands/resume-initiative.md port landed in the previous commit.
EOF
)"
```

**Controller post-task verify:**
```bash
git log -1 --format='%H %s'    # confirm commit landed
git show --stat HEAD           # confirm only CHANGELOG.md changed
git log --oneline -5           # full branch state — should be: spec, plan, command, changelog (4 commits ahead of main)
```

---

## Post-task: open the PR

After Task 2 commits cleanly:

1. Push the branch:
   ```bash
   git push -u origin feat/port-resume-initiative-command
   ```

2. Create the PR via `gh pr create` against `maxdimitrov/agent-issue-tracker` `main`. Title: `Phase 3 (#20): port /resume-initiative command`. Body follows the shape of PR #19 (summary, files, decisions settled in brainstorm, transforms applied, behaviour-change-zero, test plan with the static acceptance checklist marked, `Closes #20`, `Parent epic: maxdimitrov/trading-bot#153`).

3. Wait for merge. After merge, update parent epic `#153` Status block:
   - `Phase: Phase 2 · 6/15` → `Phase 2/3 · 7/15 sub-issues closed` (or similar — Phase 3 has now started).
   - `Next up:` recompute: `agent-issue-tracker#15` is still open (Phase 2 skill-currency, write from scratch). Phase 3 has more sub-issues to file (`/tracker-init`, `/tracker-doctor`, Jira backend). Both Phase 2 and Phase 3 are now in-flight.
   - `## Children` list: append `[x] agent-issue-tracker#20 — Phase 3: port /resume-initiative command — closed YYYY-MM-DD via agent-issue-tracker PR #<N>`.
   - Append a Decision log entry summarizing the port: the task-list-mirror flip from fallback to canonical, the three ref shapes documented, the cross-repo case validated as a binding requirement.

   Use the read-modify-write pattern from `skills/initiative-tracking/SKILL.md`:
   ```bash
   gh issue view 153 --repo maxdimitrov/trading-bot --json body --jq .body > /tmp/epic-153.md
   # edit /tmp/epic-153.md in place
   gh issue edit 153 --repo maxdimitrov/trading-bot --body-file /tmp/epic-153.md
   ```

---

## Self-review (controller, after writing this plan)

**Spec coverage:**
- §1 Goal — covered by Task 1 Step 1.2 (output file structure).
- §2 Non-goals — out-of-scope items NOT addressed (correct).
- §3 Decisions table — all 10 decisions reflected in Task 1 Step 1.2 / 1.3 / 1.4.
- §4 Architecture — §4.1 (single file) reflected in Task 1; §4.2 (three operations) referenced in Step 1.3 transform table; §4.3 (three invocation modes) Step 1.2 item 8; §4.4 (three ref shapes) Step 1.2 item 8 + Step 1.4 grep gates; §4.5 (worktree CWD + branch-name caveat) Step 1.2 item 8 Mode 3; §4.6 (inline brainstorm handoff) Step 1.2 item 5 + item 8 Mode 3.
- §5.1 standard transforms — Step 1.3 transform table.
- §5.2 surgical transforms — Step 1.2 items 8 and 9.
- §5.3 failure modes — Step 1.2 item 10.
- §5.4 conventions block — Step 1.2 item 9.
- §5.5 frontmatter — Step 1.2 item 1.
- §6 acceptance — Step 1.4 grep gates + Step 2.3 final checklist.
- §7 verification — Step 1.4 + Step 2.3.
- §8 risks — mitigations baked into Step 1.4 (grep gates catch field-prefix divergence; cold-read review in PR).
- §9 open questions — deferred per spec (URL-form refs, per-backend sort, live cross-repo smoke).

**Placeholder scan:** none — every transform has explicit source/replacement, every grep is fully written, every commit message is in HEREDOC form, no "implement appropriately."

**Type consistency:** N/A — markdown-only, no types. The two operation names (`list_open_issues`, `view_issue`) appear consistently across the spec, plan, and grep gates.

**No drift:** Task 1 commit message matches the spec wording; Task 2 commit message matches the appended CHANGELOG line; both reference issue #20 and parent epic #153.

---

## Execution mode

Per project CLAUDE.md (`~/.claude/CLAUDE.md` "Plan execution" section), execution is always via `superpowers:subagent-driven-development`. Fresh subagent per task, two-stage spec-then-quality review.

For this plan: two subagent dispatches (Task 1, Task 2). Both can use the `haiku` model — the work is rule-driven transformation against an explicit transform table, no design decisions delegated. The controller verifies `git log -1 --format='%H %s'` and `git show --stat HEAD` after each subagent returns.
