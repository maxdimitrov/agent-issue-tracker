"""Unit tests for scripts/lib/common.sh, run through bash."""
import os
import time
from pathlib import Path

import pytest

from shell_helpers import git, init_repo, run_lib

CONFIG = """schema_version: 1
backend: github   # trailing comment
github:
  repo: "acme/widgets"
  default_pr_close_syntax: "Fixes #N"
jira:
  site: example.atlassian.net
loops:
  interval: 15m
  # claim_label: agent-claimed
"""


@pytest.mark.parametrize("branch,ref", [
    ("max/WB-7657-subscription-gates", "WB-7657"),
    ("feat/42-board-support", "#42"),
    ("fix/issue-17-null-deref", "#17"),
    ("feat/board-support", ""),
    ("release/v1.8.0", ""),
    ("release/1.8.0", ""),
    ("hotfix/2.0", ""),
    ("main", ""),
    ("PROJ-9", "PROJ-9"),
    ("feat/ABC-12-then-XYZ-9", "ABC-12"),
    ("feat/12", "#12"),
    ("feat/12abc", ""),
    ("fix/issue12", "#12"),
    ("fix/do-issue-7-now", "#7"),
    ("fix/reissue-7", ""),
    ("abc-12", ""),
])
def test_ref_from_branch(branch, ref):
    r = run_lib(f'ait_ref_from_branch "{branch}"')
    assert r.stdout == ref
    assert r.returncode == (0 if ref else 1)


@pytest.mark.parametrize("branch,slug", [
    ("max/WB-7657-subscription-gates", "subscription-gates"),
    ("feat/42-board-support", "board-support"),
    ("fix/issue-17-null-deref", "null-deref"),
    ("feat/a-very-long-branch-name-that-keeps-going-on", "a-very-long-branch-name-"),
    ("release/1.8.0", "1.8.0"),
    ("feat/v1.2-widget", "v1.2-widget"),
])
def test_slug_from_branch(branch, slug):
    assert run_lib(f'ait_slug_from_branch "{branch}"').stdout == slug


def test_json_str_escapes():
    assert run_lib('ait_json_str \'he said "hi"\'').stdout.strip() == '"he said \\"hi\\""'


def test_project_key_is_stable_across_worktrees(tmp_path):
    repo = init_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feat/x", wt.as_posix())
    k1 = run_lib("ait_project_key", cwd=str(repo)).stdout
    k2 = run_lib("ait_project_key", cwd=str(wt)).stdout
    assert k1 == k2
    assert k1.startswith("repo-") and len(k1) == len("repo-") + 8


def test_project_key_outside_git(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert run_lib("ait_project_key", cwd=str(d)).stdout.startswith("plain-")


def test_state_dir_respects_override(tmp_path):
    repo = init_repo(tmp_path / "repo")
    env = dict(os.environ, AIT_STATE_DIR=(tmp_path / "state").as_posix())
    out = run_lib("ait_state_dir", env=env, cwd=str(repo)).stdout
    assert out.startswith((tmp_path / "state").as_posix())
    assert Path(out).is_dir()


def test_config_get_scalars_and_nested(tmp_path):
    cfg = tmp_path / "issue-tracker.yaml"
    cfg.write_text(CONFIG)
    c = cfg.as_posix()
    assert run_lib(f'ait_config_get backend "{c}"').stdout == "github"
    assert run_lib(f'ait_config_get github.repo "{c}"').stdout == "acme/widgets"
    assert run_lib(f'ait_config_get github.default_pr_close_syntax "{c}"').stdout == "Fixes #N"
    assert run_lib(f'ait_config_get jira.site "{c}"').stdout == "example.atlassian.net"
    assert run_lib(f'ait_config_get loops.interval "{c}"').stdout == "15m"
    r = run_lib(f'ait_config_get loops.claim_label "{c}"')
    assert r.stdout == "" and r.returncode == 1


def test_config_path_found_from_subdir(tmp_path):
    repo = init_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "issue-tracker.yaml").write_text(CONFIG)
    sub = repo / "src"
    sub.mkdir()
    out = run_lib("ait_config_path", cwd=str(sub)).stdout
    assert out.replace("\\", "/").lower().endswith("repo/.claude/issue-tracker.yaml")
    assert run_lib("ait_config_path", cwd=str(tmp_path)).returncode == 1


def test_issue_url_github_and_jira(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(CONFIG)
    c = cfg.as_posix()
    assert run_lib(f'ait_issue_url "#42" "{c}"').stdout == "https://github.com/acme/widgets/issues/42"
    assert run_lib(f'ait_issue_url "other/repo#7" "{c}"').stdout == "https://github.com/other/repo/issues/7"
    assert run_lib(f'ait_issue_url "PROJ-9" "{c}"').returncode == 1
    jira = tmp_path / "j.yaml"
    jira.write_text(CONFIG.replace("backend: github", "backend: jira"))
    j = jira.as_posix()
    assert run_lib(f'ait_issue_url "PROJ-9" "{j}"').stdout == "https://example.atlassian.net/browse/PROJ-9"
    assert run_lib(f'ait_issue_url "#42" "{j}"').returncode == 1


def test_time_helpers_round_trip(tmp_path):
    f = tmp_path / "x"
    f.write_text("x")
    mt = int(run_lib(f'ait_file_mtime "{f.as_posix()}"').stdout)
    assert abs(mt - time.time()) < 120
    iso = run_lib("ait_iso_from_epoch 1700000000").stdout
    assert iso == "2023-11-14T22:13:20Z"
    assert run_lib(f'ait_epoch_from_iso "{iso}"').stdout == "1700000000"


def test_run_capped_kills_slow_command():
    r = run_lib("ait_run_capped 1 sleep 5; echo rc=$?")
    assert "rc=" in r.stdout and "rc=0" not in r.stdout


@pytest.mark.parametrize("raw,encoded", [
    ("feat/42-widget", "feat%2F42-widget"),
    ("feat/a b+c#1", "feat%2Fa%20b%2Bc%231"),
    ("x&per_page=1", "x%26per_page%3D1"),
    ("", ""),
])
def test_uri_encode(raw, encoded):
    r = run_lib(f"ait_uri_encode '{raw}'")
    assert r.stdout == encoded and r.returncode == 0


@pytest.mark.parametrize("value,kind", [
    ("[]", "array"), ('{"a":1}', "object"), ('"s"', "string"), ("3", "number"),
    ("null", "null"), ("true", "boolean"),
])
def test_json_type(value, kind):
    r = run_lib(f"ait_json_type '{value}'")
    assert r.stdout == kind and r.returncode == 0


@pytest.mark.parametrize("value", ["", "{not json", "[1] [2]"])
def test_json_type_rejects_non_values(value):
    r = run_lib(f"ait_json_type '{value}'")
    assert r.stdout == "" and r.returncode == 1
