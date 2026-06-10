---
name: skill-currency
description: >-
  How the methodology layer (`.claude/skills/*/SKILL.md`) stays current
  as the codebase evolves — codifies the rule that when a PR changes
  API surface (new module, new public function, new CLI subcommand,
  new env var, new DB table or schema-version bump, new HTTP route,
  changed function signature, removed function/file), the affected
  skills MUST update in the same PR. A stale skill misleads every
  future agent that loads it. Use this skill before opening a PR for
  any API-changing change; when an agent asks "is the skill stale?"
  or "what skills does this change?"; when filing an issue whose
  acceptance criteria depend on a skill update being shipped
  alongside the code; whenever you notice a skill referencing a
  function, file, table, or env var that no longer exists. Covers
  the rule itself, the eight API-surface change categories, the
  trivial-work escape hatch, the application checklist, issue
  acceptance criteria carry-through, the new-subsystem-gets-a-new-skill
  case, retroactive debt routing, manual verification, worked examples,
  and cross-skill ergonomics. Trigger phrases include "skill currency",
  "is the skill stale", "what skills does this change", "skills are
  part of the deliverable", "do I need to update the skills", and
  "documentation rot". Sibling skills bug-tracking, feature-request,
  and followup-tracking cover the issue shapes that this rule routes
  through.
---

# Skill Currency — Methodology as Deliverable

The `.claude/skills/*/SKILL.md` files are not documentation. They are
the deliverable. An agent reads a skill at the start of a task, and
that skill is the source of truth for how the codebase is organized,
what the invariants are, and what the operator contract looks like.
When a skill lies — because the codebase changed and the skill didn't
— an agent writes code based on false assumptions. A stale skill is
worse than no skill. It actively misleads every future agent that
loads it. Skills update in the same PR as the code change that made
them necessary, or they don't ship at all.

## The rule

> When a PR changes API surface — new module, new public function,
> new CLI subcommand, new env var, new DB table or schema-version
> bump, new HTTP route, changed function signature, removed
> function/file — the affected `SKILL.md` files MUST update in the
> same PR. A stale skill misleads every future agent that touches the
> area.

### Where the skills live

The same rule covers two layers, and which path you grep depends on
where your PR lands:

- **Developing this plugin** (or any project that authors its own
  skills) — the skills are at `skills/*/SKILL.md`, a sibling of
  `backends/`, `templates/`, and `commands/`. The worked example and
  acceptance snippets below use this path.
- **A consumer project that installed this plugin** — the skills are
  read from `.claude/skills/*/SKILL.md`.

Apply the rule to whichever layer your change touches; the discipline
is identical, only the directory differs.

## Why a stale skill is dangerous

- An agent loads the skill at the start of a task and reads about a
  function that no longer exists. The agent's first edit references
  the dead function, ships broken code, and the PR fails review with
  "this function was removed three months ago."
- An agent loads the skill, follows its convention for error handling,
  and discovers on review that the convention was retired last week. A
  full refactor is needed. The agent's run, the reviewer's time, and
  the context budget are all wasted.
- An agent reads a skill that names a database column by its old name,
  before the rename migration landed. The agent writes SQL against the
  renamed column. Tests pass because the migration hasn't dropped the
  old column yet. Production fails silently on first deploy.
- The compounding cost is paid by every agent downstream until someone
  notices the drift and fixes the skill. The cost accumulates across
  runs, silently — not isolated to the PR that introduced the drift.

## When the rule fires

- `New module` — a new top-level package or namespace.
- `New public function` — newly exported, importable, callable from
  outside the module.
- `New CLI subcommand` — a new verb under an existing CLI, or a
  standalone new CLI binary.
- `New env var` — a new key the code reads from `os.environ`,
  `process.env`, or equivalent.
- `New DB table or schema-version bump` — a new table, a new column
  on an existing table, or a version migration that changes the
  schema.
- `New HTTP route` — a new endpoint path and method on the public API
  surface.
- `Changed function signature` — parameters added/removed/reordered,
  return type changed, in any *exported* function.
- `Removed function or file` — deletion of any of the above — the
  absence itself is a change other agents must know about.

The list is **inclusive, not exclusive** — the rule fires on these
*and* on anything reasonably analogous (e.g., a new GraphQL mutation,
a new message-queue topic, a new event payload field). When in doubt,
treat it as in scope.

## When it does NOT fire — the escape hatch

Skill updates are NOT required for:

- Typos in source comments, error messages, or docstrings that don't
  change a skill-documented contract.
- Version bumps that don't change API surface (`requirements.txt`
  minor version bump, `package.json` patch bump, version-only changes).
- One-line patches with no API surface change — renaming an internal
  helper, a `// eslint-disable` comment, a config-only change that no
  skill documents.

The discriminator is the question: **"Would an agent in a future session need to know this changed?"** If yes → update the skill. If no → ship it. The escape hatch is narrow on purpose; the cost of a missed skill update is paid downstream.

