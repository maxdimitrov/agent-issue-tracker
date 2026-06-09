---
description: Drive ONE named issue end-to-end through the full mandated agent pipeline — read, scope, worktree, brainstorm → plan → execute → verify → PR.
---

# /work-issue <ref> [--start] [--draft]

Take a single named issue and drive it to a PR through the full mandated agent workflow. `/work-issue` is the single-issue counterpart to [`/resume-initiative`](resume-initiative.md): where `/resume-initiative` is epic/initiative-oriented (it walks an initiative tree and picks the next workable leaf), `/work-issue` takes ONE issue you name and runs it end-to-end — read the body, assess scope, create an isolated worktree, then brainstorm → plan → execute → verify → open a PR. The configured backend is resolved from `.claude/issue-tracker.yaml` in the consumer project, the same as `/resume-initiative`.

It is **backend-agnostic**: it dispatches ONLY through the contract operations in [`backends/_interface.md`](../backends/_interface.md) — `view_issue` (always) and, where the workflow surfaces a label/close action, `add_label` / `close_issue`. It never adds a new operation and never reaches past the contract into a backend's raw CLI / MCP. `<ref>` is opaque: `#N`, `owner/repo#N` (cross-repo GitHub), or `PROJ-123` (Jira) — only the backend parses it. See `backends/<backend>.md` for the literal calls.

## Why a slash command, not a subagent

`/work-issue` is a **slash command that runs in the main session**, by deliberate design — it is NOT a subagent. The driver must create git worktrees and **dispatch implementation subagents** (`superpowers:subagent-driven-development` spawns a fresh subagent per task). A subagent cannot itself spawn the worktree-bound implementer subagents the execute step needs, and `EnterWorktree` must run in the session whose CWD it switches. So the driver stays in the main session and orchestrates from there. This mirrors `/resume-initiative`, which is a main-session command for the same reason (it enters worktrees and hands off to `superpowers:brainstorming` inline).

## Relationship to siblings

