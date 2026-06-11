# /audit-skills Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `skill-currency` enforcement helper in the plugin: a stdlib-only Python detector (`scripts/audit_skills.py`) + `/audit-skills` slash command that scans a branch diff and flags docs whose references may have gone stale.

**Architecture:** One stdlib-only Python module (pure cores: diff parser, doc-currency detector, paired-rule detector, report formatter; thin I/O edge: git subprocess + argparse CLI), invoked by the slash command via `${CLAUDE_PLUGIN_ROOT}` with a prose fallback. Per-consumer config rides an optional `skill_currency:` block in `.claude/issue-tracker.yaml`, translated to CLI flags by the agent so Python stays YAML-free.

**Tech Stack:** Python 3.10+ stdlib only, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-06-10-audit-skills-port-design.md` (read it first).

**Work from:** `F:/Claude/Projects/agent-issue-tracker/.claude/worktrees/feat+audit-skills-port` on branch `feat/audit-skills-port`. Every task starts with `cd` to that path and `git status` to confirm the branch.

**Port source (read-only reference):** the trading-bot checkout at `F:/Claude/Projects/Trading` — `scripts/audit/{diff,skills,report,cli}.py` and `tests/fixtures/audit/pr_139_diff.patch`. Never modify that repo.

---

### Task 1: Test scaffolding + diff parser

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_diff_parser.py`
- Create: `scripts/audit_skills.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add Python artifacts to .gitignore**

Append to `.gitignore` (it currently has only the worktrees entry):

```
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 2: Write conftest.py**

```python
"""Put scripts/ on sys.path so tests import audit_skills directly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
```

- [ ] **Step 3: Write the failing diff-parser tests**

`tests/test_diff_parser.py` — adapted from trading-bot `tests/test_audit_diff.py`, importing from the single module:

```python
"""Unit tests for the pure diff parser (_parse) -- hermetic, fixed strings.

The I/O wrapper (list_changed_files) is exercised in test_cli.py.
"""
from audit_skills import _parse, ChangedFile


def test_parses_single_modified_file_with_added_lines():
    text = """\
diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -10,0 +11,2 @@ def existing():
+    print("new line 1")
+    print("new line 2")
"""
    out = _parse(text)
    assert len(out) == 1
    cf = out[0]
    assert cf.path == "foo.py"
    assert cf.status == "M"
    assert cf.added_lines == (
        (11, '    print("new line 1")'),
        (12, '    print("new line 2")'),
    )
    assert cf.rename_from is None


def test_parses_multiple_files():
    text = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -0,0 +1,1 @@
+print("a")
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -5,0 +6,1 @@
+print("b")
"""
    out = _parse(text)
    assert {cf.path for cf in out} == {"a.py", "b.py"}


def test_parses_new_file_status_A():
    text = """\
diff --git a/new.py b/new.py
new file mode 100644
index 0000000..abc
--- /dev/null
+++ b/new.py
@@ -0,0 +1,1 @@
+print("hello")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "A"
    assert out[0].path == "new.py"


def test_parses_deleted_file_status_D():
    text = """\
diff --git a/gone.py b/gone.py
deleted file mode 100644
index abc..0000000
--- a/gone.py
+++ /dev/null
@@ -1,1 +0,0 @@
-print("removed")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "D"
    assert out[0].path == "gone.py"
    assert out[0].added_lines == ()


def test_parses_rename_status_R():
    text = """\
diff --git a/old.py b/new.py
similarity index 90%
rename from old.py
rename to new.py
index abc..def 100644
--- a/old.py
+++ b/new.py
@@ -1,1 +1,1 @@
-print("old")
+print("new")
"""
    out = _parse(text)
    assert len(out) == 1
    assert out[0].status == "R"
    assert out[0].path == "new.py"
    assert out[0].rename_from == "old.py"


def test_skips_binary_file_diff():
    text = """\
diff --git a/img.png b/img.png
index abc..def 100644
Binary files a/img.png and b/img.png differ
"""
    out = _parse(text)
    # Binary diffs have no parseable hunks; emit a ChangedFile with empty
    # added_lines so the path is still visible to doc-currency scanning.
    assert len(out) == 1
    assert out[0].path == "img.png"
    assert out[0].added_lines == ()


def test_empty_diff_returns_empty_tuple():
    assert _parse("") == ()


def test_hunk_header_offset_tracks_added_line_numbers():
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -100,0 +101,3 @@
+a
+b
+c
"""
    out = _parse(text)
    assert out[0].added_lines == ((101, "a"), (102, "b"), (103, "c"))


def test_multiple_hunks_in_one_file():
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -10,0 +11,1 @@
+first
@@ -50,0 +52,1 @@
+second
"""
    out = _parse(text)
    assert out[0].added_lines == ((11, "first"), (52, "second"))


def test_added_line_starting_with_plus_is_preserved():
    """'+++ b/path' is a header; '++ literal' after a hunk is content."""
    text = """\
diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -0,0 +1,1 @@
+++ comment with double plus
"""
    out = _parse(text)
    assert out[0].added_lines == ((1, "++ comment with double plus"),)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_diff_parser.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'audit_skills'`

- [ ] **Step 5: Write the module skeleton with the diff parser**

Create `scripts/audit_skills.py` (the diff-parser portion is a verbatim port of trading-bot `scripts/audit/diff.py`; later tasks append to this file):

