"""Unit tests for scripts/lib/common.sh, run through bash."""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shell_helpers import (REPO_ROOT, env_with_path, env_without_command, git, init_repo,
                           isolated_env, make_stub, run_lib)

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


def _home_env(home):
    """os.environ with HOME pinned, so the ancestor walk stops at `home`."""
    env = dict(os.environ)
    env["HOME"] = Path(home).as_posix()
    return env


def _write_config(root, text=CONFIG):
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "issue-tracker.yaml").write_text(text)


def _config_path_from(cwd, env):
    r = run_lib("ait_config_path", env=env, cwd=str(cwd))
    return r.returncode, r.stdout.replace("\\", "/").lower()


def test_config_path_walks_up_from_nested_repo(tmp_path):
    ws = tmp_path / "ws"
    _write_config(ws)
    repo = init_repo(ws / "repos" / "app")
    rc, out = _config_path_from(repo, _home_env(tmp_path))
    assert rc == 0 and out.endswith("ws/.claude/issue-tracker.yaml")


def test_config_path_walks_up_from_linked_worktree(tmp_path):
    ws = tmp_path / "ws"
    _write_config(ws)
    repo = init_repo(ws / "repos" / "app")
    wt = ws / "repos" / "app-worktrees" / "T-1"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "t-1")
    rc, out = _config_path_from(wt, _home_env(tmp_path))
    assert rc == 0 and out.endswith("ws/.claude/issue-tracker.yaml")


def test_config_path_finds_main_checkout_config_from_linked_worktree(tmp_path):
    repo = init_repo(tmp_path / "app")
    _write_config(repo)  # never committed, so the worktree has no copy
    wt = tmp_path / "app-worktrees" / "T-1"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "t-1")
    rc, out = _config_path_from(wt, _home_env(tmp_path))
    assert rc == 0 and out.endswith("/app/.claude/issue-tracker.yaml")


def test_config_path_nearest_wins(tmp_path):
    ws = tmp_path / "ws"
    _write_config(ws)
    repo = init_repo(ws / "repos" / "app")
    _write_config(repo)
    sub = repo / "src"
    sub.mkdir()
    rc, out = _config_path_from(sub, _home_env(tmp_path))
    assert rc == 0 and out.endswith("repos/app/.claude/issue-tracker.yaml")


def test_config_path_walk_skips_home(tmp_path):
    home = tmp_path / "home"
    _write_config(home)
    repo = init_repo(home / "code" / "app")
    rc, out = _config_path_from(repo, _home_env(home))
    assert rc == 1 and out == ""


def _worktree_for(branch, cwd):
    r = run_lib(f'ait_worktree_for_branch "{branch}"', cwd=str(cwd))
    return r.returncode, r.stdout.replace("\\", "/").lower()


def test_worktree_for_branch_ignores_the_directory_name(tmp_path):
    # #155: a bare-slug directory holding a fix/<slug> branch, which the
    # slash-to-plus path formula never matched.
    repo = init_repo(tmp_path / "repo")
    wt = repo / ".claude" / "worktrees" / "git-sign-stale-sig"
    git(repo, "worktree", "add", "-q", "-b", "fix/git-sign-stale-sig", wt.as_posix())
    plus = repo / ".claude" / "worktrees" / "feat+board"
    git(repo, "worktree", "add", "-q", "-b", "feat/board", plus.as_posix())
    for cwd in (repo, wt):  # same answer from the primary checkout and a worktree
        rc, out = _worktree_for("fix/git-sign-stale-sig", cwd)
        assert rc == 0 and out.endswith("repo/.claude/worktrees/git-sign-stale-sig")
    rc, out = _worktree_for("feat/board", repo)
    assert rc == 0 and out.endswith("repo/.claude/worktrees/feat+board")


