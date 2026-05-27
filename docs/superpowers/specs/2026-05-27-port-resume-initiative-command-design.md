# Port `/resume-initiative` Slash Command — Design Spec

**Date:** 2026-05-27
**Tracker:** [`agent-issue-tracker#20`](https://github.com/maxdimitrov/agent-issue-tracker/issues/20)
**Parent epic:** [`maxdimitrov/trading-bot#153`](https://github.com/maxdimitrov/trading-bot/issues/153) — Phase 3 slash commands.
**Parent design spec:** `docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md` (on `maxdimitrov/trading-bot` main, squash-commit `ff6cbcea436e4095c37bbf6d8b5f9c728837322e`) — §5.6 and §6.2 are the binding sections.
**Source to port from:** `.claude/commands/resume-initiative.md` on `maxdimitrov/trading-bot` `main`.

## 1. Goal

`commands/resume-initiative.md` exists in this plugin as a tracker-agnostic port of the same-named slash command from `maxdimitrov/trading-bot`. Consumers can install the plugin and run `/resume-initiative` against epics tracked in either backend (GitHub or Jira), listing open epics, parsing the Status block, showing the next-up child, and (with `--start`) creating a worktree in the consuming project and handing off to `superpowers:brainstorming` inline.

The command dispatches through the seven-operation contract from `backends/_interface.md` rather than calling `gh` directly, parses both `#N` (GitHub) and `PROJ-123` (Jira) refs in the Status block's `Next up:` line, and handles cross-repo epics (parent on one repo, children on another) by reading the `## Children` task-list mirror in the epic body — the canonical cross-backend child-discovery path per `skills/initiative-tracking/SKILL.md`.

## 2. Non-goals

- `/tracker-init` interactive scaffolder — separate Phase 3 sub-issue.
- `/tracker-doctor` validator — separate Phase 3 sub-issue.
- `backends/jira.md` (Atlassian Remote MCP dispatch module) — separate Phase 3 sub-issue. The port dispatches through `view_issue` / `list_open_issues` abstractly; acceptance is that the contract is honoured, not that both backends are tested end-to-end here.
- Trading-bot Phase 5 cutover (deletes the trading-bot version of this command) — separate Phase 5 sub-issue against trading-bot.
- Examples, workflow walkthroughs, CI — Phase 4.
- Live end-to-end smoke against `#153` itself across both backends — Phase 4 smoke-test work. Static acceptance grep checklist + cold-read review are the gate for this PR.

## 3. Form-factor + dependency decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| File location | `commands/resume-initiative.md` | Matches the slash-command convention used by the four Phase 2 skills (`skills/<name>/SKILL.md`) and the parent design spec §5.1 repo layout. |
| Dispatch depth | Contract-level prose (`list_open_issues` / `view_issue`); literal calls deferred to `backends/<backend>.md` | Same pattern as the four Phase 2 ports. Keeps the command tracker-agnostic. |
| Source format | Markdown with YAML frontmatter (`description:` field) | Slash-command convention; source already in this shape. |
| Cross-backend child discovery | `## Children` task-list mirror is canonical; native sub-issue API queries demoted to optional augmentation | The only mechanism that spans repos and backends. Native `sub_issues` is single-repo on GitHub and project-scoped on Jira. Cross-repo case is real (epic `#153` indexes children on agent-issue-tracker). |
| Cross-repo ref shapes documented | Three: `#N` (same repo), `owner/repo#N` (cross-repo GitHub), `PROJ-123` (Jira) | The parent epic for this very plugin is cross-repo. Documenting two would miss the binding case. |
| Mixed-backend child handling | Soft warning + skip + continue | Operators may legitimately track some children in different trackers during transitions (e.g. partway through a tracker migration). Hard error would block resumption. |
| Mode 3 worktree CWD | Always the consumer's CWD, even for cross-repo `owner/repo#N` children | The operator's working tree is local; only the child issue body fetch hits the child's repo via the backend. |
| `EnterWorktree` branch-name caveat | Preserved verbatim from source | Documents a real harness behaviour, tracker-neutral, bites every operator. |
| Missing-config bail message | Soft forward-reference to `/tracker-init` | That command lands in a parallel Phase 3 sub-issue; operator-facing bail messages should name the recovery path even before it ships. |
| Frontmatter `description:` field | Preserved verbatim modulo dropping the trading-bot literal name | Behaviour-change-zero invariant from parent design spec §8.2. |

## 4. Architecture

### 4.1 File touched

Single new file:

```
commands/resume-initiative.md     # NEW; ~200-260 lines, markdown + YAML frontmatter
CHANGELOG.md                      # one-line append under [Unreleased] → Phase 3
```

No skills, no templates, no backend modules. The command is the deliverable; the dispatch glue already exists (Phase 1 #9, Phase 2 #14).

### 4.2 Dispatch contract — operations used

The command uses three operations from `backends/_interface.md`:

| Operation | Used in mode | Purpose |
|---|---|---|
| `list_open_issues({label: "epic"})` | Mode 1 | List all open epics |
| `view_issue({ref})` | Modes 1, 2, 3 | Read epic body to parse Status block; read child body in Mode 3 to seed the brainstorm handoff |
| (no `link_sub_issue`, no `create_issue`, no `edit_body`, no `close_issue`, no `add_label`) | — | This command is read-only against the tracker. |

### 4.3 Invocation modes (unchanged from source)

| Invocation | Behaviour |
|---|---|
| `/resume-initiative` | Mode 1 — list open epics, ask operator to pick |
| `/resume-initiative <ref>` | Mode 2 — load epic, display phases + next-up child, ask operator what to do |
| `/resume-initiative <ref> --start` | Mode 3 — load epic, enter worktree for next-up child, hand off to `superpowers:brainstorming` inline |

The `<ref>` value accepts both `#N` (or bare `N`) and `PROJ-123` shapes. Mode 1's listing is the only place the command is backend-agnostic without an explicit ref — Modes 2 and 3 take an operator-supplied ref whose syntax tells the command which backend to dispatch to.

### 4.4 Cross-repo `## Children` task-list parsing

The canonical child-discovery path is parsing the `## Children` task-list mirror in the epic body. For each unchecked `- [ ] <ref> — <title>` line, the command must handle three ref shapes:

| Ref shape | Backend resolution | Example |
|---|---|---|
| `#N` (bare) | Same repo as the epic; use the configured `github.repo` | `#42 — worker/queue refactor` |
| `owner/repo#N` | Explicit cross-repo GitHub ref; use that `owner/repo`, NOT the configured one | `maxdimitrov/agent-issue-tracker#20 — Phase 3: port /resume-initiative command` |
| `PROJ-123` | Jira issue key (project-scoped) | `TRADE-42 — worker/queue refactor` |

**Mixed-backend handling:** if the configured backend is `github` and a `PROJ-123`-shaped ref appears in the mirror (or vice versa), log a one-line soft warning ("skipping child `<ref>` — ref syntax doesn't match the configured backend") and continue with the remaining children. Do NOT crash.

**Native sub-issue API augmentation:** the command MAY additionally query the backend's native sub-issue relation when the parent ref is same-backend and same-repo, but the result is *displayed alongside* the task-list parse, not used in place of it. The canonical source is always the task-list mirror.

### 4.5 Mode 3 worktree creation

The worktree is created via `superpowers:using-git-worktrees` (or the native `EnterWorktree` tool) in the **consumer's current CWD**, regardless of whether the next-up child is in the same repo as the epic or in a different repo via `owner/repo#N`. The branch name is taken from the child issue body's `Branch:` line if present, otherwise inferred from the child's labels:

- `enhancement` → `feat/<short-slug>`
- `bug` → `fix/<short-slug>`
- `documentation` → `docs/<short-slug>`

**`EnterWorktree` branch-name caveat (preserved verbatim from source):** the native `EnterWorktree` tool sanitizes branch names to `worktree-<slug>+<rest>` (the `/` in `feat/...` becomes `+`). Immediately after `EnterWorktree` returns, rename the branch in place:

```bash
git branch -m worktree-<sanitized> <conventional-name>
```

The worktree directory keeps its `<sanitized>` name; only the branch is renamed.

### 4.6 Inline brainstorm handoff (preserved verbatim from source)

After the worktree is created, the session's CWD is already inside the worktree (`EnterWorktree` switched it). The command fetches the child issue body via the backend's `view_issue({ref: child-ref})` and hands off to `superpowers:brainstorming` with that body as the brainstorm input — the body is already an agent prompt (Goal, Locus, Sketch, Acceptance, Verify), so brainstorming uses it as starting context, not as a re-derivable problem.

**Do NOT stop and ask the operator to open a new window.** This inline handoff is the default path. The same convention applies when re-entering an existing worktree via `EnterWorktree path=...`.

## 5. The transforms applied

### 5.1 Standard de-trading-bot-ification (per parent design spec §6.1)

| Source reference (trading-bot) | Port reference (plugin) |
|---|---|
| `gh issue list --repo maxdimitrov/trading-bot --label epic --state open` block | invoke `list_open_issues({label: "epic"})`; see `backends/<backend>.md` |
| `gh issue view <N> --repo maxdimitrov/trading-bot --json ...` block | invoke `view_issue({ref})`; the backend module documents the literal call |
| `gh api repos/maxdimitrov/trading-bot/issues/<N>/sub_issues` block | (removed from primary path; see §5.2(c)) |
| Hardcoded `--repo maxdimitrov/trading-bot` everywhere | configured `github.repo` (GitHub) or project-scoped (Jira); read from `.claude/issue-tracker.yaml` in the consumer |
| `#N` ref syntax assumption in display + parsing | accept both `#N` and `PROJ-123`; backend module renders refs, command parses both |
| `gh auth status` failure-mode advice | tracker-neutral: "if the backend reports auth failure, see `backends/<backend>.md` setup section and re-invoke" |
| Cross-link to `initiative-tracking` skill via project-local path | cross-link via skill name only (`skills/initiative-tracking/SKILL.md`) — same-plugin namespace |

### 5.2 The four surgical transforms specific to this command (per §6.2 of issue #20)

a. **Mode 1's epic list query becomes a backend dispatch.** Source runs a single `gh issue list ... --json number,title,body,updatedAt` and parses the inline `body`. The plugin's `list_open_issues({label: "epic"})` returns `[{ref, title, status}]` — body is NOT returned. The port iterates the result and calls `view_issue({ref})` per epic to pull the body. N+1 cost is acceptable: open-epic count is typically <20 (the source documents `--limit 20`). The display shape (`<ref>  <title>  <phase>  <next-up>`) stays.

b. **Status-block parser accepts both `#N` and `PROJ-123` in the `Next up:` value.** The four field-prefix strings (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) are byte-identical to the source — canonical per `skills/initiative-tracking/SKILL.md`'s "Status block — exact field spec" table. The parser treats the substring before ` — ` in the `Next up:` value as opaque (it could be `#42`, `owner/repo#42`, or `PROJ-123`); it does NOT regex against `#\d+`.

c. **Cross-repo + cross-backend child discovery — task-list mirror is canonical.** Source documents both the native `sub_issues` API (primary) and the task-list fallback (secondary). Plugin flips: parsing the `## Children` task-list mirror is THE canonical cross-backend path per `skills/initiative-tracking/SKILL.md` ("the cross-backend source of truth"). Native sub-issue API queries are optional augmentation, displayed alongside the parse but not relied upon. For each unchecked task-list entry, the command handles the three ref shapes in §4.4.

d. **Mode 3's worktree creation lands in the consumer's CWD.** The source's `EnterWorktree` / `using-git-worktrees` mechanic is already tracker-agnostic — what changes is the child body fetch: source uses `gh issue view <child-N> --repo maxdimitrov/trading-bot --json body`. Plugin port invokes `view_issue({ref: child-ref})`, where `child-ref` may carry an `owner/repo#N` prefix for cross-repo cases. Worktree still lands in the consumer's CWD; only the body fetch hits the child's repo via the backend.

### 5.3 Failure modes — six scenarios

| # | Source | Plugin port |
|---|---|---|
| 1 | `gh` not on PATH or unauthenticated → "run `gh auth status` and re-invoke" | "the configured backend reports a reachability failure → run `/tracker-doctor` and re-invoke" |
| 2 | `gh issue view` returns 404 | "the configured backend's `view_issue` returns not-found → check the ref syntax matches the configured backend (`#42` vs `PROJ-123` vs `owner/repo#42`)" |
| 3 | No open epics | unchanged — "tell the operator, do not crash" |
| 4 | Status block fields missing | unchanged — "report which fields are missing; suggest the operator runs `initiative-tracking` to rewrite the epic body" |
| 5 | `--start` invoked but `Next up:` is `none` or no children | unchanged — "report 'no next-up child to start' and exit; do not create a worktree from nothing" |
| 6 (NEW) | Mixed-backend `## Children` entry / cross-repo `owner/repo#N` ref | "log a one-line soft warning and skip the mismatched entry; for `owner/repo#N` refs extract the prefix and pass it through to the backend's `view_issue`" |

### 5.4 Conventions block — generalized

The source's "Conventions assumed" section lists three: epic body has a Status block, `epic` label is the source of truth, children link back via native sub-issue + Parent epic body line. The plugin port preserves these but reframes the third: children link back via the `## Children` task-list mirror in the parent (canonical) AND (when same-backend, same-repo) via native sub-issue linkage (optional augmentation) AND via a `## Parent epic` block in the child body (per `templates/sub-issue-body.md`).

### 5.5 Frontmatter

YAML frontmatter preserved with one transform — drop any trading-bot-specific phrasing from the `description:` field. The shape:

```yaml
---
description: Show open epic initiatives and the next-up child issue; optionally start work on the next child.
---
```

## 6. Acceptance (issue-level)

Lifted from `agent-issue-tracker#20`:

- [ ] `commands/resume-initiative.md` exists; renders cleanly; YAML frontmatter present and tracker-agnostic.
- [ ] No literal `maxdimitrov/trading-bot` string.
- [ ] No bare `gh ` shell-out commands in the prose other than inside backend-citation paragraphs (the canonical path is `view_issue` / `list_open_issues`).
- [ ] Both `#N` and `PROJ-123` named as acceptable `Next up:` ref syntaxes.
- [ ] Cross-repo `owner/repo#N` shape documented; distinct from same-repo `#N`.
- [ ] `## Children` task-list mirror named as the CANONICAL cross-backend child-discovery path; native sub-issue API queries documented as optional augmentation.
- [ ] Three invocation modes (no-arg list / `<N>` show / `<N> --start` worktree) preserved with source behaviour.
- [ ] Mode 3 inline brainstorm handoff preserved verbatim (the "do NOT stop and ask the operator to open a new window" guarantee).
- [ ] Failure-mode section covers all six scenarios from §5.3.
- [ ] `CHANGELOG.md` `[Unreleased]` → `Added` line notes the `/resume-initiative` command (Phase 3 entry).

## 7. Verification

Static grep gates (no code, no pytest — markdown-only):

```bash
test -f commands/resume-initiative.md

# Leakage gates
grep -F "maxdimitrov/trading-bot" commands/resume-initiative.md && echo LEAK || echo clean
grep -nE "^gh " commands/resume-initiative.md && echo BARE-GH || echo clean

# Canonical Status-block field prefixes
for field in '- \*\*Phase:\*\*' '- \*\*Next up:\*\*' '- \*\*Current branch:\*\*' '- \*\*Last updated:\*\*'; do
  grep -qE "$field" commands/resume-initiative.md || { echo "MISSING $field"; exit 1; }
done

# Both ref shapes
grep -qE '#N|#<N>' commands/resume-initiative.md
grep -qE 'PROJ-123|PROJ-<N>|<PROJECT>-<N>' commands/resume-initiative.md

# Cross-repo case documented
grep -qE 'owner/repo#' commands/resume-initiative.md

# Task-list mirror cited as canonical
grep -qE '## Children|task-list' commands/resume-initiative.md

# Backend operation dispatch
grep -qE 'view_issue|list_open_issues' commands/resume-initiative.md

# Markdown lint (if config exists)
[ -f .markdownlint.json ] && npx --yes markdownlint-cli commands/resume-initiative.md
```

Live smoke (deferred to Phase 4 per §2):

```bash
# In a consumer with .claude/issue-tracker.yaml pointing at maxdimitrov/trading-bot:
/resume-initiative                  # Mode 1 — should list epic #153 (+ others)
/resume-initiative 153              # Mode 2 — should display Phase 2, next-up agent-issue-tracker#15
                                    #   (cross-repo task-list parse exercised)
/resume-initiative 153 --start      # Mode 3 — should create worktree, hand off to brainstorming
                                    #   inline against #15's body
```

## 8. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Status-block field-prefix strings diverge from `skills/initiative-tracking/SKILL.md` | Static grep gate (§7) asserts the four exact strings appear in the command prose. If the SKILL changes the format, both files must change in the same PR. |
| Cross-repo ref parsing misses a shape (e.g. URL form `https://github.com/owner/repo/issues/N`) | Out of scope for this PR. Document the three canonical shapes; URLs would be a follow-on enhancement filed against agent-issue-tracker. |
| Mode 3 worktree creation in a non-git directory (consumer's CWD is not a repo) | Cite `superpowers:using-git-worktrees` for that skill's handling; do not duplicate the failure-mode prose. |
| The command references `/tracker-init` / `/tracker-doctor` that don't exist yet at merge time | Acceptable — they're parallel Phase 3 sub-issues, all land before Phase 4 smoke. Operator-facing bail messages naming the recovery path are operator-readable even if the command doesn't exist yet. |
| Behaviour-change regression against source for the single-repo GitHub case | Static grep checklist + cold-read review against source bytes. Same discipline that caught the en-dash regression in PR #19. |

## 9. Open questions (deferred)

- URL-form ref parsing (`https://github.com/owner/repo/issues/N`) — follow-on if real demand surfaces.
- Per-backend Mode 1 "recent activity" sort (Jira's `searchJiraIssuesUsingJql` supports `ORDER BY updated`; GitHub's `gh issue list` does too). Source uses `updatedAt` from the JSON; the plugin contract's `list_open_issues` doesn't return that. Acceptable: list in backend-default order; if sort matters, file a follow-on against the contract.
- Live cross-repo smoke against `#153` — Phase 4 work. Static acceptance is the gate for this PR.

## 10. Notes

- Source retrieval:
  ```bash
  gh api repos/maxdimitrov/trading-bot/contents/.claude/commands/resume-initiative.md \
    --jq .content | base64 -d
  ```
- Trading-bot epic `#153` is itself the cross-repo test case — children currently include `agent-issue-tracker#15` (open) and this issue `#20` (open at design-time). Running `/resume-initiative 153` against it after Phase 3 ships is the smoke test that the cross-repo task-list-mirror path works end-to-end.
- The `EnterWorktree` branch-name caveat is verbatim from source because it documents a real harness behaviour that bites every operator and is tracker-neutral. Do not paraphrase or generalize it.
- This is the FIRST plugin port whose dispatch is fully tracker-agnostic AND must work cross-repo. The four Phase 2 skill ports dispatch through the contract but don't enumerate children — only this command does. The cross-repo case is what forces the task-list-mirror flip from "fallback" to "canonical."
- Sibling Phase 3 sub-issues (`/tracker-init`, `/tracker-doctor`, Jira backend) are independent and can be picked up in parallel after this lands.
- The pre-Task-1 spec-then-plan-commit discipline established in #12 and re-validated in #13/#14 applies here: spec commits first, plan commits second, both before any Task 1 implementation work.