```python
"""Doc-currency + paired-rule audit for agent-readable docs.

Stdlib-only (Python 3.10+). Shipped as a plugin asset; the /audit-skills
slash command invokes it as:

    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_skills.py" [flags]

Internal layering mirrors the origin implementation (trading-bot
scripts/audit/): pure cores (_parse, doc_currency_findings,
paired_rule_findings, format_report) and a thin I/O edge
(list_changed_files, main).

Exit codes:
  0 -- informational success (findings or no findings; always)
  1 -- operational error (bad ref, git missing, malformed rule JSON)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Sequence


# --- diff parsing -----------------------------------------------------------

@dataclass(frozen=True)
class ChangedFile:
    """One file in a diff.

    `added_lines` is the sequence of (line_no_in_new_file, content) for every
    `+` line. `status` is git's letter: A added, M modified, R renamed,
    D deleted. `rename_from` is set only for status='R'.
    """
    path: str
    added_lines: tuple[tuple[int, str], ...]
    status: str
    rename_from: str | None


_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_NEW_FILE = re.compile(r"^new file mode ")
_DELETED_FILE = re.compile(r"^deleted file mode ")
_RENAME_FROM = re.compile(r"^rename from (.+)$")
_RENAME_TO = re.compile(r"^rename to (.+)$")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_BINARY_MARKER = re.compile(r"^Binary files ")


def _parse(text: str) -> tuple[ChangedFile, ...]:
    """Parse a unified diff into ChangedFile records.

    Expects `git diff --unified=0` output (no context lines), but tolerates
    context-bearing diffs by counting only '+' lines.
    """
    if not text.strip():
        return ()

    files: list[ChangedFile] = []
    cur_path: str | None = None
    cur_status: str = "M"
    cur_rename_from: str | None = None
    cur_added: list[tuple[int, str]] = []
    cur_line_no: int | None = None

    def _flush() -> None:
        if cur_path is not None:
            files.append(ChangedFile(
                path=cur_path,
                added_lines=tuple(cur_added),
                status=cur_status,
                rename_from=cur_rename_from,
            ))

    for raw in text.splitlines():
        m = _DIFF_HEADER.match(raw)
        if m:
            _flush()
            cur_path = m.group(2)   # `b/` path is the post-change name
            cur_status = "M"
            cur_rename_from = None
            cur_added = []
            cur_line_no = None
            continue
        if cur_path is None:
            continue
        if _NEW_FILE.match(raw):
            cur_status = "A"
            continue
        if _DELETED_FILE.match(raw):
            cur_status = "D"
            continue
        rm = _RENAME_FROM.match(raw)
        if rm:
            cur_status = "R"
            cur_rename_from = rm.group(1)
            continue
        if _RENAME_TO.match(raw):
            continue   # path already captured from `b/<path>` in the header
        if _BINARY_MARKER.match(raw):
            continue
        hm = _HUNK_HEADER.match(raw)
        if hm:
            cur_line_no = int(hm.group(1))
            continue
        if cur_line_no is None:
            continue   # metadata lines (index, ---, +++) before first hunk
        if raw.startswith("+"):
            cur_added.append((cur_line_no, raw[1:]))
            cur_line_no += 1
        # '-' lines don't bump the +new-side counter in --unified=0 output.

    _flush()
    return tuple(files)


def list_changed_files(base_ref: str = "origin/main") -> tuple[ChangedFile, ...]:
    """Run `git diff <base_ref>...HEAD` and parse the output.

    `--unified=0` minimises context so line numbers are unambiguous;
    `--find-renames` enables status R. Raises CalledProcessError on git
    failure (bad ref, not a repo) and FileNotFoundError if git is absent.
    """
    proc = subprocess.run(
        ["git", "diff", "--unified=0", "--find-renames", f"{base_ref}...HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return _parse(proc.stdout)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_diff_parser.py -q`
Expected: `10 passed`

- [ ] **Step 7: Commit**

```bash
git add .gitignore tests/conftest.py tests/test_diff_parser.py scripts/audit_skills.py
git commit -m "feat: diff parser core for /audit-skills detector (#2)"
```

---

### Task 2: Doc-currency detector

**Files:**
- Create: `tests/test_doc_currency.py`
- Modify: `scripts/audit_skills.py` (append after `list_changed_files`)

- [ ] **Step 1: Write the failing tests**

`tests/test_doc_currency.py`:

