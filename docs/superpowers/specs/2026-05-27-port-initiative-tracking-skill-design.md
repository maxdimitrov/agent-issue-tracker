# Port initiative-tracking skill — Design Spec

**Date:** 2026-05-27
**Tracker:** [maxdimitrov/agent-issue-tracker#14](https://github.com/maxdimitrov/agent-issue-tracker/issues/14)
**Parent epic:** [maxdimitrov/trading-bot#153](https://github.com/maxdimitrov/trading-bot/issues/153) (Phase 2 — skill rewrites)
**Parent design spec:** [maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) (§6.2 — initiative-tracking is the most-surgery port)
**Author:** brainstorm session 2026-05-27 (controller in f:\Claude\Projects\Trading; work happens in f:\Claude\Projects\agent-issue-tracker on branch `feat/port-initiative-tracking-skill`)

## 1. Goal

`skills/initiative-tracking/SKILL.md` exists in this plugin as a
tracker-agnostic port of the same-named skill from
`maxdimitrov/trading-bot`, and `templates/epic-body.md` +
`templates/sub-issue-body.md` contain the reusable body skeletons.
Together they let any plugin consumer index multi-week initiatives
as epic + sub-issue against either backend (GitHub today, Jira at
Phase 3), with a Status block the plugin's `/resume-initiative`
(Phase 3) can parse across both trackers.

This is Phase 2's 4th skill port (after `#11` bug-tracking, `#12`
feature-request, `#13` followup-tracking — all merged on
`maxdimitrov/agent-issue-tracker` main). Phase 2's conventions are
already locked in by those three PRs and this spec adopts them:
pure-addition PR; spec-then-plan-commit before Task 1; haiku-model
subagents for verbatim-content tasks; behaviour-change-zero
verified via leakage greps + cold-read.

## 2. Non-goals

- `/resume-initiative` command implementation — Phase 3, depends on
  this issue landing first (the command parses the Status-block
  format codified here).
- Jira backend (`backends/jira.md`) — Phase 3.
- Trading-bot Phase 5 cutover (delete local skill, install plugin) —
  Phase 5.
- `skill-currency/SKILL.md` — `#15`, separate Phase 2 issue.
- Cross-link to `skill-currency` in this skill's prose — defer to
  `#15` landing first; one-line follow-up edit if cross-linking is
  warranted.
- Methodology changes — bail criteria, body shape, type taxonomy,
  Status-block format are byte-identical to the trading-bot source.

## 3. Behaviour-change-zero invariant

Per parent design spec §8.2. The skill's external observable
behaviour is byte-equivalent to the trading-bot source after the
four surgical transforms in §6.2 land:

- Triage gate table preserved verbatim.
- Status-block field prefixes (`- **Phase:**`, `- **Next up:**`,
  `- **Current branch:**`, `- **Last updated:**`) are CANONICAL and
  appear LITERALLY in `templates/epic-body.md`. Phase 3's
  `/resume-initiative` parser depends on them character-for-character.
- Title format `epic: <name>` stays.
- Label rules (`epic` on the epic; same area labels + triage labels
  on children; children do NOT get the `epic` label) stay.
- Lifecycle table (`Open + has open children` etc.) stays.
- Trigger phrases in the frontmatter `description:` preserved
  verbatim ("this is a big one", "spin this up as its own
  initiative", "let's plan this across weeks", "multi-week", "epic").

The Phase 5 cutover PR (against trading-bot) is the explicit gate
where trigger-phrase regression is verified end-to-end; this PR
only ships the plugin-side port.

## 4. Decisions settled in brainstorm

Five design decisions the issue body left open. Each resolution
below is the one the brainstorm settled on, with rationale.

### 4.1 Sub-issue body template — compose, not inline

**Decision.** `templates/sub-issue-body.md` is a thin compose-by-
reference wrapper (~40-60 lines). It says: "A sub-issue is either
feature-shaped or bug-shaped — use `templates/feature-body.md` or
`templates/bug-body.md` as the base; prepend the `<phase-name>:`
title prefix convention; append the `## Parent epic` block (literal).
Optionally drop the redundant `## Goal` heading from the base since
the sub-issue's goal is one slice of an epic-level goal."

**Why not inline (self-contained).** Followup-tracking went
self-contained because its five extra blocks (Parent / What's done /
What's tried / Related / Why deferred) were genuinely sub-shape-
specific structure that didn't appear in any sibling template.
Sub-issues have ONE extra block (`## Parent epic`). The honest
expression is "feature OR bug + parent epic" — which is exactly
what compose-by-reference says.

Compose also avoids drift: if `templates/feature-body.md` changes
(adding/dropping a block), `templates/sub-issue-body.md` doesn't
need a parallel edit.

The acceptance criterion (`templates/sub-issue-body.md` contains a
literal `## Parent epic` section) is satisfied either way.

### 4.2 `link_sub_issue` indirection — methodology, not dispatch

**Decision.** Mirror followup-tracking's `edit_body` phrasing
pattern. One paragraph in the skill prose: name the operation,
point readers at `backends/<backend>.md` for the literal call, note
that backends differ. No code block in the skill itself.

The GitHub backend's typed-int gotcha (`-F` not `-f`, HTTP 422
otherwise) is documented in `backends/github.md:74-80` already.
The skill does not re-document it.

**Why.** The skill is methodology, not dispatch. Followup-tracking
already shipped this pattern for `edit_body`; reusing it keeps the
four ports stylistically consistent. The skill cites the contract;
the contract delegates to the backend module; the backend module
holds the per-tracker mechanics.

### 4.3 Read-modify-write warning — cite the contract invariant

**Decision.** Cite cross-backend invariant #2 from
`backends/_interface.md:107` directly:

> Whole-body edits are destructive — the configured backend's
> `edit_body` operation replaces the entire description in one
> call (cross-backend invariant from `backends/_interface.md`).
> There is no append-only API on either supported backend. The skill
> is responsible for the read-modify-write cycle: invoke
> `view_issue` first, modify only the Status-block lines + the
> relevant `## Children` line in memory, then invoke `edit_body`
> with the full new body.

**Why.** The contract already locks this as an invariant (and the
`edit_body` operation's "Note" at `_interface.md:84-85` says exactly
this). Citing the invariant keeps the skill out of per-backend
mechanics. If a future backend lands an append-only API, the
contract is updated in one place; the skill prose stays correct.

### 4.4 Per-backend fallback section — reframe as cross-backend invariant

**Decision.** Reframe the source skill's "task-list mirror as
fallback to native sub-issue API" into a cross-backend invariant.
Skill prose:

> **Always** maintain the `## Children` task-list mirror in the
> epic body — it is what `/resume-initiative` parses (cross-backend
> invariant). Additionally invoke `link_sub_issue` to establish
> native parent-child linkage in the tracker — this is what makes
> the tracker's UI show the relationship, but `/resume-initiative`
> does not depend on it.
>
> Per-backend native linkage mechanics — GitHub's native sub-issue
> API (`gh api .../sub_issues`), Jira's `parent` field or Epic Link
> customfield (depending on `jira.parent_link_style`) — are
> documented in `backends/<backend>.md`.

**Why.** The source's framing (native is source of truth,
task-list is fallback) is GitHub-centric. Reframing the task-list
mirror as the *cross-backend* source of truth (and native linkage
as a tracker-UI bonus) is cleaner, makes `/resume-initiative` (Phase
3) trivially parseable across backends, and naturally handles
Jira's two parent-link styles via per-backend docs. The
`/resume-initiative` parser only needs to parse markdown; it never
needs to call `link_sub_issue`'s inverse.

### 4.5 Examples — generic subject, retain shape

**Decision.** Use generic subject matter for the worked Status-block
example. Source's specific numbers (`#127 — reserve-ledger schema`,
`Phase 1a · 2/4`) → generic placeholders that retain shape
(`Phase 1 · 2/4 sub-issues closed`, `#42 — <child-title>`).

