# Port the followup-tracking skill to agent-issue-tracker (Phase 2, #13)

**Date:** 2026-05-27
**Branch:** `feat/port-followup-tracking-skill` on `maxdimitrov/agent-issue-tracker`
**Parent epic:** `maxdimitrov/trading-bot#153` (Phase 2)
**Sibling ports:** `#11` (bug-tracking, merged as PR #16) · `#12` (feature-request, merged as PR #17)
**Status:** approved 2026-05-27

## Goal

Two new files land on `agent-issue-tracker` `main`, byte-equivalent in
methodology to trading-bot's `followup-tracking` skill but
tracker-agnostic and dispatched through the seven-operation backend
contract:

1. `skills/followup-tracking/SKILL.md` — ~280-line skill prose.
2. `templates/followup-body.md` — ~110-line self-contained body template
   carrying all 12 blocks in source ordering.

Plus a `CHANGELOG.md` entry and the per-issue implementation plan
committed on the feature branch as
`docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md`.

After the PR merges, Phase 2 advances to 5/15 closed; `#14`
(initiative-tracking) and `#15` (skill-currency) remain unblocked in
parallel.

## Why

- `followup-tracking` has the highest "load-bearing context" requirement
  of the four ported skills. The parent / what's-done / what's-tried /
  related / why-deferred blocks are what prevent future agents from
  re-investigating discarded approaches. The methodology *is* the value;
  the port must preserve it byte-equivalently.
- It is the first port whose body template adds fields beyond the
  standard agent-prompt shape (the five followup-specific blocks). The
  template pattern this port validates is load-bearing for
  `templates/epic-body.md` (`#14` initiative-tracking).
- Trading-bot Phase-5 cutover requires `followup-tracking` to ship with
  byte-equivalent methodology so existing followup filings keep their
  shape.

## Decisions settled in brainstorm (2026-05-27)

The issue body explicitly invites brainstorming on three open design
choices. Recommendations and rationale below.

### Decision 1 — Template composition

**Chosen: self-contained 12-block template** in
`templates/followup-body.md`.

Alternative considered: split the template — five followup-specific
blocks in `templates/followup-body.md`, standard tail composed from
`templates/feature-body.md` or `templates/bug-body.md`.

**Rationale:** The source skill is a body monolith (all 12 blocks
inline). Behaviour-change-zero is preserved more closely when the new
template is also a monolith. A reader filling in a followup needs one
file open, not three. The cross-skill compose pattern can be revisited
later via a `followup-tracking` followup if a real DRY pain surfaces.

### Decision 2 — Block ordering

**Chosen: source ordering** — the five followup-specific blocks come
FIRST, followed by a `---` separator, followed by the seven standard
blocks (`## Goal` onwards).

The issue body §6 lists `## Goal` first; this is a documented divergence
from §6 in this port and from §6 onwards in the plan.

**Rationale:** behaviour-change-zero is the binding invariant. The
source skill puts followup-context BEFORE target state because an agent
reading the body needs to know "this exists because of #N" before it
reads "the change should produce X". Context-first ordering also
matches the rest of the skill's prose (which discusses the followup
blocks first).

### Decision 3 — Example

**Chosen: chain off `feature-request`'s `cli/list --json` example.**

The followup defers the next slice of that feature — a schema-versioning
flag — to a later change. Demonstrates all five followup-specific blocks
plus the seven standard ones in a setting the reader has just seen.

Alternative considered: a `db/migration-0042` example (per issue body
§4). Both work; the cli/list chain wins on cross-skill narrative
consistency.

### Decisions resolved by the issue body / invariants

| Decision | Resolution | Source |
|---|---|---|
| Block names | Preserve source verbatim — Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred. | Invariant §3 of issue body. |
| Title-suffix convention | Reframe to tracker syntax: "include a parent reference in your tracker's syntax (e.g. `#N` for GitHub, `PROJ-123` for Jira); the backend module renders the syntax." | Issue body §2, spec §6.2. |
| Related-issues block | Reframe to the `list_open_issues` contract operation; "filter optionally by keyword if your backend supports it; otherwise document the search you ran inline." | Spec §6.1; mirrors #11/#12 reframe of `gh issue list`. |
| Closing-the-loop verbs | Use backend close-on-merge convention; cite `Fixes #N` / `Closes #N` as the GitHub-backend example. | Spec §6.1; mirrors #11/#12. |
| `link_sub_issue` is OUT of scope | Follow-ups are NOT sub-issues; parent linkage is the body's Parent block plus the `followup` label. | Backend contract: `link_sub_issue` is reserved for `initiative-tracking`'s epic-to-child relation. |

## Architecture & boundaries

| Path | Action | Why |
|---|---|---|
| `skills/followup-tracking/SKILL.md` | NEW (~280 lines) | The port |
| `templates/followup-body.md` | NEW (~110 lines) | Self-contained 12-block body template |
| `CHANGELOG.md` | MODIFY | `[Unreleased] → ### Phase 2 (in progress)` entry |
| `docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md` | NEW | Per-issue implementation plan, shipped on the feature branch |
| `backends/_interface.md` | UNCHANGED | Reference only |
| `backends/github.md` | UNCHANGED | Reference only |
| `skills/bug-tracking/SKILL.md` | UNCHANGED | Reference only |
| `skills/feature-request/SKILL.md` | UNCHANGED | Reference only |
| `templates/bug-body.md` | UNCHANGED | Reference only |
| `templates/feature-body.md` | UNCHANGED | Reference only |