```python
"""Doc-currency detector tests, incl. the documented false-positive guard."""
from pathlib import Path

from audit_skills import ChangedFile, doc_currency_findings


def _write(p: Path, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _cf(path: str) -> ChangedFile:
    return ChangedFile(path=path, added_lines=(), status="M", rename_from=None)


def test_path_match_three_forms(tmp_path):
    """Each changed file matches in three forms: full path, basename,
    basename-without-extension."""
    _write(tmp_path / ".claude/skills/foo/SKILL.md",
           "Line 1\nsee scripts/foo.py here\n"      # path
           "and bar.py too\n"                        # basename
           "and baz module elsewhere\n")             # basename_no_ext
    diff = (_cf("scripts/foo.py"), _cf("lib/bar.py"), _cf("lib/baz.py"))
    findings = doc_currency_findings(diff, docs_root=str(tmp_path),
                                     doc_globs=(".claude/skills/*/SKILL.md",))
    forms = {(f.changed_file, f.matched_form) for f in findings}
    assert ("scripts/foo.py", "path") in forms
    assert ("lib/bar.py", "basename") in forms
    assert ("lib/baz.py", "basename_no_ext") in forms


def test_path_match_records_line_number(tmp_path):
    _write(tmp_path / ".claude/skills/foo/SKILL.md",
           "Header\n\nsee scripts/foo.py here\n")
    findings = doc_currency_findings((_cf("scripts/foo.py"),),
                                     docs_root=str(tmp_path),
                                     doc_globs=(".claude/skills/*/SKILL.md",))
    assert any(f.line_no == 3 for f in findings)


def test_no_match_when_unrelated(tmp_path):
    _write(tmp_path / ".claude/skills/foo/SKILL.md", "Nothing relevant here.\n")
    assert doc_currency_findings((_cf("scripts/foo.py"),),
                                 docs_root=str(tmp_path),
                                 doc_globs=(".claude/skills/*/SKILL.md",)) == ()


def test_default_globs_cover_consumer_layout(tmp_path):
    _write(tmp_path / "CLAUDE.md", "see scripts/x.py\n")
    _write(tmp_path / "AGENTS.md", "see scripts/x.py\n")
    _write(tmp_path / ".claude/skills/foo/SKILL.md", "see scripts/x.py\n")
    _write(tmp_path / ".claude/agents/foo.md", "see scripts/x.py\n")
    _write(tmp_path / ".claude/commands/bar.md", "see scripts/x.py\n")
    findings = doc_currency_findings((_cf("scripts/x.py"),),
                                     docs_root=str(tmp_path))
    docs = {f.referencing_doc for f in findings}
    assert "CLAUDE.md" in docs
    assert "AGENTS.md" in docs
    assert ".claude/skills/foo/SKILL.md" in docs
    assert ".claude/agents/foo.md" in docs
    assert ".claude/commands/bar.md" in docs


def test_default_globs_cover_plugin_dev_layout(tmp_path):
    _write(tmp_path / "skills/foo/SKILL.md", "see scripts/x.py\n")
    _write(tmp_path / "commands/bar.md", "see scripts/x.py\n")
    _write(tmp_path / "backends/github.md", "see scripts/x.py\n")
    _write(tmp_path / "templates/bug-body.md", "see scripts/x.py\n")
    findings = doc_currency_findings((_cf("scripts/x.py"),),
                                     docs_root=str(tmp_path))
    docs = {f.referencing_doc for f in findings}
    assert "skills/foo/SKILL.md" in docs
    assert "commands/bar.md" in docs
    assert "backends/github.md" in docs
    assert "templates/bug-body.md" in docs


def test_basename_no_ext_skips_short_stems(tmp_path):
    """THE documented false-positive case (trading-bot #144): a <3-char stem
    (e.g. db.py -> 'db') would fire on any line mentioning 'dashboard.db',
    'db_py', etc., so it is excluded from basename_no_ext matching."""
    _write(tmp_path / ".claude/skills/foo/SKILL.md",
           "the canonical store is data/dashboard.db\n")
    findings = doc_currency_findings((_cf("scripts/db.py"),),
                                     docs_root=str(tmp_path),
                                     doc_globs=(".claude/skills/*/SKILL.md",))
    assert not any(f.matched_form == "basename_no_ext" for f in findings)


def test_basename_no_ext_keeps_three_char_stems(tmp_path):
    """The guard boundary: a 3-char stem still matches."""
    _write(tmp_path / ".claude/skills/foo/SKILL.md",
           "the dca router lives here\n")
    findings = doc_currency_findings((_cf("scripts/dca.py"),),
                                     docs_root=str(tmp_path),
                                     doc_globs=(".claude/skills/*/SKILL.md",))
    assert any(f.matched_form == "basename_no_ext" for f in findings)


def test_empty_diff_short_circuits(tmp_path):
    assert doc_currency_findings((), docs_root=str(tmp_path)) == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_doc_currency.py -q`
Expected: FAIL — `ImportError: cannot import name 'doc_currency_findings'`

- [ ] **Step 3: Append the detector to scripts/audit_skills.py**

Port of trading-bot `scripts/audit/skills.py::doc_currency_findings` with the new dual-layout defaults:

```python
# --- doc-currency detector ---------------------------------------------------

_DEFAULT_DOC_GLOBS = (
    # consumer-project layout
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/skills/*/SKILL.md",
    ".claude/agents/*.md",
    ".claude/commands/*.md",
    # plugin-dev repo layout (this repo's own shape)
    "skills/*/SKILL.md",
    "commands/*.md",
    "backends/*.md",
    "templates/*.md",
)


@dataclass(frozen=True)
class SkillFinding:
    referencing_doc: str   # repo-relative, forward-slash
    changed_file: str      # the file in the diff whose ref may be stale
    matched_form: str      # "path" | "basename" | "basename_no_ext"
    line_no: int


def doc_currency_findings(
    diff: tuple[ChangedFile, ...],
    docs_root: str = ".",
    doc_globs: tuple[str, ...] = _DEFAULT_DOC_GLOBS,
) -> tuple[SkillFinding, ...]:
    """For each changed file, scan every doc in `doc_globs` (under
    `docs_root`) for substring matches of the file's path, basename, and
    basename-without-extension. One finding per (doc, file, form).
    """
    if not diff:
        return ()

    search_forms: list[tuple[ChangedFile, list[tuple[str, str]]]] = []
    for cf in diff:
        forms: list[tuple[str, str]] = [(cf.path, "path")]
        base = os.path.basename(cf.path)
        if base and base != cf.path:
            forms.append((base, "basename"))
        stem, ext = os.path.splitext(base)
        # Length guard: a <3-char stem (db, fx) matches spuriously as a
        # substring of unrelated words; require >= 3 chars.
        if stem and ext and stem != base and len(stem) >= 3:
            forms.append((stem, "basename_no_ext"))
        search_forms.append((cf, forms))

    out: list[SkillFinding] = []
    root = Path(docs_root)
    for pattern in doc_globs:
        for doc_path in sorted(root.glob(pattern)):
            try:
                body = doc_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lines = body.splitlines()
            for cf, forms in search_forms:
                for needle, form in forms:
                    for line_no, line in enumerate(lines, start=1):
                        if needle in line:
                            rel = str(doc_path.relative_to(root)).replace("\\", "/")
                            out.append(SkillFinding(
                                referencing_doc=rel,
                                changed_file=cf.path,
                                matched_form=form,
                                line_no=line_no,
                            ))
                            break    # one match per (doc, file, form)
    return tuple(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_doc_currency.py tests/test_diff_parser.py -q`
Expected: `18 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_doc_currency.py scripts/audit_skills.py
git commit -m "feat: doc-currency detector with dual-layout default globs (#2)"
```

---

### Task 3: Paired-rule detector

**Files:**
- Create: `tests/test_paired_rules.py`
- Modify: `scripts/audit_skills.py` (append after `doc_currency_findings`)

- [ ] **Step 1: Write the failing tests**

`tests/test_paired_rules.py`:

```python
"""Paired-rule detector: the config-driven generalization of trading-bot's
DB-canonical subsystem detector. Zero default rules ship."""
import pytest

from audit_skills import (
    ChangedFile, PairedRule, PairedRuleFinding,
    paired_rule_findings, parse_rule,
)

DB_RULE = PairedRule(
    watch="scripts/db.py",
    pattern=r"CREATE\s+TABLE\s+(\w+)",
    expect=".claude/skills/*-architecture/SKILL.md",
    message="new table `{1}` has no matching *-architecture skill in this diff",
)


def _cf(path, added=()):
    return ChangedFile(path=path, added_lines=tuple(added),
                       status="M", rename_from=None)


def test_rule_fires_on_matching_added_line():
    diff = (_cf("scripts/db.py",
                [(100, "CREATE TABLE foo_bar (id INTEGER PRIMARY KEY)")]),)
    findings = paired_rule_findings(diff, (DB_RULE,))
    assert len(findings) == 1
    f = findings[0]
    assert f.watch == "scripts/db.py"
    assert f.line_no == 100
    assert f.entity == "foo_bar"
    assert "`foo_bar`" in f.message


def test_rule_fires_once_per_matching_line():
    diff = (_cf("scripts/db.py",
                [(10, "CREATE TABLE one (x)"), (20, "CREATE TABLE two (y)")]),)
    findings = paired_rule_findings(diff, (DB_RULE,))
    assert [f.entity for f in findings] == ["one", "two"]


def test_rule_suppressed_when_expect_glob_matches_a_changed_file():
    diff = (
        _cf("scripts/db.py", [(100, "CREATE TABLE foo_bar (id INTEGER)")]),
        _cf(".claude/skills/foo-bar-architecture/SKILL.md", [(1, "---")]),
    )
    assert paired_rule_findings(diff, (DB_RULE,)) == ()


def test_rule_noop_when_watch_file_not_in_diff():
    diff = (_cf("scripts/other.py"),)
    assert paired_rule_findings(diff, (DB_RULE,)) == ()


def test_rule_matches_case_insensitively_when_pattern_says_so():
    rule = PairedRule(watch="scripts/db.py",
                      pattern=r"(?i)create\s+table\s+(\w+)",
                      expect="docs/*.md", message="table `{1}`")
    diff = (_cf("scripts/db.py", [(50, "create table widget (x INTEGER)")]),)
    findings = paired_rule_findings(diff, (rule,))
    assert findings[0].entity == "widget"


def test_pattern_without_capture_group_gives_entity_none():
    rule = PairedRule(watch="api/routes.py", pattern=r"@app\.route",
                      expect="docs/api.md", message="new route, update docs/api.md")
    diff = (_cf("api/routes.py", [(7, '@app.route("/x")')]),)
    findings = paired_rule_findings(diff, (rule,))
    assert findings[0].entity is None
    assert findings[0].message == "new route, update docs/api.md"


def test_parse_rule_roundtrip():
    raw = ('{"watch": "scripts/db.py", "pattern": "CREATE\\\\s+TABLE\\\\s+(\\\\w+)", '
           '"expect": ".claude/skills/*-architecture/SKILL.md", "message": "table `{1}`"}')
    rule = parse_rule(raw)
    assert rule.watch == "scripts/db.py"
    assert rule.expect == ".claude/skills/*-architecture/SKILL.md"


def test_parse_rule_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_rule("{nope")


def test_parse_rule_rejects_missing_keys():
    with pytest.raises(ValueError, match="missing keys"):
        parse_rule('{"watch": "x"}')


def test_parse_rule_rejects_invalid_regex():
    with pytest.raises(ValueError, match="invalid regex"):
        parse_rule('{"watch": "x", "pattern": "(", "expect": "y", "message": "z"}')


def test_parse_rule_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_rule('["not", "an", "object"]')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_paired_rules.py -q`
Expected: FAIL — `ImportError: cannot import name 'PairedRule'`

- [ ] **Step 3: Append the detector to scripts/audit_skills.py**

```python
# --- paired-rule detector ------------------------------------------------------
# Generalization of trading-bot's DB-canonical subsystem detector (added
# CREATE TABLE in scripts/db.py without a *-architecture skill change).
# ZERO default rules ship; consumers configure rules via the
# skill_currency.paired_rules block in .claude/issue-tracker.yaml, which the
# slash command passes here as --paired-rule JSON flags.

@dataclass(frozen=True)
class PairedRule:
    watch: str     # exact repo-relative path to inspect
    pattern: str   # regex over added lines; group 1 (optional) = entity name
    expect: str    # fnmatch glob; any changed file matching it suppresses the rule
    message: str   # finding text; "{1}" interpolates group 1


@dataclass(frozen=True)
class PairedRuleFinding:
    watch: str
    line_no: int
    entity: str | None
    message: str


def parse_rule(raw: str) -> PairedRule:
    """Parse one --paired-rule JSON object. Raises ValueError on any shape
    or regex problem so the CLI can exit 1 with a clear message."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"--paired-rule is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("--paired-rule must be a JSON object")
    missing = [k for k in ("watch", "pattern", "expect", "message")
               if k not in data]
    if missing:
        raise ValueError(f"--paired-rule missing keys: {', '.join(missing)}")
    try:
        re.compile(str(data["pattern"]))
    except re.error as e:
        raise ValueError(f"--paired-rule has invalid regex: {e}") from e
    return PairedRule(
        watch=str(data["watch"]),
        pattern=str(data["pattern"]),
        expect=str(data["expect"]),
        message=str(data["message"]),
    )


def paired_rule_findings(
    diff: tuple[ChangedFile, ...],
    rules: tuple[PairedRule, ...],
) -> tuple[PairedRuleFinding, ...]:
    """Apply each rule: if the watched file has added lines matching the
    pattern AND no changed file matches the expect glob, emit one finding
    per matching line.

    Suppression heuristic (inherited from the origin detector): ANY
    expect-matching change suppresses the whole rule -- assume the author
    handled the requirement. Accepts a false-negative corner to keep the
    noise floor low.
    """
    out: list[PairedRuleFinding] = []
    for rule in rules:
        watched = next((cf for cf in diff if cf.path == rule.watch), None)
        if watched is None:
            continue
        rx = re.compile(rule.pattern)
        hits: list[tuple[int, str | None]] = []
        for line_no, content in watched.added_lines:
            m = rx.search(content)
            if m:
                entity = m.group(1) if rx.groups else None
                hits.append((line_no, entity))
        if not hits:
            continue
        if any(fnmatch.fnmatch(cf.path.replace("\\", "/"), rule.expect)
               for cf in diff):
            continue
        for line_no, entity in hits:
            msg = (rule.message.replace("{1}", entity)
                   if entity is not None else rule.message)
            out.append(PairedRuleFinding(
                watch=rule.watch, line_no=line_no,
                entity=entity, message=msg,
            ))
    return tuple(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -q`