Chain the worked example off a `worker/queue redesign` thread (the
generic subject used by bug-tracking + feature-request +
followup-tracking ports). Stays within the four-skill example
universe; gives the plugin's worked examples cross-skill narrative
consistency.

**Why.** Some concreteness anchors the reader; pure abstraction
(`#N — <epic-title>`) loses signal about the shape of a real epic.
Generic subject keeps it portable.

## 5. File plan

All paths relative to the `maxdimitrov/agent-issue-tracker` repo root.

| File | Action | Approx size | Role |
|---|---|---|---|
| `skills/initiative-tracking/SKILL.md` | NEW | ~300-340 lines | Tracker-agnostic methodology — triage gate, Status block field spec, sub-issue creation flow, `link_sub_issue` indirection, maintenance / read-modify-write, lifecycle. Dispatches to `backends/<backend>.md` via the contract's seven operations. |
| `templates/epic-body.md` | NEW | ~100-130 lines | Epic body skeleton — preamble + machine-readable Status block (the four canonical field prefixes appear LITERALLY) + Phases + Children task-list mirror + Decision log + Resume-from-here. All-placeholder content. |
| `templates/sub-issue-body.md` | NEW | ~40-60 lines | Thin compose-by-reference wrapper. Title prefix convention + "compose with feature-body.md / bug-body.md" + `## Parent epic` block skeleton. |
| `CHANGELOG.md` | MODIFY | +1 line | Append Phase 2 (#14) entry under `## [Unreleased]` → `### Added`. |
| `docs/superpowers/specs/2026-05-27-port-initiative-tracking-skill-design.md` | NEW (this file) | ~design | Committed pre-Task 1 per Phase 2 convention. |
| `docs/superpowers/plans/2026-05-27-port-initiative-tracking-skill.md` | NEW | implementation plan | Committed pre-Task 1; mirrors PR #18's plan shape. |

Pure-addition PR (no edits to existing files except the CHANGELOG
one-liner). Estimated final diff: `+~600 / -0` across 6 new files +
the CHANGELOG append.

## 6. Skill outline

Sections in order, mapped to source-skill sections + the four
surgical transforms from parent spec §6.2.

1. **Frontmatter** — preserve trading-bot source's trigger phrases
   verbatim ("this is a big one", "spin this up as its own
   initiative", "let's plan this across weeks", "multi-week",
   "epic"). Replace the trading-bot-specific description prefix
   with "the configured tracker (see `.claude/issue-tracker.yaml`)"
   per parent §6.1.
2. **Header + opener** — "The canonical tracker is the one
   configured in the consumer's `.claude/issue-tracker.yaml`." Cite
   `backends/_interface.md`.
3. **Why structure matters** — preserve verbatim from source.
4. **Triage gate — is this actually an initiative?** — table
   preserved verbatim. The "If you would only file 1-2 sub-issues..."
   callout stays. The "If multi-week BUT no design spec, run
   brainstorming + writing-plans first" callout stays.
5. **When to file an epic** — source's bullet list with two minor
   reframings:
   - "the original `followup-tracking` issue gets superseded by the
     epic" — keep the pointer to follow-up-tracking (sibling
     cross-link), but generalize the close-comment phrasing.
   - `memory/PENDING-FIXES.md is frozen legacy` — dropped per
     parent §6.1 (trading-bot operator concern, not portable
     methodology).
