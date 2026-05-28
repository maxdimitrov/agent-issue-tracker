# Walkthrough: filing a bug

This page shows what happens when you ask Claude Code to file a bug, end-to-end, against a GitHub-backed project. It's operator-facing — read it once to know what to expect; you do not need to memorize anything before using the [`bug-tracking`](../../skills/bug-tracking/SKILL.md) skill.

**Configured for this walkthrough:**

```yaml
# .claude/issue-tracker.yaml
schema_version: 1
backend: github
areas: [dashboard, backend, frontend, infra]
subsystems: [api, worker, scheduler, scripts]
github:
  repo: your-org/your-repo
```

## 1. Trigger

You type into Claude Code:

> file a bug — the worker scheduler is hanging on shutdown when the queue has pending jobs. I see "Stopping..." in the logs but the process never exits, so my CI deploy timeout fires after five minutes and the container gets SIGKILL'd. Reproduces every time on staging with `make deploy-staging`. Blocks today's deploy.

The phrase "file a bug" activates the [`bug-tracking`](../../skills/bug-tracking/SKILL.md) skill. (Other triggers: "open a bug", "track a bug", "I want to file a bug".)

## 2. Skill activation

The skill reads `.claude/issue-tracker.yaml`, sees `backend: github`, and resolves the dispatch target to [`backends/github.md`](../../backends/github.md). It pulls the title format (`<component>: <symptom>`) and the labels (`[bug, <area>]`) from the config's `types.bug` block (defaulted in your config because you didn't override).

It applies the bug-tracking bail criteria:

- **Locus is clear** — "worker scheduler" maps to `subsystems: scheduler`.
- **Symptom is concrete** — "process never exits" beats "deploy is broken".
- **Repro exists** — `make deploy-staging`.
- **Impact is stated** — "blocks today's deploy".
- **Acceptance is testable** — "scheduler returns from main() within N seconds of SIGTERM with pending jobs present".

No bail. Skill proceeds.

## 3. Body draft

The skill fills [`templates/bug-body.md`](../../templates/bug-body.md) with your input:

```markdown
## Goal
Scheduler returns from main() within 30 seconds of SIGTERM, even when the
internal job queue has pending entries.

## Locus  **[required]**
- File(s): TBD (agent picks up; likely `worker/scheduler/main.py` or the
  signal-handler wiring)
- Function/route: scheduler shutdown path
- Subsystem: scheduler

## Skills to load  **[required]**
- worker-architecture (if your project has one)
- signal-handling

## Symptom  **[required]**
After SIGTERM, scheduler logs "Stopping..." but the process never exits;
CI deploy timeout fires at 5 minutes and the container gets SIGKILL'd.

## Repro  **[required]**
```bash
make deploy-staging
# Wait for the rolling restart phase; observe scheduler container
# transitioning to Terminating but never reaching Terminated.
```

## Expected
Scheduler drains or rejects pending jobs and exits cleanly within 30s.

## Impact  **[required]**
blocks-deploy — today's release cannot ship until shutdown completes
within the deploy timeout window.

## Constraints
- Out of scope: queue persistence layer; this is a shutdown-path bug only.
- Invariants to preserve: in-flight jobs must not be silently lost on
  shutdown (either drain or surface as deferred).
- Style: minimal fix; no refactor of the scheduler main-loop.

## Acceptance  **[required]**
- [ ] On SIGTERM with N pending jobs, scheduler logs the count, drains or
      defers them, returns from main() within 30s.
- [ ] CI deploy completes without SIGKILL on staging.

## Verify  **[required]**
```bash
pytest -q tests/scheduler/test_shutdown.py
make deploy-staging  # observe clean rollover
```

## Notes
First seen on staging 2026-05-28 during routine deploy.
```

(Sections are tracker-agnostic; the same body works for GitHub or Jira.)

## 4. Dispatch

The skill invokes the GitHub backend's `create_issue` operation per [`backends/github.md`](../../backends/github.md):

```bash
gh issue create \
  --repo your-org/your-repo \
  --title "scheduler: hangs on shutdown when queue has pending jobs" \
  --body-file <draft.md> \
  --label "bug,backend"
```

## 5. Result

GitHub returns `https://github.com/your-org/your-repo/issues/142`. The skill captures `#142` as the ref and confirms to you:

> Filed: [#142 scheduler: hangs on shutdown when queue has pending jobs](https://github.com/your-org/your-repo/issues/142) — labels: `bug, backend`. Ready to hand to an issue-fix agent.

## Variations

- **`backend: jira`** — same body, different dispatch. The skill resolves [`backends/jira.md`](../../backends/jira.md) instead and invokes `createJiraIssue` via the Atlassian Remote MCP. The ref comes back as `TRADE-142` instead of `#142`. Labels and components map per your `jira.area_field` config — see [`examples/jira-config.yaml`](../jira-config.yaml).
- **Subsystem missing from `subsystems:`** — the skill nudges you: "scheduler is not in your configured subsystems enum (api / worker / scripts). Pick one of those, or add `scheduler` to `.claude/issue-tracker.yaml` and re-trigger."
- **Bail criteria triggered** — if your input is "things are slow" with no repro and no acceptance, the skill refuses and asks for: a specific symptom, a repro command, a testable acceptance. The bail is intentional: a vague body wastes an agent run.
- **Cross-repo filing** — the skill files to whatever `github.repo` says in `.claude/issue-tracker.yaml`. If your bug lives in a different repo, edit the config or use [`feature-request`](../../skills/feature-request/SKILL.md)'s cross-repo flow.

## See also

- [`bug-tracking` skill](../../skills/bug-tracking/SKILL.md) — the methodology.
- [`templates/bug-body.md`](../../templates/bug-body.md) — the body skeleton.
- [`backends/github.md`](../../backends/github.md) — the `gh` dispatch reference.
- [Walkthrough: filing an epic](file-an-epic.md) — for initiatives, not bugs.
