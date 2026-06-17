---
name: feature-request
description: >-
  How feature requests, enhancements, new capabilities, and redesigns are
  tracked — they go in the configured issue tracker (see
  `.claude/issue-tracker.yaml`) with the `enhancement` label, not in chat
  and not as `// TODO` code comments. Issues here are consumed by Claude
  Code agents, which means the body is an **agent prompt**, not a human
  note — it must give a clear locus, scope boundaries, and writable
  acceptance criteria or no agent can pick it up. Use this skill whenever
  a new capability, missing feature, redesign idea, "it would be nice
  if...", "we should add...", or planned improvement surfaces; whenever
  filing, triaging, labelling, or closing enhancement issues; when
  opening a PR that ships a requested feature; and any time the user
  says "feature request", "add this to the backlog", "we should build
  X", or asks what is planned vs. shipped. The siblings bug-tracking
  (defects) and followup-tracking (scope deferred from in-flight work)
  cover the other two issue shapes. Covers the capability-vs-defect
  framing, the `enhancement` label + area labels, the agent-execution
  issue body template, the backend dispatch contract from
  `backends/_interface.md`, PR linkage via the backend's close-on-merge
  convention, and the enhancement lifecycle.
---

# Feature Requests — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the eight operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the literal
CLI / MCP invocation for each operation.

A feature idea noted only in chat is forgotten the moment the session
ends. A `// TODO` rots — no one re-reads them. An idea filed as a
well-formed issue can be picked up by a Claude Code agent: the agent
loads the relevant project skills, writes the change, runs the
verification suite, and opens a draft PR. So **the body of every issue
is an agent prompt**, not a human note.

This skill is the enhancement-side counterpart to `bug-tracking`. Same
tracker, same backend dispatch, same lifecycle — different shape of body
(no symptom/repro, but a sketch and an acceptance contract).

