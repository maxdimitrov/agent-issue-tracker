---
description: Run ONE iteration of an unattended loop — babysit a PR to green, clear an epic leaf by leaf, or poll a label and dispatch /work-issue — with budgets and stop conditions kept on disk. Recurrence comes from /loop or a session cron.
---

# /tracker-loop <mode> [ref] [--label <name>] [--merge | --draft] [--restart] | status | stop [<id>]

One iteration per invocation. `/tracker-loop` never schedules itself and never calls `ScheduleWakeup`; recurrence is external:

| Recurrence | How |
|---|---|
| Self-paced (preferred) | `/loop /agent-issue-tracker:tracker-loop babysit #42` — the harness picks each delay; this command ends every iteration with a **pacing hint** the self-paced loop follows |
| Fixed interval | `/loop 15m /agent-issue-tracker:tracker-loop poll` |
| Armed by a driver | `/work-issue #42 --start --loop` or `/resume-initiative #9 --start --loop` creates a session cron that fires this command (see those commands) |

Session crons expire after seven days and end with the conversation; `/schedule` (cloud routines) is the documented answer for longer-lived automation and is not wrapped here.

## Modes

```
/tracker-loop babysit [<pr-number> | <issue-ref>] [--merge] [--restart]
/tracker-loop clear <epic-ref> [--draft | --merge] [--restart]
/tracker-loop poll [--label <name>] [--draft | --merge] [--restart]
/tracker-loop status
/tracker-loop stop [<loop-id>]
```

`--draft` and `--merge` are mutually exclusive; refuse with a one-line message if both are passed. They pass straight through to the `/work-issue` invocations a loop makes and to the babysit merge rule. When neither is on the command line, the loaded record's `options.merge` / `options.draft` apply (a loop armed by a driver, or re-armed from a resume note, keeps the flags it was created with); a flag on the command line wins over the record for that iteration. "The effective `--merge`" / "the effective `--draft`" below means this resolved value. `--restart` creates a fresh record even when a stopped one already exists for that mode and ref (see step 2).

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

1. **Collect.** Run `"${CLAUDE_PLUGIN_ROOT}/scripts/session-brief-collect.sh"` for the current branch (`SB` below). It runs first, before the record is loaded, because step 2 needs `SB` (the babysit ref and the session transcript). Modes `clear` and `poll` also read the tracker in their own step.
2. **Load or create the record.** The record's `<ref>` is: `poll` → the poll label in use (`--label`, else `loops.poll_label`, default `agent-ready`); `babysit` with no argument → `SB.ticket.key`, else `#<SB.pr.number>`, else the current branch name; `babysit <arg>` → that argument, normalised: strip a leading `#`; a bare number is then a PR number when `gh pr view <n>` resolves one, else an issue number, and either way is recorded as `#<n>` (the form the no-argument case uses), so `babysit 128` and `babysit #128` find the same record; `owner/repo#N` and any other issue ref are kept as-is; `clear` → the epic ref. `LR find` and `LR create` always take the normalised ref.

   `LR find <mode> <ref>`; if it returns a live record, use it. Otherwise, unless `--restart` was passed, `LR find --any <mode> <ref>`:
   - `null` → create (below).
   - the newest record is stopped with a `stop_reason` beginning `checkpoint:` → a checkpoint continues only in a *different* session. If `SB.session.transcript` is non-null and differs from the record's `stop_transcript`, `LR reopen <id>` and continue with that record: its `started` time, iterations, `prs_opened`, budgets and options are kept, so the budgets keep counting, and its `cron_job_id` is cleared, since the checkpointing session's cron ended with that session. Otherwise print `loop <id> is checkpointed for a fresh session; press Esc to end this /loop, then start a new session with the resume note (or pass --restart)` and end the iteration without acting, with pacing hint `stopped`: a same-session `/loop` keeps firing into this message until the operator presses Esc.
   - the newest record is stopped for any other reason → print `loop <id> is stopped (<reason>); pass --restart to begin a new loop` and end the iteration without creating or acting.

   `--restart` skips the `find --any` check above and always creates a fresh record.

   `reopen` never resets `started`: a reopened record's `max_hours` budget includes the gap between the checkpointing session and the one that reopened it. That is by design; `--restart` is the way to a fresh clock.

   **Create:** `LR create <mode> <ref> <branch> [--merge] [--draft] --max-iterations … --max-hours … --idle-stop-after … --interval …` with the configured budgets and the command-line flags. `<branch>` is the current branch for `babysit`, the epic ref's slug for `clear`, and `""` for `poll`. Refuse to create a second live loop of the same mode and ref; report the existing id instead.

   **Flags.** With the record loaded, resolve the effective `--merge` / `--draft` (see Modes): the command line wins; otherwise the record's `options.merge` / `options.draft`.