def test_worktree_for_branch_rejects_path_outside_claude_worktrees(tmp_path):
    repo = init_repo(tmp_path / "repo")
    git(repo, "worktree", "add", "-q", "-b", "fix/elsewhere", (tmp_path / "elsewhere").as_posix())
    sibling = repo / ".claude" / "worktrees-other" / "x"  # shares the prefix, not the dir
    git(repo, "worktree", "add", "-q", "-b", "fix/sibling", sibling.as_posix())
    assert _worktree_for("fix/elsewhere", repo) == (1, "")
    assert _worktree_for("fix/sibling", repo) == (1, "")
    assert _worktree_for("main", repo) == (1, "")  # the primary checkout


def test_worktree_for_branch_skips_a_deleted_directory(tmp_path):
    # Still registered (prunable), but there is nothing to enter or remove.
    repo = init_repo(tmp_path / "repo")
    wt = repo / ".claude" / "worktrees" / "gone"
    git(repo, "worktree", "add", "-q", "-b", "fix/gone", wt.as_posix())
    shutil.rmtree(wt)
    assert _worktree_for("fix/gone", repo) == (1, "")


@pytest.mark.skipif(sys.platform == "win32", reason="needs an unprivileged symlink")
def test_worktree_for_branch_from_a_symlinked_checkout(tmp_path):
    # git lists real paths; the shell's logical cwd goes through the link.
    real = tmp_path / "real"
    repo = init_repo(real / "repo")
    wt = repo / ".claude" / "worktrees" / "x"
    git(repo, "worktree", "add", "-q", "-b", "fix/x", wt.as_posix())
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    via_link = link / "repo"
    env = dict(os.environ, PWD=str(via_link))  # keep bash's cwd logical
    r = run_lib('ait_worktree_for_branch "fix/x"', env=env, cwd=str(via_link))
    assert r.returncode == 0 and r.stdout.endswith("repo/.claude/worktrees/x")


def test_worktree_for_branch_matches_the_whole_branch_name(tmp_path):
    repo = init_repo(tmp_path / "repo")
    wt = repo / ".claude" / "worktrees" / "auth-retry"
    git(repo, "worktree", "add", "-q", "-b", "fix/auth-retry", wt.as_posix())
    assert _worktree_for("fix/auth", repo) == (1, "")
    assert _worktree_for("auth-retry", repo) == (1, "")
    assert _worktree_for("", repo) == (1, "")
    assert _worktree_for("fix/auth-retry", tmp_path) == (1, "")  # not a git repo


@pytest.mark.parametrize("command", ["work-issue", "tracker-loop", "resume-initiative"])
def test_commands_find_worktrees_by_branch_not_by_directory_name(command):
    # #155: the lookup is stated once (/work-issue Step 3) and referenced by
    # name elsewhere; no command may resolve a worktree from the path formula.
    text = (REPO_ROOT / "commands" / f"{command}.md").read_text(encoding="utf-8")
    assert "ait_worktree_for_branch" in text
    assert "branch-with-slash" not in text


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


def test_config_get_pathless_reads_merged_view(tmp_path):
    home = tmp_path / "home"
    repo = init_repo(home / "code" / "app")
    _write_config(repo, "schema_version: 1\nbackend: github\n")
    _write_config(home, "schema_version: 1\nloops:\n  interval: 7m\n")
    env = _home_env(home)
    assert run_lib("ait_config_get loops.interval", env=env, cwd=str(repo)).stdout == "7m"
    raw = (repo / ".claude" / "issue-tracker.yaml").as_posix()
    r = run_lib(f'ait_config_get loops.interval "{raw}"', env=env, cwd=str(repo))
    assert r.returncode == 1 and r.stdout == ""   # explicit path = that file only


def test_issue_url_pathless_honours_override(tmp_path):
    home = tmp_path / "home"
    repo = init_repo(home / "code" / "app")
    _write_config(repo, CONFIG)
    env = _home_env(home)
    env["TRACKER_GITHUB_REPO_OVERRIDE"] = "sandbox/repo"
    r = run_lib('ait_issue_url "#5"', env=env, cwd=str(repo))
    assert r.stdout == "https://github.com/sandbox/repo/issues/5"


