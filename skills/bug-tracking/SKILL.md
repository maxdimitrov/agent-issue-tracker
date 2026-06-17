---
name: bug-tracking
description: >-
  How bugs, defects, and regressions are tracked — they go in the configured
  issue tracker (see `.claude/issue-tracker.yaml`) with the `bug` label, not
  in chat. Issues here are consumed by Claude Code agents (e.g. via an
  issue-fix loop), which means the body is an **agent prompt**, not a human
  note — it must give a clear locus, small blast radius, no open design
  question, and writable regression test, or an agent picking it up cold
  will refuse to work it. Use this skill whenever a real defect, regression,
  or broken behaviour surfaces; whenever filing, triaging, labelling, or
  closing a bug; when opening a PR that resolves a bug; and any time the
  user mentions bug tracking, defects, the known-broken list, or "we should
  track this" in a defect context. The siblings feature-request (new
  capabilities) and followup-tracking (scope deferred from in-flight work)
  cover the other two issue shapes. Covers the configured tracker as
  canonical, the label taxonomy, the agent-execution issue body template,
  the backend dispatch contract from `backends/_interface.md`, PR linkage
  via the backend's close-on-merge convention, and the issue lifecycle.
---

# Bug Tracking — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the eight operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the literal
CLI / MCP invocation for each operation.

A bug noted only in chat is lost the moment the session ends. A bug filed
as a well-formed issue can be picked up by an issue-fix agent (if your
project has one) — typically a headless agent that clones the repo, writes
a failing regression test, makes a minimal fix, runs the full verification
suite, and opens a draft PR. So **the body of every issue is an agent
prompt**, not a human note.

**Slash-command entry-point.** [`/file-bug`](../../commands/file-bug.md) is a
discoverable wrapper around this skill — it surfaces in Claude Code's command
palette and triggers the exact flow described here, adding no behaviour of its
own. This skill is the source of truth; filing by intent ("file a bug") is
equivalent.

## Why structure matters

An agent picking the issue up cold will **bail** (refuse to work it, leave
a comment, no PR) on any of:

- No clear locus — body doesn't name a file/function/route.
- Large blast radius — the change would span many files or subsystems.
- Open design question — there's a real choice to make.
- No writable regression test — no measurable signal that "fixed" means
  fixed.

A vague body wastes an agent run. A structured body gets a draft PR back.

## When to file

File an issue when:

- A real defect, regression, or broken behaviour surfaces — even mid-task,
  even if it isn't what you were working on.
- A known gap or limitation needs to be tracked.

Do **not** file an issue when:

- You are fixing it right now in the current change — just fix it, and
  describe it in the PR.
- It is pure speculation, not an observed problem.
- It already exists — search the tracker (your backend's
  `list_open_issues` operation, optionally filtered by keyword) first.
- It is feature-shaped (missing capability) — that goes through
  `feature-request`.