3. **Budget check.** `LR check <id>`. On `ok: false`, go to step 8 with the `reason`. `max_iterations` counts the record's `iterations[]` entries whose action is not `skip`: skip entries are clear-mode bookkeeping, so a cascade of skips does not burn the iteration budget, and `iterations[]` can be longer than the count `LR check` reports.
4. **Decide.** The mode's table yields exactly one action, or `wait`, or `stop <reason>`.
5. **Act.** Perform that one action through the existing skills and commands. An "action" is one mutating work action — a push, a rebase, a merge, or a `/work-issue` dispatch; bookkeeping (the skip comment, `LR append … skip`) doesn't count against the limit. Never two mutating actions in one iteration, except where a mode's table below says otherwise (poll, clear).
6. **Checkpoint.** Apply the `/session-brief` verdict table (`commands/session-brief.md` Step 3) to `SB.session`. On a `fresh session` verdict, in this order: run step 7's `LR append` for the action just taken (so it is on the record), write the resume note exactly as `/session-brief` Step 4 does, including the `**Loop:**` re-arm line, then `LR stop <id> "checkpoint: fresh session" --transcript <SB.session.transcript>` (omit `--transcript` when that is null) and go to step 8, which does not stop the record a second time.
   - The `**Loop:**` re-arm line is written from the record this iteration holds (its mode, ref and effective `--merge` / `--draft`), not from `SB.loop`: the collector matches `SB.loop` by branch, so it is null for a clear or poll loop.
   - A `/compact` verdict does not checkpoint: continue to step 7 and append `· suggest /compact` to its report line. The loop never compacts itself.
   - The verdict applies only to the loop's own session. When this command runs inside a subagent, `SB.session` describes the parent's transcript whatever its `transcript_source` (`env`, `session-id` or `discovered`); treat the verdict as `keep going` there. Branches a clear or poll loop entered itself (its leaves' and PRs' worktrees) do not count toward the table's "more than one branch or ticket" row; only the turn, span and compaction rows can checkpoint such a loop.