| Command | Scope | Pipeline | Backend | Session | Bail behaviour |
|---|---|---|---|---|---|
| `/work-issue <ref>` | ONE named issue | Full mandated pipeline (scope-graded: trivial → TDD-implement-verify; non-trivial → brainstorm → plan → execute) | Backend-agnostic (`view_issue`, optional `add_label` / `close_issue`) | Main session (creates worktrees, dispatches implementer subagents) | **Never bails for size** — a non-trivial verdict *escalates rigor*, it does not refuse |
| `/resume-initiative <ref>` | An epic **tree** → its next-up **leaf** | Walks the tree, resolves the next workable leaf, then hands that leaf into the same pipeline | Backend-agnostic (`list_open_issues`, `view_issue`) | Main session (enters the leaf's worktree, hands off inline) | Stops only when there is no open leaf to start |
| A consumer's trivial-only headless auto-fixer | ONE issue, **only if trivially scoped** | Triages, fixes inline if trivial, opens a draft PR | Typically project-local + GitHub-specific | Headless (no operator) | **Bails** to manual handling the moment scope is non-trivial (open design question, fuzzy acceptance, large blast radius) |

The third row describes the *class* of command some consumer projects ship — a headless, trivial-only auto-fixer that refuses anything needing judgement. It is **not** part of this plugin; it is named generically here only to contrast the bail semantics. The defining difference: a trivial-only auto-fixer treats "non-trivial" as a **stop condition**; `/work-issue` treats it as a **mode switch** to the longer, more rigorous path. `/work-issue` never refuses an issue for being too big — it escalates.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/work-issue <ref>` | Read the issue, assess scope, derive the branch name, and **create (or enter) the worktree**. Then **wait** — report the scope verdict + worktree path and pause for the operator to confirm before running the pipeline. |
| `/work-issue <ref> --start` | Same read + scope + worktree, then proceed **straight into the inline workflow** without pausing for confirmation (mirrors `/resume-initiative --start`). |
| `/work-issue <ref> --draft` | Modifier (combinable with `--start`). The finish step opens a **draft** PR instead of a ready-for-review PR. Everything else is identical. |

`--start` and `--draft` are orthogonal: `/work-issue #42 --start --draft` runs the whole pipeline inline and finishes with a draft PR.

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

### Step 6 — Finish

Run `superpowers:finishing-a-development-branch`: open a PR whose body links the issue via the configured backend's **close-on-merge convention**.

- **GitHub** (see `backends/github.md` "PR close-on-merge convention") — include the literal `Fixes <ref>` line in the PR body for a `bug`, or `Closes <ref>` for a non-bug (enhancement / docs). Both phrasings auto-close on merge to the default branch; honour the consumer's `github.default_pr_close_syntax` if set.
- **Jira** (see `backends/jira.md` "PR close-on-merge convention") — Jira does not auto-close from PR keywords; the close-on-merge transition is the consumer's DVCS smart-commit / branch-name convention. Render the consumer's `jira.close_on_merge_hint` into the PR body as the advisory line (omit if empty).

`--draft` opens a **draft** PR. The PR is the **human gate** — `/work-issue` **NEVER auto-merges**, on any backend, in any mode. With `--start`, the run proceeds straight from worktree creation (Step 3) through Steps 4–6 inline without pausing for confirmation, mirroring `/resume-initiative --start`. Without `--start`, the run pauses at the end of Step 3 for the operator to confirm before Step 4.

## Conventions assumed

- **The issue body is an agent prompt.** Every issue this plugin files carries the agent-prompt shape (Goal, Locus, Skills to load, Constraints, Acceptance, Verify) per the `bug-tracking` / `feature-request` / `followup-tracking` skills. `/work-issue` uses that body as starting context; it does not re-derive the problem. A body too vague to drive a run is itself the finding — report it and stop rather than inventing scope.
- **`.claude/issue-tracker.yaml` selects the backend.** The same config `/resume-initiative` and `/tracker-doctor` read. `/work-issue` dispatches `view_issue` (and any `add_label` / `close_issue`) through `backends/<backend>.md`; it never calls a backend's raw CLI / MCP directly.
- **Worktree-first.** All work happens in an isolated worktree on a `feat/` | `fix/` | `docs/` branch — never on `main` in the primary working tree. This keeps the operator's primary checkout stable for any long-running processes while the run proceeds.

## Failure modes

- **Backend authentication or reachability failure** → the configured backend reports a reachability failure on the `view_issue` dispatch. Run `/tracker-doctor` to diagnose the setup; see `backends/<backend>.md` setup section, fix, and re-invoke.
- **`view_issue` returns not-found for the supplied ref** → check the ref syntax matches the configured backend (`#42` vs `owner/repo#42` vs `PROJ-123`). Report the hint and stop; do not guess a different ref.
- **Verification cannot pass** (tests fail, build breaks at Step 5) → do **NOT** open a non-draft PR. Report the failing command output and stop. (With `--draft`, a draft PR may be opened so the in-progress work is visible — a non-draft PR is never opened on red.)
- **A worktree for this issue already exists** → enter it (`.claude/worktrees/<branch-with-slash-replaced-by-plus>`) instead of creating a duplicate; report its path and continue.
- **The issue body is too vague to drive a run** (no locus, fuzzy acceptance, an unresolved open design question) → report that the body is unfileable-as-an-agent-prompt and stop. The fix is to enrich the issue (or file a `needs-design` issue first), not to invent scope. `/work-issue` escalating rigor for a *non-trivial-but-well-specified* issue is different from a *vague* one — the former gets the full pipeline, the latter gets reported back.
- **Cross-repo `owner/repo#N` ref** → the worktree is created in the consumer's current working directory regardless; only the `view_issue` body fetch hits the child's repo via the backend. The backend module documents how it handles cross-repo refs.
