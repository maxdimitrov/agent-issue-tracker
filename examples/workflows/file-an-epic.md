# Walkthrough: filing an epic + sub-issues

This page shows what happens when you ask Claude Code to scope a multi-week initiative — an epic plus its sub-issue index — against a GitHub-backed project. The evergreen description this walkthrough produces is what [`/resume-initiative`](../../commands/resume-initiative.md) reads weeks later when you return to the work; everything else — child status, counts, next-up — is derived live from the tracker at that point, never written here.

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

## 3. Body draft — evergreen

The skill fills [`templates/epic-body.md`](../../templates/epic-body.md). The description is **evergreen**: `## Goal`, `## Scope`, `## Success criteria`, `## Design spec` only — no phase state, no child list, no status fields. It is edited again only if the initiative's own goal or scope changes, never per sub-issue.

```markdown
## Goal
api, worker, and scheduler all log via a shared `obs/logging` module
with one format, one rotation policy, and one redaction pass — the
three subsystem-local logger modules are deleted.

## Scope
In:
- A shared `obs/logging` module with format spec + redaction pass
- Cutover of api, worker, and scheduler to the shared module

Out:
- Log aggregation / shipping (existing pipeline unchanged)

## Success criteria
- [ ] `obs/logging` is the only logger module in the tree
- [ ] api, worker, and scheduler produce identically-formatted log lines
- [ ] Redaction pass covers all previously-logged secret fields

## Design spec
- `docs/superpowers/specs/2026-05-28-shared-logging-design.md`
  (branch `main`, commit `<sha>`)
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

## 5. Machine-block comment — the decision log

Nothing about phase membership is known yet (no sub-issues exist), so the only non-derivable structure at file time is the initial decision. The skill posts a marker-tagged comment carrying just that section, via `upsert_comment`:

```markdown
<!-- agent-issue-tracker:machine-block -->

## Decision log
- **2026-05-28** — Epic filed. Cutover-style sequencing: Phase 0
  ships skeleton + spec; Phase 1 cuts over all three subsystems in
  one PR (no per-subsystem feature flag — design spec §6).
```

```bash
gh issue comment 200 --repo your-org/your-repo --body-file <machine-block.md>
```

A flat epic with no phases, no branch, no probe, and no decisions to log yet would carry no comment at all — the machine block is entirely optional.

## 6. Filing the four sub-issues

Sub-issues are filed AFTER the epic, in a separate batch. Each sub-issue uses [`templates/sub-issue-body.md`](../../templates/sub-issue-body.md) (a thin wrapper around the relevant feature/bug body plus a `## Parent epic` block) and references the epic by ref.

You type:

> file the four sub-issues for #200 — Phase 0a (the `obs/logging` skeleton), Phase 0b (the format spec), Phase 1a (api + worker cutover), Phase 1b (scheduler cutover + delete legacy loggers).

For each, the skill:

1. Fills `templates/sub-issue-body.md` with sub-issue-specific Goal / Locus / Acceptance.
2. Calls `create_issue` with `type: sub`, `parent: #200`.
3. Calls `link_sub_issue(parent_ref=#200, child_ref=#<new>)` to create the native GitHub sub-issue relationship — this is what `/resume-initiative` derives child membership from.

GitHub returns `#201`, `#202`, `#203`, `#204`.

## 7. Updating the machine block's phase map

After all four sub-issues are filed, the skill re-reads the machine-block comment (`read_comments`) and appends the phase map — a read-modify-write `upsert_comment`, same destructive whole-comment-replace shape as a body edit:

```markdown
<!-- agent-issue-tracker:machine-block -->

## Phases
- **Phase 0** — `obs/logging` skeleton + format spec + redaction pass — #201, #202
- **Phase 1** — cutover (api, worker, scheduler) + delete subsystem loggers — #203, #204

## Decision log
- **2026-05-28** — Epic filed. Cutover-style sequencing: Phase 0
  ships skeleton + spec; Phase 1 cuts over all three subsystems in
  one PR (no per-subsystem feature flag — design spec §6).
```

The phase map holds **refs only** — no titles, no status. Titles and open/closed state are always re-fetched live by `/resume-initiative`, so this comment never needs another write when a child closes, is retitled, or is reprioritized.

## 8. Result

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

- **`backend: jira`** — same flow, different refs. The epic comes back as `LOG-1`; sub-issues as `LOG-2..5`. Sub-issue linkage uses `editJiraIssue` setting `fields.parent.key` (modern Cloud) or `customfield_10014` (classic Epic Link, configurable via `jira.parent_link_style`). The machine-block comment is written via `addCommentToJiraIssue`; its `## Phases` map lines become `- **Phase 0** — ... — LOG-2, LOG-3`.
- **Cross-repo sub-issues** — if a sub-issue lives in a different repo (e.g. the initiative is tracked against `your-org/api` but one sub-issue lives in `your-org/lib`), the phase-map ref is `your-org/lib#N`. [`/resume-initiative`](../../commands/resume-initiative.md) handles all three ref shapes.
- **Bail criteria triggered** — if you said "I have a vague idea about better logging", the skill refuses: an initiative needs a design spec, named phases, and a finite sub-issue count. The bail prevents an epic that drifts into "ongoing migration" with no end state.
- **A sub-issue closes** — nothing is written, anywhere. `/resume-initiative` re-derives phase progress and next-up from `list_child_issues` on the next resume; there is no epic edit to make and no maintenance ritual to run.
- **Adopting a hand-filed epic that predates this shape** — run `/resume-initiative <ref> --adopt` to convert an epic still carrying the older body `## Status block` + `## Children` mirror into this evergreen shape in place. See [`skills/initiative-tracking/SKILL.md`](../../skills/initiative-tracking/SKILL.md) "Adopting an existing epic into the template".

## See also

- [`initiative-tracking` skill](../../skills/initiative-tracking/SKILL.md) — the methodology.
- [`templates/epic-body.md`](../../templates/epic-body.md) — the evergreen epic body skeleton.
- [`templates/epic-machine-block.md`](../../templates/epic-machine-block.md) — the machine-block comment skeleton.
- [`templates/sub-issue-body.md`](../../templates/sub-issue-body.md) — the sub-issue body skeleton.
- [`backends/github.md`](../../backends/github.md) — the `gh` dispatch reference.
- [Walkthrough: resuming an initiative](resume-an-initiative.md) — what to do weeks later when you return.