6. **Filing the epic** — replace `gh issue create` block with:
   "Invoke the configured backend's `create_issue` operation with
   `type: epic`, `title: epic: <name>`, `labels: [epic, <area>]`,
   `body: <filled-in templates/epic-body.md>`. See
   `backends/<backend>.md` for the literal invocation." Title
   format stays `epic: <name>`.
7. **Epic body template** — point at `templates/epic-body.md`.
   Don't inline the template in the skill (it's its own file).
8. **Status block — exact field spec** — table preserved with the
   parser-extension note added (Q4.2 transform): "The `Next up:`
   value accepts both `#N` (GitHub) and `PROJ-123` (Jira);
   `/resume-initiative` (Phase 3) parses both, the backend module
   renders them."
9. **Creating sub-issues** — title prefix convention
   (`<phase-name>: <capability>`) + `## Parent epic` block
   convention + label rules (`epic` does NOT get added to children).
   Body template pointer: "Use `templates/sub-issue-body.md` —
   composes with `templates/feature-body.md` or
   `templates/bug-body.md` based on whether the sub-issue is
   feature-shaped or bug-shaped."
10. **Linking children to the epic** — `link_sub_issue` indirection
    paragraph (per §4.2 resolution). One-paragraph cross-backend
    invariant pointer.
11. **Children task-list mirror — the cross-backend index** — per
    §4.4 resolution. The `## Children` task-list mirror in the epic
    body is ALWAYS maintained; `link_sub_issue` is additional,
    per-backend native linkage that backends document themselves.
12. **Maintenance** — when a child closes: increment the Phase
    line's `<closed>/<total>`, recompute `Next up`, bump
    `Last updated`. Cite the destructive-edit invariant from §4.3
    resolution.
13. **Epic lifecycle** — table preserved with `gh issue close` →
    `close_issue` indirection.
14. **Returning the epic number** — preserved verbatim. "Epic
    created: <ref>. Resume any time with `/resume-initiative <ref>`."
    (`<ref>` because Phase 3 cross-backend.)
15. **See also** — cross-link to `feature-request`, `bug-tracking`,
    `followup-tracking` (sibling tracker skills). Cross-link to
    `skill-currency` is DEFERRED to a one-line follow-up after `#15`
    lands.

