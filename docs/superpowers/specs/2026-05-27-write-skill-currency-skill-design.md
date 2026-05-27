# Write `skill-currency` Skill — Design

**Date:** 2026-05-27
**Tracker:** [`maxdimitrov/agent-issue-tracker#15`](https://github.com/maxdimitrov/agent-issue-tracker/issues/15)
**Parent epic:** [`maxdimitrov/trading-bot#153`](https://github.com/maxdimitrov/trading-bot/issues/153)
**Parent design spec:** [`docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) on `maxdimitrov/trading-bot` `main` — sections §6.2 (`skill-currency/SKILL.md (NEW)`), §14 (`skill-currency is the genuinely new skill in v1`).

## 1. Problem

The other four Phase 2 skills (`bug-tracking`, `feature-request`, `followup-tracking`, `initiative-tracking`) teach consumers how to *file* issues. They make the methodology layer easy to extend with new issues. They do NOT teach consumers how to keep that methodology layer *current*.

In any project that uses this plugin, the methodology layer is `.claude/skills/*/SKILL.md`. Agents read these skills before generating advice in a subsystem. The skills are the source of truth: they encode subsystem conventions, file paths, invariants, "this is how we do X here." When the codebase evolves (new module, renamed function, dropped env var, schema bump) and the skill does NOT, the skill starts lying. Every future agent that loads it ships work against an obsolete contract.

This is a real failure mode — not theoretical. Projects that adopt agent-driven workflows accumulate skill-drift the same way they accumulate stale comments: nobody is on the hook for keeping it fresh, so it rots, and the cost is paid silently by downstream agent runs.

The plugin needs a fifth skill that codifies the discipline: **when API surface changes, the affected skills change in the same PR**. This is what trading-bot's project-level CLAUDE.md "Skills are part of the deliverable" section says, but said *once*, at the project level, where it doesn't travel. Lifting it into the plugin makes it portable methodology any consumer can adopt.

## 2. Goal

Ship `skills/skill-currency/SKILL.md` — a brand-new ~250-350-line tracker-agnostic skill that:

- States the rule prominently and unambiguously: API-surface changes ship skill updates in the same PR.
- Enumerates the API-surface change categories (new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file).
- Names the trivial-work escape hatch (typo / version bump / one-line patch).
- Explains *why* a stale skill is dangerous (agents load skills, follow them, ship broken patches when the skill is lying).
- Cross-links the three filing-shape siblings (`bug-tracking`, `feature-request`, `followup-tracking`).
- References the v1.1 enforcement helper (`agent-issue-tracker#2` — port of `/audit-skills` + detector library) as the automated path; explicit that until it ships, the rule is honor-system.
- Carries a worked example with **generic** placeholder names (no `maxdimitrov/trading-bot`, no trading-bot-specific skill names, file paths, or DB tables).

When `skill-currency` is loaded, an agent about to open an API-changing PR has a checklist for "what skills did I just affect, and what do I need to commit on this same branch."

## 3. Non-goals (explicit)

- **The `/audit-skills` slash command and `scripts/audit/` detector library.** v1 ships prose only. The detector port is filed against this repo as `agent-issue-tracker#2` (v1.1). The skill cross-links it as deferred enforcement; it does NOT inline the detector code, glob list, or doc-corpus configuration.
- **The other four skills' content.** Each is its own Phase 2 sub-issue (`#11`/`#12`/`#13`/`#14`). This skill cross-links them; it does not duplicate their substance.
- **A `templates/skill-currency-body.md` artifact.** `skill-currency` is a *rule* skill, not a *filing* skill. It dispatches to no backend operation directly; it tells other skills (and humans) when to act. The four filing-shape siblings own the template artifacts.
- **A new backend interface operation.** The skill consumes the same backend dispatch the four filing siblings consume (via cross-link to `feature-request` for "I need a new skill" and `bug-tracking` for "a skill is wrong"). No `backends/_interface.md` change.
- **Validating that already-shipped PRs honored the rule retroactively.** That is a one-shot audit, not a recurring discipline; the prose names the retroactive case and routes it through `followup-tracking`, but the audit itself is outside the skill's scope.
- **Hooks, automation, or CI gates.** The rule is honor-system until the v1.1 detector lands. The skill says so explicitly.
- **A trading-bot CLAUDE.md edit.** Phase 5 (dogfood cutover, parent epic) is where trading-bot's CLAUDE.md cites this skill by name and lets it carry the methodology. Out of scope for this issue.

## 4. Architecture decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| File shape | Single markdown file: `skills/skill-currency/SKILL.md` | Mirrors the four filing-shape siblings. No template artifact (see Non-goals); no helper scripts. |
| Length target | ~250-350 lines | Parent spec §6.2 names this range explicitly. Acceptance allows 200-400. Less risks under-specifying the rule's edges; more risks bloat for a rule that is fundamentally one sentence + justification + application. |
| Rule placement | Block-quoted within the first ~30 lines after frontmatter | The rule is the load-bearing core; everything else is justification, application, edge cases. Burying it loses agents who load the skill mid-task. |
| Rule wording | Verbatim from parent spec §6.2 | The rule has been iterated on against real PRs in trading-bot. The spec phrasing is the lived experience. Don't paraphrase what you don't first understand (issue `#15` Notes). |
| API-surface enumeration | All eight categories, verbatim phrasing | Acceptance criterion §"Skill enumerates API-surface change categories" requires the full list. Reviewers (and the v1.1 detector) parse this enumeration. |
| Escape hatch | Same shape as sibling skills' escape hatches (typo / version bump / one-line patch) | Consistency with `bug-tracking`'s "do not file when ... you are fixing it right now" and `feature-request`'s analogous list. The test phrase ("would an agent in a future session need to know this changed?") is the discriminator. |
| Worked example | Single generic example using `myproj-cli` placeholders | Issue `#15` Sketch §3 calls this out. Acceptance includes a no-trading-bot-mention gate. One example is enough; the rule is general, not example-specific. |
| Cross-link targets | `bug-tracking`, `feature-request`, `followup-tracking` | Issue `#15` Acceptance requires all three. `initiative-tracking` is NOT cross-linked from skill-currency body — initiatives are about *coordinating multi-issue work*, not about the methodology layer's freshness. (Initiatives may *contain* sub-issues that change API surface, but that's just the rule firing per-sub-issue.) |
| v1.1 detector reference | One paragraph naming `agent-issue-tracker#2` and the honor-system framing | Per spec §6.2: "The v1.1 detector port (`/audit-skills` + `scripts/audit/`) is referenced as 'an enforcement helper tracked as a follow-on' — not part of v1." |
| Tracker-agnostic discipline | No `gh`, no `Closes #N`, no `maxdimitrov/...` references in the SKILL body | Same de-trading-bot-ification mapping as the four siblings. The only literal repo-qualified ref in the file is `agent-issue-tracker#2` (and that is *this* repo — the plugin's own follow-up tracker). |
| Frontmatter trigger phrases | Per issue `#15` Sketch §6 | Drives CC's matcher fires the skill at the right moments (PR-open time, "do I need to update skills" questions). |
| Issue-acceptance carry-through | Named explicitly | Issue acceptance criteria for API-changing issues MUST list the specific skills to update. This is a reviewer-visible gate, not aspiration. The filing skills (`bug-tracking`, `feature-request`) house the body template; this skill says "when you fill that template for API-changing work, the Acceptance section names the skills." |
| New DB-canonical subsystem clause | Kept, generalized | Trading-bot CLAUDE.md's "for any new DB-canonical subsystem, a new `<subsystem>-architecture` skill MUST exist" is a real lived rule. Generalized: "a new single-source-of-truth module deserves a new single-source-of-truth skill." No trading-bot-specific examples (no `execution-service-architecture`, `reserve-ledger`, etc.). |

## 5. Skill structure

Sections in order. Heading levels match the sibling skills (`#` for title, `##` for top-level sections, `###` for sub-sections where needed). The skill body keeps the same prose tone as the four filing siblings — terse, dispatch-through-contract, second-person instructional.

### 5.1 Frontmatter (YAML)

Single-line scalar wrapped in `>-` (matches the four siblings). The `description:` value carries the trigger phrases enumerated in issue `#15` Sketch §6 plus the standard "Use when ..." framing. Approximate shape:

```yaml
---
name: skill-currency
description: >-
  How the methodology layer (`.claude/skills/*/SKILL.md`) stays current
  as the codebase evolves — codifies the rule that when a PR changes
  API surface (new module, new public function, new CLI subcommand,
  new env var, new DB table or schema-version bump, new HTTP route,
  changed function signature, removed function/file), the affected
  skills MUST update in the same PR. A stale skill misleads every
  future agent that loads it. Use this skill before opening a PR for
  any API-changing change; when an agent asks "what skills does this
  change?" or "is this skill still current?"; when filing an issue
  whose acceptance criteria depend on a skill update being shipped
  alongside the code; whenever you notice a skill referencing a
  function, file, table, or env var that no longer exists. Sibling
  skills bug-tracking, feature-request, and followup-tracking cover
  the issue shapes that this rule routes through: "a skill is wrong"
  is a bug; "I need a new skill" is a feature; "the skill update was
  deferred from an in-flight PR" is a follow-up. Covers the rule
  itself, the eight API-surface change categories, the trivial-work
  escape hatch, the application checklist (before opening the PR),
  issue acceptance criteria carry-through, the new-subsystem-gets-a-
  new-skill case, retroactive debt routing, and the deferred v1.1
  enforcement helper (`agent-issue-tracker#2`).
---
```

(Final wording during authoring — keep the trigger-phrase list intact.)

### 5.2 Title

`# Skill Currency — Methodology as Deliverable` (matches the sibling-skill title convention: `Bug Tracking — Issues as Agent Prompts`, etc.).

### 5.3 Opening paragraph

One paragraph framing the load-bearing claim: **the methodology layer IS the deliverable, not "documentation."** Agents read skills before generating advice. A skill that lies is worse than no skill — it actively misleads. The skill commits ship with the code that made them necessary, or they don't ship at all.

### 5.4 The rule

Block-quoted, prominently formatted (within first 30 lines after frontmatter). Verbatim phrasing from parent spec §6.2:

> When a PR changes API surface — new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file — the affected `.claude/skills/*.md` files MUST update in the same PR. A stale skill misleads every future agent that touches the area.

### 5.5 Why a stale skill is dangerous

Concrete failure mode, not abstract. One worked sentence each:

- An agent loads the skill at the start of a task. The skill names a function that no longer exists. The agent's first edit references the dead function and ships a broken patch.
- An agent loads the skill and follows its convention. The convention was retired three weeks ago. The PR review surfaces "we don't do that anymore" — wasted run.
- An agent reads a skill that names a DB table column that has been renamed. The agent's SQL references the old name. Tests pass (the migration hasn't dropped the column yet); production fails.
- The compounding cost: every future agent loads the stale skill until someone notices. The cost is paid silently by every downstream run, not by the PR that introduced the drift.

### 5.6 When the rule fires (API surface defined)

Bullet list — all eight categories, named explicitly:

- New module (new top-level package / namespace).
- New public function (newly exported, importable, callable from outside the module).
- New CLI subcommand (new verb under an existing CLI, or a new CLI binary).
- New env var (new key the code reads from `os.environ` / `process.env` / equivalent).
- New DB table or schema-version bump (new table, new column on an existing table, version migration).
- New HTTP route (new endpoint path + method on the public API surface).
- Changed function signature (parameters added/removed/reordered, return type changed, in any *exported* function).
- Removed function or file (deletion of any of the above — the absence is itself a change other agents must know about).

The list is **inclusive, not exclusive** — the rule fires on these *and* on anything reasonably analogous (e.g., a new GraphQL mutation, a new message queue topic, a new event payload field). When in doubt, treat it as in scope.

### 5.7 When it does NOT fire (trivial-work escape hatch)

Same shape as `bug-tracking`'s "do not file" list. Skill updates are NOT required for:

- Typos in source comments, error messages, or docstrings that don't change a skill-documented contract.
- Version bumps that don't change API surface (`requirements.txt` minor version bump, `package.json` patch bump).
- One-line patches with no API surface change — a literal renaming of an internal helper, a `// eslint-disable` line, a config-only change that no skill references.

The discriminator is the question: **"Would an agent in a future session need to know this changed?"** If yes → update the skill. If no → ship it. The escape hatch is narrow on purpose; the cost of a missed skill update is paid downstream.

### 5.8 Application — before opening the PR

Three-step checklist:

1. **Identify the affected skills.** For each file you changed, search the skill prose for references — function names, file paths, table names, env vars, CLI subcommand names. Any matching skill must be reviewed.
2. **Decide: update existing skill, write new skill, or escape-hatch.**
   - The change touches a subsystem with an existing `*-architecture` or domain skill → update that skill.
   - The change introduces a brand-new subsystem (new module + new accessors + new CLI verbs) → write a new skill. See §5.9.
   - The change is trivial per §5.7 → escape hatch.
3. **Fold the skill commit(s) into the same PR.** Not a follow-up. A reviewer should see the code diff and the skill diff side-by-side. The PR review is the gate where the skill update gets scrutinized; landing the skill in a separate PR loses that scrutiny.

### 5.9 New subsystem gets a new skill

Specific case worth calling out. When a PR introduces a new *single-source-of-truth module* — a new Python module that owns the writes to a DB table, a new service that owns a contract, a new CLI verb family — a new `<subsystem>` skill MUST exist alongside.

Generic shape: a single-source-of-truth module deserves a single-source-of-truth skill. The module is where the code lives; the skill is where the *invariants, the why, and the operator contract* live. Without the skill, every future agent has to re-derive the invariants from the code, and most won't bother.

(Do NOT name specific examples — the rule is general. Different consumer projects will have different architectures.)

### 5.10 Issue acceptance criteria carry-through

When filing an API-changing issue via `bug-tracking` or `feature-request`, the issue's **Acceptance** section MUST list the specific skills to create or update. The filing-shape skills house the body template; this skill says "for API-changing work, the Acceptance section names skills, not just code." Sample bullet shapes:

```
- [ ] `skills/<subsystem>/SKILL.md` updated with the new <thing>.
- [ ] `skills/<sibling>/SKILL.md` updated where it referenced the removed <thing>.
```

This is a reviewer-visible gate, not aspiration. A PR that lands the code change without the skill commit fails the issue acceptance — reviewers should treat it as a blocker.

### 5.11 Retroactive debt

If you discover the rule was missed in a prior shipped PR — a skill that should have been updated, wasn't — file a follow-up issue via `followup-tracking`. The follow-up's Parent block points at the PR that missed the update; the What's already done block names what landed; the deferred work is the skill update.

Do NOT silently fix the drift in your current PR's scope — that hides the cost. File the follow-up; surface that the rule was missed; let the deferred work be scheduled normally. Over time, the rate of retroactive-debt follow-ups is the project's calibration signal for how well the discipline is holding.

### 5.12 Verification — manual today, automated later

Today the rule is honor-system. Before opening a PR, the author reviews the diff against the skill corpus by hand: grep the changed files' identifiers against `.claude/skills/`. Reviewers do the same on the way in.

An automated detector — a `/audit-skills` slash command + a `scripts/audit/` detector library that parses the PR diff and flags skills referencing changed identifiers — is filed as `agent-issue-tracker#2` (v1.1 follow-on against this repo). Until it ships, the rule is honor-system. The detector codifies a *subset* of this skill's discipline; the skill itself remains the source of truth for the rule.

### 5.13 Worked example (generic)

Concrete, fully generic example. Approximate shape:

> A PR adds a `--dry-run` flag to a hypothetical `myproj-cli build` subcommand. The flag changes the command's output (prints the plan, doesn't execute) and changes its exit code semantics (returns 0 even when the plan is non-empty).
>
> **Affected skill:** `myproj-cli-architecture`, the project's domain skill that documents the CLI subcommand surface, flag conventions, and exit-code semantics.
>
> **What lands in the same PR:**
>
> 1. Code: the new `--dry-run` branch in `myproj_cli/build.py`, the new test covering the flag.
> 2. Skill: the `myproj-cli-architecture` section listing `build` subcommand flags — add `--dry-run` with one-line semantics; the exit-code semantics section — note the dry-run override.
>
> A reviewer who opens the PR sees `myproj_cli/build.py` AND `skills/myproj-cli-architecture/SKILL.md` in the same diff. The skill is reviewable against the code change. If the operator's domain skill is missing this section entirely, that surfaces as a separate finding: file an enhancement issue via `feature-request` to write the missing skill section.

(Do NOT use `trading-bot`, `dca`, `IBKR`, `proposal-service`, `reserve-ledger`, or any other trading-bot-specific identifier. The rule is general; the example demonstrates the rule, not the trading-bot domain.)

### 5.14 Cross-skill ergonomics

Pointer block at the end, naming the three filing-shape siblings and what each handles:

- **`feature-request`** — file when you need a new skill (the skill itself is a new capability for the methodology layer).
- **`bug-tracking`** — file when a skill is wrong, out of date, or misleading (a stale skill is a defect in the methodology layer).
- **`followup-tracking`** — file when scope deferred from this PR includes a skill update (the deferred work IS the skill update).

### 5.15 See-also footer

Closing line matches the four siblings' "See also:" footers. References `bug-tracking`, `feature-request`, `followup-tracking` (NOT `initiative-tracking` — see §4 decision table).

## 6. CHANGELOG entry

Single line under `[Unreleased]` → `### Added`. Format matches the four prior Phase 2 entries:

```
- Phase 2 (#15): skill-currency skill — written from scratch (only new skill in v1, not a port). Codifies the rule that when a PR changes API surface (new module, new public function, new CLI subcommand, new env var, new DB table or schema-version bump, new HTTP route, changed function signature, removed function/file), the affected `.claude/skills/*.md` files MUST update in the same PR. Cross-links the three filing-shape siblings (`bug-tracking`, `feature-request`, `followup-tracking`); references the v1.1 enforcement helper (`agent-issue-tracker#2`, port of `/audit-skills` + detector library) as the deferred automated path — until then, the rule is honor-system. Closes Phase 2 (all five skills shipped).
```

## 7. Failure modes considered

- **Skill drifts to "guidelines" tone.** Risk: the skill becomes vague advisory prose ("try to keep skills updated"). Mitigation: the rule is block-quoted with MUST capitalized, and §5.6 enumerates the eight categories explicitly. A reviewer can grep for "MUST update in the same PR" and the eight category strings.
- **Detector port gets duplicated inline.** Risk: an authoring agent helpfully inlines the `scripts/audit/skills.py` glob list or detector logic from trading-bot. Mitigation: §3 names it as out of scope; §5.12 explicitly cross-links to `agent-issue-tracker#2` instead.
- **Trading-bot-specific identifiers leak through.** Risk: skill names (`dca-router-mechanics`, `execution-service-architecture`), file paths (`scripts/db.py`), DB tables (`watchlist_items`, `claude_tasks`), or repo refs (`maxdimitrov/trading-bot`) appear in the worked example or anywhere else. Mitigation: acceptance includes explicit grep gates for these strings.
- **Length drift.** Risk: the skill grows past 400 lines as authoring adds defensive prose. Mitigation: 200-400 acceptance gate; if it overshoots, the §5.5 / §5.13 sections are first to trim — they're elaboration, not load-bearing rule.
- **Rule wording paraphrased.** Risk: the rule's eight-category enumeration gets condensed or reworded. Mitigation: §4 decision table pins "verbatim from parent spec §6.2"; acceptance §"Skill enumerates API-surface change categories" greps for each category by name.
- **Escape hatch over-broadens.** Risk: §5.7 grows to include "any non-trivial change" and swallows the rule. Mitigation: §5.7's enumeration is closed-form (three specific cases) with the discriminator test ("would an agent in a future session need to know this changed?") as the gate.
- **Initiative-tracking cross-link confusion.** Risk: an authoring agent adds `initiative-tracking` to the cross-link list because "all four siblings get cross-linked." Mitigation: §4 decision table calls this out explicitly; the See-also footer in §5.15 names only three siblings.
- **`agent-issue-tracker#2` ref shape.** Risk: the bare `#2` gets typed without the `agent-issue-tracker` qualifier, becoming ambiguous in a cross-repo context. Mitigation: §5.12 names the full ref; acceptance §"agent-issue-tracker#2 named" greps for the qualified form.

## 8. Invariants (cross-cuts the whole skill)

- **Markdown-only.** No code, no shell scripts, no Python. The skill is prose methodology, not tooling.
- **Tracker-agnostic.** No `gh issue create`, no `Closes #N`, no `maxdimitrov/...` (except the literal plugin self-reference `agent-issue-tracker#2`).
- **No template artifact.** This skill ships SKILL.md only; no `templates/skill-currency-body.md`. The four filing siblings own templates because they file issues; this skill tells *other* skills (and humans) when to act.
- **No backend dispatch.** Unlike the four filing siblings, this skill does NOT dispatch to a backend operation. It does not invoke `create_issue` / `view_issue` / `edit_body` / etc. directly. When it surfaces a need to file ("a skill is wrong"), it routes through `bug-tracking` which owns the dispatch.
- **Verbatim source phrasings preserved.** The rule (§5.4) is verbatim from parent spec §6.2. The eight API-surface categories (§5.6) are verbatim from the same source. Reviewers grep these strings character-for-character.

## 9. Out of scope (explicit, in addition to §3)

- **A trading-bot CLAUDE.md edit that cites this skill by name.** Phase 5 (dogfood cutover, parent epic) owns that change.
- **Updating `bug-tracking` / `feature-request` / `followup-tracking` to mention `skill-currency`.** Reverse cross-links from the four siblings to this skill are useful but out of scope here — file them as a separate `agent-issue-tracker` enhancement at Phase 4 (README rewrite) or Phase 5 (dogfood) if needed. (Sketched as a potential v1.0.1 polish task; do not file from this PR.)
- **Hooks / settings.json / CI gates.** The skill says explicitly: rule is honor-system. The detector port (`agent-issue-tracker#2`) is the path to automation. No `PreToolUse` block, no GitHub Action, no pre-commit hook lands in v1.

## 10. Acceptance — beyond the issue's already-stated gates

The issue body's Acceptance and Verify sections are the binding gates. This spec adds three observational checks the implementer should self-run after writing the SKILL.md, before opening the PR:

1. **Cold-read sanity.** Read the file end-to-end from top, as if you'd just been handed it. Does the rule land in the first ~30 lines? Is the escape hatch unambiguously narrow? Does the worked example sound generic (no trading-bot smell)? If any of these feel off, rework before opening the PR.
2. **De-trading-bot grep sweep.** `grep -rE "trading-bot|maxdimitrov/trading-bot|dca|IBKR|proposal-service|execution-service|reserve-ledger|watchlist_items|claude_tasks|positions_meta|ic-memo-framework|atr-stops|dashboard-maintenance" skills/skill-currency/` — must return zero lines. This is broader than the issue's Acceptance grep (which lists a subset) — be exhaustive.
3. **Cross-link verify.** `grep -E "bug-tracking|feature-request|followup-tracking" skills/skill-currency/SKILL.md` — must match all three. `grep -E "agent-issue-tracker#2" skills/skill-currency/SKILL.md` — must match (the v1.1 detector ref).

## 11. Conventions established by this issue

This issue closes Phase 2 (all five skills shipped). No new conventions for downstream Phase 3 work — those siblings have already shipped (`#20` `/resume-initiative`, `#22` `/tracker-init`, `#23` `/tracker-doctor`; `#24` `backends/jira.md` remains). One small convention worth recording for Phase 4 (README rewrite):

- **The five Phase 2 skills are NOT symmetric.** Four (`bug-tracking`, `feature-request`, `followup-tracking`, `initiative-tracking`) are filing-shape — they teach how to file issues. One (`skill-currency`) is rule-shape — it teaches when filing-or-updating must happen. The Phase 4 README should distinguish the two shapes; treating skill-currency as "the fifth filing skill" misframes it.
