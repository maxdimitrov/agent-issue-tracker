---
description: Run ONE iteration of an unattended loop — babysit a PR to green, clear an epic leaf by leaf, or poll a label and dispatch /work-issue — with budgets and stop conditions kept on disk. Recurrence comes from /loop or a session cron.
---

# /tracker-loop <mode> [ref] [--merge | --draft] | status | stop [<id>]

One iteration per invocation. `/tracker-loop` never schedules itself and never calls `ScheduleWakeup`; recurrence is external:

| Recurrence | How |
|---|---|
| Self-paced (preferred) | `/loop /agent-issue-tracker:tracker-loop babysit #42` — the harness picks each delay; this command ends every iteration with a **pacing hint** the self-paced loop follows |
| Fixed interval | `/loop 15m /agent-issue-tracker:tracker-loop poll` |
| Armed by a driver | `/work-issue #42 --start --loop` or `/resume-initiative #9 --start --loop` creates a session cron that fires this command (see those commands) |

Session crons expire after seven days and end with the conversation; `/schedule` (cloud routines) is the documented answer for longer-lived automation and is not wrapped here.

## Modes

```
/tracker-loop babysit [<pr-number> | <issue-ref>] [--merge]
/tracker-loop clear <epic-ref> [--draft | --merge]
/tracker-loop poll [--label <name>] [--draft | --merge]
/tracker-loop status
/tracker-loop stop [<loop-id>]
```

`--draft` and `--merge` are mutually exclusive; refuse with a one-line message if both are passed. They pass straight through to the `/work-issue` invocations a loop makes and to the babysit merge rule.

## Configuration

Optional `loops:` block in `.claude/issue-tracker.yaml` (defaults shown; `examples/issue-tracker.yaml.example` documents it):

```yaml
loops:
  interval: 15m          # cron cadence for --loop; poll idle cadence
  max_iterations: 50
  max_hours: 24
  idle_stop_after: 12    # consecutive no-change iterations
  pr_mode: draft         # draft | ready — PRs opened by unattended loops
  poll_label: agent-ready
  # claim_label: agent-claimed
  # max_concurrent: 1
```

Read each key with `"${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"`'s `ait_config_get loops.<key>`; an unset key takes the default above.

## The iteration skeleton (every mode)

All bookkeeping goes through `"${CLAUDE_PLUGIN_ROOT}/scripts/loop-record.sh"` (`LR` below). Every subcommand prints JSON.

1. **Load or create the record.** `LR find <mode> <ref>`; when `null`, `LR create <mode> <ref> <branch> [--merge] [--draft] --max-iterations … --max-hours … --idle-stop-after … --interval …` with the configured budgets. `<branch>` is the current branch for `babysit`, the epic ref's slug for `clear`, and `""` for `poll`. Refuse to create a second live loop of the same mode and ref; report the existing id instead.
2. **Budget check.** `LR check <id>`. On `ok: false`, go to step 8 with the `reason`.
3. **Collect.** Run `"${CLAUDE_PLUGIN_ROOT}/scripts/session-brief-collect.sh"` for the current branch (`SB` below). Modes `clear` and `poll` also read the tracker in their own step.
4. **Decide.** The mode's table yields exactly one action, or `wait`, or `stop <reason>`.
5. **Act.** Perform that one action through the existing skills and commands. Never two actions in one iteration.
6. **Checkpoint.** Apply the `/session-brief` verdict table (`commands/session-brief.md` Step 3) to `SB.session`. A `fresh session` verdict writes the resume note exactly as `/session-brief` Step 4 does, including the `**Loop:**` re-arm line, then goes to step 8 with reason `checkpoint: fresh session`.
7. **Record and report.** `LR append <id> <action> "<detail>" [--noop]` — `--noop` for `wait`. Then print one line:

   `loop <id> · <mode> <ref> · iteration <n> · <action or noop> · next: <pacing hint>`

8. **Stop.** `LR stop <id> "<reason>"`; if the printed `cron_job_id` is set, `CronDelete` it. Print the reason. When the reason is NEEDS YOU, print the NEEDS YOU block (author, path:line, excerpt) exactly as `/session-brief` would. A stopped loop is over; `/loop` running this command again sees `ok: false` at step 2 and stops again, cheaply.

## Mode: babysit

Work source: `SB.pr` for the current branch, or — when a ref was given and the current branch has no PR — the branch of the PR `gh pr list --repo <nwo> --head <branch>` resolves for that ref's worktree (`.claude/worktrees/<branch-with-slash-as-plus>`); enter that worktree first.

Before the table, classify every `SB.review.threads[]` with `awaiting_you == true` as `code` (a concrete, actionable change request: rename, split, add a test, handle a case) or `judgement` (a question, a design objection, or anything a reasonable engineer would want the author to answer in prose).

| Observation (first match wins) | Action |
|---|---|
| `pr.state` is `MERGED` or `CLOSED` | **stop: done** |
| `pr.mergeable == "CONFLICTING"` | **rebase** onto `git.base`, resolve, push |
| `ci.conclusion == "failure"` | **fix-ci**: `superpowers:systematic-debugging` on `ci.failed_jobs`, `superpowers:test-driven-development` for the fix, push |
| an awaiting thread classified `code` | **address-review**: make the change, push, reply on the thread naming the commit SHA, resolve the thread |
| an awaiting thread classified `judgement` | **stop: needs-you** — quote author, path:line, excerpt |
| `pr.reviewDecision == "APPROVED"` and `--merge` | **merge**: `gh pr merge --squash --auto` (falls back to a direct squash merge only where auto-merge is unavailable), then **stop: done** |
| `pr.reviewDecision == "APPROVED"`, no `--merge` | **stop: ready-to-merge** — the operator's call |
| `ci.status == "in_progress"` | **wait** (hint: CI) |
| anything else | **wait** (hint: idle; counts toward `idle_stop_after`) |

