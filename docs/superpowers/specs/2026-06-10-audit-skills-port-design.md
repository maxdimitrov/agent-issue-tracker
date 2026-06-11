# /audit-skills port — design

**Date:** 2026-06-10
**Issue:** [#2](https://github.com/maxdimitrov/agent-issue-tracker/issues/2) — feat(skill-currency): port /audit-skills slash command and detector library
**Branch:** `feat/audit-skills-port`
**Target release:** 1.4.0

## Problem

The `skill-currency` skill codifies the rule that skills MUST update in the
same PR as API-surface changes — but enforcement is honor-system. The
trading-bot project (the plugin's origin project) already runs a working
deterministic detector (`scripts/audit/` + a local `/audit-skills` command)
that scans a branch diff against base and flags docs whose references may
have gone stale. This design ports that detector into the plugin, stripped
of trading-bot-isms, so every consumer gets the enforcement helper.

## Decisions made (brainstorm 2026-06-10)

1. **Form factor:** stdlib-only Python shipped in the plugin, invoked by the
   slash command via `${CLAUDE_PLUGIN_ROOT}`, with a prose fallback when no
   Python is on PATH. Rationale: the acceptance criterion "frozen-diff
   fixtures port and pass" requires real testable code; the skills-detector
   subset of trading-bot's library has zero third-party deps (PyYAML belongs
   to the out-of-scope PII gate).
2. **Detector scope:** doc-currency detector ports as the core; the
   trading-bot-specific DB-canonical detector (added `CREATE TABLE` in
   `scripts/db.py` without a `*-architecture` skill change) generalizes into
   an optional config-driven **paired-rule** detector with zero default
   rules. Nothing trading-bot-specific remains in plugin code.
3. **Config model:** an optional `skill_currency:` block in
   `.claude/issue-tracker.yaml`. The slash command's prose has the **agent**
   read the YAML and translate it to CLI flags — the Python tool stays
   stdlib-only and config-format-agnostic.
4. **skill-currency prose:** the issue's "no changes to skill-currency
   prose" constraint is read as "don't weaken the rule". The skill's
   "Verification — manual today, automated later" section goes stale the
   moment this ships, so that one section updates in the same PR; the rule
   prose is untouched.

## 1. Detector library — `scripts/audit_skills.py`

One Python file (~400 lines), stdlib only, Python 3.10+. Internally layered
pure-core / IO-edge, mirroring the trading-bot original's split but in one
module so the plugin asset is drop-in invocable with no package/sys.path
mechanics.

### Diff parser (ported verbatim from trading-bot `scripts/audit/diff.py`)

- `ChangedFile(path, added_lines, status, rename_from)` frozen dataclass.
  `added_lines` = tuple of `(new_file_line_no, content)` for every `+` line.
- Pure `_parse(text)` core over `git diff --unified=0` output; tolerates
  context-bearing diffs; handles A/M/R/D statuses, rename detection, binary
  markers.
- IO edge `list_changed_files(base_ref)` shells out to
  `git diff --unified=0 --find-renames <base>...HEAD`.

### Doc-currency detector (ported from trading-bot `scripts/audit/skills.py`)

Behavior preserved exactly:

- Three match forms per changed file: full path, basename,
  basename-without-extension.
- The ≥3-char stem guard (trading-bot #144): a `<3`-char stem (`db`, `fx`)
  matches spuriously as a substring of unrelated words, so it is excluded
  from `basename_no_ext` matching. This is the **documented false-positive
  case** required by the issue's acceptance criteria.
- One finding per (doc, changed-file, form) — first matching line wins.
- `SkillFinding(referencing_doc, changed_file, matched_form, line_no)`.

**New default doc globs** (replacing trading-bot's): dual-layout so the same
defaults work in a consumer project and in a plugin-dev repo. Globs that
match nothing contribute nothing.

| Layer | Globs |
|---|---|
| Consumer project | `CLAUDE.md`, `AGENTS.md`, `.claude/skills/*/SKILL.md`, `.claude/agents/*.md`, `.claude/commands/*.md` |
| Plugin-dev repo | `skills/*/SKILL.md`, `commands/*.md`, `backends/*.md`, `templates/*.md` |

Trading-bot's `routines/*.md` is project-specific and moves to that
consumer's `skill_currency.doc_globs` config.

### Paired-rule detector (generalizes the DB-canonical detector)

A rule is `{watch, pattern, expect, message}`:

- `watch` — repo-relative path of the file to inspect (exact match against
  `ChangedFile.path`).
- `pattern` — regex applied to each **added line** of the watched file;
  capture group 1 (if present) names the matched entity.
- `expect` — glob; if **any** changed file in the diff matches it, the rule
  is suppressed entirely (same heuristic as trading-bot: assume the author
  handled the requirement; false-negative corner accepted to keep the noise
  floor low).
- `message` — finding text; `{1}` interpolates capture group 1.

`PairedRuleFinding(watch, line_no, entity, message)`. **Zero default
rules** — trading-bot's `CREATE TABLE` → `*-architecture` pairing becomes
the documented example config.

### CLI

```
python audit_skills.py [--base origin/main] [--json]
                       [--doc-glob GLOB]...        # replaces defaults when given
                       [--paired-rule JSON]...     # one rule per flag, JSON object
                       [--docs-root PATH]          # default "."
```

- Exit 0 always for findings/no-findings (informational discipline — PR
  never blocked). Exit 1 only on operational error (bad ref, git missing,
  malformed `--paired-rule` JSON) with the error on stderr.
- Markdown report ported from trading-bot's `format_skills_report`: header
  with base ref + changed-file count, findings grouped by referencing doc
  with line numbers and matched form, paired-rule section, action guidance
  footer. `--json` emits the structured payload instead.

## 2. Slash command — `commands/audit-skills.md`

Shape mirrors the existing plugin commands (frontmatter description,
invocation modes table, "What you should do" steps):

1. **Read config:** if `.claude/issue-tracker.yaml` has a `skill_currency:`
   block, translate `doc_globs` → repeated `--doc-glob` flags and each
   `paired_rules` entry → a `--paired-rule '<json>'` flag. No block → no
   flags (defaults apply).
2. **Invoke:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_skills.py"`
   (fall back to `python` if `python3` is absent), passing `--base <ref>`
   when the operator supplied one (default `origin/main`).
3. **Present the output verbatim.** Do not filter or summarise findings.
4. **Paired-rule reminder:** if paired-rule findings appear, remind the
   operator of the skill-currency rule ("skills are part of the
   deliverable").
5. **Prose fallback:** if no Python is on PATH, run the same algorithm
   manually — `git diff --name-only <base>...HEAD`, build the three match
   forms per changed file (applying the ≥3-char stem guard), Grep the doc
   corpus, report per doc. Clearly labeled as the degraded path; paired
   rules are evaluated by reading the config and checking the diff by hand.

Explicitly stated: informational only, never blocks, never auto-fixes; does
not scan git history (current diff vs base only); does not detect
renamed-to references from previous PRs.

Note: a consumer with its own project-level `/audit-skills` (trading-bot
today) shadows the plugin command; the plugin form stays reachable as
`/agent-issue-tracker:audit-skills`. Repointing trading-bot is a follow-up.

## 3. Config — `skill_currency:` block in `.claude/issue-tracker.yaml`

```yaml
# optional; both keys optional
skill_currency:
  doc_globs:        # REPLACES the dual-layout defaults when set
    - CLAUDE.md
    - .claude/skills/*/SKILL.md
    - routines/*.md
  paired_rules:     # default: none
    - watch: scripts/db.py
      pattern: 'CREATE\s+TABLE\s+(\w+)'
      expect: '.claude/skills/*-architecture/SKILL.md'
      message: 'new table `{1}` has no matching *-architecture skill in this diff'
```

Documented in `examples/issue-tracker.yaml.example` as a commented-out block
with the trading-bot pairing as the example. `/tracker-doctor` is untouched
(unknown top-level blocks are already tolerated); teaching doctor to
validate the block is a possible later enhancement, out of scope.

## 4. Tests + CI

New `tests/` directory (pytest; `conftest.py` puts `scripts/` on
`sys.path`):

- **Diff parser:** adapted from trading-bot `test_audit_diff.py` — header /
  hunk / rename / new / deleted / binary parsing, line-number accounting.
- **Doc-currency:** adapted from `test_audit_skills.py` — three match
  forms, line numbers, no-match case, default-globs coverage (both
  layouts), and the **short-stem false-positive pair** (`db.py` suppressed,
  `dca.py` kept) satisfying the documented-false-positive acceptance
  criterion.
- **Paired-rule:** new — rule fires on added matching line; suppressed when
  an `expect`-matching file changed; no-op when watch file absent from
  diff; `{1}` message interpolation; malformed-JSON rejection at the CLI.
- **Report:** adapted from `test_audit_report.py` — no-findings shape,
  grouped findings shape, exit-0 footer.
- **PR-139 frozen-diff replay, hermetic:** trading-bot's replay reads live
  skills at HEAD (its own docstring flags the fragility). The port freezes
  **both** the diff patch and a minimal corpus snapshot under
  `tests/fixtures/pr139/` (`diff.patch` + `corpus/.claude/skills/...` with
  the two skills' relevant lines), asserting `dashboard-maintenance` and
  `core-trail-architecture` are flagged. Same motivating-miss proof,
  no live-repo coupling.

CI: one new `python-tests` job in `.github/workflows/ci.yml`
(actions/setup-python 3.11, `pip install pytest`, `pytest`). Existing
markdown-lint / yaml-validate / backend-contract jobs untouched.

## 5. Packaging, docs, release

- `.claude-plugin/plugin.json`: version → `1.4.0`; description gains the
  fifth command (`/audit-skills`). Mirror any version/description field in
  `.claude-plugin/marketplace.json`.
- `CHANGELOG.md`: 1.4.0 entry.
- `README.md`: command table row + short usage section.
- `skills/skill-currency/SKILL.md`: **only** the "Verification — manual
  today, automated later" section is rewritten to describe the shipped
  helper (how to run `/audit-skills`, what it does and doesn't catch); the
  rule prose stays byte-identical.
- PR body: `Closes #2` (enhancement → `Closes` per `backends/github.md`).

## Out of scope (follow-ups filed at finish)

1. Trading-bot/quant-atelier consuming the plugin detector and retiring its
   local `scripts/audit/skills.py` + `/audit-skills` command → follow-up in
   the quant-atelier tracker.
2. `/audit-pii` port — personal-pattern-heavy, stays local to trading-bot.
3. `/tracker-doctor` validating the `skill_currency:` block.
4. markdownlint expansion into `commands/` (pre-existing v1.1 note in
   `ci.yml`, not this issue).

## Error handling summary

| Failure | Behavior |
|---|---|
| Bad `--base` ref / not a git repo | exit 1, git error on stderr |
| Malformed `--paired-rule` JSON | exit 1, parse error on stderr |
| Doc glob matches nothing | silently contributes zero findings |
| Unreadable doc file | skipped (OSError swallowed, same as origin) |
| No Python on consumer PATH | command's prose fallback path |
| Findings present | exit 0 — informational, never blocks |
