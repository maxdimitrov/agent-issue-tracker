---
description: Catch up on the current session — issue link, branch, PR, CI, review threads awaiting you, what was in flight, and a verdict on keep going / compact / fresh session, with a resume note written for a cold start.
---

# /session-brief

Orient the operator in the session they are **currently in** — resumed after a weekend, or long enough that they have lost the thread. Answers five questions in order: what am I working on, what state is it in, what needs me, what did I already resolve, and should I keep going here or start clean.

**This command is read-only.** Never commit, push, comment on a PR, transition an issue, or edit source. The only file written is the resume note, outside every repo. The one outward action is opening a new editor tab (Step 5), and only after the operator accepts the offer. If the operator wants an action taken, they will ask in the next turn.

## Step 1 — Collect the facts

One call:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/session-brief-collect.sh"
```

The script always exits 0 and always prints valid JSON. Everything in that JSON is ground truth; everything else in the brief comes from your own memory of this conversation. Keep the two straight — never report a PR number, CI result, or branch state from recollection when the JSON has it, and never invent a value the JSON returned as `null`.

When `config.backend` is set and `ticket.key` is non-null, enrich the ticket with one `view_issue({ref: ticket.key})` through the configured backend (`backends/<backend>.md`) for its title and status. A not-found is reported on the ticket line, not hidden.

Degrade, don't fail:

| JSON says | Do this |
|---|---|
| `repo.is_git: false` | Brief the session only. Say there is no repo here; skip WHERE / PR / CI. |
| `repo.gh_available: false` | Say git-host state is unavailable; brief git + session. |
| `pr: null` | "No PR yet" — a real and useful fact, not an error. Say it on the PR line rather than dropping the line. |
| `ci: null` | No runs for this branch. Don't imply CI passed. |
| `session: null` | No transcript found. Brief repo state only; skip the verdict and say why. `session.transcript_source` of `discovered` means a heuristic match — say so in one clause when the verdict is a close call. |
| `git.detached: true` | Report detached HEAD prominently — it is usually a surprise. |
| `config.backend: null` | No `.claude/issue-tracker.yaml`. The ticket line carries the key only. |

## Step 2 — Print the brief

Fixed section order. Terse — values, not sentences. **Omit any line whose data is null** rather than printing "unknown". Use real markdown links for paths so they are clickable.

**Never emit the header block inside a code fence.** A fence renders every link and path in it as dead text. The layout below is shown fenced so the placeholders are readable here — your output must be plain markdown, aligned with the same column positions.

**The ticket and PR links are mandatory, every time.** A brief whose whole job is to re-orient someone is useless if they have to go hunting for the two URLs they need. Take them verbatim from `ticket.url` and `pr.url`; never reconstruct either from a key or number. The only reason to omit one is that the JSON returned it as null, and then you say so on that line.

```
<TICKET> · <session title>
<ticket url>
<pr url>

WHERE      <cwd, marked (worktree) if repo.is_worktree>
           <branch> · <ahead> ahead, <behind> behind <base> · <dirty_count> dirty
