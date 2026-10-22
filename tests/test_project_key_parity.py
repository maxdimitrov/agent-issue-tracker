"""ait_project_key: one key per checkout, whatever the path spelling.

The key names the per-project state dir (loop records, resume notes, brief
windows), and other tools match on it: keel's sweep lists loop records by
it and a project's `ait_project_keys` names it. So the Git Bash spelling
(`/f/Claude/Projects/X`), the forward-slash Windows spelling
(`F:/Claude/Projects/X`) and the backslash one (`F:\\Claude\\Projects\\X`)
must give the same key from bash, and the same key as `py_project_key`
below, the Python port of the algorithm a non-bash reader uses.
"""
import hashlib
import re
import sys
from pathlib import Path

import pytest

from shell_helpers import init_repo, run_lib

WINDOWS = sys.platform == "win32"


def py_project_key(path: str) -> str:
    """`<basename>-<sha256(main repo path)[0:8]>`, where the path is
    absolute, forward-slashed, in drive form (`F:/...`, never `/f/...`),
    with no trailing slash. Mirrors common.sh's ait_norm_path +
    ait_project_key for a main checkout."""
    p = path.replace("\\", "/")
    m = re.match(r"^/([A-Za-z])(/.*)?$", p)
    if WINDOWS and m:
        p = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    m = re.match(r"^([A-Za-z]):(/.*)?$", p)
    if m:
        p = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    if len(p) > 1:
        p = p.rstrip("/")
    name = re.sub(r"[^A-Za-z0-9._-]", "", p.rsplit("/", 1)[-1])[:40] or "project"
    return f"{name}-{hashlib.sha256(p.encode('utf-8')).hexdigest()[:8]}"


def spellings(path: Path) -> list[str]:
    """The three spellings of one directory (only the POSIX one off Windows)."""
    posix = path.as_posix()
    if not WINDOWS:
        return [posix]
    drive, rest = posix[0], posix[2:]
    return [f"/{drive.lower()}{rest}", f"{drive.upper()}:{rest}", str(path).replace("/", "\\")]


def bash_key(path: str) -> str:
    r = run_lib(f'ait_project_key "{path}"')
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "Widget-Repo")


def test_three_spellings_give_one_key_in_bash_and_python(repo):
    keys = {bash_key(s) for s in spellings(repo)}
    assert len(keys) == 1, keys
    (key,) = keys
    assert key.startswith("Widget-Repo-")
    assert {py_project_key(s) for s in spellings(repo)} == {key}


@pytest.mark.skipif(not WINDOWS, reason="drive-letter spellings exist only on Windows")
def test_spellings_are_really_different(repo):
    s = spellings(repo)
    assert len(set(s)) == 3
    assert s[0].startswith("/") and s[1][1] == ":" and "\\" in s[2]


def test_a_linked_worktree_shares_the_primary_key(repo, tmp_path):
    from shell_helpers import git
    wt = tmp_path / "runner-wt"
    git(repo, "worktree", "add", "-q", "-b", "runner", wt.as_posix())
    assert bash_key(wt.as_posix()) == bash_key(repo.as_posix()) == py_project_key(repo.as_posix())


def test_override_is_returned_unchanged(repo, monkeypatch):
    monkeypatch.setenv("AIT_PROJECT_KEY", "abc")
    assert bash_key(repo.as_posix()) == "abc"
    r = run_lib('ait_state_dir "$PWD"', cwd=str(repo), env=None)
    assert r.returncode == 0 and r.stdout.endswith("/abc")


def test_unset_override_gives_the_hash(repo, monkeypatch):
    monkeypatch.delenv("AIT_PROJECT_KEY", raising=False)
    assert re.fullmatch(r"Widget-Repo-[0-9a-f]{8}", bash_key(repo.as_posix()))


@pytest.mark.parametrize("bad", ["", "..", ".", "a/b", "../escape", "has space"])
def test_unsafe_override_is_ignored(repo, monkeypatch, bad):
    monkeypatch.setenv("AIT_PROJECT_KEY", bad)
    assert re.fullmatch(r"Widget-Repo-[0-9a-f]{8}", bash_key(repo.as_posix()))