## 7. The four surgical transforms — checklist

Per parent spec §6.2. Each transform below corresponds to a specific
section of the source skill and a specific change in the port.

### 7.1 Native sub-issue API block

**Source** (`.claude/skills/initiative-tracking/SKILL.md:182-187` on
trading-bot main):

```bash
CHILD_ID=$(gh api repos/maxdimitrov/trading-bot/issues/<child-N> --jq .id)
gh api -X POST repos/maxdimitrov/trading-bot/issues/<epic-N>/sub_issues \
  -F sub_issue_id=$CHILD_ID
```

**Port:** drop the code block from the skill. Replace with one
paragraph:

> After creating the child, invoke the configured backend's
> `link_sub_issue` operation to attach the child as a native
> sub-issue of the epic. The skill does not parse refs — pass the
> child ref and the epic ref to the backend; the backend module
> handles the per-tracker mechanism (GitHub's typed-int sub-issue
> API, Jira's `parent` field or Epic Link customfield depending on
> `jira.parent_link_style`). See `backends/<backend>.md`.

### 7.2 Status block format — byte-identical, parser extension

**Source** (`.claude/skills/initiative-tracking/SKILL.md:137-151`):

The four-line table `- **Phase:**` / `- **Next up:**` /
`- **Current branch:**` / `- **Last updated:**` and their formats.

**Port:** preserve the table EXACTLY. Add one bullet under it:

> The `Next up:` value accepts both `#N` (GitHub) and `PROJ-123`
> (Jira) ref syntaxes. `/resume-initiative` (Phase 3) parses both;
> the backend module renders the syntax. The field-prefix strings
> themselves are canonical and EXACT — paraphrasing them is a
> breaking change.

### 7.3 Read-modify-write warning — generalize across backends

**Source** (`.claude/skills/initiative-tracking/SKILL.md:225-237`):

GitHub-centric language: "`gh issue edit --body-file` is
**destructive** — it overwrites the entire body. There is no
append-only API on `gh`."

**Port:** per §4.3 resolution. Cite the contract's destructive-edit
invariant; show the read-modify-write cycle in tracker-neutral
terms; no code block, no per-backend mechanics in the skill prose.

### 7.4 Fallback section — reframe as cross-backend invariant

**Source** (`.claude/skills/initiative-tracking/SKILL.md:199-213`):

"If a host or a future GitHub change blocks the native API..."
followed by a `gh issue view` + `gh issue edit` example.

**Port:** per §4.4 resolution. The task-list mirror is the
cross-backend source of truth; native linkage is per-backend native
plumbing that backends document themselves. No code block in the
skill.

## 8. Acceptance — mirrors issue #14 Verify block

The PR is mergeable when ALL of these hold:

- [ ] `skills/initiative-tracking/SKILL.md` exists; renders cleanly.
- [ ] `templates/epic-body.md` exists; contains the four exact
  Status-block field-prefix strings (literally):
  - `- **Phase:**`
  - `- **Next up:**`
  - `- **Current branch:**`
  - `- **Last updated:**`
- [ ] `templates/sub-issue-body.md` exists; contains a `## Parent
  epic` section (literal).
- [ ] No literal string `maxdimitrov/trading-bot` anywhere in the
  three new files.
- [ ] No `gh api repos/...` snippet in
  `skills/initiative-tracking/SKILL.md` (the native sub-issue API
  is owned by `backends/github.md` only).
- [ ] Skill prose cites `link_sub_issue`, the configured backend,
  and the generalized read-modify-write warning.
- [ ] Skill prose names both `#N` and `PROJ-123` as acceptable
  ref syntaxes for the `Next up:` line.
- [ ] Triage gate table preserved verbatim from source (four rows:
  `Fits in one PR` / `Spans 1-3 days` / `Spans weeks` / `Multiple
  phases`...).
- [ ] Sibling cross-links present (`feature-request`,
  `bug-tracking`, `followup-tracking` — at least 3 references).
- [ ] No trading-bot-specific skill or path leaks (PENDING-FIXES,
  /fix-issue, ic-memo-framework, dca-router, dashboard-maintenance,
  atr-stops, reserve-ledger, execution-service-architecture,
  proposal-service-architecture, quant-atelier-design,
  twr-benchmarking, position-sizing).
- [ ] No absolute paths or `~/.claude/` references.
- [ ] CHANGELOG.md `## [Unreleased]` → `### Added` notes the
  initiative-tracking skill + epic/sub-issue templates landed.
