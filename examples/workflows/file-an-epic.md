# Walkthrough: filing an epic + sub-issues

This page shows what happens when you ask Claude Code to scope a multi-week initiative — an epic plus its sub-issue index — against a GitHub-backed project. The four-line Status block this walkthrough produces is what [`/resume-initiative`](../../commands/resume-initiative.md) parses weeks later when you return to the work.

**Configured for this walkthrough:** same `.claude/issue-tracker.yaml` as [filing a bug](file-a-bug.md) — `backend: github`, project `your-org/your-repo`.

## 1. Trigger

You type into Claude Code:

> file an initiative — extract our logging into a shared package so api, worker, and scheduler all use the same format and rotation policy. Roughly four sub-issues across two phases. Design lives at `docs/superpowers/specs/2026-05-28-shared-logging-design.md`.

The phrase "file an initiative" activates the [`initiative-tracking`](../../skills/initiative-tracking/SKILL.md) skill. (Other triggers: "open an epic", "scope this initiative", "track this multi-week effort".)

## 2. Skill activation

The skill reads `.claude/issue-tracker.yaml` and dispatches through [`backends/github.md`](../../backends/github.md). It applies the initiative-tracking bail criteria:

- **Design spec exists** — `2026-05-28-shared-logging-design.md` on `main`.
- **Phases are sketched** — two phases named.
- **Scope is finite** — "four sub-issues" beats "ongoing migration".
- **Acceptance is testable** — implied by the sub-issues being concrete PRs.

No bail. Skill proceeds.

## 3. Body draft

The skill fills [`templates/epic-body.md`](../../templates/epic-body.md). Critical: the four field prefixes under `## Status block` are CANONICAL — `- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`. [`/resume-initiative`](../../commands/resume-initiative.md) parses these character-for-character.

```markdown
## Goal
api, worker, and scheduler all log via a shared `obs/logging` module
with one format, one rotation policy, and one redaction pass — the
three subsystem-local logger modules are deleted.

## Design spec
- `docs/superpowers/specs/2026-05-28-shared-logging-design.md`
  (branch `main`, commit `<sha>`)

## Status block
- **Phase:** Phase 0 · 0/4 sub-issues closed
- **Next up:** none — sub-issues to be filed after this epic lands
- **Current branch:** none
- **Last updated:** 2026-05-28

## Phases
- **Phase 0** — `obs/logging` skeleton + format spec + redaction pass —
  sub-issues: to be filed
- **Phase 1** — cutover (api, worker, scheduler) + delete subsystem
  loggers — sub-issues: to be filed

## Children
- [ ] (to be filed) — Phase 0
- [ ] (to be filed) — Phase 0
- [ ] (to be filed) — Phase 1
- [ ] (to be filed) — Phase 1

## Decision log
- **2026-05-28** — Epic filed. Cutover-style sequencing: Phase 0
  ships skeleton + spec; Phase 1 cuts over all three subsystems in
  one PR (no per-subsystem feature flag — design spec §6).

## Resume from here
Run `/resume-initiative #<epic-N>` in a fresh Claude Code session.
```

## 4. Dispatch

The skill invokes `create_issue` with `type: epic`:

```bash
gh issue create \
  --repo your-org/your-repo \
  --title "epic: extract shared logging into obs/logging" \
  --body-file <epic-draft.md> \
  --label "epic"
```

GitHub returns `#200`. The skill captures the ref.

## 5. Filing the four sub-issues

Sub-issues are filed AFTER the epic, in a separate batch. Each sub-issue uses [`templates/sub-issue-body.md`](../../templates/sub-issue-body.md) (a thin wrapper around the relevant feature/bug body plus a `## Parent epic` block) and references the epic by ref.

You type:

> file the four sub-issues for #200 — Phase 0a (the `obs/logging` skeleton), Phase 0b (the format spec), Phase 1a (api + worker cutover), Phase 1b (scheduler cutover + delete legacy loggers).

For each, the skill:

1. Fills `templates/sub-issue-body.md` with sub-issue-specific Goal / Locus / Acceptance.
2. Calls `create_issue` with `type: sub`, `parent: #200`.
3. Calls `link_sub_issue(parent_ref=#200, child_ref=#<new>)` to create the native GitHub sub-issue relationship.

GitHub returns `#201`, `#202`, `#203`, `#204`.

## 6. Updating the epic's Children block

After all four sub-issues are filed, the skill calls `edit_body` on `#200` to update the `## Children` task-list mirror:

```markdown
## Children
- [ ] #201 — obs/logging skeleton (Phase 0)
- [ ] #202 — logging format spec (Phase 0)
- [ ] #203 — api + worker cutover (Phase 1)
- [ ] #204 — scheduler cutover + delete legacy loggers (Phase 1)
```

The `## Children` task-list mirror is the **cross-backend source of truth** — it works for `#N` (same-repo GitHub), `owner/repo#N` (cross-repo GitHub), and `PROJ-123` (Jira). Native sub-issue linkage via `link_sub_issue` is additional per-backend metadata for the tracker's UI; the mirror is what every consumer of this epic reads.

## 7. Result

```text
Filed:
  Epic #200 — extract shared logging into obs/logging
  Sub-issue #201 — obs/logging skeleton (Phase 0)
  Sub-issue #202 — logging format spec (Phase 0)
  Sub-issue #203 — api + worker cutover (Phase 1)
  Sub-issue #204 — scheduler cutover + delete legacy loggers (Phase 1)

Resume with: /resume-initiative #200
```

## Variations

- **`backend: jira`** — same flow, different refs. The epic comes back as `LOG-1`; sub-issues as `LOG-2..5`. Sub-issue linkage uses `editJiraIssue` setting `fields.parent.key` (modern Cloud) or `customfield_10014` (classic Epic Link, configurable via `jira.parent_link_style`). The `## Children` task-list mirror's lines become `- [ ] LOG-2 — ...`.
- **Cross-repo sub-issues** — if a sub-issue lives in a different repo (e.g. you're tracking the initiative against trading-bot but one sub-issue lives in agent-issue-tracker), the `## Children` line is `- [ ] owner/other-repo#N — title`. [`/resume-initiative`](../../commands/resume-initiative.md) handles all three ref shapes.
- **Bail criteria triggered** — if you said "I have a vague idea about better logging", the skill refuses: an initiative needs a design spec, named phases, and a finite sub-issue count. The bail prevents an epic that drifts into "ongoing migration" with no end state.
- **Updating the Status block** — every time a sub-issue closes, the skill (or your `/audit-skills` workflow) updates the `Phase:` count and the `Next up:` line. See [`skills/initiative-tracking/SKILL.md`](../../skills/initiative-tracking/SKILL.md) §Maintenance.

## See also

- [`initiative-tracking` skill](../../skills/initiative-tracking/SKILL.md) — the methodology.
- [`templates/epic-body.md`](../../templates/epic-body.md) — the epic body skeleton.
- [`templates/sub-issue-body.md`](../../templates/sub-issue-body.md) — the sub-issue body skeleton.
- [`backends/github.md`](../../backends/github.md) — the `gh` dispatch reference.
- [Walkthrough: resuming an initiative](resume-an-initiative.md) — what to do weeks later when you return.