def test_config_pick_reads_yaml_on_stdin():
    # The pick half of ait_config_get: callers that resolved once reuse the text.
    snippet = "printf '%s' \"$Y\" | _ait_config_pick"
    env = dict(os.environ, Y=CONFIG)
    assert run_lib(f"{snippet} backend", env=env).stdout == "github"
    assert run_lib(f"{snippet} github.repo", env=env).stdout == "acme/widgets"
    assert run_lib(f"{snippet} github.default_pr_close_syntax", env=env).stdout == "Fixes #N"
    assert run_lib(f"{snippet} loops.interval", env=env).stdout == "15m"
    r = run_lib(f"{snippet} loops.claim_label", env=env)
    assert r.returncode == 1 and r.stdout == ""


def test_issue_url_from_pre_resolved_text():
    snippet = '_ait_issue_url_from "$R" "$Y"'
    env = dict(os.environ, Y=CONFIG, R="#42")
    assert run_lib(snippet, env=env).stdout == "https://github.com/acme/widgets/issues/42"
    env = dict(os.environ, Y=CONFIG.replace("backend: github", "backend: jira"), R="PROJ-9")
    assert run_lib(snippet, env=env).stdout == "https://example.atlassian.net/browse/PROJ-9"
    r = run_lib(snippet, env=dict(os.environ, Y="schema_version: 1\n", R="#1"))
    assert r.returncode == 1 and r.stdout == ""


# --- ait_commit_in_tag (#149): is a merge commit contained in a release tag? ---

# gh stub: answers the compare API with $GH_COMPARE_STATUS and logs every call.
GH_COMPARE_STUB = r'''
printf '%s\n' "$*" >> "$GH_LOG"
case "$*" in
  *"/compare/"*) [ -n "${GH_COMPARE_STATUS:-}" ] || exit 1; printf '%s\n' "$GH_COMPARE_STATUS" ;;
  *) exit 1 ;;
esac
'''


def _rev(repo, rev):
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", rev], check=True, capture_output=True,
        text=True, stdin=subprocess.DEVNULL,
    ).stdout.strip()


@pytest.fixture
def released(tmp_path):
    """origin: old merge commit -> one more commit, tagged v1 -> one commit after the tag."""
    origin = init_repo(tmp_path / "origin")
    git(origin, "commit", "--allow-empty", "-m", "the merge")
    merge = _rev(origin, "HEAD")
    git(origin, "commit", "--allow-empty", "-m", "release prep")
    git(origin, "tag", "v1")
    git(origin, "commit", "--allow-empty", "-m", "after the release")
    # Lets a shallow clone fetch one old commit by sha, as a deepen/prune leaves it.
    git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    return {"origin": origin, "merge": merge, "after": _rev(origin, "HEAD")}


def _shallow_clone(tmp_path, origin, name="shallow"):
    clone = tmp_path / name
    git(tmp_path, "clone", "-q", "--depth", "1", "--branch", "v1", origin.as_uri(), str(clone))
    return clone


def _gh_env(tmp_path, status=None):
    stub = make_stub(tmp_path / "bin", "gh", GH_COMPARE_STUB)
    env = env_with_path(isolated_env(tmp_path), stub)
    env["GH_LOG"] = (tmp_path / "gh.log").as_posix()
    if status is not None:
        env["GH_COMPARE_STATUS"] = status
    return env


def _in_tag(repo, sha, tag, env):
    r = run_lib(f'ait_commit_in_tag "{sha}" "{tag}"', env=env, cwd=str(repo))
    return r.returncode, r.stdout


def _gh_calls(tmp_path):
    log = tmp_path / "gh.log"
    return log.read_text().splitlines() if log.exists() else []