## Application — before opening the PR

1. **Identify the affected skills.** For each file you changed, search
   the skill prose for references — function names, file paths, table
   names, env vars, CLI subcommand names. Any matching skill must be
   reviewed. Grep is your friend: `grep -r "function_name" skills/` when
   developing this plugin, or `.claude/skills/` in a consumer project that
   installed it.

2. **Decide: update existing skill, write new skill, or escape-hatch.**
   - The change touches a subsystem with an existing `*-architecture`
     or domain skill → update that skill.
   - The change introduces a brand-new subsystem with its own
     single-source-of-truth module → write a new skill (see next
     section).
   - The change is trivial per the escape hatch above → ship it.

3. **Fold the skill commit(s) into the same PR.** Not a follow-up. A
   reviewer should see the code diff and the skill diff side-by-side.
   The PR review is the gate where the skill update gets scrutinized;
   landing the skill in a separate PR loses that scrutiny.

## New subsystem gets a new skill

When a change introduces a brand-new subsystem — a new single-source-of-truth
Python module, a new major HTTP service, a new query builder, a new
state machine — write a new skill. The module is the *what* (the code);
the skill is the *why* (the invariants, the operator contract, the
gotchas that no one will re-derive). A skill for a new subsystem
mirrors the shape of the existing `*-architecture` skills: the problem
it solves, the design choices made, the invariants that hold, the
public surface (functions, routes, DB tables), and the common failure
modes seen in the wild. Without the skill, every future agent loads the
module cold, re-derives the invariants from the code, and most won't
bother — they'll invent patterns that conflict with existing code.

## Issue acceptance criteria carry-through

When filing an API-changing issue via `bug-tracking` or
`feature-request`, the issue's **Acceptance** section MUST list the
specific skills to create or update. This is a reviewer-visible gate,
not aspiration. A PR that lands the code change without the skill
commit fails the issue acceptance.

Example checklist items:

```
- [ ] `skills/<subsystem>/SKILL.md` updated with documentation of the new <thing>.
- [ ] `skills/<sibling>/SKILL.md` updated where it referenced the removed <thing>.
- [ ] (if new subsystem) A new skill file created at `skills/<new-subsystem>/SKILL.md`.
```

## Retroactive debt

When you discover the rule was missed in a prior shipped PR, file a
follow-up issue via `followup-tracking`. The follow-up's Parent block
points at the PR that missed the update; the What's already done block
names what landed; the deferred work is the skill update. Do NOT
silently fix the drift in the current PR's scope — that hides the cost
to downstream agents. Over time, the rate of retroactive-debt
follow-ups is the project's calibration signal for how well the
discipline is holding.

## Verification — run /audit-skills

The plugin ships an automated detector: the `/audit-skills` slash command
plus the stdlib-only `scripts/audit_skills.py` library. Run it from your
branch before opening a PR — it diffs against the base ref (default
`origin/main`) and lists docs whose references to changed files may have
gone stale, plus any paired-rule findings configured under
`skill_currency:` in `.claude/issue-tracker.yaml`.

The detector codifies a *subset* of this skill's discipline — the
syntactic identifier-matching part. It is informational only (exit 0
always; a PR is never blocked) and cannot catch semantic drift such as a
retired convention that never names a file. The skill itself remains the
source of truth for the rule and its edge cases; reviewers still check
skill currency on the way in. Indirect references — a renamed function
parameter type that propagates into a skill's code example — still need
the manual grep described above.

## Worked example

You add a new `--async` flag to an existing CLI binary `myproj-cli
build`. The flag changes the function signature of `build_project()`:
it now returns a job ID instead of a completion status. This is an
API-surface change — both the CLI interface and the exported function
signature changed.

**Affected skill:** `myproj-cli-architecture` (documents the CLI
structure, the build command, and the return-value contract).

**What lands in the same PR:**

1. Code changes: `cli/build.py` (new flag, updated function signature),
   tests updated, docs updated.
2. Skill changes: `skills/myproj-cli-architecture/SKILL.md` updated to:
   - Document the new `--async` flag and what it does.
   - Update the `build_project()` signature section to show the new
     return type (job ID vs completion status).
   - Add a note about when to use `--async` and how to poll the job.

A reviewer reading the skill update immediately understands the
contract change; a future agent loading the skill sees the current
state, not a half-true version.

## Cross-skill ergonomics

- **`feature-request`** — file when you need a new skill. The skill
  itself is a new capability for the methodology layer.
- **`bug-tracking`** — file when a skill is wrong, out of date, or
  actively misleading. A stale skill is a defect in the methodology
  layer.
- **`followup-tracking`** — file when scope deferred from this PR
  includes a skill update. The deferred work IS the skill update.

---

See also: `bug-tracking` (a stale skill is a defect), `feature-request`
(file new-skill requests), `followup-tracking` (deferred skill updates).
