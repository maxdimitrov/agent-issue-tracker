# Write `skill-currency` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `skills/skill-currency/SKILL.md` from scratch — a brand-new ~250-350-line tracker-agnostic skill that codifies the rule: when a PR changes API surface, the affected `.claude/skills/*.md` files MUST update in the same PR. The only new skill in v1 (the other four Phase 2 skills are ports). Closes Phase 2.

**Architecture:** Single new markdown file under `skills/skill-currency/` plus a one-line `CHANGELOG.md` append. No templates (this is a rule skill, not a filing skill — Non-goals §3). No backend modules, no commands, no helpers. Phase 1 (`#9`) landed the schema; Phase 2 (`#11`-`#14`) landed the four filing-shape siblings this skill cross-links to; Phase 3 (`#20`/`#22`/`#23`) shipped three commands; the v1.1 detector port (`agent-issue-tracker#2`) is the referenced enforcement helper.

**Tech Stack:** Markdown only. YAML frontmatter, `grep` for static acceptance gates. No code, no tests, no build step.

**Spec:** `docs/superpowers/specs/2026-05-27-write-skill-currency-skill-design.md` (committed pre-Task-1 on this branch as `4a74ec5`).

**Source:** None — write-from-scratch. The shape precedent is the four Phase 2 sibling skills on this plugin's `main`:

- `skills/bug-tracking/SKILL.md` (216 lines, PR #16)
- `skills/feature-request/SKILL.md` (239 lines, PR #17)
- `skills/followup-tracking/SKILL.md` (314 lines, PR #18)
- `skills/initiative-tracking/SKILL.md` (284 lines, PR #19)

The conceptual rule is the trading-bot project-level `CLAUDE.md` section "Skills are part of the deliverable", which this skill ports into portable methodology. Do NOT read trading-bot's CLAUDE.md as a literal source — the spec carries the rule verbatim in §5.4, and the spec is the binding source.

**Issue:** `agent-issue-tracker#15`. **Parent epic:** `maxdimitrov/trading-bot#153` (Phase 2 — closes Phase 2 on merge).

---

## Pre-task setup (controller, not a subagent task)

Before dispatching Task 1, the controller MUST:

1. Verify CWD is the worktree `f:/Claude/Projects/agent-issue-tracker/.worktrees/feat-skill-currency-skill/`.
2. Verify the branch is `feat/skill-currency-skill`.
3. Verify the spec is committed: `git log --oneline -3` shows the design spec landing on the branch as the first commit ahead of `main`.

No source-bytes retrieval step — this is write-from-scratch, not a port. The subagent receives the spec's binding sections (§4 decisions table, §5 skill structure, §6 CHANGELOG entry, §8 invariants) inline in the dispatch prompt; it does NOT have to read the spec end-to-end.

---

## File structure

| Path | Status | Responsibility |
|---|---|---|
| `skills/skill-currency/SKILL.md` | NEW (~250-350 lines) | The skill — markdown with YAML frontmatter, opening paragraph, block-quoted rule (within first ~30 lines), justification + escape hatch + application + retroactive-debt + verification + worked-example + cross-skill ergonomics + See-also footer |
| `CHANGELOG.md` | MODIFY (+1 line) | Append a Phase 2 entry under `[Unreleased]` → `### Added`, matching the four prior Phase 2 entry formats |

---

## Task 1: Author `skills/skill-currency/SKILL.md`

**Files:**
- Create: `skills/skill-currency/SKILL.md`
- Reference (read-only, for the design): `docs/superpowers/specs/2026-05-27-write-skill-currency-skill-design.md`
- Reference (read-only, for the shape precedent — pick ONE to mirror tone, prefer `feature-request`): `skills/feature-request/SKILL.md`
- Reference (read-only, for cross-link sibling phrasings): `skills/bug-tracking/SKILL.md`, `skills/followup-tracking/SKILL.md`

**Subagent model recommendation:** `haiku` is fine — the work is rule-driven authoring against an explicit section-by-section design. No design decisions delegated (those are locked in the spec).

**Subagent context to include in prompt verbatim:** spec §3 Non-goals, §4 Decisions table, §5 Skill structure (all sub-sections), §7 Failure modes considered, §8 Invariants. Also include the LITERAL rule string (spec §5.4 block-quote) and the EIGHT API-surface category strings (spec §5.6) so there is no paraphrase risk.

### Step 1.1: Read the shape precedent

Read `skills/feature-request/SKILL.md` end-to-end. It is the closest tonal match — single-skill, descriptive frontmatter, second-person instructional, "When to file" / "Application" rhythm. Also skim `skills/bug-tracking/SKILL.md` for the bug-vs-feature disambig table convention (the format of the cross-skill ergonomics block in this skill mirrors it).

Do NOT read the design spec end-to-end — the dispatch prompt carries the binding sections inline.

### Step 1.2: Author the new file — section by section

Write `skills/skill-currency/SKILL.md` from scratch, following this ordered structure (mirrors spec §5):

1. **YAML frontmatter.** `name: skill-currency` + multi-line `description: >-` scalar. Description text per spec §5.1; include ALL of these trigger phrases (a reviewer greps for them):
   - "skill currency"
   - "is the skill stale"
   - "what skills does this change"
   - "skills are part of the deliverable"
   - "do I need to update the skills"
   - "documentation rot"

2. **Title.** `# Skill Currency — Methodology as Deliverable`

3. **Opening paragraph.** One paragraph (3-5 sentences) framing the claim: methodology layer IS the deliverable, not documentation. Agents read skills before generating advice. Skill that lies is worse than no skill.

4. **The rule.** Heading `## The rule`. Block-quoted (`> ...`), verbatim from spec §5.4. The full string is:

   > When a PR changes API surface — new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file — the affected `.claude/skills/*.md` files MUST update in the same PR. A stale skill misleads every future agent that touches the area.

   The em-dash (`—`) characters are intentional. Reviewer will grep for `MUST update in the same PR` and the eight category strings byte-for-byte.

5. **Why a stale skill is dangerous.** Heading `## Why a stale skill is dangerous`. Four concrete failure-mode bullets (per spec §5.5). Each bullet is one sentence, present-tense, naming a specific way the rot manifests (function no longer exists, retired convention, renamed column, compounding cost).

6. **When the rule fires.** Heading `## When the rule fires`. Bullet list with all eight categories, named EXACTLY (do not paraphrase — these strings are gated):
   - `New module`
   - `New public function`
   - `New CLI subcommand`
   - `New env var`
   - `New DB table or schema-version bump`
   - `New HTTP route`
   - `Changed function signature`
   - `Removed function or file`

   Plus a closing line per spec §5.6: "inclusive, not exclusive — when in doubt, treat it as in scope."

7. **When it does NOT fire (escape hatch).** Heading `## When it does NOT fire — the escape hatch`. Three bullets (typo / version bump / one-line patch with no API surface change) plus the discriminator question: **"Would an agent in a future session need to know this changed?"** Closed-form list, narrow on purpose.

8. **Application — before opening the PR.** Heading `## Application — before opening the PR`. Three numbered steps per spec §5.8:
   - Identify the affected skills (grep changed files against `.claude/skills/`).
   - Decide: update existing skill, write new skill, or escape-hatch.
   - Fold skill commits into the same PR.

9. **New subsystem gets a new skill.** Heading `## New subsystem gets a new skill`. Per spec §5.9 — generic framing ("a single-source-of-truth module deserves a single-source-of-truth skill"). NO specific example names (no `execution-service-architecture`, no `reserve-ledger`, etc. — those are trading-bot identifiers).

10. **Issue acceptance criteria carry-through.** Heading `## Issue acceptance criteria carry-through`. Per spec §5.10. Include the sample acceptance bullet shapes in a fenced code block:

    ```
    - [ ] `skills/<subsystem>/SKILL.md` updated with the new <thing>.
    - [ ] `skills/<sibling>/SKILL.md` updated where it referenced the removed <thing>.
    ```

11. **Retroactive debt.** Heading `## Retroactive debt`. Per spec §5.11 — file a follow-up issue via `followup-tracking` when the rule was missed retroactively. Do NOT silently fix the drift in the current PR's scope.

12. **Verification — manual today, automated later.** Heading `## Verification — manual today, automated later`. Per spec §5.12. Two-paragraph block:
    - Today's manual path (grep changed files' identifiers against `.claude/skills/`).
    - Tomorrow's automated path: name `agent-issue-tracker#2` (v1.1 follow-on) as the detector port. Until it ships, honor-system.

13. **Worked example.** Heading `## Worked example`. Per spec §5.13. ONE generic example using `myproj-cli build --dry-run` placeholders. Format: scenario paragraph → "Affected skill" line → "What lands in the same PR" numbered list (code item + skill item) → reviewer-perspective close. NO `trading-bot`, `dca`, `IBKR`, etc. (acceptance gates this with grep).

14. **Cross-skill ergonomics.** Heading `## Cross-skill ergonomics`. Three bullets per spec §5.14:
    - `feature-request` — file when you need a new skill.
    - `bug-tracking` — file when a skill is wrong, out of date, or misleading.
    - `followup-tracking` — file when scope deferred from this PR includes a skill update.

    NOTE: `initiative-tracking` is NOT in this list. Spec §4 decision table is explicit.

15. **See-also footer.** Closing line matching the four siblings' "See also:" format. Names `bug-tracking`, `feature-request`, `followup-tracking` — NOT `initiative-tracking`.

### Step 1.3: Length self-check

Run `wc -l skills/skill-currency/SKILL.md`. Expected range: 200-400, target ~250-350 per spec §4 decision row "Length target". If under 200, sections 5/8/13 are most likely too thin — flesh them out. If over 400, sections 5/13 are first to trim (elaboration, not load-bearing rule).

### Step 1.4: Static acceptance gates (subagent runs these before reporting done)

All these must PASS before the subagent reports completion. Each command must be run from the worktree root (`f:/Claude/Projects/agent-issue-tracker/.worktrees/feat-skill-currency-skill/`):

```bash
# Gate 1: file exists and is in range
test -f skills/skill-currency/SKILL.md
LINES=$(wc -l < skills/skill-currency/SKILL.md)
[ "$LINES" -ge 200 ] && [ "$LINES" -le 400 ] || { echo "LENGTH FAIL: $LINES"; exit 1; }

# Gate 2: literal rule present
grep -q "MUST update in the same PR" skills/skill-currency/SKILL.md || { echo "RULE STRING MISSING"; exit 1; }

# Gate 3: all eight API-surface categories enumerated
for kind in "New module" "New public function" "New CLI subcommand" \
            "New env var" "New DB table" "New HTTP route" \
            "Changed function signature" "Removed function"; do
  grep -qi "$kind" skills/skill-currency/SKILL.md || { echo "MISSING category: $kind"; exit 1; }
done

# Gate 4: escape hatch language present
grep -qi "Would an agent in a future session need to know this changed" skills/skill-currency/SKILL.md \
  || { echo "ESCAPE HATCH DISCRIMINATOR MISSING"; exit 1; }

# Gate 5: cross-links to three siblings (each at least once)
for sib in bug-tracking feature-request followup-tracking; do
  grep -q "$sib" skills/skill-currency/SKILL.md || { echo "MISSING cross-link: $sib"; exit 1; }
done

# Gate 6: v1.1 detector reference
grep -q "agent-issue-tracker#2" skills/skill-currency/SKILL.md || { echo "MISSING v1.1 detector ref"; exit 1; }

# Gate 7: no trading-bot identifiers leak through
LEAKS=$(grep -rE "maxdimitrov/trading-bot|trading-bot|dca-router|ic-memo-framework|dashboard-maintenance|atr-stops|reserve-ledger|execution-service-architecture|proposal-service-architecture|positions_meta|watchlist_items|claude_tasks|IBKR" skills/skill-currency/ 2>&1 | grep -v "^skills/skill-currency/$" || true)
[ -z "$LEAKS" ] || { echo "LEAK FOUND:"; echo "$LEAKS"; exit 1; }

# Gate 8: initiative-tracking NOT cross-linked from See-also footer
# (it MAY appear in the body as a passing reference, but the See-also line must list only three)
tail -5 skills/skill-currency/SKILL.md | grep -q "initiative-tracking" && { echo "INITIATIVE-TRACKING IN SEE-ALSO FOOTER (per spec §4 it should NOT be)"; exit 1; } || true

echo "All gates pass."
```

### Step 1.5: Commit

```bash
git add skills/skill-currency/SKILL.md
git commit -m "feat(skills): add skill-currency skill (#15)"
```

Subagent reports: file path, line count, all-gates-pass confirmation, commit SHA.

---

## Task 2: Append CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md` (append one line under `[Unreleased]` → `### Added`)

**Subagent model recommendation:** `haiku` is sufficient. The entry shape is locked in spec §6.

### Step 2.1: Read current CHANGELOG

Read `CHANGELOG.md`. Find the `[Unreleased]` → `### Added` block. The last existing entry (top of the section) is the Phase 3 `#23` `/tracker-doctor` line — the new entry goes AFTER it (chronological order: oldest first, newest last within `Added`).

### Step 2.2: Append entry

Append this line (verbatim, after the existing Phase 3 (#23) bullet):

```
- Phase 2 (#15): skill-currency skill — written from scratch (only new skill in v1, not a port). Codifies the rule that when a PR changes API surface (new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file), the affected `.claude/skills/*.md` files MUST update in the same PR. Cross-links the three filing-shape siblings (`bug-tracking`, `feature-request`, `followup-tracking`); references the v1.1 enforcement helper (`agent-issue-tracker#2`, port of `/audit-skills` + detector library) as the deferred automated path — until then, the rule is honor-system. Closes Phase 2 (all five skills shipped).
```

Use `Edit` with `old_string` set to the last existing bullet (Phase 3 #23 line) and `new_string` set to that same bullet + `\n` + the new bullet. This is the standard append pattern for CHANGELOGs in this plugin.

### Step 2.3: Static check

```bash
grep -q "Phase 2 (#15): skill-currency" CHANGELOG.md || { echo "CHANGELOG entry missing"; exit 1; }
grep -c "Phase 2" CHANGELOG.md
# Expected: 5 (Phase 2 (#11), (#12), (#13), (#14), (#15))
```

### Step 2.4: Commit

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note skill-currency under Phase 2 (#15)"
```

Subagent reports: line added, the two grep results, commit SHA.

---

## Controller-side cold-read review (after Task 2 returns)

After both tasks return, the controller (NOT a subagent) runs a cold-read pass:

1. Read `skills/skill-currency/SKILL.md` end-to-end from top, as if the file were unfamiliar.
2. Verify the rule lands in the first ~30 lines (target: by line 25 after frontmatter ends).
3. Verify the escape hatch reads narrowly (three closed-form bullets + discriminator question).
4. Verify the worked example reads generically — no trading-bot smell. Specifically: are `myproj-cli` / `build` / `--dry-run` the placeholder names? Is the affected-skill name `myproj-cli-architecture` (or another `myproj-*` placeholder)? Does any sentence read like it was originally about trading-bot and incompletely de-domain'd?
5. Verify cross-link discipline: `initiative-tracking` is NOT in the See-also footer or the cross-skill ergonomics block.
6. Verify length: `wc -l skills/skill-currency/SKILL.md` returns 200-400.
7. Verify CHANGELOG: `grep "Phase 2 (#15)" CHANGELOG.md` matches; the entry sits at the bottom of the `### Added` block.

If any check surfaces a finding, the controller issues a precisely-scoped inline fix-up commit (`fix(skills): <one-line>`) — same precedent as the en-dash fix-up on `#14` (commit `df4836d`) and the Phase 3 fix-ups on `#20` / `#22` / `#23`.

The PR is opened ONLY after cold-read returns clean.

---

## Task 3 (controller, not a subagent): open the PR

After both subagent tasks have returned and cold-read is clean:

### Step 3.1: Push

```bash
git push -u origin feat/skill-currency-skill
```

### Step 3.2: Open the PR via `--body-file`

Write a PR body to a temp file (`.tmp_pr_body.md` at the worktree root, already-gitignored). The body must include:

- One-paragraph summary: closes Phase 2 by shipping the only write-from-scratch skill in the phase.
- "What this PR ships" section: the new skill + the CHANGELOG entry.
- "What this PR does NOT ship" section: detector port (`agent-issue-tracker#2`), trading-bot CLAUDE.md edit (Phase 5), reverse cross-links from the four siblings.
- "Verify" section: line-count, the eight grep gates, leak check.
- `Closes #15`.
- `Parent epic: maxdimitrov/trading-bot#153 — closes Phase 2 (all five skills shipped).`

Then:

```bash
gh pr create --repo maxdimitrov/agent-issue-tracker \
  --base main \
  --head feat/skill-currency-skill \
  --title "Phase 2 (#15): write skill-currency skill from scratch" \
  --body-file .tmp_pr_body.md
```

Do NOT use a heredoc here-string for the body — past Phase 2/3 PRs hit apostrophe-escaping issues with `gh pr create --body` and HEREDOC on Windows. `--body-file` is the established workaround.

### Step 3.3: Confirm PR opened

```bash
gh pr view <PR-NUMBER> --repo maxdimitrov/agent-issue-tracker --json number,state,headRefName,baseRefName,title
# Expected: state OPEN, headRefName feat/skill-currency-skill, baseRefName main
```

Report PR URL.

---

## Task 4 (controller): auto-merge

After Task 3 confirms PR is open:

```bash
gh pr merge <PR-NUMBER> --repo maxdimitrov/agent-issue-tracker --squash --delete-branch
```

If `--delete-branch` errors (this has happened on prior PRs when GH's branch-deletion permission is glitchy), drop the flag and delete manually:

```bash
gh pr merge <PR-NUMBER> --repo maxdimitrov/agent-issue-tracker --squash
git push origin --delete feat/skill-currency-skill
```

Capture the squash-commit SHA from the merge output (or via `gh pr view <PR> --json mergeCommit --jq .mergeCommit.oid`).

Then locally on the controller's primary clone (NOT the worktree):

```bash
cd f:/Claude/Projects/agent-issue-tracker
git fetch origin
git checkout main
git pull --ff-only origin main
# Verify the squash commit lands:
git log --oneline -3
```

Clean up the worktree:

```bash
git worktree remove .worktrees/feat-skill-currency-skill --force
git branch -D feat/skill-currency-skill  # local branch
```

(The `--force` is for the worktree gitignored `.tmp_pr_body.md`; harmless because the branch is already merged.)

---

## Task 5 (controller): update epic #153 Status block

After Task 4 confirms merge, update the epic on `maxdimitrov/trading-bot`:

### Step 5.1: Fetch current body

```bash
gh issue view 153 --repo maxdimitrov/trading-bot --json body --jq .body > .tmp_epic_153_body.md
```

(Run from any working directory; the file lands in CWD.)

### Step 5.2: Edit the body

Three edits:

1. **Phase line.** Change `Phase 2/3 · 9/15 sub-issues closed` to `Phase 2/3 · 10/15 sub-issues closed`. Update the parenthetical context to reflect that `#15` just merged and Phase 2 is now COMPLETE.

2. **Next up line.** With `#15` closed, Phase 2 is done. The remaining open child is `#24` (`backends/jira.md` — last Phase 3 deliverable). Set the Next-up line to:

   ```
   - **Next up:** `agent-issue-tracker#24` — Phase 3: write `backends/jira.md` (Atlassian Remote MCP) — last Phase 3 deliverable; Phase 2 is now COMPLETE (all five skills shipped).
   ```

3. **Last updated line.** Change to `2026-05-27`.

4. **Children task-list mirror.** Flip `- [ ]` → `- [x]` for the `#15` line. Append `— closed 2026-05-27 via agent-issue-tracker PR #<PR-NUMBER> (squash-commit <SHA>)` to match the format of the other closed children.

5. **Decision log.** Append a new dated entry (format matches the prior entries — terse, one paragraph, names the PR + squash-commit SHA + end state). Approximate shape:

   ```
   - **2026-05-27** — `#15` (write skill-currency skill from scratch — last Phase 2 deliverable, only write-from-scratch sub-issue in the phase) merged via `agent-issue-tracker` PR #<PR-NUMBER> (squash-commit `<SHA>`). Three-commit feature branch (spec → plan → SKILL+CHANGELOG) shipped as a pure-addition PR (+<NNN> / -0 across <N> files). End state on `agent-issue-tracker` main: `skills/skill-currency/SKILL.md` (<NNN> lines, frontmatter + N sections, the block-quoted rule lands in the first ~30 lines per spec §4 decision table; 8 API-surface categories enumerated by name; 3 sibling cross-links — bug-tracking, feature-request, followup-tracking — `initiative-tracking` deliberately NOT cross-linked per spec §4; worked example fully generic with `myproj-cli` placeholders; v1.1 detector ref `agent-issue-tracker#2` cited as honor-system-until-shipped). CHANGELOG `[Unreleased] → Added` carries the Phase 2 (#15) entry as the fifth and last Phase 2 line. Phase 2 is now COMPLETE (4 ports + 1 write-from-scratch all shipped). Phase 3 is 3/4 done; only `#24` (`backends/jira.md`) remains. Phase 2/3 is now 10/15 closed; next-up flips to `agent-issue-tracker#24` (closes Phase 3 when it lands).
   ```

6. **Resume from here paragraph.** Update at the bottom — replace the two-open-children language with "Phase 2 is complete; one Phase 3 sub-issue remains (`#24`)".

### Step 5.3: Commit the body

```bash
gh issue edit 153 --repo maxdimitrov/trading-bot --body-file .tmp_epic_153_body.md
```

### Step 5.4: Verify

```bash
gh issue view 153 --repo maxdimitrov/trading-bot --json body --jq .body | head -20
# Verify the Status block now shows 10/15 and Next up: #24
```

Clean up: `rm .tmp_epic_153_body.md`.

---

## Task 6 (controller): close issue #15

Closing the issue is normally automatic from the `Closes #15` line in the PR body. If GitHub didn't auto-close (cross-repo PR refs sometimes flake — though `Closes #15` against an issue in the SAME repo as the PR works reliably; the issue is on `agent-issue-tracker`, same repo as the PR), close manually:

```bash
gh issue close 15 --repo maxdimitrov/agent-issue-tracker --reason completed
```

Verify:

```bash
gh issue view 15 --repo maxdimitrov/agent-issue-tracker --json state --jq .state
# Expected: CLOSED
```

---

## Final report

Controller emits a final summary message to the operator with:

- **PR URL:** `https://github.com/maxdimitrov/agent-issue-tracker/pull/<N>`
- **Squash-commit SHA:** `<sha>` on `agent-issue-tracker` `main`
- **Issue state:** `agent-issue-tracker#15` CLOSED
- **Epic state:** `maxdimitrov/trading-bot#153` updated — Phase 2/3 · 10/15 closed; Next-up: `agent-issue-tracker#24` (last Phase 3 deliverable)
- **Phase 2 status:** COMPLETE (5/5 skills shipped — 4 ports + 1 write-from-scratch)
- **Files shipped:** `skills/skill-currency/SKILL.md` (~<NNN> lines), `docs/superpowers/specs/2026-05-27-write-skill-currency-skill-design.md`, `docs/superpowers/plans/2026-05-27-write-skill-currency-skill.md`, `CHANGELOG.md` (+1 line)
- **What's NOT in v1:** detector port (`agent-issue-tracker#2`), trading-bot CLAUDE.md edit (Phase 5)
- **Next session:** `/resume-initiative 153` → next-up `agent-issue-tracker#24`.

---

## Risk register (controller awareness)

- **En-dash regression risk.** Multiple prior PRs (`#14`, `#19`, `#22`) hit en-dash → ASCII-hyphen drift in plan-or-CHANGELOG content that the subagent faithfully transcribed. The CHANGELOG entry in Task 2 has multiple `—` characters. The subagent MUST paste those source bytes through the Write tool without retyping. The cold-read step §"Verify the rule lands ..." catches this; if the rule's em-dashes drop to `--`, fix inline.
- **Trading-bot identifier leak.** Highest-likelihood failure mode (the prompt necessarily references trading-bot as the conceptual source). The subagent has explicit out-of-scope guidance and the gate-7 grep; controller cold-read step §4 is the second line of defense.
- **`initiative-tracking` accidental cross-link.** Authoring agent's natural instinct is "if there are four siblings, cross-link all four." Spec §4 decision table is explicit; the subagent prompt cites it; gate-8 catches it in the See-also footer; cold-read step §5 catches body-text occurrences.
- **Length overrun.** Risk if the worked example or §5.5 rationale block sprawls. Acceptance gate is 200-400; spec target is ~250-350. The subagent should self-check at step 1.3 and trim §5.5 or §5.13 if over.
- **PR auto-merge race.** The epic-update step depends on the merge having landed. Verify merge state (`gh pr view <N> --json state`) shows `MERGED` before editing the epic body — same precaution that bit the `feedback_branch_staleness_pre_pr_check` precedent.
- **Worktree cleanup before epic update.** Do NOT remove the worktree until after the epic Status-block edit lands — the `.tmp_pr_body.md` and any controller scratch lives in the worktree. Order is: merge → verify merge → epic edit → clean up worktree.

---

## Definition of done

- `skills/skill-currency/SKILL.md` exists on `agent-issue-tracker` `main`, 200-400 lines, all eight static gates from Step 1.4 pass.
- `CHANGELOG.md` on `main` carries the Phase 2 (#15) entry as the fifth Phase 2 bullet.
- PR is merged via squash; the feature branch is deleted both remotely and locally.
- The local `agent-issue-tracker` working clone is on `main`, up to date with origin, no leftover worktree.
- Issue `agent-issue-tracker#15` is CLOSED.
- Epic `maxdimitrov/trading-bot#153` body shows Phase 2/3 · 10/15 closed, Next-up `agent-issue-tracker#24`, Last updated `2026-05-27`, the `#15` row in `## Children` is checked, and the Decision log has the new dated entry.
- Final report message sent to operator with PR URL, squash SHA, epic link, and explicit Phase-2-COMPLETE statement.