def test_commit_in_tag_full_clone_trusts_git_both_ways(released, tmp_path):
    env = _gh_env(tmp_path, status="behind")  # a wrong host answer must not be consulted
    origin = released["origin"]
    assert _in_tag(origin, released["merge"], "v1", env) == (0, "contained git")
    assert _in_tag(origin, released["after"], "v1", env) == (1, "not-contained git")
    assert _gh_calls(tmp_path) == []


def test_commit_in_tag_unknown_tag(released, tmp_path):
    env = _gh_env(tmp_path, status="ahead")
    assert _in_tag(released["origin"], released["merge"], "v9", env) == (2, "unknown no-tag")
    assert _gh_calls(tmp_path) == []


def test_commit_in_tag_shallow_clone_asks_the_host(released, tmp_path):
    clone = _shallow_clone(tmp_path, released["origin"])
    merge = released["merge"]
    # The released merge is behind the graft: git alone cannot say yes.
    plain = subprocess.run(["git", "-C", str(clone), "merge-base", "--is-ancestor", merge, "v1"],
                           capture_output=True, stdin=subprocess.DEVNULL)
    assert plain.returncode != 0
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path, status="ahead")) == (0, "contained host")
    assert _gh_calls(tmp_path) == [f"api repos/{{owner}}/{{repo}}/compare/{merge}...v1 --jq .status"]
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path, status="identical")) == (0, "contained host")
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path, status="behind")) == (1, "not-contained host")
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path, status="diverged")) == (1, "not-contained host")


def test_commit_in_tag_shallow_clone_with_the_commit_object_present(released, tmp_path):
    # The case from the report: the commit object is there, the history between
    # it and the tag is not, so `is-ancestor` exits 1 exactly as for an
    # unreleased commit.
    clone = _shallow_clone(tmp_path, released["origin"])
    merge = released["merge"]
    git(clone, "fetch", "-q", "--depth", "1", "origin", merge)
    plain = subprocess.run(["git", "-C", str(clone), "merge-base", "--is-ancestor", merge, "v1"],
                           capture_output=True, stdin=subprocess.DEVNULL)
    assert plain.returncode == 1
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path, status="ahead")) == (0, "contained host")


def test_commit_in_tag_shallow_clone_without_a_host_answer_is_unknown(released, tmp_path):
    clone = _shallow_clone(tmp_path, released["origin"])
    merge = released["merge"]
    # gh fails (no status configured in the stub): never "not contained".
    assert _in_tag(clone, merge, "v1", _gh_env(tmp_path)) == (2, "unknown shallow")
    # No gh at all.
    env = env_without_command(isolated_env(tmp_path), tmp_path, "gh")
    assert _in_tag(clone, merge, "v1", env) == (2, "unknown shallow")


def test_commit_in_tag_full_clone_without_the_commit_asks_the_host(released, tmp_path):
    # A stale full clone that never fetched the merge commit: git cannot answer
    # (exit 128), which is not a "no" either.
    missing = "0123456789abcdef0123456789abcdef01234567"
    origin = released["origin"]
    assert _in_tag(origin, missing, "v1", _gh_env(tmp_path, status="ahead")) == (0, "contained host")
    assert _in_tag(origin, missing, "v1", _gh_env(tmp_path)) == (2, "unknown no-commit")
    assert _in_tag(origin, "", "v1", _gh_env(tmp_path)) == (2, "unknown usage")


def test_commit_in_tag_shallow_clone_still_trusts_a_yes_from_git(released, tmp_path):
    # v1's own commit is in the shallow history: no host call needed.
    clone = _shallow_clone(tmp_path, released["origin"])
    tip = _rev(clone, "v1^{commit}")
    assert _in_tag(clone, tip, "v1", _gh_env(tmp_path, status="behind")) == (0, "contained git")
    assert _gh_calls(tmp_path) == []