- [ ] Spec file (this doc) committed to the branch as part of this
  PR.
- [ ] Plan file committed to the branch as part of this PR.
- [ ] PR title: `Phase 2 (#14): port initiative-tracking skill`.
- [ ] PR body includes `Closes #14` plus parent epic ref
  `maxdimitrov/trading-bot#153`.
- [ ] Branch staleness check before push showed `0` on the RIGHT
  side (origin/main did not move during the work).

Markdownlint is deferred to Phase 4 per the parent spec (no
`.markdownlint.json` config yet).

## 9. Execution sketch

Three tasks, serial (no parallel-subagent isolation needed). Mirror
PR #18's structure.

### Pre-flight (controller does this once)

1. Confirm controller cwd resets between Bash calls and the work
   directory is `f:/Claude/Projects/agent-issue-tracker`.
2. Confirm branch `feat/port-initiative-tracking-skill` is checked
   out and equals `origin/main` (`git rev-list --left-right --count
   HEAD...origin/main` → `0\t0`).
3. Commit this spec on the branch.
4. Write + commit the implementation plan.

### Task 1 — Templates

Haiku subagent writes both `templates/epic-body.md` and
`templates/sub-issue-body.md`. The four canonical Status-block
field-prefix strings appear in `epic-body.md` literally; verified by
the `grep -F` invariant check before commit.

**Subagent CWD discipline:** first line of subagent prompt is `cd
f:/Claude/Projects/agent-issue-tracker && git status && git
rev-parse --abbrev-ref HEAD`. Subagent verifies it's on
`feat/port-initiative-tracking-skill` before doing any writes.

Commit: `feat(templates): add epic-body and sub-issue-body
skeletons`.

Controller verifies `git log -1 --format='%H %s'` after return.

### Task 2 — Skill + CHANGELOG

Haiku subagent writes `skills/initiative-tracking/SKILL.md` and
appends the CHANGELOG entry. Same CWD discipline as Task 1. The
full acceptance grep suite runs at the end of this task; any
failure → fix inline and rerun.

Commit: `feat(skills): port initiative-tracking from trading-bot`.

### Task 3 — Push + PR

Controller pushes the branch (`git push -u origin
feat/port-initiative-tracking-skill`) and opens the PR via `gh pr
create`. PR title `Phase 2 (#14): port initiative-tracking skill`;
body includes `Closes #14`, parent epic ref, decisions log,
transforms-applied table, behaviour-change-zero invariant note.

## 10. Out of scope (do not let scope creep)

- `/resume-initiative` command implementation — Phase 3.
- Jira backend — Phase 3.
- Trading-bot Phase 5 cutover — Phase 5.
- `skill-currency` — `#15`, separate Phase 2 issue.
- Cross-link to `skill-currency` in the skill prose — defer to
  `#15` landing first.
- Native sub-issue API mechanics in the skill — owned by
  `backends/github.md` per the contract.
- Per-backend fallback mechanics in the skill — owned by
  `backends/<backend>.md` per §4.4 resolution.
- Markdownlint config — Phase 4.

## 11. Notes

- This is the **most-surgery** port of the four per parent spec
  §6.2. The bulk of the source skill is preserved verbatim; the
  four surgical transforms in §7 are where the real work happens.
  Read the source skill end-to-end before starting — many sentences
  need only one or two words changed, and the temptation to
  paraphrase will break behaviour-change-zero.
- The Status-block field-prefix strings (`- **Phase:**` etc.) appear
  in this spec, the parent spec §5.3, the source skill, and will
  appear in `/resume-initiative` (Phase 3). Any rewording is a
  load-bearing breaking change — coordinate with whoever picks up
  Phase 3.
- This port introduces `templates/epic-body.md` — the most
  structured template in the plugin (Status block + Phases +
  Children + Decision log + Resume-from-here). It validates the
  `templates/*-body.md` non-standard-block pattern for the most
  complex case after `templates/followup-body.md` (#13) validated
  it for the medium case.
- The compose-by-reference choice for `templates/sub-issue-body.md`
  (§4.1) is deliberate divergence from followup-tracking's
  self-contained pattern. The skill prose must be explicit about
  which way it went (per the issue body's Step 5 requirement).
- The cross-repo controller / worktree-free dance is identical to
  PR #18. Every subagent dispatch in this plan MUST start with the
  literal `cd f:/Claude/Projects/agent-issue-tracker && git status`
  and the controller MUST run `git log -1` after each subagent
  returns. This satisfies the project's "subagent CWD discipline"
  rule.
