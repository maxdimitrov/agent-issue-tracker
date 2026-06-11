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
    # stdin=DEVNULL: pytest's capture mode replaces the standard handles
    # with non-inheritable pipe objects on Windows; letting the child
    # inherit the captured stdin trips WinError 6 in _make_inheritable.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", "HEAD"],
        capture_output=True, text=True,
        stdin=subprocess.DEVNULL,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert "No findings" in proc.stdout
