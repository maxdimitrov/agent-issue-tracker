# Loops and briefs — design

**Date:** 2026-09-24
**Status:** approved design, pending implementation plan
**Branch:** `feat/loops-and-briefs`

## 1. Goal

Two additions to the plugin, designed together because they share plumbing:

1. **Briefs.** Port the operator's personal `session-brief` and `morning-brief`
   skills into the plugin as `/session-brief` and `/tracker-brief`, stripped of
   everything specific to one employer's environment and re-rooted on the
   plugin's own concepts: the configured tracker backend, the branch-derived
   issue ref, `.claude/worktrees/`, and the per-project state directory.
2. **Loops.** Give the plugin's drivers a way to keep going without a human
   re-prompting: one iteration command, `/tracker-loop`, with three work
   sources (babysit a PR, clear an epic, poll a label), recurrence supplied by
   the harness's `/loop` or a session cron, and hard budgets and stop
   conditions so an unattended run cannot wander.

Success looks like: an operator runs `/work-issue #42 --start --loop`, walks
away, and comes back to a PR whose CI is green and whose review comments have
been addressed or surfaced as NEEDS YOU; the next morning `/tracker-brief`
shows what the loop did, which PRs are drifted against their issues, and which
worktrees can be removed.

## 2. Non-goals

- Email, Slack, Calendar and phishing collectors. A shell script cannot reach
  MCP and an issue-tracker plugin has no business in a mailbox. The personal
  skills keep those; a followup turns them into thin wrappers over the plugin
  versions.
- Cross-machine claim coordination for the poll loop. The claim signals are
  local (worktree, open PR, loop record) plus an optional label. Two machines
  polling the same label with no `claim_label` can collide; documented.
- Persistent recurrence beyond one session. Session crons expire after seven
  days and die with the conversation. `/schedule` (cloud routines) is the
  documented answer for longer-lived automation; the plugin does not wrap it.
- Calling `ScheduleWakeup` from a command. The harness documents it as an
  internal of self-paced `/loop`, not a public primitive. Commands only ever
  create or delete crons via `CronCreate` / `CronDelete`.
- Wrapping the personal-skills copies. Out of scope; filed as a followup.

## 3. Shared plumbing

### 3.1 `scripts/lib/common.sh`

Sourced by both collectors and by `hooks/session-title.sh`. Bash 3.2 and BSD
userland compatible, like the hook. Functions:

| Function | Contract |
|---|---|
| `ait_ref_from_branch <branch>` | Prints the issue ref parsed from the branch leaf: Jira key `[A-Z][A-Z0-9]+-[0-9]+`, else leading number, else `issue-N`, else empty. Same rules the hook uses today (stage 5); the hook switches to calling this. |
| `ait_slug_from_branch <branch>` | The hook's slug derivation, extracted verbatim. |
| `ait_project_key [<dir>]` | `<basename-of-main-repo>-<sha256(git common dir)[0:8]>`. Uses `git rev-parse --git-common-dir` so every worktree of a repo yields the same key. Outside git: `<basename-of-cwd>-<sha256(cwd)[0:8]>`. |
| `ait_state_dir [<dir>]` | `${AIT_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker}/<project-key>`. Creates it. |
| `ait_config_path [<dir>]` | Path of `.claude/issue-tracker.yaml` in cwd or toplevel, or empty. |
| `ait_config_get <key>` | Flat `grep`/`awk` read of a top-level or one-level-nested scalar (`backend`, `github.repo`, `jira.site`, `loops.interval`). No YAML parser; the config schema is deliberately flat enough. |
| `ait_issue_url <ref>` | GitHub: `https://github.com/<github.repo>/issues/<N>`; Jira: `https://<jira.site>/browse/<KEY>`; no config: empty. |
| `ait_run_capped <secs> <cmd…>` | `timeout` / `gtimeout` / watchdog fallback, from the source scripts. |
| `ait_json_str <s>` | `jq -Rn --arg v "$1" '$v'`. |

### 3.2 State directory layout

```
${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker/
  session-titles/              # existing hook state, untouched
  <project-key>/
    resume/<slug>.md           # /session-brief resume notes
    tracker-brief.json         # {last_run, previous_run}
    loops/<loop-id>.json       # one record per loop, see 6.5
```