- It is scope deferred from an in-flight change — that goes through
  `followup-tracking`.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:` in
`.claude/issue-tracker.yaml`. Pass:

- `type`: `bug`
- `title`: `<component>: <symptom>` (see Title format below)
- `labels`: `[bug, <area>]` where `<area>` is one of your configured
  `areas:` enum
- `body`: the filled-in `templates/bug-body.md` template

**Title format:** `<component>: <symptom>`. Component is the path-like
locus (e.g. `worker/queue`, `cli/auth`, `services/payments`). Examples:
`worker/queue: retry returns 500 on dead-letter messages`,
`cli/auth: login fails when token is whitespace-padded`.

## Agent-execution issue body template

The body template lives at `templates/bug-body.md` in this plugin. Use it
verbatim — each section maps to a step an issue-fix agent will take.
Sections marked **[required]** are what an agent reads to decide auto-fix
vs bail.

See `templates/bug-body.md` for the canonical skeleton with placeholders.

### What each required field unlocks

- **Locus** — satisfies "clear, identified locus" (bail criterion #1).
- **Skills to load** — gets the agent the subsystem conventions before the
  first edit, prevents stylistic drift.
- **Symptom + Repro + Impact** — lets the agent reproduce the bug and
  prioritize.
- **Constraints** — bounds the blast radius (bail criterion #2). An issue
  that can't list "out of scope" usually has an unstated design question
  (bail criterion #3).
- **Acceptance** — must be writable as a failing test (bail criterion #4).
  If the acceptance is fuzzy, rewrite it until it isn't.
- **Verify** — the exact commands the agent runs at the end; matches the
  issue-fix agent's verification step.

If you cannot fill in all of the required fields above, the issue is
probably not auto-fixable yet — file it anyway (so it's tracked), but tag
it `needs-triage` and expect a human pass before any agent can work it.

## Labels

| Type | Meaning |
|---|---|
| `bug` | A defect, regression, or known gap. |
| `enhancement` | (sibling skill) New capability or redesign. |

**Area labels** are project-specific. The consumer's
`.claude/issue-tracker.yaml` lists the project's valid `areas:` enum (e.g.
`dashboard / backend / frontend / infra`, or whatever the consumer chose).
Pick the matching area from that enum when filling the `area` label.

Optional triage flag: `needs-triage` if any required field is missing. An
issue-fix agent will skip `needs-triage` issues.

## Closing the loop

A PR that resolves a bug must follow the backend's close-on-merge
convention — see `backends/<backend>.md` PR close-on-merge section.

For example, on the `github` backend the convention is to include `Fixes
#N` (or `Closes #N`) in the PR title or body so GitHub auto-closes the
issue when the PR merges to the default branch. Other backends document
their own conventions (e.g. Jira may auto-close via a PR-integration hook
configured outside the plugin).

Manual closures follow the same convention — use the backend's
`close_issue` operation with a one-line reason if a bug turns out to be
resolved another way (config, upstream fix, won't-fix).

## At the start of work

The backend's `list_open_issues` operation filtered by `{type: bug}` shows
the auto-fixable backlog — useful before proposing new work in an area.
Filter additionally by the `needs-triage` label to see what agents can't
pick up yet.

## Example — a well-formed bug

````markdown
## Goal
POST /api/queues/<name>/retry returns 200 with the requeued message id
when the message is in the dead-letter queue, instead of 500.

## Locus
- File: `services/queue/retry_handler.py:87`
- Function: `retry_dead_letter`
- Subsystem: queue   # from your configured `subsystems:` enum

## Skills to load
- <your-queue-architecture-skill>
- <your-retry-policy-skill>

## Symptom
Calling the retry endpoint on a known-dead-letter message returns HTTP
500 with a generic stack trace. The expected behaviour is HTTP 200 with
a structured response naming the requeued id.

## Repro
```bash
curl -X POST http://localhost:8080/api/queues/payments/retry \
  -H 'Content-Type: application/json' \
  -d '{"message_id": "abc-123"}'
```
```
HTTP/1.1 500 Internal Server Error
KeyError: 'requeue_target'
```

## Expected
HTTP 200 with body `{"requeued_id": "<uuid>", "queue": "payments"}`.

## Impact
degrades-UX — operators cannot recover failed messages from the
dashboard. Does not block message ingestion.

## Root cause hypothesis
`retry_dead_letter` reads `requeue_target` from the message envelope
without checking for the dead-letter-specific shape, where that key is
namespaced under `dlq.requeue_target`.

## Constraints
- Out of scope: the queue driver itself (`services/queue/driver.py`).
- Invariants: dead-letter retention policy unchanged; no new queue states.
- Style: minimal fix; no drive-by refactors.

## Acceptance
- [ ] Calling retry on a dead-letter message returns HTTP 200.
- [ ] Response body matches `{"requeued_id": "<uuid>", "queue": "<name>"}`.
- [ ] The dead-letter row is removed atomically with the requeue insert.

## Verify
```bash
pytest -q tests/test_queue_retry.py::test_retry_dead_letter
pytest -q
```
````

---

See also: `feature-request` (new capabilities), `followup-tracking` (scope
deferred from in-flight work), `initiative-tracking` (multi-issue epics).