Pure-addition PR (`+~500 / -0` across 4 files, mirroring #11/#12 shape).

## SKILL.md section map

Mirrors the sibling-port skeleton established by #11 and #12, with
followup-specific content swapped in. Section-by-section transforms:

| Section | Treatment |
|---|---|
| Frontmatter | Trigger phrases preserved literal. `description:` rewritten tracker-agnostic — strip "for the trading-bot project" / "maxdimitrov/trading-bot", strip the `// TODO` reference, generalize sibling-skill names to plain skill names. |
| H1 title | "Follow-up Tracking — Issues as Agent Prompts" — matches sibling pattern. |
| Opening | "The canonical tracker is the one configured in the consumer project's `.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md` documents the seven operations..." — same opener as siblings. |
| Type-orthogonal | Preserved methodology. Cross-link `skills/bug-tracking/` and `skills/feature-request/`. Replace the `gh issue list --label followup` snippet with "use the configured backend's `list_open_issues` operation, filtered by `label: followup`". |
| Why structure matters | Preserved. Cite same bail criteria as siblings plus the followup-specific "agent skips `needs-design`" callout. |
| When to file / not to file | Preserved verbatim — tracker-neutral. |
| Filing | Rewritten to dispatch through `create_issue`. Pass `type: followup`, `title`, `labels: [<bug or enhancement>, <area>, followup]`, `body`. Title-suffix convention reframed per Decision 1. Drop the `gh label create followup` snippet — a backend setup concern; the consumer documents it in their `.claude/issue-tracker.yaml`. |
| Agent-execution body template | Body template pointer to `templates/followup-body.md`. Block-by-block-why-each-matters table preserved — this is the highest-value methodology piece of the source skill. |
| When the parent has not landed yet | Preserved. Rewrite the `gh issue edit` snippet to dispatch through `edit_body` (contract operation). |
| Labels | Preserved structure. Drop the trading-bot-specific area list, point at "the consumer's `.claude/issue-tracker.yaml` `areas:` enum". Keep `needs-design` / `needs-triage` triage flags. |
| Closing the loop | Reframed to the backend close-on-merge convention; cite `Fixes #N` / `Closes #N` as the GitHub-backend example. |
| Example | Chained off `cli/list --json` per Decision 3 — a followup deferring JSON schema versioning to the next slice. Demonstrates all 5 extra blocks + 7 standard blocks. Generic. |
| See also (h3) | Cross-link `skills/bug-tracking/` (defect-shaped sibling), `skills/feature-request/` (capability-shaped sibling), `initiative-tracking` (multi-issue epics — when followup work compounds). |

## templates/followup-body.md structure

Self-contained, 12 blocks in source ordering. Preamble + 5
followup-specific blocks + `---` separator + 7 standard blocks + Notes
tail.

```
# Followup Body Template
(preamble — use-verbatim instructions; pointer to backends/<backend>.md)
---
## Parent                          [required]   followup-specific
## What's already done             [required]   followup-specific
## What's been tried / ruled out   [required]   followup-specific
## Related issues                               followup-specific
## Why deferred                    [required]   followup-specific
---
## Goal
## Locus                           [required]
## Skills to load                  [required]
## <task-specific block>                        (pointer to bug-body / feature-body templates)
## Constraints                     [required]
## Acceptance                      [required]
## Verify                          [required]
## Notes (optional)                             (matches #11/#12 template tail)
```

Each block carries one-line placeholder guidance only. Guidance prose
lives in `SKILL.md`, not in the template — matches the terse style of
`templates/bug-body.md` and `templates/feature-body.md`.

## Data flow / dispatch

The skill prose dispatches through these contract operations:

| Operation | When | Notes |
|---|---|---|
| `create_issue` | File a new follow-up | `type: followup`; labels include `followup` plus type-shape (`bug` or `enhancement`) plus area. |
| `list_open_issues` | Search for related issues to fill the "Related" block; check whether a followup already exists for the same scope | Filter by `label: followup` and optionally by keyword. |
| `edit_body` | Update body when parent PR merges and the branch ref needs to be swapped for the PR number | Whole-body replace; skill is responsible for read-modify-write. |
| `close_issue` | Manual close (won't-do / superseded / fixed-by-other-PR) | Optional `comment` argument. |

**Explicitly NOT used:** `link_sub_issue`. Follow-ups are not
sub-issues; parent linkage is the body's Parent block plus the
`followup` label. The skill prose calls this out so an agent doesn't
accidentally reach for it.

## Out of scope

- Backend implementation changes — purely consumes the v1 contract.
- Jira backend — Phase 3.
- `/resume-initiative`, `/tracker-init`, `/tracker-doctor` — Phase 3.
- Examples / workflows / CI — Phase 4.
- Trading-bot Phase-5 cutover — separate epic phase.
- Literal-diff verification vs source — explicitly deferred. The
  "behaviour-change-zero" invariant is a methodology guarantee
  (terminology, ordering, bail criteria, lifecycle), not a byte-for-byte
  guarantee. `#11` and `#12` confirmed controller-side leak-greps +
  cold-read are sufficient.

## Testing strategy

No code-test suite — the plugin has no test runner. Verification is
purely controller-side grep + cold-read, matching the established
#11/#12 pattern.

| Check | Method |
|---|---|
| No `maxdimitrov/trading-bot` literal | `grep -r "maxdimitrov/trading-bot" skills/followup-tracking templates/followup-body.md` — expected no matches |
| No trading-bot-specific skill or path leaks | `grep -rE "PENDING-FIXES\|/fix-issue\|ic-memo-framework\|dca-router\|dashboard-maintenance\|reserve-ledger"` — expected no matches |
| All 5 followup-specific blocks present in template | `for block in "Parent" "What's already done" "What's been tried" "Related" "Why deferred"; do grep -q "$block" templates/followup-body.md; done` |
| Backend dispatch cited | `grep -E "create_issue\|backends/<backend>\.md\|configured backend" skills/followup-tracking/SKILL.md` — expected at least one match |
| Sibling cross-links present | `grep -E "bug-tracking\|feature-request" skills/followup-tracking/SKILL.md` — expected matches |
| Title-suffix is tracker-neutral | `grep -F "(followup #" skills/followup-tracking/SKILL.md` — should NOT appear as a hard-coded literal in the skill prose; backend module renders the syntax |
| Cold-read | Read both files end-to-end with no source context; verify the methodology reads correctly without trading-bot pre-knowledge. |
| Optional markdown lint | If `.markdownlint.json` exists at the plugin root, run `npx --yes markdownlint-cli` against both files. |

## Workflow

1. Already done — worktree at
   `F:\Claude\Projects\agent-issue-tracker\.claude\worktrees\feat+port-followup-tracking-skill`
   on branch `feat/port-followup-tracking-skill` off `origin/main`
   (commit `73a31ca`). Source skill staged in the worktree as
   `.followup-tracking-source.md` (312 lines).
2. Write this spec to
   `docs/superpowers/specs/2026-05-27-port-followup-tracking-skill-design.md`
   on the feature branch. Commit.
3. Invoke `writing-plans` to produce the per-issue implementation plan
   at `docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md`.
   Commit.
4. Execute the plan via `subagent-driven-development` (per the user's
   global CLAUDE.md). Each subagent's prompt starts with `cd <worktree
   absolute path> && git status` per the project's Subagent CWD
   discipline. Verbatim-content tasks dispatched to haiku-model
   subagents.
5. Controller-side verification per the table above. Cold-read
   reviewer pass.
6. Update `CHANGELOG.md` `[Unreleased] → ### Phase 2 (in progress)`.
7. Open PR against `maxdimitrov/agent-issue-tracker` `main` with
   `Closes #13`. Backlink the parent epic
   `maxdimitrov/trading-bot#153` in the PR body. Use the standard
   `Fixes #N` / `Closes #N` close-on-merge convention.
8. On merge: delete the feature branch; remove the worktree directory;
   update epic #153's Status block (Phase 2 → 5/15 closed; Next up:
   `agent-issue-tracker#14` — port initiative-tracking).

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Block-ordering drift between source and §6 of the issue body | Lock in source ordering; document the deliberate divergence-from-§6 in the implementation plan (Decision 2). |
| `link_sub_issue` accidentally invoked by an agent reading the skill | Skill prose explicitly notes "follow-ups are NOT sub-issues; never call `link_sub_issue` from this skill". |
| Cross-skill drift between sibling templates after `#14` lands | Out of scope here. If `#14`'s landing surfaces drift, file via `followup-tracking` (this skill). |
| The "Related issues" `list_open_issues` reframe could lose the `gh search` keyword nuance | Skill prose explicitly says "filter optionally by keyword if your backend supports it; otherwise document the search you ran inline." |
| Subagent commits land on `main` instead of the feature branch | Every subagent prompt MUST start with `cd <full-worktree-path> && git status`; controller runs `git log -1 --format='%H %s' feat/port-followup-tracking-skill` after every implementer returns. Belt-and-suspenders per project memory `feedback_subagent_cwd_not_worktree`. |

## Resume from here

The implementation plan ships at
`docs/superpowers/plans/2026-05-27-port-followup-tracking-skill.md` on
the feature branch. Open the plan to pick up execution. The plan's task
ordering mirrors the #11/#12 6-task shape:

1. Frontmatter + opening + type-orthogonal section.
2. Why structure matters + when-to-file + filing + template pointer.
3. Block-by-block-why + when-parent-has-not-landed + labels + closing.
4. Example (cli/list chain).
5. `templates/followup-body.md` (self-contained 12 blocks).
6. CHANGELOG entry + final controller-side verification + PR open.