`AIT_STATE_DIR` overrides the root. Nothing under it is ever committed; no
path inside a consumer repo is written by any brief or loop.

### 3.3 Contract operation 11: `list_updated_issues`

Added to `backends/_interface.md` under `## Operations`; op-parity CI enforces
presence in both backend modules.

**Inputs:** `since` (ISO-8601 UTC), `involving_me` (boolean, default true).
**Output:** list of `{ref, title, status, updated, url}`, newest first,
capped at 50 by the backend.

- GitHub: `gh issue list --repo <repo> --state all --search "updated:>=<date> involves:@me" --json number,title,state,updatedAt,url --limit 50`. Without `involving_me`, drop the `involves:` qualifier.
- Jira: `searchJiraIssuesUsingJql` with `project = "<project>" AND updated >= "<yyyy-MM-dd HH:mm>"` plus, when `involving_me`, `AND (assignee = currentUser() OR reporter = currentUser() OR watcher = currentUser())`. `commentedByUser()` is not used; it is not valid JQL on Cloud.

Comment activity inside the window comes from the existing `read_comments`
op, applied to at most the first 20 returned issues, filtered to comments
newer than `since` and not authored by the viewer.

The Jira mapping is documented but cannot be live-verified from the
development machine; it joins the deferred Jira smoke list (CHANGELOG
release-gate record), as `read_comments` / `upsert_comment` did in 1.8.0.

### 3.4 Transcript discovery

The harness exposes no session id or transcript path to Bash commands. The
session collector resolves the transcript best-effort, in this order, and
reports which step won in `session.transcript_source`:

1. `AIT_TRANSCRIPT` env var (explicit override; tests use it).
2. `CLAUDE_CODE_SESSION_ID` if the harness happens to set it (undocumented):
   `~/.claude/projects/*/<id>.jsonl`.
3. Newest `.jsonl` (mtime within the last 30 minutes) under the project
   folders for the cwd, its git toplevel, and its main repo, **whose last 50
   entries record `cwd` equal to the current directory**. The cwd filter is
   what stops parallel sessions in sibling worktrees of one repo from reading
   each other's transcript.
4. None. `session: null`; the brief says so and skips the verdict.

The transcript JSONL entry shape used (`type`, `timestamp`, `cwd`,
`gitBranch`, `isCompactSummary`, `message.content`) is the same one the
existing hook already parses; the collector tolerates missing fields.

## 4. `/session-brief`

Command file `commands/session-brief.md`; collector
`scripts/session-brief-collect.sh`. Read-only except the resume note.

### 4.1 Collector output

Same top-level shape as the source script, with these differences:

| Field | Source behaviour | Plugin behaviour |
|---|---|---|
| `ticket.key`, `ticket.url` | Jira key from branch, URL from a hard-coded host | `ait_ref_from_branch`, URL from `ait_issue_url` (null with no config) |
| `git.base` | Probe `develop staging master main production` | `origin/HEAD` symbolic ref first, then the probe list |
| `session` | `CLAUDE_CODE_SESSION_ID` only | Discovery per 3.4, plus `transcript_source` |
| `session.tickets_seen` | Jira keys only | Any ref shape `ait_ref_from_branch` recognises |
| `handoff.resume_path` | `~/.claude/session-briefs/<slug>.md` | `<state-dir>/resume/<slug>.md` |
| `loop` | absent | The active loop record for this branch, if `loops/*.json` names it: `{id, mode, ref, iterations, last_action, cron_job_id}` |

PR, CI and review-thread collection is unchanged: it is git-host state read
through `gh` and is independent of the tracker backend. `repo.gh_available:
false` degrades those to null exactly as today.

### 4.2 Command prose

Ports the source skill's Steps 1–4 and red-flags table. Additions:

- Step 1 enriches the ticket line with `view_issue({ref})` through the
  configured backend for title and status when a config exists; no config
  means key-only, which is stated on the line.
- The header always carries both links when the JSON has them; the resume
  note carries both too. Unchanged rule, restated because it is the one the
  source skill found agents dropping.
- A `LOOP` line appears between `PR` and `LAST TASK` when `loop` is non-null:
  mode, iteration count, last action, and whether a cron is armed.