**Slash-command entry-point.** [`/file-feature`](../../commands/file-feature.md)
is a discoverable wrapper around this skill — it surfaces in Claude Code's
command palette and triggers the exact flow described here, adding no behaviour
of its own. This skill is the source of truth; filing by intent ("file a
feature request") is equivalent.

## Why structure matters

A vague feature request burns an agent run on guesswork. A structured
one bounds the work and ships a draft PR. An agent (an issue-fix agent
if your project has one, or any agent picking the issue up cold) will
**bail** (refuse to work it, leave a comment, no PR) on:

- No clear locus — body doesn't name where the feature lives.
- Open design question — there's a real choice the agent can't make
  unilaterally.
- No writable acceptance signal — no measurable "done when".
- Unbounded scope — body lists "and also..." for several pages.

If the feature has a real open design question, that's fine — file it
anyway, tag `needs-design`, and accept that a human pass (likely a
brainstorm) happens before any agent works it.

## Bug vs. feature — quick disambig

| Signal | Bug | Feature |
|---|---|---|
| Existing behaviour is wrong | yes | no |
| Component crashes / returns wrong value | yes | no |
| Capability does not exist yet | no | yes |
| "It would be nice if..." | no | yes |
| User-visible regression | yes | no |
| Refactor / redesign of working code | no | yes |

If it's scope spun out of an in-flight PR, use `followup-tracking` instead.

## When to file

File a feature request when:

- You want a capability the project does not have yet — a new command,
  a new UI panel, a new endpoint, a new automation.
- An existing feature works correctly but could be materially better —
  a redesign, a UX improvement, a new flag, a performance pass.
- The user says "we should also add X" or "let's track that for later"
  and the thing is genuinely new capability.

Do **not** file when:

- You are building it right now in the current change.
- It is pure speculation with no clear user value.
- It already exists — search the tracker first (your backend's
  `list_open_issues` operation, optionally filtered by keyword). If a
  similar issue exists, comment on it with the new context instead of
  duplicating.
- The thing is broken — that's a bug; use `bug-tracking`.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:` in
`.claude/issue-tracker.yaml`. Pass:

- `type`: `feature`
- `title`: `<component>: <capability>` (see Title format below)
- `labels`: `[enhancement, <area>]` where `<area>` is one of your
  configured `areas:` enum
- `body`: the filled-in `templates/feature-body.md` template

**Title format:** `<component>: <capability>`. Component is the
path-like locus (e.g. `cli/list`, `worker/queue`, `dashboard/overview`).
Examples: `cli/list: support --json output format`,
`worker/queue: add dead-letter retention policy`,
`dashboard/overview: per-environment status panel`.

## Agent-execution issue body template

The body template lives at `templates/feature-body.md` in this plugin.
Use it verbatim — each section maps to a step an agent picking up the
issue cold will take. Sections marked **[required]** are what an agent
reads to decide whether to work the issue or bail.

See `templates/feature-body.md` for the canonical skeleton with
placeholders.

### What each required field unlocks

- **Locus** — names where the feature lives so the agent knows what to
  open first. New files should be named.
- **Skills to load** — gets the agent the subsystem conventions; without
  this it may invent patterns that conflict with existing code.
- **What's missing + Why** — frames the problem so an agent can judge
  whether its draft solves it.
- **Sketch** — bounds the solution space. An empty Sketch with
  `needs-design` tag is honest; a missing Sketch is bait-and-switch.
- **Constraints** — bounds the blast radius. Most "small features"
  sprawl because no one wrote down what's out of scope.
- **Acceptance** — must be testable. Vague acceptance is the most common
  reason agent drafts get rejected at review.
- **Verify** — the exact commands the agent runs at the end.

## Labels

| Type | Meaning |
|---|---|
| `enhancement` | A new capability, redesign, or improvement. |
| `bug` | (sibling skill) A defect, regression, or known gap. |

**Area labels** are project-specific. The consumer's
`.claude/issue-tracker.yaml` lists the project's valid `areas:` enum
(e.g. `dashboard / backend / frontend / infra`, or whatever the consumer
chose). Pick the matching area from that enum when filling the `area`
label.

Triage flags:
- `needs-design` — open design question, no sketch yet.
- `needs-triage` — body is missing required fields.

Agents skip both.

## Closing the loop

A PR that ships a feature must follow the backend's close-on-merge
convention — see `backends/<backend>.md` PR close-on-merge section.

For example, on the `github` backend the convention is to include the
literal line `Closes #N` in the PR title or body so GitHub auto-closes
the issue when the PR merges to the default branch. Prefer `Closes`
over `Fixes` for feature PRs — the thing wasn't broken; the linguistic
distinction is a recommendation, not a backend-enforced rule. Other
backends document their own conventions (e.g. Jira may auto-close via a
PR-integration hook configured outside the plugin).

If the idea is abandoned (better path found, no longer relevant,
won't-build), close by hand with the backend's `close_issue` operation
and a one-line reason.

## At the start of work

The backend's `list_open_issues` operation filtered by `{type: feature}`
shows the current capability backlog — useful before proposing new
direction. Filter additionally by the `needs-design` label to see the
ideas that still need a human brainstorm pass.

## Example — a well-formed feature request

````markdown
## Goal
`cli/list` supports a `--json` output format that emits each row as a
JSON object on its own line (NDJSON), instead of only the existing
human-formatted table.

## Locus
- File: `cli/list.py:42` (`render_list`)
- New helper: `cli/_format_json.py` (pure functions)
- Subsystem: cli   # from your configured `subsystems:` enum

## Skills to load
- <your-cli-architecture-skill>
- <your-output-format-conventions-skill>

## What's missing
`cli/list` only prints a fixed-width table. Downstream automation has
no machine-readable shape — consumers pipe through `awk` to parse.

## Why
A scriptable `--json` flag unblocks an automation that currently shells
out, parses, and reformats the table. It also lays the groundwork for
a planned `--format=<json|table|csv>` family. Without it, every
consumer reinvents the parser.

## Sketch
- Add `cli/_format_json.py` with `to_ndjson(rows) -> str` — pure, no
  I/O.
- `cli/list.py:render_list` branches on the `--json` flag.
- Default behaviour (no flag) is byte-identical to today.
- No schema versioning yet — out of scope.

## Constraints
- Out of scope: the storage layer that produces `rows` — already stable.
- Invariants: existing table output is byte-identical when `--json` is
  not passed.
- Dependencies: none.
- Style: minimal change; no drive-by refactors.

## Acceptance
- [ ] `cli list --json` prints one JSON object per row, NDJSON-shaped.
- [ ] `cli list` (no flag) output is byte-identical to before.
- [ ] Empty result set with `--json` prints zero lines, exit 0.

## Verify
```bash
pytest -q tests/test_cli_list.py
pytest -q
```
````

---

See also: `skills/bug-tracking/` for the defect-shaped sibling.
`followup-tracking` (scope deferred from in-flight work),
`initiative-tracking` (multi-issue epics).