Expected: `29 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_paired_rules.py scripts/audit_skills.py
git commit -m "feat: config-driven paired-rule detector (#2)"
```

---

### Task 4: Report formatter

**Files:**
- Create: `tests/test_report.py`
- Modify: `scripts/audit_skills.py` (append after `paired_rule_findings`)

- [ ] **Step 1: Write the failing tests**

`tests/test_report.py`:

```python
"""Markdown report formatter tests."""
from audit_skills import (
    DiffSummary, SkillFinding, PairedRuleFinding, format_report,
)

SUMMARY = DiffSummary(base_ref="origin/main", changed=3)


def test_no_findings_report():
    text = format_report((), (), SUMMARY, rules_configured=False)
    assert "[audit-skills] Doc-currency scan vs origin/main (3 changed files)" in text
    assert "No findings" in text
    assert "Exit 0 (informational; PR not blocked)." in text


def test_singular_file_word():
    text = format_report((), (), DiffSummary(base_ref="main", changed=1),
                         rules_configured=False)
    assert "(1 changed file)" in text


def test_doc_findings_grouped_by_referencing_doc():
    doc = (
        SkillFinding(referencing_doc="skills/b/SKILL.md",
                     changed_file="scripts/x.py", matched_form="path", line_no=9),
        SkillFinding(referencing_doc="skills/a/SKILL.md",
                     changed_file="scripts/x.py", matched_form="basename", line_no=4),
        SkillFinding(referencing_doc="skills/a/SKILL.md",
                     changed_file="lib/y.py", matched_form="path", line_no=12),
    )
    text = format_report(doc, (), SUMMARY, rules_configured=False)
    a_pos = text.index("skills/a/SKILL.md:")
    b_pos = text.index("skills/b/SKILL.md:")
    assert a_pos < b_pos                      # sorted by doc
    assert "L4" in text and "L9" in text and "L12" in text
    assert "(basename)" in text and "(path)" in text


def test_paired_section_shown_when_rules_configured():
    text = format_report((), (), SUMMARY, rules_configured=True)
    assert "Paired rules:" in text
    assert "(no paired-rule findings)" in text


def test_paired_section_hidden_when_no_rules_configured():
    text = format_report((), (), SUMMARY, rules_configured=False)
    assert "Paired rules:" not in text


def test_paired_findings_listed():
    paired = (PairedRuleFinding(watch="scripts/db.py", line_no=100,
                                entity="foo_bar",
                                message="new table `foo_bar` has no skill"),)
    text = format_report((), paired, SUMMARY, rules_configured=True)
    assert "scripts/db.py L100: new table `foo_bar` has no skill" in text
    assert "Exit 0 (informational; PR not blocked)." in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_report.py -q`
Expected: FAIL — `ImportError: cannot import name 'DiffSummary'`

- [ ] **Step 3: Append the formatter to scripts/audit_skills.py**

```python
# --- report -------------------------------------------------------------------

@dataclass(frozen=True)
class DiffSummary:
    base_ref: str
    changed: int


def format_report(
    doc: tuple[SkillFinding, ...],
    paired: tuple[PairedRuleFinding, ...],
    summary: DiffSummary,
    rules_configured: bool,
) -> str:
    """Operator-readable markdown report. The paired-rule section only
    renders when rules were configured, so rule-less consumers see no
    dangling empty section."""
    lines: list[str] = []
    file_word = "file" if summary.changed == 1 else "files"
    lines.append(f"[audit-skills] Doc-currency scan vs {summary.base_ref} "
                 f"({summary.changed} changed {file_word})")
    lines.append("")

    if not doc and not paired:
        lines.append("No findings -- doc corpus appears clean against this diff.")
        lines.append("")
        if rules_configured:
            lines.append("Paired rules:")
            lines.append("  (no paired-rule findings)")
            lines.append("")
        lines.append("Exit 0 (informational; PR not blocked).")
        return "\n".join(lines) + "\n"

    if doc:
        lines.append("References to changed files:")
        lines.append("")
        sorted_doc = sorted(doc, key=lambda f: (f.referencing_doc, f.line_no))
        for ref_doc, group in groupby(sorted_doc, key=lambda f: f.referencing_doc):
            lines.append(f"{ref_doc}:")
            for f in group:
                lines.append(f"  L{f.line_no:<4} -> {f.changed_file}    ({f.matched_form})")
            lines.append("")

    if rules_configured:
        lines.append("Paired rules:")
        if paired:
            for f in paired:
                lines.append(f"  {f.watch} L{f.line_no}: {f.message}")
        else:
            lines.append("  (no paired-rule findings)")
        lines.append("")

    lines.append("Action: review each referencing doc; if the surface in the changed")
    lines.append("file shifted, update the doc in this PR.")
    lines.append("Exit 0 (informational; PR not blocked).")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -q`
Expected: `35 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_report.py scripts/audit_skills.py
git commit -m "feat: markdown report formatter (#2)"
```

---

### Task 5: CLI edge

**Files:**
- Create: `tests/test_cli.py`
- Modify: `scripts/audit_skills.py` (append after `format_report`)

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
"""CLI tests: flag parsing, exit codes, JSON mode, real-git smoke."""
import json
import subprocess
import sys
from pathlib import Path