- The resume note gains `**Loop:** re-arm with /loop /agent-issue-tracker:tracker-loop <mode> <ref>` when a loop was active.
- The verdict table is unchanged and is the one `/tracker-loop clear` reuses
  as its checkpoint (6.2, step 6).

## 5. `/tracker-brief`

Command file `commands/tracker-brief.md`; collector
`scripts/tracker-brief-collect.sh`. Read-only except `--commit-run`.

### 5.1 Window

`tracker-brief.json` holds `last_run` and `previous_run`. `since` is
`AIT_SINCE` if set, else `last_run`, else 24 hours ago. `summarize_mode` is
true past five days. `--commit-run` stamps after the brief is written, never
before; a failed run must not skip its window.

### 5.2 Collector sections

| Section | Content |
|---|---|
| `worktrees[]` | `git worktree list --porcelain` for the current repo. Per entry: path, branch, ref, detached, dirty count, last commit, idle days, `stale` (idle ≥ `AIT_STALE_DAYS`, default 14, and clean), `touched_in_window`, `landed_pr` via `gh pr list --repo <nwo> --head <branch> --state all`. The primary checkout on the default branch is listed but never stale. |
| `prs` | Scoped to `--repo <nwo>` from the origin remote. `authored_open`, `review_requested`, `mentions`, `merged_in_window`, `all_time_authored` (limit 100; needed for drift). |
| `pr_detail[]` | Up to `AIT_MAX_PR_DEEP` (12) PRs that are mine or awaiting me: review decision, unresolved threads, comments in window not by me, CI from the Actions API (never `statusCheckRollup`). |
| `resume_notes[]` | Files under `resume/` with slug, ref, written time, age. |
| `loops[]` | Loop records under `loops/`: id, mode, ref, state, iteration count, last action, actions in window. |
| `ledger[]` | Join on ref across worktrees, resume notes, loops, and PRs (title ref match by extracted key, equality not substring). `actionable` when a worktree, resume note, live loop, or open PR exists. `tracker_status` left null for the command to fill. |
| `orphan_worktrees[]` | Detached, or no ref and not the primary checkout. |
| `errors[]` | Every degraded step, named. |

`gh` unavailable degrades every PR field to `[]` with one error entry;
worktree and state sections still work.

### 5.3 Command prose

1. Run the collector; read `.window` and `.errors`.
2. Tracker activity via `list_updated_issues({since})`, then `read_comments`
   on the first 20 for in-window comments not by me. Jira and GitHub go
   through the backend module; the command never calls `gh` or an MCP tool
   directly for tracker data.
3. Fill `ledger[].tracker_status` with `view_issue` for actionable rows only.
4. Verdict per actionable row:

   | Verdict | Condition |
   |---|---|
   | Needs action | Unresolved threads, new comments, CI failure, CHANGES_REQUESTED, or a loop stopped on NEEDS YOU |
   | Status drift | PR merged but issue open, or issue closed but PR open |
   | Waiting | PR open, review required, nothing unresolved |
   | Closeable | PR merged and issue closed: print the `git worktree remove` line and the resume-note path to delete |
   | Stale | `stale: true`, then confirmed against `landed_pr` |
   | No code artifact | Resume note or loop record with no worktree and no PR |

   Status drift is expected to be common: GitHub's `Closes #a, #b` auto-closes
   only the first ref, and the plugin's own working notes record closing the
   rest by hand.
5. Output. Terminal: `Needs you` list, drift list, closeable list, and the
   loop summary; nothing else. When the Artifact tool exists, publish the full
   brief titled `Tracker Brief` and keep the title stable across days. No daily
   log file.
6. `--commit-run`.

## 6. `/tracker-loop`

Command file `commands/tracker-loop.md`. **One iteration per invocation.**
Recurrence is external. Not `disable-model-invocation`, so `/loop` can fire
it.

### 6.1 Invocation

```
/tracker-loop babysit [<pr-number> | <issue-ref>] [--merge]
/tracker-loop clear <epic-ref> [--draft | --merge]
/tracker-loop poll [--label <name>] [--draft | --merge]
/tracker-loop status
/tracker-loop stop [<loop-id>]
```