7. **Record and report.** `LR append <id> <action> "<detail>" [--noop]` — append `wait-ci` **without** `--noop` for the CI-in-progress wait (babysit table row 8; it doesn't count toward `idle_stop_after`), and `wait` **with** `--noop` for the idle wait (row 9) and any other no-op iteration. No other action takes `--noop`. Then print one line:

   `loop <id> · <mode> <ref> · iteration <n> · <action or noop> · next: <pacing hint>`

8. **Stop.** `LR stop <id> "<reason>"` (already done by step 6 for a checkpoint); if the printed `cron_job_id` is set, `CronDelete` it. For a checkpoint, first print step 7's report line with `next: stopped` for the action step 6 appended. Print the reason. When the reason is NEEDS YOU, print the NEEDS YOU block (author, path:line, excerpt) exactly as `/session-brief` would. A loop stopped with reason `checkpoint: fresh session` continues only from a different session: a fire whose `SB.session.transcript` differs from the record's `stop_transcript` reopens it (step 2) with its iterations, `prs_opened` and budgets intact, while a fire from the same session reports it checkpointed and takes no action. A loop stopped for any other reason stays stopped: the next fire's step 2 reports it and takes no action. `--restart` begins a fresh record in either case.

## Mode: babysit

Work source, by case:

- **The current branch has a PR** → `SB.pr`.
- **The ref is a PR number** (step 2's normalised `#<n>` that `gh pr view` resolved) → `gh pr view <n> --repo <nwo> --json headRefName` gives the branch; enter `.claude/worktrees/<branch-with-slash-as-plus>` when it exists, else operate from the primary checkout, and collect `SB` there.
- **The ref is an issue ref** → derive its branch with `/work-issue` Step 3's naming, then `gh pr list --repo <nwo> --head <branch>` finds the PR; enter that branch's worktree as above.

**gh must have answered before the table is read.** Whenever `SB.repo.gh_ok` is false or `SB.errors[]` names a failed gh step (for example `gh api user failed (auth?)`, `gh pr view failed`, `gh graphql review threads failed`), the iteration's action is **wait** (hint: 5m), recorded with `--noop`, regardless of `SB.pr`, `SB.ci` or `SB.review`: the table's inputs are then untrustworthy (with no viewer, no thread is marked `awaiting_you`, so an open change request would be invisible to the merge rows). A gh outage that never clears still ends the loop through `idle_stop_after`. The table below is consulted only when the collector reports no gh errors; only then does a null `SB.pr` mean the branch has no PR (see Failure modes).

Before the table, classify every `SB.review.threads[]` with `awaiting_you == true` as `code` (a concrete, actionable change request: rename, split, add a test, handle a case) or `judgement` (a question, a design objection, or anything a reasonable engineer would want the author to answer in prose).

| Observation (first match wins) | Action |
|---|---|
| `pr.state` is `MERGED` or `CLOSED` | **stop: done** — when `pr.state == MERGED` and the record's ref is an issue ref (or `SB.ticket.key` resolves one), the stop action is `/work-issue <ref> --finish`; a failure there is a WARN in the stop line, never a reason to keep looping |
| `pr.mergeable == "CONFLICTING"` | **rebase** onto `git.base`, resolve, push |
| `ci.conclusion == "failure"` | **fix-ci**: `superpowers:systematic-debugging` on `ci.failed_jobs`, `superpowers:test-driven-development` for the fix, push |
| an awaiting thread classified `code` | **address-review**: make the change, push, reply on the thread naming the commit SHA, resolve the thread |
| an awaiting thread classified `judgement` | **stop: needs-you** — quote author, path:line, excerpt |
| `pr.reviewDecision == "APPROVED"` and the effective `--merge` | **merge**: `gh pr merge --<merge_method> --match-head-commit <pr.headRefOid> --auto` (`merge_method` from `.claude/issue-tracker.yaml`, default `squash`; falls back to a direct merge with the same method and pin only where auto-merge is unavailable; never `--delete-branch`). A direct merge lands immediately: run `/work-issue <ref> --finish` and **stop: done**. An armed auto-merge lands when the checks pass: record the action and keep iterating (`wait-ci` while checks run), so the first row observes `pr.state == MERGED` and runs `--finish` at its stop |
| `pr.reviewDecision == "APPROVED"`, no effective `--merge` | **stop: ready-to-merge** — the operator's call |
| `ci.status` is `queued`, `in_progress`, `waiting` or `pending` | **wait-ci** (hint: CI in progress) — recorded without `--noop`; does not count toward `idle_stop_after` |
| anything else | **wait** (hint: idle, see Pacing hint) — recorded with `--noop`; counts toward `idle_stop_after` |

Replies to humans are always code-backed: a pushed commit plus a comment naming it. The loop never argues a review point in prose; that is a NEEDS YOU.

## Mode: clear

Work source: `/resume-initiative <epic-ref>`'s next-up derivation (`commands/resume-initiative.md` "Deriving child state" and "Tree traversal"), reused as written — depth cap, cycle guard, and legacy branch included.

| Observation (first match wins) | Action |
|---|---|
| no open leaf | **stop: initiative clear** |
| the next leaf carries the `needs_design_label`, or its body fails the agent-prompt bail criteria (`skills/feature-request/SKILL.md`) | **skip** (bookkeeping, not this iteration's action — see step 5): `upsert_comment` on the leaf with marker `<!-- tracker-loop:skip -->` and a body naming the gap, `LR append … skip`, move to the next open leaf; three consecutive skips stop: **stop: three skips** |
| the next leaf already has an open PR | run **one babysit iteration** against it (enter its worktree; table above) instead of starting a new leaf |
| the next leaf is workable | **start**: `/work-issue <leaf> --start` with the effective `--draft` / `--merge` passed through; `LR add-pr <id> <pr-ref>` when it opens a PR. That PR is this loop's babysit target on later iterations |

The skip comment goes through `upsert_comment`, so it is idempotent: a later iteration that derives the same leaf as next-up again replaces that one marker comment instead of adding another.

Skipping may cascade within one iteration — the skip row moves to the next open leaf without ending the iteration — but at most one **start** may follow a run of skips in the same iteration, once a workable (or already-open-PR) leaf is found; that start (or babysit action) is the iteration's one action. Each skip is its own `LR append … skip` entry, and step 3's `LR check` does not count skip entries toward `max_iterations`.

The checkpoint after each leaf is the reason this mode exists: a long clearing run compacts or hands off instead of degrading.

## Mode: poll

Work source: `list_open_issues({label: <poll_label>})` through the configured backend.

**Claimed** issues are skipped. An issue is claimed when any of:

- a worktree for its ref exists (`.claude/worktrees/` naming from `/work-issue` Step 3, or a `worktrees[]` entry in `tracker-brief-collect.sh` output whose `ref` matches),
- an open PR in this repo references it (`gh pr list --repo <nwo> --state open --search "<ref>"`),
- another live loop record names it (`LR list`): its `ref` equals the issue ref, or one of its `prs_opened` PRs has the issue ref in its body (`gh pr view <n> --repo <nwo> --json body`),
- it carries `loops.claim_label`, when that key is set.

Per iteration (at most one mutating action — see step 5):

1. If this record's `prs_opened` has any still-open PR, babysit only the **oldest** one, entering its worktree (table above). A babysit stop reason of `done` drops that PR from consideration; `needs-you` stops the whole loop.
2. A new issue may be dispatched in this same iteration only when step 1 found no open PR, or that babysit iteration took no mutating action of its own: its outcome was `wait`, `wait-ci` or `stop: done`. A mutating action (rebase, fix-ci, address-review, merge) or `needs-you` permits no dispatch. If fewer than `max_concurrent` (default 1) of this record's PRs are open, take the **oldest unclaimed** issue (the lowest issue number on GitHub; elsewhere the earliest `created` when `list_open_issues` returns it, else the backend's listing order), apply `claim_label` via `add_label` when configured, and **dispatch** `/work-issue <ref> --start`. The PR mode: an effective `--merge` on the loop wins over `loops.pr_mode` and is passed through as `--merge`; otherwise an effective `--draft` passes `--draft`; otherwise `loops.pr_mode` decides (`draft`, the default, passes `--draft`; `ready` passes neither). `LR add-pr <id> <pr-ref>` once the PR exists.
3. Nothing to do → **wait** (hint: `loops.interval`).

No `remove_label` operation exists in the contract, so a `claim_label` stays on the issue until a human removes it or the issue closes. Two machines polling the same label without a `claim_label` can collide; the local claim signals do not cross machines.

## Pacing hint

The last line of every iteration. A self-paced `/loop` follows it; a fixed-interval loop ignores it.

| State | Hint |
|---|---|
| CI in progress | the duration of that workflow's last completed run, from one call: `gh run list --repo <nwo> --workflow <name> --branch <branch> --status completed --limit 1 --json databaseId,startedAt,updatedAt` (`updatedAt` − `startedAt`), floor 3m, cap 30m |
| a fix was just pushed | 5m — CI is about to start |
| gh could not answer (`gh_ok` false or a gh entry in `errors[]`) | 5m |
| waiting on a reviewer | 30m |
| idle (babysit `wait`: nothing to act on) | 30m, as waiting on a reviewer |
| poll found nothing | `loops.interval` |
| clear just started a leaf | none — the leaf's pipeline ran inline in this turn; next hint is 5m |
| stopped | none — say `stopped` |

## `status` and `stop`

- `status`: `LR list`, printed one line per live loop (`id · mode ref · iteration n · last action · cron armed|none`), followed by the last three stopped records with their reasons. `<state-dir>` is `ait_state_dir "$PWD"` from `"${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"` (`${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker/<project-key>/`); list `<state-dir>/loops/*.json` and `LR get` each stopped one.
- `stop [<id>]`: with an id, `LR stop <id> "operator stop"` and `CronDelete` its `cron_job_id` if set. Without an id and exactly one live loop, stop that one; with several, list them and ask which.

## Prerequisites

An unattended loop commits while nobody is at the keyboard, so on a machine that signs commits it needs a signer that never prompts. A 1Password desktop signer (`op-ssh-sign`) fails while the app is locked, and the iteration ends with its work staged and uncommitted. The documented answer is [`scripts/git-sign.sh`](../scripts/git-sign.sh) as `gpg.ssh.program`: it tries `op-ssh-sign` first and falls back to a dedicated agent key read through the 1Password Automation service account (setup in the script's header). `/tracker-doctor` Phase 4 warns when it is missing. Never bypass signing to get a loop past a commit.

## Safety rails

- Never merge without `--merge`; never open a ready PR on red (`/work-issue` Step 5 already refuses); never force-push.
- Never delete a remote branch; GitHub's `deleteBranchOnMerge` setting owns that.
- At most one mutating action per iteration (step 5's definition; poll and clear's controlled exceptions are spelled out in their tables); a NEEDS YOU always stops the loop over continuing.
- Every tracker write is a contract op (`backends/_interface.md`): `add_label` for the claim label, `upsert_comment` for the skip comment (marker `<!-- tracker-loop:skip -->`). Every git-host write is one `/work-issue` already documents.
- Budgets are enforced from the record on disk (`LR check`), before acting.
- `/tracker-loop stop`, `CronDelete`, and `Esc` on a `/loop` all end a loop; the record says which when it was `stop`.

## Failure modes

- **`LR find`/`create` cannot write the state dir** → report the path and stop; nothing else runs.
- **gh could not answer in babysit** (`SB.repo.gh_ok` false, or `SB.errors[]` names a failed gh step) → **wait** (hint: 5m) with `--noop`, whatever `SB.pr`, `SB.ci` and `SB.review` say: never `stop: no PR`, and never a merge, rebase or review action on inputs gh did not fully deliver. An auth or network blip must not end the loop, delete its cron, or merge over a thread it could not see. A gh outage that never clears ends through `idle_stop_after`.
- **`SB.pr` is null in babysit and gh answered** → no PR on this branch; stop with reason `no PR` and print the `/work-issue` line that would open one.
- **The tracker is unreachable in clear/poll** → the backend reports it; stop with the reason and point at `/tracker-doctor`. Do not fall back to `gh issue` or an MCP call.
- **A leaf is not workable** (needs-design label, vague body) → that is the clear `skip` row, checked here before any dispatch: `/work-issue` does not refuse a leaf for scope and leaves no comment. The skip row's own `upsert_comment` (marker `<!-- tracker-loop:skip -->`) is the record.
- **Iteration exceeds the session cron's interval** (a full `/work-issue` pipeline can) → the harness skips fires while the REPL is busy and does not catch up; nothing to do, the next fire picks up from the record.
