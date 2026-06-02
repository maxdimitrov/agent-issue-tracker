---
name: tracker-contribute
description: >-
  How to report a problem with the agent-issue-tracker plugin itself, or
  contribute a fix — file a well-formed issue or open a PR UPSTREAM against
  the plugin's own repo (maxdimitrov/agent-issue-tracker), NOT the consumer
  project's configured tracker. Use this skill the moment the plugin
  misbehaves or falls short while you are using it: a backend operation
  errors or returns wrong/missing data, a skill's instructions are stale /
  ambiguous / contradicted by what the tracker actually does,
  /resume-initiative or /tracker-doctor or /tracker-init misbehaves, the
  operation contract is missing a capability you needed (e.g. no way to
  enumerate an epic's existing children), a body-template field doesn't fit,
  or the docs are wrong. Also use when the user says "file a bug against the
  tracker", "report this to agent-issue-tracker", "open a PR upstream", "the
  tracker plugin is broken", or "contribute this back". This is the ONE skill
  that ignores .claude/issue-tracker.yaml — the upstream repo is always
  GitHub, reached via the gh CLI, regardless of the consumer's backend.
---

# Contributing to agent-issue-tracker (upstream)

This skill is for problems with **the plugin**, not problems in your own
project. When agent-issue-tracker itself misbehaves or falls short while
you are using it, this skill turns that friction into a well-formed issue —
or a PR if you already have a fix — filed against the plugin's own
repository, so the maintainer (and the next agent) can act on it.

## The one rule that's different here

**Target the upstream repo, not your configured tracker.** Every other skill
in this plugin dispatches through the backend in `.claude/issue-tracker.yaml`
(your Jira, your GitHub repo). This one does NOT. A bug in the plugin belongs
to the plugin's repo:

- **Upstream repo:** `maxdimitrov/agent-issue-tracker`. The `repository`
  field in the plugin's `.claude-plugin/plugin.json` is the authoritative
  source if you need to confirm it.
- **Backend:** always GitHub, always via the `gh` CLI — even when the
  consumer project is configured for Jira. Do not file plugin problems into
  the consumer's tracker; they will never reach the maintainer.

If `gh auth status` fails, tell the user to run `gh auth login` once — there
is no plugin-managed credential.

## When to use

Reach for this skill the moment the plugin gets in your way:

- A backend operation errors, returns wrong/missing data, or behaves
  differently from `backends/_interface.md`.
- A skill's instructions are stale, ambiguous, or contradicted by what the
  tracker actually does (e.g. a step that assumes a capability that is not
  there).
- The operation contract is missing something you needed — the motivating
  example: no way to enumerate an epic's existing children, so an adoption
  step trusted stale body prose instead.
- `/resume-initiative`, `/tracker-doctor`, or `/tracker-init` misbehaves.
- A body-template field does not fit a real case, or the docs are wrong.
- The user explicitly asks to report a problem or contribute a fix upstream.

Do **not** use this skill for problems in the consumer's own project — those
go through the normal `bug-tracking` / `feature-request` /
`followup-tracking` skills against the configured backend.

## Decide: issue or PR

- **No fix in hand → file an issue.** The default. Capture the problem as a
  structured agent prompt (below) so the maintainer or an issue-fix agent
  can pick it up cold.
- **Fix in hand → open a PR.** If you already changed the plugin (e.g. added
  a missing operation), open a PR against `main` and reference the issue if
  one exists.

## Filing an issue

Use the plugin's own agent-prompt body shape — the same one `CONTRIBUTING.md`
documents and the plugin's skills ship. A vague body wastes a maintainer or
agent round-trip; a structured one gets a draft PR back.

Body shape (match `CONTRIBUTING.md`'s "Issue body shape"):

- **Goal** — one sentence; the observable outcome once fixed.
- **Locus** — the plugin files/areas involved: path + section/op name, e.g.
  `backends/_interface.md` (`list_child_issues`),
  `skills/initiative-tracking/SKILL.md`, `commands/resume-initiative.md`.
- **Skills to load** — which plugin skill(s) + which superpowers skills an
  agent should read first.
- **What's missing** (enhancement) OR **Symptom + Repro + Impact** (bug) —
  what the plugin does not do, or what went wrong with the exact sequence
  that triggered it.
- **Why** — the workflow it blocks.
- **Sketch** (enhancement) or **Root-cause hypothesis** (bug, optional) — the
  shape of the fix. If there is an open design question, say so and tag
  `needs-design`.
- **Constraints** — out of scope; invariants to preserve (e.g. "op-parity CI
  stays green", "no version bump — release is a separate commit"); style.
- **Acceptance** — writable as a check/test (e.g. "the CI `backend-contract`
  grep finds the new op heading in both backends").
- **Verify** — exact commands to prove the fix.
- **Notes** — related issues/PRs, links.

Capture the **session context that produced the problem** — what you were
doing when the plugin fell short — into Symptom/Repro. That context is the
whole reason filing now beats filing later: it will not survive the session.

File it with `gh` against the upstream repo:

```bash
gh issue create \
  --repo maxdimitrov/agent-issue-tracker \
  --title "<type>(<area>): <one-line>" \
  --body-file <path-to-body.md> \
  --label "<bug|enhancement>"
```

- **Title:** match the repo's commit/issue style — e.g.
  `feat(initiative-tracking): …`, `fix(backends): …`, `docs(readme): …`.
- **Label:** `bug` for a defect, `enhancement` for a missing capability; add
  `needs-design` if there is an open design question. Do not invent labels
  that do not exist on the repo.
- **Confirm before creating** — it is an outward action on a public repo.
  Show the drafted title + body first.

## Opening a PR (when you have the fix)

If a fix is already in hand, follow the repo's conventions:

1. Branch off `main`: `git checkout -b <username>/<short-slug>`.
2. Respect the **skill-currency** rule — if the change touches API surface (a
   contract op, a command, a template field), update the affected skills and
   the op-count references in the **same** PR.
3. If you added or removed a contract operation, the CI `backend-contract`
   op-parity job requires a matching `### <op>` operation heading in **both**
   `backends/github.md` and `backends/jira.md`. Run the op-parity grep
   locally before pushing.
4. Add a `## [Unreleased]` entry to `CHANGELOG.md`. Do **not** bump the
   version — releases are a separate `chore(release)` commit (see
   `CONTRIBUTING.md` "Release process").
5. `markdownlint-cli2` runs in CI on `README.md`, `CONTRIBUTING.md`,
   `CHANGELOG.md`, and `examples/**` — keep those clean.
6. Open the PR against `main` with a Summary / Motivation / Changes / Test
   plan body. **Confirm before pushing + opening.**

## Why route plugin problems upstream

A plugin bug noted only in your session — or filed into your project's own
tracker — is invisible to the maintainer and to every other team using the
plugin. Routed to `maxdimitrov/agent-issue-tracker` as a structured issue or
PR, it becomes fixable once, for everyone. This is the plugin dogfooding its
own thesis: an issue worth tracking is worth filing in a shape an agent can
pick up cold.