Recurrence, in order of preference:

- `/loop /agent-issue-tracker:tracker-loop <mode> <ref>` — self-paced. The
  command ends each iteration with a **pacing hint** line (6.7) that the
  self-paced loop follows when choosing its next delay.
- `/loop 15m /agent-issue-tracker:tracker-loop <mode> <ref>` — fixed.
- `--loop` on a driver (6.8) — arms a session cron for the operator.

### 6.2 Iteration skeleton (all modes)

1. **Load or create the loop record** (6.6). Refuse to start a second live
   loop of the same mode and ref; report the existing id.
2. **Budget check.** Stop with reason when `iterations ≥ max_iterations`,
   elapsed ≥ `max_hours`, or consecutive no-change iterations ≥
   `idle_stop_after`.
3. **Collect.** Run `session-brief-collect.sh` for the current branch;
   for `clear` and `poll` also the tracker ops the mode needs.
4. **Decide.** The mode's decision table yields exactly one action, or
   `wait`, or `stop <reason>`.
5. **Act.** Perform that one action through the existing skills and
   commands. Never two actions in one iteration.
6. **Checkpoint.** Apply the `/session-brief` verdict table. `fresh session`
   writes the resume note (with the `Loop:` re-arm line) and stops the loop.
7. **Record and report.** Append the iteration to the record; print one
   status line: `loop <id> <mode> <ref> · iteration N · <action|noop> · next: <pacing hint>`.
8. **Stop handling.** On stop: delete the armed cron if the record holds a
   job id, mark the record `stopped` with reason, and print NEEDS YOU if that
   is why.

### 6.3 Mode: `babysit`

Work source: the PR for the current branch (`pr` in the collector output), or
the PR the given ref resolves to via `gh pr list --head`.

| Observation (first match wins) | Action |
|---|---|
| `pr.state` MERGED or CLOSED | stop: done |
| `pr.mergeable` CONFLICTING | rebase onto base, resolve, push |
| `ci.conclusion` failure | `superpowers:systematic-debugging` on `ci.failed_jobs`, fix with TDD, push |
| a review thread `awaiting_you` whose ask is code-level | make the change, push, reply with the commit SHA, resolve the thread |
| a review thread `awaiting_you` that asks a judgement question | stop: NEEDS YOU, quoting author, path:line, excerpt |
| `reviewDecision` APPROVED and `--merge` | `gh pr merge --squash --auto`, then stop: done |
| `reviewDecision` APPROVED, no `--merge` | stop: ready to merge, operator's call |
| `ci.status` in_progress | wait |
| nothing above | wait (counts toward `idle_stop_after`) |

Replies to humans are always code-backed: a pushed commit plus a comment naming
it. The loop never argues a review point in prose; that is a NEEDS YOU.

### 6.4 Mode: `clear`

Work source: `/resume-initiative <epic-ref>` derivation of next-up, reused as
written (tree walk, depth cap, cycle guard).

| Observation | Action |
|---|---|
| no open leaf | stop: initiative clear |
| next leaf carries `needs-design`, or its body fails the agent-prompt bail criteria | comment on the leaf naming the gap, count a skip, move to the next open leaf; three consecutive skips stop the loop |
| next leaf has an open PR | run one babysit iteration on it instead of starting a new leaf |
| next leaf is workable | `/work-issue <leaf> --start` with `--draft`/`--merge` passed through; the PR it opens becomes this loop's babysit target for later iterations |

The checkpoint after each leaf is the reason this mode exists: a long clearing
run compacts or hands off instead of degrading.

### 6.5 Mode: `poll`

Work source: `list_open_issues({label: <poll_label>})`.

Claimed issues are skipped. An issue is claimed when any of: a worktree for
its ref exists (`.claude/worktrees/<branch>` convention from `/work-issue`), an
open PR in this repo references it, another live loop record names it, or it
carries `loops.claim_label` when that key is set.

Per iteration: first run one babysit iteration for each PR this loop opened
(oldest first); then, if fewer than `max_concurrent` (default 1) of this
loop's PRs are open, dispatch `/work-issue <ref> --start` on the oldest
unclaimed issue with `loops.pr_mode` (default `--draft`), applying
`claim_label` via `add_label` when configured. Idle when nothing to do.