import audit_skills
from audit_skills import ChangedFile, main

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit_skills.py"


def _fake_diff(*paths):
    return tuple(ChangedFile(path=p, added_lines=(), status="M",
                             rename_from=None) for p in paths)


def test_exit_0_and_no_findings_on_empty_diff(monkeypatch, capsys):
    monkeypatch.setattr(audit_skills, "list_changed_files", lambda base: ())
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "No findings" in out


def test_exit_1_on_bad_paired_rule_json(capsys):
    assert main(["--paired-rule", "{nope"]) == 1
    err = capsys.readouterr().err
    assert "not valid JSON" in err


def test_exit_1_when_git_fails(monkeypatch, capsys):
    def _boom(base):
        raise subprocess.CalledProcessError(128, ["git", "diff"])
    monkeypatch.setattr(audit_skills, "list_changed_files", _boom)
    assert main(["--base", "no-such-ref"]) == 1
    assert "git diff failed" in capsys.readouterr().err


def test_doc_glob_replaces_defaults(monkeypatch, tmp_path, capsys):
    (tmp_path / "mydocs").mkdir()
    (tmp_path / "mydocs" / "guide.md").write_text(
        "see scripts/x.py\n", encoding="utf-8")
    monkeypatch.setattr(audit_skills, "list_changed_files",
                        lambda base: _fake_diff("scripts/x.py"))
    rc = main(["--docs-root", str(tmp_path), "--doc-glob", "mydocs/*.md"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "mydocs/guide.md:" in out


def test_json_mode_payload_shape(monkeypatch, capsys):
    monkeypatch.setattr(audit_skills, "list_changed_files",
                        lambda base: _fake_diff("scripts/x.py"))
    rc = main(["--json", "--docs-root", "no-such-dir"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "audit-skills"
    assert payload["diff_summary"] == {"base_ref": "origin/main", "changed": 1}
    assert payload["doc_findings"] == []
    assert payload["paired_findings"] == []


def test_paired_rule_flag_end_to_end(monkeypatch, capsys):
    diff = (ChangedFile(path="scripts/db.py",
                        added_lines=((42, "CREATE TABLE widget (x)"),),
                        status="M", rename_from=None),)
    monkeypatch.setattr(audit_skills, "list_changed_files", lambda base: diff)
    rule = json.dumps({
        "watch": "scripts/db.py",
        "pattern": r"CREATE\s+TABLE\s+(\w+)",
        "expect": ".claude/skills/*-architecture/SKILL.md",
        "message": "table `{1}` needs a skill",
    })
    rc = main(["--paired-rule", rule, "--docs-root", "no-such-dir"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "scripts/db.py L42: table `widget` needs a skill" in out


def test_real_git_smoke_empty_diff():
    """End-to-end subprocess run in this repo: HEAD...HEAD is an empty
    diff, so the script must print the no-findings report and exit 0."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert "No findings" in proc.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -q`
Expected: FAIL — `ImportError: cannot import name 'main'`

- [ ] **Step 3: Append the CLI to scripts/audit_skills.py**

```python
# --- CLI ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="audit_skills.py",
        description="PR-time doc-currency audit (informational; never blocks)",
    )
    p.add_argument("--base", default="origin/main",
                   help="Git ref to diff against (default: origin/main)")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON instead of markdown")
    p.add_argument("--doc-glob", action="append", default=None, metavar="GLOB",
                   help="Doc-corpus glob; repeatable; REPLACES the built-in "
                        "defaults when given")
    p.add_argument("--paired-rule", action="append", default=None, metavar="JSON",
                   help='One rule as a JSON object with keys '
                        '"watch", "pattern", "expect", "message"; repeatable')
    p.add_argument("--docs-root", default=".",
                   help="Root directory for doc-corpus globs (default: cwd)")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        rules = tuple(parse_rule(raw) for raw in (args.paired_rule or ()))
    except ValueError as e:
        sys.stderr.write(f"[audit-skills] {e}\n")
        return 1

    try:
        diff = list_changed_files(args.base)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        sys.stderr.write(f"[audit-skills] git diff failed: {e}\n")
        return 1

    doc_globs = tuple(args.doc_glob) if args.doc_glob else _DEFAULT_DOC_GLOBS
    doc = doc_currency_findings(diff, docs_root=args.docs_root,
                                doc_globs=doc_globs)
    paired = paired_rule_findings(diff, rules)
    summary = DiffSummary(base_ref=args.base, changed=len(diff))

    if args.json:
        payload = {
            "kind": "audit-skills",
            "diff_summary": {"base_ref": args.base, "changed": len(diff)},
            "doc_findings": [f.__dict__ for f in doc],
            "paired_findings": [f.__dict__ for f in paired],
        }
        print(json.dumps(payload, indent=2))
    else:
        sys.stdout.write(format_report(doc, paired, summary,
                                       rules_configured=bool(rules)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -q`
Expected: `42 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli.py scripts/audit_skills.py
git commit -m "feat: argparse CLI edge with exit-code contract (#2)"
```

---

### Task 6: PR-139 hermetic replay fixture

**Files:**
- Create: `tests/fixtures/pr139/diff.patch` (copied from the trading-bot checkout)
- Create: `tests/fixtures/pr139/corpus/.claude/skills/dashboard-maintenance/SKILL.md`
- Create: `tests/fixtures/pr139/corpus/.claude/skills/core-trail-architecture/SKILL.md`
- Create: `tests/test_pr139_replay.py`

Background: trading-bot PR #139 changed `scripts/core_trail.py`,
`scripts/backfill_core_trail.py`, `dashboard/api/app/data/memory_files.py`
(among others) and the doc-currency detector demonstrably flags the two
skills that reference those files. Trading-bot's version of this test reads
LIVE skills at HEAD (its docstring admits the fragility); the port freezes a
minimal corpus snapshot so the replay is hermetic.

- [ ] **Step 1: Copy the frozen diff fixture**

```bash
mkdir -p tests/fixtures/pr139
cp "F:/Claude/Projects/Trading/tests/fixtures/audit/pr_139_diff.patch" tests/fixtures/pr139/diff.patch
```

Verify: `grep -c "^diff --git" tests/fixtures/pr139/diff.patch` → expected `18`.

- [ ] **Step 2: Write the frozen corpus snapshot**

`tests/fixtures/pr139/corpus/.claude/skills/dashboard-maintenance/SKILL.md`:

```markdown
# dashboard-maintenance (frozen snapshot for the PR-139 replay)

Minimal excerpt of the trading-bot skill as it stood before PR #139,
keeping only lines that reference files changed in that PR.

The dashboard read path for memory files lives in
`dashboard/api/app/data/memory_files.py`; sleeve classification is driven
by `memory/CORE-TRAIL.md`.
```

`tests/fixtures/pr139/corpus/.claude/skills/core-trail-architecture/SKILL.md`:

```markdown
# core-trail-architecture (frozen snapshot for the PR-139 replay)

Minimal excerpt of the trading-bot skill as it stood before PR #139,
keeping only lines that reference files changed in that PR.

The pure-function ratchet lives in `scripts/core_trail.py`; the one-shot
backfill is `scripts/backfill_core_trail.py`; the rendered view is
`memory/CORE-TRAIL.md`; the dashboard reads via
`dashboard/api/app/data/memory_files.py:read_core_trail()`.
```

- [ ] **Step 3: Write the failing replay test**

`tests/test_pr139_replay.py`:

```python
"""Replay trading-bot PR #139's frozen diff against a frozen corpus
snapshot and assert the doc-currency detector flags the two skills whose
references went stale in that PR.

This is the issue's motivating-miss proof, made hermetic: both the diff
AND the corpus are fixtures (the origin repo's version scanned live
skills at HEAD and admitted the fragility in its own docstring).
"""
from pathlib import Path

from audit_skills import _parse, doc_currency_findings

FIXTURES = Path(__file__).parent / "fixtures" / "pr139"


def test_pr139_replay_flags_expected_skills():
    diff = _parse((FIXTURES / "diff.patch").read_text(encoding="utf-8",
                                                      errors="ignore"))
    assert len(diff) == 18, "frozen PR-139 diff should parse 18 files"

    findings = doc_currency_findings(diff, docs_root=str(FIXTURES / "corpus"))
    referenced = {f.referencing_doc for f in findings}
    assert any("dashboard-maintenance" in r for r in referenced), \
        f"expected dashboard-maintenance flagged; got {referenced}"
    assert any("core-trail-architecture" in r for r in referenced), \
        f"expected core-trail-architecture flagged; got {referenced}"
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/test_pr139_replay.py -q`
Expected: PASS (the detector already exists; this is a fixture-driven
integration test — if it fails, check the corpus reference lines against
the changed paths in the patch).

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest tests/ -q`
Expected: `43 passed`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/pr139 tests/test_pr139_replay.py
git commit -m "test: hermetic PR-139 frozen-diff replay (#2)"
```

---

### Task 7: /audit-skills slash command

**Files:**
- Create: `commands/audit-skills.md`

- [ ] **Step 1: Write the command**

`commands/audit-skills.md` (full content):

````markdown
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
````

- [ ] **Step 2: Verify the command file shape**

Run: `head -5 commands/audit-skills.md`
Expected: frontmatter opens with `---` and a `description:` line, matching
the sibling commands.

- [ ] **Step 3: Commit**

```bash
git add commands/audit-skills.md
git commit -m "feat: /audit-skills slash command (#2)"
```

---

### Task 8: Config example + skill-currency Verification section

**Files:**
- Modify: `examples/issue-tracker.yaml.example`
- Modify: `skills/skill-currency/SKILL.md` (ONLY the "Verification — manual today, automated later" section)

- [ ] **Step 1: Append the skill_currency block to the example config**

Open `examples/issue-tracker.yaml.example` and append at the end (commented
out, mirroring how optional blocks are documented there — read the file
first and match its commenting style):

```yaml
# --- Optional: /audit-skills configuration -----------------------------------
# Consumed by the /audit-skills slash command (the skill-currency
# enforcement helper). Both keys optional; omit the whole block to use
# the built-in defaults.
#
# skill_currency:
#   doc_globs:        # REPLACES the dual-layout defaults when set
#     - CLAUDE.md
#     - .claude/skills/*/SKILL.md
#     - routines/*.md
#   paired_rules:     # default: none. Example: the trading-bot pairing --
#     - watch: scripts/db.py                # added CREATE TABLE here...
#       pattern: 'CREATE\s+TABLE\s+(\w+)'
#       expect: '.claude/skills/*-architecture/SKILL.md'   # ...without this
#       message: 'new table `{1}` has no matching *-architecture skill in this diff'
```

- [ ] **Step 2: Replace the skill-currency Verification section**

In `skills/skill-currency/SKILL.md`, replace the section that starts with
`## Verification — manual today, automated later` and ends just before
`## Worked example` with:

```markdown
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
```

Touch NOTHING else in that file — the rule prose stays byte-identical
(issue #2 constraint, read as "don't weaken the rule").

- [ ] **Step 3: Verify the diff is scoped**

Run: `git diff --stat skills/skill-currency/SKILL.md`
Expected: one file, roughly `-17/+20` lines, all within the Verification
section. Run `git diff skills/skill-currency/SKILL.md` and confirm no rule
prose changed.

- [ ] **Step 4: Commit**

```bash
git add examples/issue-tracker.yaml.example skills/skill-currency/SKILL.md
git commit -m "docs: skill_currency config example + Verification section repoint (#2)"
```

---

### Task 9: CI python-tests job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add the job**

Append to the `jobs:` map in `.github/workflows/ci.yml` (sibling of
`markdown-lint`, `yaml-validate`, `backend-contract` — do not touch those):

```yaml
  python-tests:
    name: Python tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install pytest
        run: pip install pytest
      - name: Run tests
        run: pytest -q
```

- [ ] **Step 2: Validate the workflow YAML locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('ok')"`
(If PyYAML isn't available locally, run `yamllint -d relaxed .github/workflows/ci.yml` or rely on a clean `git push` + CI.)
Expected: `ok` (or no yamllint errors).

- [ ] **Step 3: Run the full local suite one more time**

Run: `python -m pytest tests/ -q`
Expected: `43 passed`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: run pytest on the audit-skills library (#2)"
```

---

### Task 10: Packaging + docs (v1.4.0)

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `CHANGELOG.md`
- Modify: `README.md`

- [ ] **Step 1: Bump plugin.json**

In `.claude-plugin/plugin.json`: `"version": "1.3.0"` → `"version": "1.4.0"`,
and in `"description"` replace

```
four slash commands (/tracker-init, /tracker-doctor, /resume-initiative, /work-issue)
```

with

```
five slash commands (/tracker-init, /tracker-doctor, /resume-initiative, /work-issue, /audit-skills)
```

- [ ] **Step 2: Mirror in marketplace.json**

In `.claude-plugin/marketplace.json`, the plugin entry's `"version"` →
`"1.4.0"` and apply the same four→five description replacement.

- [ ] **Step 3: CHANGELOG entry**

In `CHANGELOG.md`, under `## [Unreleased]` insert a new release section
(keep `[Unreleased]` itself empty above it):

```markdown
## [1.4.0] - 2026-06-10

### Added

- **`/audit-skills` slash command + stdlib-only detector library — the
  `skill-currency` enforcement helper** (#2). `scripts/audit_skills.py`
  (Python 3.10+, zero third-party deps) parses the branch diff vs a base
  ref (`git diff --unified=0 --find-renames`) and reports agent-readable
  docs whose references to changed files may have gone stale, using
  three match forms (path / basename / 3+-char stem) and dual-layout
  default globs covering both consumer projects (`CLAUDE.md`,
  `AGENTS.md`, `.claude/{skills,agents,commands}/`) and plugin-dev repos
  (`skills/`, `commands/`, `backends/`, `templates/`). The
  trading-bot-specific DB-canonical detector generalized into optional
  config-driven **paired rules** (`{watch, pattern, expect, message}`,
  zero defaults) configured under a new optional `skill_currency:` block
  in `.claude/issue-tracker.yaml` — the slash command translates YAML to
  CLI flags so the Python stays YAML-free. Informational discipline
  throughout: exit 0 always on success, the PR is never blocked. The
  command carries a prose fallback for consumers without Python on PATH.
  Tested by a pytest suite (43 tests) including a hermetic frozen-diff
  replay of the motivating miss (trading-bot PR #139) and the documented
  short-stem false-positive guard; CI gains a `python-tests` job.

### Changed

- `skills/skill-currency/SKILL.md` — the "Verification" section now
  points at the shipped `/audit-skills` helper instead of describing the
  honor-system as the only option. The rule prose is unchanged.
```

- [ ] **Step 4: README updates**

Three places in `README.md`:

1. The command table (around line 31): add a row after `/work-issue`:

```markdown
| [`/audit-skills`](commands/audit-skills.md) | PR-time doc-currency audit — lists docs whose references may be stale vs the branch's diff; informational, never blocks |
```

2. The skill-currency paragraph (around line 138): replace the trailing
sentence `the `/audit-skills` enforcement helper is a v1.1 follow-on.`
with:

```markdown
the [`/audit-skills`](commands/audit-skills.md) command is its shipped enforcement helper — run it before opening a PR.
```

3. The roadmap bullet (around line 155) `- **v1.1** (planned) — port the
`/audit-skills` detector + library as the enforcement helper for
`skill-currency`.` — replace with:

```markdown
- **v1.4** (shipped) — `/audit-skills` detector + library as the enforcement helper for `skill-currency`.
```

(Read the surrounding lines first; exact line numbers may have drifted —
match on content, not position.)

- [ ] **Step 5: Verify markdownlint-covered files still lint**

CI lints `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `examples/**/*.md`.
If `npx` is available run:
`npx markdownlint-cli2 "README.md" "CHANGELOG.md" "examples/**/*.md"`
Expected: no errors. (If npx is unavailable, note it and rely on the CI
job — but eyeball list indentation and line lengths against neighboring
entries.)

- [ ] **Step 6: Full suite + commit**

Run: `python -m pytest tests/ -q`
Expected: `43 passed`

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md README.md
git commit -m "chore(release): 1.4.0 — /audit-skills enforcement helper (#2)"
```

---

### Task 11: Final verification + PR

**Files:** none (verification + PR only)

- [ ] **Step 1: Full test run with output captured**

Run: `python -m pytest tests/ -v`
Expected: all tests pass, zero failures. Capture the tail for the PR body.

- [ ] **Step 2: Live end-to-end run against this very branch**

```bash
python scripts/audit_skills.py --base origin/main
```

Expected: exit 0, and the report SHOULD flag real findings: this branch
changes `scripts/audit_skills.py`, and the (also-changed)
`skills/skill-currency/SKILL.md` — which IS in the default plugin-dev
corpus — now references that path, so at least one `path`-form finding
must appear. Confirm the output shape matches `format_report` and quote
the self-referential finding in the PR body (the helper auditing its own
PR is the best smoke test there is).

- [ ] **Step 3: Branch staleness check**

```bash
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

Expected: `N 0` (ahead only). If behind, rebase onto `origin/main` and
re-run the suite.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/audit-skills-port
gh pr create --repo maxdimitrov/agent-issue-tracker \
  --title "feat(skill-currency): /audit-skills command + stdlib detector library (v1.4.0)" \
  --body-file <body file>
```

PR body must include: summary of the five design decisions (link the spec
file), the test evidence from Steps 1–2, the acceptance-criteria checklist
from issue #2 mapped to what shipped, and the literal line `Closes #2`
(enhancement → `Closes` per `backends/github.md`).

**Do NOT merge** — the PR is the human gate.