Replies to humans are always code-backed: a pushed commit plus a comment naming it. The loop never argues a review point in prose; that is a NEEDS YOU.

## Mode: clear

Work source: `/resume-initiative <epic-ref>`'s next-up derivation (`commands/resume-initiative.md` "Deriving child state" and "Tree traversal"), reused as written — depth cap, cycle guard, and legacy branch included.

| Observation (first match wins) | Action |
|---|---|
| no open leaf | **stop: initiative clear** |
| the next leaf carries the `needs_design_label`, or its body fails the agent-prompt bail criteria (`skills/feature-request/SKILL.md`) | **skip**: comment on the leaf naming the gap, `LR append … skip`, move to the next open leaf in the same iteration; after three consecutive skips, **stop: three skips** |
| the next leaf already has an open PR | run **one babysit iteration** against it (enter its worktree; table above) instead of starting a new leaf |
| the next leaf is workable | **start**: `/work-issue <leaf> --start` with `--draft` / `--merge` passed through; `LR add-pr <id> <pr-ref>` when it opens a PR. That PR is this loop's babysit target on later iterations |

The checkpoint after each leaf is the reason this mode exists: a long clearing run compacts or hands off instead of degrading.

## Mode: poll

Work source: `list_open_issues({label: <poll_label>})` through the configured backend.

**Claimed** issues are skipped. An issue is claimed when any of:

- a worktree for its ref exists (`.claude/worktrees/` naming from `/work-issue` Step 3, or a `worktrees[]` entry in `tracker-brief-collect.sh` output whose `ref` matches),
- an open PR in this repo references it (`gh pr list --repo <nwo> --state open --search "<ref>"`),
- another live loop record names it (`LR list`, any record whose `ref` or `prs_opened` matches),
- it carries `loops.claim_label`, when that key is set.

Per iteration:

1. For each PR in this record's `prs_opened` that is still open (oldest first), run **one babysit iteration** against it, entering its worktree. A babysit stop reason of `done` drops that PR from consideration; `needs-you` stops the whole loop.
2. If fewer than `max_concurrent` (default 1) of this record's PRs are open, take the **oldest unclaimed** issue, apply `claim_label` via `add_label` when configured, and **dispatch** `/work-issue <ref> --start` with `--draft` when `loops.pr_mode` is `draft` (the default) or `--merge` when passed. `LR add-pr <id> <pr-ref>` once the PR exists.
3. Nothing to do → **wait** (hint: `loops.interval`).

No `remove_label` operation exists in the contract, so a `claim_label` stays on the issue until a human removes it or the issue closes. Two machines polling the same label without a `claim_label` can collide; the local claim signals do not cross machines.

## Pacing hint

The last line of every iteration. A self-paced `/loop` follows it; a fixed-interval loop ignores it.

| State | Hint |
|---|---|
| CI in progress | the duration of that workflow's last completed run (`ci.all_workflows[]` `when` deltas are not exposed — use the run's `run_started_at`/`updated_at` from `gh run view <id> --json startedAt,updatedAt`), floor 3m, cap 30m |
| a fix was just pushed | 5m — CI is about to start |
| waiting on a reviewer | 30m |
| poll found nothing | `loops.interval` |
| clear just started a leaf | none — the leaf's pipeline ran inline in this turn; next hint is 5m |
| stopped | none — say `stopped` |

## `status` and `stop`

- `status`: `LR list`, printed one line per live loop (`id · mode ref · iteration n · last action · cron armed|none`), followed by the last three stopped records with their reasons (`ls <state-dir>/loops`, `LR get`).
- `stop [<id>]`: with an id, `LR stop <id> "operator stop"` and `CronDelete` its `cron_job_id` if set. Without an id and exactly one live loop, stop that one; with several, list them and ask which.

## Safety rails

- Never merge without `--merge`; never open a ready PR on red (`/work-issue` Step 5 already refuses); never force-push.
- One action per iteration; a NEEDS YOU always stops the loop over continuing.
- Every tracker write goes through contract ops (`add_label`, comments via `upsert_comment` only where a machine block is involved; plain leaf comments use the backend's documented comment call); every git-host write is one `/work-issue` already documents.
- Budgets are enforced from the record on disk (`LR check`), before acting.
- `/tracker-loop stop`, `CronDelete`, and `Esc` on a `/loop` all end a loop; the record says which when it was `stop`.

## Failure modes

- **`LR find`/`create` cannot write the state dir** → report the path and stop; nothing else runs.
- **`SB.pr` is null in babysit** → no PR on this branch; stop with reason `no PR` and print the `/work-issue` line that would open one.
- **The tracker is unreachable in clear/poll** → the backend reports it; stop with the reason and point at `/tracker-doctor`. Do not fall back to `gh issue` or an MCP call.
- **`/work-issue` bails on a leaf** (vague body, needs-design) → that is the `skip` row; the comment it leaves is the record.
- **Iteration exceeds the session cron's interval** (a full `/work-issue` pipeline can) → the harness skips fires while the REPL is busy and does not catch up; nothing to do, the next fire picks up from the record.
