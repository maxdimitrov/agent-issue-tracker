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
