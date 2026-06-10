---
description: PR-time doc-currency audit — list docs whose references may be stale vs the branch's diff. Informational; always exits 0.
---

# /audit-skills [--base <ref>]

Surface agent-readable docs that mention files changed in the current
branch's diff against a base ref, so the operator can update what's
actually stale before opening the PR. This is the enforcement helper for
the `skill-currency` skill: it codifies the *syntactic* subset of that
rule (identifier matching); the skill prose remains the source of truth
for the rule and its edge cases.

**Informational only.** Exit 0 always; the PR is never blocked, nothing
is auto-fixed. Findings need human judgement — a reference to a changed
file is a *candidate* staleness, not proof.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/audit-skills` | Diff the current branch against `origin/main`. |
| `/audit-skills --base <ref>` | Diff against `<ref>` instead. |

## What you should do

### Step 1 — Read the optional config

If `.claude/issue-tracker.yaml` exists and has a `skill_currency:` block,
translate it to CLI flags:

- each entry under `doc_globs:` → a `--doc-glob '<glob>'` flag
  (when present these REPLACE the detector's built-in defaults);
- each entry under `paired_rules:` → one `--paired-rule '<json>'` flag,
  where `<json>` is the rule object compacted to a single-line JSON
  string with keys `watch`, `pattern`, `expect`, `message`.

No config file or no block → pass no flags; the built-in dual-layout
defaults apply (consumer layout: `CLAUDE.md`, `AGENTS.md`,
`.claude/skills/*/SKILL.md`, `.claude/agents/*.md`,
`.claude/commands/*.md`; plugin-dev layout: `skills/*/SKILL.md`,
`commands/*.md`, `backends/*.md`, `templates/*.md`).

### Step 2 — Run the detector

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_skills.py" [--base <ref>] [flags from Step 1]
```

If `python3` is not on PATH, try `python`. If neither exists, use the
fallback procedure below.

### Step 3 — Present the output verbatim

Do not filter, dedupe, or summarise the findings. The operator decides
per finding whether the referencing doc is actually stale.

### Step 4 — Paired-rule reminder

If the report contains paired-rule findings, remind the operator of the
`skill-currency` rule: skills (and their analogues) are part of the
deliverable and update in the same PR as the API-surface change.

## Fallback — no Python on PATH

Run the same algorithm manually (degraded path — say so in your output):

1. `git diff --name-only <base>...HEAD` for the changed-file list.
2. For each changed file build up to three search needles: the full
   path, the basename, and the basename without extension — but ONLY
   include the extensionless stem when it is 3+ characters (shorter
   stems like `db` match spuriously inside unrelated words).
3. Grep each needle (fixed-string) across the doc corpus from Step 1
   (config globs, or the defaults).
4. Report per referencing doc: line number, changed file, matched form.
5. For each configured paired rule: check whether the diff adds a line
   matching `pattern` in the `watch` file; if yes and no changed file
   matches the `expect` glob, report the rule's `message`.

## What this does NOT do

- Block or auto-fix anything — the operator decides per finding.
- Scan git history — only the current diff vs base.
- Detect renamed-to references where the rename happened in a previous PR.
- Catch *semantic* drift (a convention change that never names a file) —
  that remains the `skill-currency` skill's human-judgement territory.