PR         [#<n>](<pr url>) <state><, draft><, reviewDecision> · CI [<workflow> <conclusion>](<ci run_url>)
LOOP       <mode> <ref> · iteration <n> · last <last_action> · cron <armed|none>
LAST TASK  <what you were doing, one line>
           last commit <when> — <subject>

NEEDS YOU
  ...

ALREADY RESOLVED
  ...

VERDICT    <keep going | /compact | fresh session> — <reason>
```

**LOOP** appears only when `loop` is non-null: a live `/tracker-loop` record for this branch. `cron armed` when `loop.cron_job_id` is set.

**LAST TASK** is the one section that is yours, not the script's. State what was actually in flight, cross-checked against `git.last_commit` and `git.dirty_files`. If `session.compaction_markers > 0` and you no longer hold the detail, say so plainly — "session was compacted; reconstructing from git state and last prompt" — and fall back to `session.last_prompt` plus the dirty files. Never fabricate continuity you don't have.

**NEEDS YOU** — every item that blocks progress, most-blocking first:

- `review.threads[]` where `awaiting_you` — show `author`, `path:line`, `excerpt`. These are unresolved threads where someone other than you spoke last.
- `ci.conclusion == "failure"` — name the failed jobs from `ci.failed_jobs`.
- `git.behind > 0` by a large margin — needs a base sync before it can merge.
- `git.dirty_count > 0` — uncommitted work that would be lost.
- `pr.state == "OPEN"` with `reviewDecision == "APPROVED"` — ready to merge, waiting on you.
- `pr.mergeable == "CONFLICTING"` — conflicts to resolve.
- `loop.stop_reason` naming NEEDS YOU — the loop stopped for a judgement call; repeat what it asked.

**ALREADY RESOLVED** exists so the operator doesn't re-litigate something last-week-them already closed. Sources: `review.threads[]` where `resolved` is true, plus what you remember fixing in this session. If there is nothing to report, omit the whole section — don't pad it.

Note `pr.state` of `MERGED` or `CLOSED` loudly. A merged PR on a branch that is far behind usually means the work shipped and the session is finished, which changes the verdict to a fresh session.

## Step 3 — The verdict

Three outcomes. Signals come from `session`: `turns_user`, `span_hours`, `compaction_markers`, `branches_seen`, `tickets_seen`.

| Condition | Verdict |
|---|---|
| `turns_user` < 25, `span_hours` < 2, no compaction, one ticket in `tickets_seen` | **keep going** |
| `turns_user` ≥ 25 or `span_hours` ≥ 2 — and still the same ticket/branch | **/compact** |
| `tickets_seen` or `branches_seen` has more than one, and the next task belongs to a different one | **fresh session** |
| `compaction_markers` ≥ 1 and `turns_user` ≥ 25 since | **fresh session** |
| The next task is cleanly separable — new ticket, different repo | **fresh session** |
| `pr.state == "MERGED"` and nothing left in NEEDS YOU | **fresh session** — this work is done |

Why `/compact` rather than fresh when the work is coherent: compaction keeps recent turns verbatim and drops old tool output, so mid-ticket detail survives. A fresh session is better when the *shape* of the work changed, because then the old detail is ballast — and compacting an already-compacted session loses more than a clean handoff does.

Always give the reason, never a bare verdict. The thresholds live in this one table so they are easy to retune. `/tracker-loop` applies this same table as its per-iteration checkpoint.

**Honesty constraint:** no tool exposes real context-window usage to a command. This verdict is a proxy from turn count, elapsed time, and compaction markers. Say that when it is a close call, and point the operator at `/context` for the real number. Never phrase it as if you measured the context window.

## Step 4 — Write the resume note

Write to `handoff.resume_path` from the JSON — under the plugin's state directory, outside any repo, so it can't dirty a working tree. Overwrite in place; the timestamped header is the version marker. Then print the same block so it is usable immediately without opening the file.

```markdown
# Resume: <TICKET or branch> — written <YYYY-MM-DD HH:MM>

cd <cwd>

Resume <TICKET> (<ticket url>) on branch `<branch>`, PR #<n> (<pr url>).

**Done so far:** <2-4 bullets of what actually landed — commits, decisions made>

**Next action:** <the single most specific next step, with file:line if known>

**Open threads to answer:**
- <author> on <path:line> — <excerpt>

**Loop:** re-arm with `/loop /agent-issue-tracker:tracker-loop <mode> <ref>`   ← only when `loop` was non-null

**Constraints / gotchas:** <repo rules and traps that would bite a cold start — base branch, formatting rule, anything learned the hard way this session>
```

Both URLs are required here too — this note is read cold, by a session with no memory of the work, so an unlinked key or PR number is a dead end.

Then tell the operator, in one line, that it is at that path and what to do with it: paste it as the first message of a new session.

If `handoff.exists` is true and `handoff.written` is older than this session, mention the previous note is being replaced — it may describe a different stage of the work.

## Step 5 — Offer a new tab (`fresh session` only)

Only when the verdict is **fresh session**. On a VS Code host (`CLAUDE_CODE_ENTRYPOINT` is `claude-vscode`), **offer** to open the fresh session for the operator: "Open a new tab with the resume note?" Offer only. Never open one unasked. On a yes:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/open-session-tab.sh" "Read the resume note at <handoff.resume_path> and continue from it."
```

The script fires `code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"`. The prompt is **typed into** the new tab's input box but **not submitted**; the operator presses Enter. VS Code first asks whether to allow the extension to open the URI, so mention that dialog. The prompt points at the note's path instead of carrying its body, which keeps the URI short (the script refuses prompts over 2000 characters) and leaves the file as the single copy.

On any other host (CLI, JetBrains), or when the script prints `"opened":false`, keep the Step 4 behaviour: the note is already printed for copy-paste, so name the `reason` in one clause and stop. The new tab gets no custom title: the URI has no title parameter, and `/rename` cannot share a message with the real prompt.

## Red flags

| Thought | Reality |
|---|---|
| "I'll just describe the PR state from memory" | Resumed sessions have stale recollections. The JSON is truth. |
| "The operator knows their own ticket and PR number" | They asked to be re-oriented. Link both, every time, from `ticket.url` and `pr.url`. |
| "The header block looks tidier fenced" | A fence makes every link in it unclickable. Plain markdown, aligned columns. |
| "CI is probably fine" | `ci: null` means no runs found, not passing. Say which. |
| "Newest workflow run is the CI result" | The script already picks a primary; the newest run is often a skipped bot workflow. Use `ci.workflow` / `ci.conclusion` as given. |
| "The session feels long, I'll say the context is nearly full" | You cannot see context usage. Use the countable signals and say they are a proxy. |
| "There are no resolved threads so I'll write 'nothing to report'" | Omit the section. Don't pad. |
| "I'll fix the failing test while I'm here" | Read-only command. Report, then stop. |