No `remove_label` operation exists in the contract, so a `claim_label` stays
on the issue until a human removes it or the issue closes. Documented.

### 6.6 Loop record

`loops/<loop-id>.json`, `loop-id` = `<mode>-<ref-sanitised>-<yyyymmddHHMM>`:

```json
{
  "id": "babysit-42-202609240915",
  "mode": "babysit",
  "ref": "#42",
  "branch": "feat/42-widget",
  "started": "2026-09-24T09:15:00Z",
  "state": "live | stopped",
  "stop_reason": null,
  "cron_job_id": null,
  "options": {"merge": false, "draft": true},
  "budget": {"max_iterations": 50, "max_hours": 24, "idle_stop_after": 12},
  "iterations": [
    {"at": "…", "action": "fix-ci", "detail": "pushed a1b2c3d", "noop": false}
  ],
  "prs_opened": ["#57"]
}
```

Written after every iteration. `tracker-brief` reads it (5.2).

### 6.7 Pacing hint

Printed as the last line of every iteration and followed by a self-paced
`/loop`; ignored by a fixed-interval loop.

| State | Hint |
|---|---|
| CI in progress | the typical duration of that workflow's last green run, min 3m, max 30m |
| waiting on a reviewer | 30m |
| fix just pushed | 5m (CI will start) |
| poll, nothing found | `loops.interval` |
| clear, leaf just started | none: the leaf's pipeline runs inline in this turn |

### 6.8 `--loop` on the drivers

`/work-issue <ref> … --loop` and `/resume-initiative <ref> --start --loop`:
after their current final step, create a recurring session cron
(`CronCreate`, `loops.interval`, off-minute) whose prompt is the matching
`/agent-issue-tracker:tracker-loop babysit <pr>` or `clear <epic>`, store the
job id in a fresh loop record, and tell the operator the loop is armed, that
session crons expire after seven days and end with the conversation, and that
`/loop` or `/schedule` are the alternatives. `--loop` with `--draft` or
`--merge` passes those through to the loop record.

### 6.9 Config

New optional block in `examples/issue-tracker.yaml.example`:

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

`/tracker-doctor` validates the block when present (types and enum values)
and stays silent when absent.

### 6.10 Safety rails

- Never merge without `--merge`; never open a ready PR on red; never force-push.
- One action per iteration; a NEEDS YOU always stops the loop over continuing.
- Every tracker write goes through contract ops; every git-host write goes
  through the same `gh` calls `/work-issue` already documents.
- Budgets are enforced before acting, from the record on disk, so a loop
  survives a context compaction with its counters intact.
- `/tracker-loop stop` and a plain `CronDelete` both end a loop; the record
  says which.

## 7. Testing

- `tests/test_common_lib.sh` — bash unit tests for `scripts/lib/common.sh`
  (ref parsing table, project key stability across worktrees, config reads,
  URL rendering), run by a new CI step; shellcheck extended to
  `scripts/**/*.sh`.
- `tests/test_session_brief_collect.py` — subprocess tests in the style of
  the hook tests: temp git repo, stubbed `gh`, isolated `AIT_STATE_DIR`,
  transcript fixtures (`AIT_TRANSCRIPT`) covering compaction markers, branch
  and cwd filtering, `null` degradation paths, and the resume path slug.
- `tests/test_tracker_brief_collect.py` — worktree fixture with a stale, a
  dirty, and a landed branch; PR search stubs; ledger join correctness
  (`#604` must not steal `#6041`); window and stamp behaviour; loop records
  in the ledger.
- `tests/test_session_title_hook.py` — unchanged expectations after the hook
  sources the lib; that is the regression guard for the extraction.
- Command prose: fixture replay for the babysit decision table
  (`tests/fixtures/loops/*.json` → expected action), same approach as the
  evergreen and drift fixture tests.

## 8. Documentation and packaging

- `README.md`: nine commands → twelve; a Loops section; briefs in the
  session-titles neighbourhood.
- `CONTRIBUTING.md`: contract ten → eleven; smoke gate gains scenario 9
  (briefs) and 10 (a babysit loop against a real PR).
