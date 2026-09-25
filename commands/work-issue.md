---
description: Drive ONE named issue end-to-end through the full mandated agent pipeline — read, scope, worktree, brainstorm → plan → execute → verify → PR.
---

# /work-issue <ref> [--start] [--draft | --merge] [--loop] | --finish [--released <tag>]

Take a single named issue and drive it to a PR through the full mandated agent workflow. `/work-issue` is the single-issue counterpart to [`/resume-initiative`](resume-initiative.md): where `/resume-initiative` is epic/initiative-oriented (it walks an initiative tree and picks the next workable leaf), `/work-issue` takes ONE issue you name and runs it end-to-end — read the body, assess scope, create an isolated worktree, then brainstorm → plan → execute → verify → open a PR. The configured backend is resolved from `.claude/issue-tracker.yaml` in the consumer project, the same as `/resume-initiative`.

It is **backend-agnostic**: it dispatches ONLY through the contract operations in [`backends/_interface.md`](../backends/_interface.md) — `view_issue` (always); `edit_body` (start-side epic Status sync and the `--finish` Status block / `## Children` refresh, best-effort, legacy parents); `read_comments` / `upsert_comment` (start-side epic machine-block sync and the `--finish` decision-log append, best-effort, evergreen parents; `--finish`'s evidence comment on other Jira tickets the PR fixed); and, where the workflow surfaces a label/close action, `add_label` / `close_issue` (`--finish --released <tag>` closes through `close_issue`). It never adds a new operation and never reaches past the contract into a backend's raw CLI / MCP; the start-side sync's in-progress marking and `--finish`'s merged-status transition use the per-backend **optional affordances** (not contract operations — see `backends/_interface.md` "Optional backend-specific capabilities"), likewise dispatched through the backend module. `<ref>` is opaque: `#N`, `owner/repo#N` (cross-repo GitHub), or `PROJ-123` (Jira) — only the backend parses it. See `backends/<backend>.md` for the literal calls.

## Why a slash command, not a subagent

`/work-issue` is a **slash command that runs in the main session**, by deliberate design — it is NOT a subagent. The driver must create git worktrees and **dispatch implementation subagents** (`superpowers:subagent-driven-development` spawns a fresh subagent per task). A subagent cannot itself spawn the worktree-bound implementer subagents the execute step needs, and `EnterWorktree` must run in the session whose CWD it switches. So the driver stays in the main session and orchestrates from there. This mirrors `/resume-initiative`, which is a main-session command for the same reason (it enters worktrees and hands off to `superpowers:brainstorming` inline).

## Relationship to siblings

| Command | Scope | Pipeline | Backend | Session | Bail behaviour |
|---|---|---|---|---|---|
| `/work-issue <ref>` | ONE named issue | Full mandated pipeline (scope-graded: trivial → TDD-implement-verify; non-trivial → brainstorm → plan → execute) | Backend-agnostic (`view_issue`, best-effort `edit_body`, optional `add_label` / `close_issue`) | Main session (creates worktrees, dispatches implementer subagents) | **Never bails for size** — a non-trivial verdict *escalates rigor*, it does not refuse |
| `/resume-initiative <ref>` | An epic **tree** → its next-up **leaf** | Walks the tree, resolves the next workable leaf, then hands that leaf into the same pipeline | Backend-agnostic (`list_open_issues`, `view_issue`) | Main session (enters the leaf's worktree, hands off inline) | Stops only when there is no open leaf to start |
| A consumer's trivial-only headless auto-fixer | ONE issue, **only if trivially scoped** | Triages, fixes inline if trivial, opens a draft PR | Typically project-local + GitHub-specific | Headless (no operator) | **Bails** to manual handling the moment scope is non-trivial (open design question, fuzzy acceptance, large blast radius) |

The third row describes the *class* of command some consumer projects ship — a headless, trivial-only auto-fixer that refuses anything needing judgement. It is **not** part of this plugin; it is named generically here only to contrast the bail semantics. The defining difference: a trivial-only auto-fixer treats "non-trivial" as a **stop condition**; `/work-issue` treats it as a **mode switch** to the longer, more rigorous path. `/work-issue` never refuses an issue for being too big — it escalates.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/work-issue <ref>` | Read the issue, assess scope, derive the branch name, and **create (or enter) the worktree**. Then **wait** — report the scope verdict + worktree path and pause for the operator to confirm before running the pipeline. |
| `/work-issue <ref> --start` | Same read + scope + worktree, then proceed **straight into the inline workflow** without pausing for confirmation (mirrors `/resume-initiative --start`). |
| `/work-issue <ref> --draft` | Modifier (combinable with `--start`). The finish step opens a **draft** PR instead of a ready-for-review PR. Everything else is identical. |
| `/work-issue <ref> --merge` | Modifier (combinable with `--start`). **Explicit operator override of the default merge gate:** after verification passes and the ready-for-review PR is open, the finish step also merges it via the git host with the configured `merge_method` (`merge` | `squash` | `rebase`, default `squash`) — arm auto-merge where the repo supports it (GitHub: `gh pr merge --<merge_method> --match-head-commit <verified head sha> --auto`, so required checks still gate the actual merge and only the head Step 5 verified can land), falling back to a direct merge with the same method and pin only when auto-merge is unavailable. Refuses (no merge) when the PR is already merged or the base moved since Step 5 — the fix is a rebase and a re-verify. Never passes `--delete-branch`. Mutually exclusive with `--draft`: if both are passed, refuse with a clear message instead of guessing. |
| `/work-issue <ref> --loop` | Modifier (combinable with `--start`, `--draft`, `--merge`). After Step 6 opens the PR, Step 7 arms a session cron that runs `/agent-issue-tracker:tracker-loop babysit <ref>` at `loops.interval` until the PR merges, is approved, or needs a judgement call. |
| `/work-issue <ref> --finish [--released <tag>]` | **Post-merge phase** (Step 8), run in place of Steps 1–7. Idempotent; safe to run any time after the merge, from any directory of the repo (the worktree need not still exist). Refuses with **no writes** unless the PR for `<ref>` is `MERGED` — which also covers a `--merge` run whose auto-merge landed after the session ended. Moves the ticket to its merged status, handles the other tickets the PR fixed, refreshes the parent index, and removes the worktree and local branch Step 3 created behind provenance gates. `--released <tag>` (Jira with `jira.merged_transition` set; one ref per invocation) also closes `<ref>` when its merge commit is an ancestor of `<tag>`. |

`--start` and `--draft` are orthogonal: `/work-issue #42 --start --draft` runs the whole pipeline inline and finishes with a draft PR. `--merge` combines with `--start` the same way (`--start --merge` runs inline and merges on green) but never with `--draft` — a draft PR is by definition not ready to merge. `--finish` stands alone: it takes no flag but `--released <tag>`.

## What you should do

### Step 1 — Read

Invoke `view_issue({ref})` via the configured backend (resolved from `.claude/issue-tracker.yaml`). `<ref>` may be `#N` (same repo), `owner/repo#N` (cross-repo GitHub), or `PROJ-123` (Jira) — refs are opaque, only the backend parses them; see `backends/<backend>.md` for the literal call. The returned `{ref, title, body, labels[], status, parent?}` carries the issue body — already an agent prompt (Goal, Locus, Skills to load, Constraints, Acceptance, Verify) — that drives the rest of the run.

If `view_issue` returns not-found, **stop** and report a ref-syntax hint: check the ref matches the configured backend (`#42` vs `owner/repo#42` vs `PROJ-123`). Do not guess at a different ref.

### Step 2 — Scope assessment

Apply the trivial-work test: **"could two reasonable engineers disagree about scope, approach, or acceptance criteria?"**

- **NO** (a typo, a version bump, a one-line patch, a mechanical rename) → **trivial path.** Skip brainstorm + plan; go straight to TDD-implement-verify in Step 4.
- **YES** (the body has an open design question, a non-obvious approach, a wide blast radius, or fuzzy acceptance) → **full pipeline.** Run brainstorm → plan → execute in Step 4.

**Critical distinction from a trivial-only auto-fixer.** A non-trivial verdict does **NOT** bail. Where a headless trivial-only auto-fixer would refuse the issue and hand it back for manual work, `/work-issue` instead **triggers the LONGER path** — brainstorm → plan → execute. `/work-issue` never refuses an issue for being too big; it escalates rigor instead. The scope verdict chooses *which* path, never *whether* to proceed.

Report the verdict (`trivial` / `non-trivial`) to the operator with a one-line justification so they can see why the path was chosen.

### Step 3 — Worktree

Create an isolated worktree on a convention-named branch so the run never touches `main` in the primary working tree. The branch prefix is **label-derived** from the issue's labels:

- `enhancement` → `feat/<short-slug-of-title>`
- `bug` → `fix/<short-slug>`
- `documentation` → `docs/<short-slug>`
- anything else (or no matching label) → `feat/<short-slug>`

Reuse `/resume-initiative` Mode-3's worktree mechanics **verbatim**:

1. **Idempotency first.** If a worktree for this issue already exists (convention: `.claude/worktrees/<branch-with-slash-replaced-by-plus>` — e.g. branch `feat/fix-auth` → dir `feat+fix-auth`), **enter it** instead of creating a duplicate. Report its path and continue (do not create a second worktree).
2. Otherwise, prefer the native `EnterWorktree` tool (or the `superpowers:using-git-worktrees` skill) to create one.
3. **Rename the sanitized branch in place to the convention.** `EnterWorktree` sanitizes the branch name to `worktree-<slug>+<rest>` (prefix + `/` replaced by `+`), which does NOT match the project's `feat/...` / `fix/...` / `docs/...` convention. Immediately after `EnterWorktree` returns, rename the branch in place — keeping the worktree directory name:

   ```bash
   git branch -m worktree-<sanitized> <conventional-name>
   ```

   The worktree directory keeps its `<sanitized>` name (matching the on-disk convention `feat+<slug>`); only the branch is renamed.

**Start-side initiative sync (best-effort).** Immediately after the worktree
exists, reflect "work has started" into the initiative state. Every step here is
best-effort: a failure emits a WARN and never blocks the run, the worktree, or the
eventual PR. With no `.claude/issue-tracker.yaml`, skip the whole block (fail-open).

1. **Discover the parent epic — from the body, not the backend.** Parse the issue
   body (fetched at Step 1) for a `## Parent epic` block; the ref opening its first
   non-blank line names the immediate parent (`templates/sub-issue-body.md` pins the
   shape). This is the portable cross-backend signal — do NOT rely on `view_issue`'s
   `parent?` field, which is absent on GitHub plain reads (`backends/_interface.md`).
   No `## Parent epic` block → not an initiative child; skip step 2 (step 3's
   in-progress marking still applies).
2. **Sync the parent's in-progress signal — branch on shape.** `view_issue(parent)`
   determines shape (`commands/resume-initiative.md` "Two epic shapes" — a
   `## Status block` heading in the body means legacy; its absence means
   evergreen).
   - **Legacy parent** (body has `## Status block`) — unchanged: read-modify-write
     per cross-backend invariant 2 — set the Status block's `- **Current branch:**`
     line to the new branch name and `- **Last updated:**` to today (`YYYY-MM-DD`),
     then `edit_body(parent, new_body)`. Touch NOTHING else — not `Phase`, not
     `Next up`, not the `## Children` mirror; those are legacy Maintenance
     (`skills/initiative-tracking/SKILL.md`). Parent unfetchable, or its body has no
     Status block → WARN and skip.
   - **Evergreen parent** (no `## Status block`) — `read_comments(parent)` to
     locate the machine-block comment (earliest marker-carrying comment from a
     trusted author — `backends/_interface.md` "Machine-block comment
     convention"), then `upsert_comment(parent, marker, new_body)` setting the
     `## Current branch` section to the new branch name. No TRUSTED marker-carrying comment
     found → create one (`templates/epic-machine-block.md`'s marker
     `<!-- agent-issue-tracker:machine-block -->`); the newly created block then
     carries only the marker plus the `## Current branch` section. Touch NOTHING
     else — not `## Phases`, `## Decision log`, or `## Parent epic`. Parent
     unfetchable, or the comment read/write fails → WARN and skip. Close-side
     maintenance is obsolete for evergreen parents: there is no close-side body
     edit to automate — child state is derived at read time under the evergreen
     model (superseding follow-up #87). Legacy parents still follow
     `initiative-tracking`'s legacy close-side Maintenance ritual, unchanged.
3. **Mark the issue in progress** via the backend's configured affordance — see
   `skills/initiative-tracking/SKILL.md` "In-progress status (optional affordances)":
   GitHub with `github.project` set → board item Status `In Progress`
   (`backends/github.md`); Jira with `jira.in_progress_transition` set → fire that
   workflow transition (`backends/jira.md`), and with `jira.in_progress_sprint:
   active` also set → right after the transition, also add the issue to the
   project's single active sprint (`backends/jira.md` "In-progress sprint
   (optional)"). Neither configured → no-op; the `Current branch` signal set in
   step 2 is the fallback — but only when step 2 actually ran.

   **When step 2 was skipped too, there is no fallback — say so.** A parentless
   issue (no `## Parent epic` block) with no configured affordance emits *zero*
   in-progress signal: nothing on a board, no workflow transition, and no
   `Current branch` line, because there is no parent to carry one. Each half is a
   documented no-op on its own, so neither warns today — and their combination is
   the one path where a full run leaves the tracker indistinguishable from
   untouched. Emit one WARN naming both halves, so it lands in the run output the
   operator actually reads:

   ```
   WARN: no in-progress signal emitted — this issue has no parent epic and no
         in-progress affordance is configured (jira.in_progress_transition /
         github.project). The tracker will still show this issue as not started.
   ```

   Best-effort as ever — this warns, it never blocks. The two fixes are config
   (`/tracker-doctor` Phase 1 flags the unset Jira key) or filing the issue under
   an epic so step 2 has a parent to stamp.

`EnterWorktree` switches the session's CWD into the worktree — do **NOT** stop and tell the operator to open a new window. The driver continues inline in the same session.

### Step 4 — Execute

Hand the issue body — already an agent prompt — to the workflow as **starting context**. Do NOT re-derive the problem from scratch; the body's Goal / Locus / Constraints / Acceptance / Verify are the brief.

**Full path (non-trivial):**

1. `superpowers:brainstorming` — explore intent, edges, and the chosen approach, using the issue body as starting context.
2. `superpowers:writing-plans` — ordered tasks with acceptance criteria, blast radius, and per-task verification.
3. `superpowers:subagent-driven-development` — execute the plan, a fresh subagent per task, with a review checkpoint after each.
4. `superpowers:test-driven-development` — red → green → refactor for **every** behaviour change, throughout. New code without a failing-first test is a defect.
5. `superpowers:requesting-code-review` — before claiming the work is done.

**Trivial path:** skip brainstorm + plan; go straight to TDD-implement-verify (`superpowers:test-driven-development` red → green → refactor, then Step 5).

### Step 5 — Verify

Run `superpowers:verification-before-completion` with **REAL command output** — actual test runs, actual build output — before any success claim. No "should work", no "looks good". If verification cannot pass (tests fail, build breaks), **do not open a non-draft PR** — report the failure and stop (or, if `--draft` was passed, the finish step opens a draft PR so the work-in-progress is visible; a non-draft PR is never opened on red).

When verification passes, record the verified head (`git rev-parse HEAD`) and the base it was verified against (`git rev-parse origin/<base>`); `--merge` pins both in Step 6.

### Step 6 — Finish

Run `superpowers:finishing-a-development-branch`: open a PR whose body links the issue via the configured backend's **close-on-merge convention**.

- **GitHub** (see `backends/github.md` "PR close-on-merge convention") — include the literal `Fixes <ref>` line in the PR body for a `bug`, or `Closes <ref>` for a non-bug (enhancement / docs). Both phrasings auto-close on merge to the default branch; honour the consumer's `github.default_pr_close_syntax` if set.
- **Jira** (see `backends/jira.md` "PR close-on-merge convention") — Jira does not auto-close from PR keywords; the close-on-merge transition is the consumer's DVCS smart-commit / branch-name convention. Render the consumer's `jira.close_on_merge_hint` into the PR body as the advisory line (omit if empty).

`--draft` opens a **draft** PR. The PR is the **human gate by default** — `/work-issue` does **not** merge the PR, on any backend, in any mode, **unless the operator passed `--merge`** (the explicit per-invocation override; see Invocation modes). Even with `--merge`, never merge on red: if Step 5 verification did not pass, no ready-for-review PR exists to merge in the first place. With `--merge`, merge using `merge_method` from `.claude/issue-tracker.yaml` (`merge` | `squash` | `rebase`, default `squash`): `gh pr merge --<merge_method> --match-head-commit <head sha Step 5 recorded> --auto`, or the same without `--auto` where auto-merge is unavailable — never with `--delete-branch` (remote branches are the repo's to keep or delete; see Step 8). Right before merging, `git fetch` and re-check: the PR is already `MERGED`, or `git rev-parse origin/<base>` differs from the base Step 5 recorded → refuse, report which, and do not merge (rebase and re-verify instead). On GitHub, squashing via the CLI also changes the account's preselected merge method in the web UI for the next manual merge; a repo on a merge-commit convention sets `merge_method: merge` for that reason alone. The post-merge steps are not part of this run: `--finish` (Step 8) does them once the PR has merged. Note the override authorizes only this command's behavior — the harness's own permission layer may still require its own approval for the merge action, and that layer is the operator's to configure, not this command's to bypass. With `--start`, the run proceeds straight from worktree creation (Step 3) through Steps 4–6 inline without pausing for confirmation, mirroring `/resume-initiative --start`. Without `--start`, the run pauses at the end of Step 3 for the operator to confirm before Step 4.

### Step 7 — Arm the loop (`--loop` only)

Only when `--loop` was passed and Step 6 opened a PR:

1. `LR="${CLAUDE_PLUGIN_ROOT}/scripts/loop-record.sh"`; `$LR create babysit <ref> <branch> [--merge] [--draft] --interval <loops.interval> --max-iterations <…> --max-hours <…> --idle-stop-after <…>` with values from the `loops:` block (`ait_config_get loops.<key>` from `scripts/lib/common.sh`; defaults in `commands/tracker-loop.md`).
2. `CronCreate` a recurring job at `loops.interval` on an off-minute (the tool's guidance), prompt `/agent-issue-tracker:tracker-loop babysit <ref>` with this invocation's `--draft` / `--merge` appended when passed (for example `/agent-issue-tracker:tracker-loop babysit #42 --merge`); then `$LR set-cron <id> <job-id>`. The record carries the same flags in `options`, so a fire that lost them still reads them from there.
3. Tell the operator, in three lines: the loop id and cadence; that session crons expire after seven days and end with the conversation; and that `/loop /agent-issue-tracker:tracker-loop babysit <ref>` (self-paced) or `/schedule` are the alternatives.

`--loop` without a PR (verification failed, no `--draft`) arms nothing and says so.

### Step 8 — Finish (`--finish`)

Only when `--finish` was passed; Steps 1–7 do not run. Every sub-step is **best-effort** — a failure WARNs and the next sub-step still runs — except sub-step 1's gate, which stops with no writes, and sub-step 5's cleanup gates, which refuse rather than force. Re-running is safe: a transition already applied is no longer offered, marker comments are replaced rather than added, index lines already in their target state are left alone, and a removed worktree is skipped.

1. **Gate — the PR must be merged.** Resolve the PR for `<ref>`: `gh pr list --repo <nwo> --state all --search "<ref>" --json number,url,state,headRefName,headRefOid,mergeCommit,body`, newest first; when that finds none, fall back to `--head <branch>` with Step 3's branch derivation (which needs `view_issue({ref})` for the labels and title). No PR, or `state != MERGED` → print the ref, the PR (if any) and its state, and **stop with no writes**. The merge sha is `mergeCommit.oid`.
2. **Ticket status.**
   - **Jira** with `jira.merged_transition` set → apply it to `<ref>` (`backends/jira.md` "Merged transition (optional)"). Unset → nothing, as today. `done_transition` is **never** applied on merge when `merged_transition` is set; it stays the release / close step.
   - **GitHub** → nothing to transition: the PR's `Fixes` / `Closes <ref>` line already closed the issue on merge. With `github.project` set, set its board item Status to `Done` (`backends/github.md` "Post-merge (optional)").
   - **`--released <tag>`** — only with `jira.merged_transition` set (otherwise say it does not apply and skip). `git fetch --tags`, then `git merge-base --is-ancestor <merge sha> <tag>`: true → `close_issue({ref, reason: completed, comment: "Released in <tag>."})`, which applies `done_transition`; false (or the tag is unknown) → WARN `<merge sha> is not in <tag>` and apply nothing. One ref per invocation; sweeping every ticket a tag released is out of scope.
3. **Other tickets the PR fixed.** Parse the PR body for `Fixes|Closes|Resolves <ref>` lines (every ref, in the ref syntax the backend owns). For each ref other than `<ref>`:
   - **Jira** → apply `jira.merged_transition` when set, and leave an evidence comment: `upsert_comment(<other>, "<!-- work-issue:finish -->", "<!-- work-issue:finish -->\nMerged in <PR url> (<merge sha>)")` — idempotent by marker.
   - **GitHub** → nothing; the keywords already closed them. Board `Done` sync when `github.project` is set.
4. **Parent index refresh.** Discover the parent the portable way, as Step 3 does: the `## Parent epic` block in the body `view_issue({ref})` returns. No block → skip. `view_issue(parent)` determines the shape.
   - **Legacy parent** (body has `## Status block`) — the one-hop Maintenance ritual from `skills/initiative-tracking/SKILL.md`, in one read-modify-write `edit_body(parent, new_body)`: recount `- **Phase:**` as `<closed>/<total>` over the direct children; set `- **Next up:**` to the first open direct child in `## Children` order (or `none`); set `- **Current branch:**` to `none` if it names this branch; set `- **Last updated:**` to today (`YYYY-MM-DD`); flip this child's `## Children` line to `- [x]`. Match Status-block lines on the bold field label, not the bullet (Jira rewrites `-` to `*`). Touch nothing else.
   - **Evergreen parent** (no `## Status block`) — `read_comments(parent)` to locate the machine-block comment (earliest trusted marker-carrying comment), append `- **YYYY-MM-DD** — <ref> merged in <PR url>` to its `## Decision log` (skip the append when that line is already there), clear `## Current branch` when it names this branch, then `upsert_comment(parent, marker, new_body)`. No trusted machine-block comment → create one carrying the marker and the `## Decision log` entry only, as Step 3 does for `## Current branch`. Child state itself is derived on read; nothing else is written.
5. **Local cleanup (provenance-gated, never forced).** Only the worktree Step 3 created: `.claude/worktrees/<branch-with-slash-replaced-by-plus>` for the PR's `headRefName`, and only when `git worktree list --porcelain` shows that branch checked out there. Anything else is left alone. All three gates are required:
   - the PR is `MERGED` (sub-step 1);
   - the local branch tip equals the PR's `headRefOid` (`git rev-parse <branch>`) — nothing unpushed. Squash and rebase merges rewrite history, so "tip is an ancestor of the base" is the wrong test;
   - `git -C <worktree> status --porcelain -uall` is empty.

   Any gate fails → print what is at stake (the commits `git log --oneline <headRefOid>..<branch>` shows, or the dirty paths) and stop cleanup; the worktree and branch stay, and the sub-steps above have already run. All gates pass → if the session is still inside the worktree, `ExitWorktree` first (keeping it — the removal below does it); then, from the primary checkout: `git worktree remove <path>` (never `--force`), `git worktree prune`, `git branch -D <branch>` (`-D` because a squash-merged branch is never "fully merged" in git's sense; the head-equals-PR-head gate is what makes it safe). No such worktree → skip the removal; the local branch, if it exists, is still deleted behind the first two gates. **The remote branch is never deleted by the plugin:** when the repo has `deleteBranchOnMerge` enabled GitHub already removed it, and when it does not, the repo keeps merged branches by policy (`backends/github.md` "Post-merge (optional)").
6. **Report** one line, after any WARNs:

   `finish <ref> · PR #<n> merged <short sha> · status: <transition | closed by keyword | none> · others: <n> · parent: <refreshed | skipped | none> · cleanup: <removed | refused: <gate> | nothing to do>`

## Conventions assumed

- **The issue body is an agent prompt.** Every issue this plugin files carries the agent-prompt shape (Goal, Locus, Skills to load, Constraints, Acceptance, Verify) per the `bug-tracking` / `feature-request` / `followup-tracking` skills. `/work-issue` uses that body as starting context; it does not re-derive the problem. A body too vague to drive a run is itself the finding — report it and stop rather than inventing scope.
- **`.claude/issue-tracker.yaml` selects the backend.** The same config `/resume-initiative` and `/tracker-doctor` read. `/work-issue` dispatches `view_issue`, the start-side sync's `edit_body` (legacy parents) / `read_comments` + `upsert_comment` (evergreen parents), and any `add_label` / `close_issue` through `backends/<backend>.md`; it never calls a backend's raw CLI / MCP directly.
- **Worktree-first.** All work happens in an isolated worktree on a `feat/` | `fix/` | `docs/` branch — never on `main` in the primary working tree. This keeps the operator's primary checkout stable for any long-running processes while the run proceeds.
- **Post-merge is its own invocation.** The run ends at the PR; `/work-issue <ref> --finish` (Step 8) is the idempotent post-merge phase and writes nothing until the PR is `MERGED`. On Jira, *merged* and *released* are separate statuses when `jira.merged_transition` is set: `--finish` applies the merged one, `--finish --released <tag>` the release (`done_transition`). The plugin never deletes a remote branch and never force-removes a worktree.

## Failure modes

- **Backend authentication or reachability failure** → the configured backend reports a reachability failure on the `view_issue` dispatch. Run `/tracker-doctor` to diagnose the setup; see `backends/<backend>.md` setup section, fix, and re-invoke.
- **`view_issue` returns not-found for the supplied ref** → check the ref syntax matches the configured backend (`#42` vs `owner/repo#42` vs `PROJ-123`). Report the hint and stop; do not guess a different ref.
- **Verification cannot pass** (tests fail, build breaks at Step 5) → do **NOT** open a non-draft PR. Report the failing command output and stop. (With `--draft`, a draft PR may be opened so the in-progress work is visible — a non-draft PR is never opened on red.)
- **A worktree for this issue already exists** → enter it (`.claude/worktrees/<branch-with-slash-replaced-by-plus>`) instead of creating a duplicate; report its path and continue.
- **The issue body is too vague to drive a run** (no locus, fuzzy acceptance, an unresolved open design question) → report that the body is unfileable-as-an-agent-prompt and stop. The fix is to enrich the issue (or file a `needs-design` issue first), not to invent scope. `/work-issue` escalating rigor for a *non-trivial-but-well-specified* issue is different from a *vague* one — the former gets the full pipeline, the latter gets reported back.
- **Cross-repo `owner/repo#N` ref** → the worktree is created in the consumer's current working directory regardless; only the `view_issue` body fetch hits the child's repo via the backend. The backend module documents how it handles cross-repo refs.
- **Start-side initiative sync fails** (parent epic unfetchable; legacy parent — Status block missing; evergreen parent — machine-block comment read/write rejected; board write, transition, or sprint write rejected) → WARN and continue; status writes never block the run. Legacy parents catch up on the close side via `initiative-tracking`'s legacy Maintenance ritual (formerly tracked as follow-up #87). For evergreen parents, #87 is superseded: there is no close-side body edit left to catch up with — child membership, status, and counts are all derived at read time.
- **Start-side sync succeeds but emits no in-progress signal** (parentless issue AND no configured affordance) → one WARN from Step 3 naming both halves, then continue. Not a failure — every individual step did what it documents — but it is the only path on which a completed run leaves the tracker indistinguishable from untouched, so it must not be silent. Fix is config (`/tracker-doctor` Phase 1 flags an unset `jira.in_progress_transition`) or filing the issue under an epic.
- **`--loop` but `CronCreate` is unavailable** (cron disabled by `CLAUDE_CODE_DISABLE_CRON`, or not in the tool surface) → stop the record with reason `no cron`, print the `/loop …` line for the operator to run by hand, and continue; the PR is already open.
- **`--merge` but the PR is already merged, or the base moved since Step 5** → refuse the merge and report which; nothing is merged. A moved base needs a rebase and a re-verify (the babysit loop's `rebase` row), not a silent merge.
- **`--finish` on a PR that is not merged** (no PR found, still open, or closed unmerged) → print the PR state and stop with **no writes**. Re-run `--finish` after the merge.
- **A `--finish` cleanup gate fails** (local tip differs from the PR's `headRefOid`, or the worktree is dirty) → print what is at stake (unpushed commits, dirty paths) and leave the worktree and branch in place; the ticket, other-ticket and index sub-steps have already run. Never `--force`.
- **Jira transition name absent** (`getTransitionsForJiraIssue` does not offer `merged_transition` or `done_transition` from the issue's current state — already there, or the workflow lacks it) → WARN and skip that ticket's transition; continue.
- **`--released <tag>` but the merge commit is not an ancestor of `<tag>`** (or the tag is unknown) → WARN and apply no transition.
