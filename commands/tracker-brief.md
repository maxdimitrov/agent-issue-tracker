---
description: Inbound digest for this project since the last run — tracker activity, PRs awaiting you, CI, worktrees, resume notes and loop records joined into one ledger with a verdict per issue.
---

# /tracker-brief

Answers one question: **what moved in this project while I was away, and what wants me now?** Inbound only. The state of the current Claude conversation is `/session-brief`'s job.

Read-only except the window stamp at the end. Never comments, closes, merges, or removes a worktree — it prints the exact command for each of those and stops.

## Step 0 — Collect the deterministic facts

```bash
TB="$(mktemp "${TMPDIR:-/tmp}/tracker-brief-XXXXXX")"
"${CLAUDE_PLUGIN_ROOT}/scripts/tracker-brief-collect.sh" > "$TB"
echo "$TB"
jq -c '.generated_at, .window, .viewer, .config, .errors' "$TB"
```

`mktemp` gives each run its own file, so parallel sessions never overwrite each other's facts. Shell variables do not survive between tool calls: note the printed path (`<brief-json>` below; every later `jq` read uses it) and the `generated_at` value, which Step 4 hands back to `--commit-run`.

The script always exits 0 and always prints one JSON object. It covers this repo's worktrees, PRs on the git host (authored, review-requested, mentions, merged in window, all-time authored), per-PR review threads + comments + CI, the resume notes `/session-brief` wrote, `/tracker-loop` records, and a `ledger` joining all of it on issue ref. It does **not** read the tracker — a shell script has no backend access — so tracker activity is gathered in Step 1 and `ledger[].tracker_status` in Step 2.

Read `.window`: `since` is the lookback start, `days` its span, `summarize_mode` true past five days (compress hard — a post-holiday run must not emit a wall of text). Read `.errors` and carry each into the brief's last line; a degraded source is reported, never silently blank.

## Step 1 — Tracker activity

Through the configured backend (`backends/<backend>.md`), never a raw CLI or MCP call:

1. `list_updated_issues({since: window.since})` — issues that moved in the window.
2. For the first 20 of those, `read_comments({ref})`; keep comments with `created >= since` whose author is not the viewer. These are the "someone said something on my issue" items.

With no `.claude/issue-tracker.yaml` (`config.backend: null`), skip this step and say so; the brief is then git-host + worktrees only.

## Step 2 — Fill the ledger

For every `ledger[]` row with `actionable == true`, `view_issue({ref})` and set `tracker_status` to its `status`. Rows with `actionable == false` are history (a shipped PR whose issue is closed and nothing left on disk) and are neither fetched nor printed.

Then one verdict per actionable row, first match wins:

| Verdict | Condition | Print |
|---|---|---|
| **Needs action** | `detail.unresolved_threads > 0`, `detail.new_comments` non-empty, `detail.ci.conclusion == "failure"`, `detail.review_decision == "CHANGES_REQUESTED"`, or a loop with `stop_reason` naming NEEDS YOU | The specific thing, linked |
| **Status drift** | `merged_pr` set and `tracker_status` is open; or `tracker_status` closed and `open_pr` set | Which side is stale, and the close / reopen command |
| **Waiting** | `open_pr` set, review required, nothing unresolved | Who it is waiting on — no operator action |
| **Closeable** | `merged_pr` set and `tracker_status` closed, with a `worktree` or `resume_note` still on disk | `git worktree remove <path>` and the resume-note path to delete |
| **Stale** | `worktree.stale == true` | `worktree.landed_pr` state: `MERGED` → shipped, free it; `CLOSED` → closed unmerged, confirm before discarding; `OPEN` → still in flight; `null` → genuine abandonment |
| **No code artifact** | `resume_note` or a live loop, but no worktree and no PR | List it; do not force a verdict |

Status drift is expected to be common: GitHub's `Closes #a, #b` auto-closes only the first ref. Judge "closed" on the backend's status, not on a resolution field.

Never use `git merge-base --is-ancestor` to prove a branch landed. Squash and rebase merges rewrite the SHA, so a branch whose PR merged reports "not an ancestor". Trust `landed_pr`, which asked the git host about the branch directly.

`orphan_worktrees[]` (detached, or no ref) are listed after the ledger with their path and last subject; the primary checkout is never among them.

## Step 3 — Loops

`loops[]` are `/tracker-loop` records. For each `live` one, print mode, ref, iteration count, last action, and `actions_in_window`. For each `stopped` one whose `stop_reason` is set, print the reason — a loop that stopped on NEEDS YOU is a Needs-action item and is already in the ledger row.

## Step 4 — Output

Terminal, in this order and nothing else:

1. **Needs you** — merged and ranked across tracker comments, PR threads, CI, drift, and loop stops. The only section that must be read.
2. **Status drift** — one line per row, with the command that fixes it.
3. **Closeable / stale** — one line per row, with the `git worktree remove` line.
4. **Loops** — one line per live loop.
5. **Degraded** — one line per `errors[]` entry; omit the section when empty.

When the `Artifact` tool exists in this session, also publish the full brief (the five sections above plus the tracker activity list, the PR lists, and the complete ledger table) titled `Tracker Brief`, and keep that title stable across days so it stays one recognisable page. No daily log file is written.

Then stamp the window so the next run picks up exactly here:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/tracker-brief-collect.sh" --commit-run "<generated_at from Step 0>"
rm -f "<brief-json>"
```

Stamp **only after** the brief is written. Stamping a failed run silently skips that window forever. Pass Step 0's `generated_at`, not nothing: the stamp then marks when the facts were collected, so activity that arrived while the brief was being written falls inside the next run's window instead of being skipped.

## Known traps

| Trap | Why it bites |
|---|---|
| `gh pr checks` / `statusCheckRollup` | 403 on a fine-grained PAT. The collector already used the Actions API |
| `git merge-base --is-ancestor` as landed-proof | False negative on squash/rebase merges. Use `landed_pr` |
| Verdicting every ledger row | The PR join is all-time. Filter `actionable` first |
| Stamping `--commit-run` before the brief is written | That window is skipped permanently |
| `--commit-run` without Step 0's `generated_at` | It stamps now, so whatever arrived while the brief was being written is never shown |
| Reading the tracker with `gh issue list` or an MCP call directly | Backend-agnostic means contract ops only; `backends/<backend>.md` has the literal call |
| Treating an empty `errors[]`-less section as "nothing happened" | Say what was checked so an absence reads as a result |