- `backends/_interface.md`, `backends/github.md`, `backends/jira.md`: the new op.
- `examples/issue-tracker.yaml.example`: `loops:` block.
- `.claude-plugin/plugin.json` description count; `CHANGELOG.md` `[Unreleased]`.
- `skills/initiative-tracking/SKILL.md`: one paragraph pointing at `clear`.
- `skills/skill-currency/SKILL.md`: new scripts and config keys are API
  surface; the audit's default globs already cover `commands/*.md`.
- Release is a separate step after merge (operator's usual flow).

## 9. Followups to file after merge

- personal-skills: shrink `session-brief` and `morning-brief` to wrappers
  over the plugin commands plus the email, Slack, Calendar and phishing feeds.
- Jira live smoke for `list_updated_issues`.
- A `remove_label` contract op, if `claim_label` proves useful.
- `/tracker-brief` daily log file, if anyone misses it.

## 10. Open risks, stated

- Transcript discovery is heuristic (3.4). The brief names its source; a
  wrong pick shows up as `cwds_seen` not containing the cwd, which the brief
  treats as `session: null`.
- `CLAUDE_CODE_SESSION_ID` may or may not exist; the design does not depend
  on it.
- Cron fires only when the REPL is idle. A loop iteration that runs a full
  `/work-issue` pipeline can take long enough that a fixed-interval cron
  skips fires; no catch-up is attempted, by harness design.

## 11. Implementation notes

Where the shipped code departs from the sections above, it wins; the
departures are recorded here.

- **Poll babysits one PR per iteration (6.5 vs 6.2).** 6.5's "one babysit
  iteration for each PR this loop opened" is superseded by 6.2 step 5's
  one-action rule: a poll iteration babysits only the oldest still-open PR
  it opened, and may dispatch a new issue in the same iteration only when
  that babysit took no mutating action.
- **Project key (3.2).** `ait_project_key` hashes the main-repo path
  (`ait_main_repo`) rather than the git common dir. The two are equivalent
  for this purpose and equally stable across worktrees of one repo.
- **Library tests (7).** `scripts/lib/common.sh` is tested with pytest
  (`tests/test_common_lib.py`) inside the existing CI test job, not with a
  bash test file and a CI step of its own.
- **Checkpoint continuation (6.2 steps 1, 6 and 8).** The collector runs
  first, before the record is loaded. A `fresh session` checkpoint appends
  the iteration, writes the resume note, then stops the record with reason
  `checkpoint: fresh session` and the current transcript path
  (`loop-record.sh stop … --transcript`, stored as `stop_transcript`). The
  loop continues only from a *different* session: a fire whose transcript
  is non-null and differs from `stop_transcript` runs `loop-record.sh reopen`, which
  returns the record to `live` with `started`, `iterations`, `prs_opened`,
  `budget` and `options` kept, so the budgets keep counting. A fire from the
  same session reports the loop as checkpointed and does nothing;
  `--restart` always begins a fresh record.
- **Flags on driver-armed loops (6.8).** The drivers append `--draft` /
  `--merge` to the cron prompt, and `/tracker-loop` falls back to the
  record's `options` when neither flag is on its command line. In poll, an
  effective `--merge` on the loop wins over `loops.pr_mode` and is passed
  through as `--merge`; otherwise an effective `--draft` passes `--draft`;
  otherwise `loops.pr_mode` decides (`draft`, the default, passes
  `--draft`; `ready` passes neither).
- **gh failure is not "no PR" (6.3).** `session-brief-collect.sh` reports a
  top-level `errors[]` and `repo.gh_ok`. Whenever `gh_ok` is false or
  `errors[]` names a gh step, a babysit iteration waits (5m, no-op)
  whatever `pr`, `ci` and `review` say; the decision table is consulted
  only when the collector reports no gh errors.
- **Skip comments (6.4, 6.10).** The clear-mode skip comment is written
  with `upsert_comment` under a `tracker-loop:skip` marker, so it is a
  contract op and idempotent across iterations.
- **Tracker-brief window stamp (5.1).** `--commit-run <generated_at>`
  stamps the collection time, not the write time. Loop refs become ledger
  keys only when they are issue-shaped; a poll loop contributes the refs in
  its `prs_opened` instead of its label.
