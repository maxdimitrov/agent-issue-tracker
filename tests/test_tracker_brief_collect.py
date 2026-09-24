"""Subprocess tests for scripts/tracker-brief-collect.sh."""
import json
import subprocess
from pathlib import Path

import pytest

from shell_helpers import (SCRIPTS, env_with_path, git, init_repo, isolated_env,
                           make_stub, run_script)

SCRIPT = SCRIPTS / "tracker-brief-collect.sh"
CONFIG = "schema_version: 1\nbackend: github\ngithub:\n  repo: acme/widgets\n"
OLD = {"GIT_AUTHOR_DATE": "2026-08-01T10:00:00Z", "GIT_COMMITTER_DATE": "2026-08-01T10:00:00Z"}


def pr(number, title, branch, state="OPEN"):
    return {"number": number, "title": title, "url": f"https://github.com/acme/widgets/pull/{number}",
            "state": state, "isDraft": False, "updatedAt": "2026-09-24T08:00:00Z",
            "createdAt": "2026-09-20T08:00:00Z", "author": {"login": "me"}, "headRefName": branch}


PRS = {
    "open": [pr(70, "[#604] widget", "feat/604-widget"), pr(71, "unrelated", "feat/nothing")],
    "merged": [pr(60, "[#6041] big widget", "feat/6041-big", "MERGED")],
    "all": [pr(70, "[#604] widget", "feat/604-widget"), pr(71, "unrelated", "feat/nothing"),
            pr(60, "[#6041] big widget", "feat/6041-big", "MERGED"),
            pr(50, "[#17] landed", "fix/17-old", "MERGED")],
}
PR_VIEW = {"reviewDecision": "CHANGES_REQUESTED", "headRefName": "feat/604-widget", "isDraft": False,
           "mergeable": "MERGEABLE", "updatedAt": "2026-09-24T08:00:00Z",
           "comments": [{"author": {"login": "reviewer"}, "createdAt": "2026-09-24T07:30:00Z",
                         "url": "https://x/c/1", "body": "please split this"}],
           "reviews": []}
THREADS = {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
    {"isResolved": False, "isOutdated": False,
     "comments": {"nodes": [{"author": {"login": "reviewer"}, "body": "nit", "url": "https://x/t/1",
                             "createdAt": "2026-09-24T07:00:00Z"}]}}]}}}}}
RUNS = {"workflow_runs": [{"status": "completed", "conclusion": "success", "name": "CI",
                           "html_url": "https://x/runs/3", "run_started_at": "2026-09-24T07:50:00Z"}]}

GH_STUB = r'''
echo "$@" >> "$GH_CALLS"
case "$*" in
  *"api user"*)               echo "me" ;;
  *"pr list"*"--head"*)       if [[ "$*" == *"fix/17-old"* ]]; then echo '[{"number":50,"state":"MERGED","mergedAt":"2026-08-02T00:00:00Z","title":"[#17] landed","url":"https://github.com/acme/widgets/pull/50"}]'; else echo '[]'; fi ;;
  *"pr list"*"--state merged"*) cat "$GH_MERGED" ;;
  *"pr list"*"--state all"*)  cat "$GH_ALL" ;;
  *"pr list"*"review-requested"*) echo '[]' ;;
  *"pr list"*"mentions"*)     echo '[]' ;;
  *"pr list"*)                cat "$GH_OPEN" ;;
  *"pr view"*)                cat "$GH_VIEW" ;;
  *"graphql"*)                cat "$GH_THREADS" ;;
  *"actions/runs"*)           cat "$GH_RUNS" ;;
  *) exit 1 ;;
esac
'''


def run(cwd, env, *args):
    r = run_script(SCRIPT, args=args, env=env, cwd=str(cwd))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture
def repo(tmp_path):
    repo = init_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "issue-tracker.yaml").write_text(CONFIG)
    git(repo, "remote", "add", "origin", "https://github.com/acme/widgets.git")
    return repo


@pytest.fixture
def gh(tmp_path):
    files = {"GH_OPEN": PRS["open"], "GH_MERGED": PRS["merged"], "GH_ALL": PRS["all"],
             "GH_VIEW": PR_VIEW, "GH_THREADS": THREADS, "GH_RUNS": RUNS}
    extra = {"GH_CALLS": (tmp_path / "gh-calls").as_posix()}
    for k, v in files.items():
        p = tmp_path / f"{k}.json"
        p.write_text(json.dumps(v))
        extra[k] = p.as_posix()
    return make_stub(tmp_path / "bin", "gh", GH_STUB), extra


def test_first_run_window_and_stamp(repo, tmp_path):
    env = isolated_env(tmp_path)
    out = run(repo, env)
    assert out["window"]["first_run"] is True and out["window"]["days"] in (0, 1)
    assert out["window"]["summarize_mode"] is False
    stamp = run(repo, env, "--commit-run")
    assert Path(stamp["state_file"]).is_file()
    again = run(repo, env)
    assert again["window"]["first_run"] is False
    assert again["window"]["since"] == stamp["committed"]
    assert again["window"]["last_run"] == stamp["committed"]


def test_since_override_and_summarize_mode(repo, tmp_path):
    out = run(repo, isolated_env(tmp_path, AIT_SINCE="2026-01-01T00:00:00Z"))
    assert out["window"]["since"] == "2026-01-01T00:00:00Z"
    assert out["window"]["summarize_mode"] is True and out["window"]["days"] > 5


def test_no_gh_and_no_remote_still_valid(tmp_path):
    repo = init_repo(tmp_path / "bare-repo")
    stub = make_stub(tmp_path / "bin", "gh", "exit 1")
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["viewer"]["gh_available"] is False
    assert out["prs"]["authored_open"] == [] and out["ledger"] == []
    assert any("origin" in e for e in out["errors"])
    assert out["worktrees"][0]["primary"] is True


def test_worktrees_stale_dirty_and_landed(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    old = tmp_path / "old"
    git(repo, "worktree", "add", "-q", "-b", "fix/17-old", old.as_posix())
    git(old, "commit", "--allow-empty", "-m", "old work", env={**env, **OLD})
    dirty = tmp_path / "dirty"
    git(repo, "worktree", "add", "-q", "-b", "feat/6041-big", dirty.as_posix())
    (dirty / "x").write_text("x")
    out = run(repo, env)
    by_branch = {w["branch"]: w for w in out["worktrees"]}
    assert by_branch["main"]["primary"] is True and by_branch["main"]["stale"] is False
    o = by_branch["fix/17-old"]
    assert o["ref"] == "#17" and o["stale"] is True and o["idle_days"] >= 14
    assert o["landed_pr"]["state"] == "MERGED" and o["touched_in_window"] is False
    d = by_branch["feat/6041-big"]
    assert d["dirty_count"] == 1 and d["stale"] is False and d["landed_pr"] is None


def test_ledger_joins_by_exact_ref(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    git(repo, "worktree", "add", "-q", "-b", "feat/6041-big", (tmp_path / "big").as_posix())
    out = run(repo, env)
    rows = {r["ref"]: r for r in out["ledger"]}
    assert rows["#604"]["open_pr"]["number"] == 70
    assert rows["#604"]["worktree"] is None
    assert rows["#6041"]["merged_pr"]["number"] == 60 and rows["#6041"]["open_pr"] is None
    assert rows["#6041"]["worktree"]["branch"] == "feat/6041-big"
    assert rows["#6041"]["actionable"] is True
    assert rows["#17"]["actionable"] is False
    assert rows["#604"]["ticket_url"] == "https://github.com/acme/widgets/issues/604"
    assert "#nothing" not in rows and None not in rows


def test_pr_detail_threads_comments_ci(repo, tmp_path, gh):
    stub, extra = gh
    out = run(repo, env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub))
    detail = {d["number"]: d for d in out["pr_detail"]}
    d = detail[70]
    assert d["review_decision"] == "CHANGES_REQUESTED"
    assert d["unresolved_threads"] == 1 and d["threads"][0]["excerpt"] == "nit"
    assert d["new_comments"][0]["excerpt"] == "please split this"
    assert d["ci"]["conclusion"] == "success"
    assert d["ref"] == "#604"
    row = {r["ref"]: r for r in out["ledger"]}["#604"]
    assert row["detail"]["number"] == 70


def test_resume_notes_and_loops_join_ledger(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub)
    state = Path(run(repo, env)["config"]["state_dir"])
    (state / "resume").mkdir(parents=True)
    (state / "resume" / "6041.md").write_text("# Resume: #6041 — written 2026-09-23 18:00\n\ncd x\n")
    (state / "loops").mkdir()
    (state / "loops" / "babysit-604-1.json").write_text(json.dumps({
        "id": "babysit-604-1", "mode": "babysit", "ref": "#604", "branch": "feat/604-widget",
        "state": "live", "stop_reason": None, "started": "2026-09-24T01:00:00Z", "prs_opened": ["#70"],
        "iterations": [{"at": "2026-09-23T23:00:00Z", "action": "wait", "noop": True},
                       {"at": "2026-09-24T02:00:00Z", "action": "fix-ci", "detail": "pushed", "noop": False}]}))
    out = run(repo, env)
    assert out["resume_notes"][0]["ref"] == "#6041" and out["resume_notes"][0]["slug"] == "6041"
    lp = out["loops"][0]
    assert lp["iterations_count"] == 2 and lp["last_action"] == "fix-ci"
    assert [a["action"] for a in lp["actions_in_window"]] == ["fix-ci"]
    rows = {r["ref"]: r for r in out["ledger"]}
    assert rows["#6041"]["resume_note"]["slug"] == "6041" and rows["#6041"]["actionable"] is True
    assert rows["#604"]["loops"][0]["id"] == "babysit-604-1"


def test_gh_failure_lists_error_and_keeps_worktrees(repo, tmp_path):
    stub = make_stub(tmp_path / "bin", "gh", "exit 1")
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["viewer"]["gh_available"] is False
    assert out["prs"]["all_time_authored"] == [] and out["pr_detail"] == []
    assert any("gh" in e for e in out["errors"])
    assert out["worktrees"][0]["branch"] == "main"


def test_orphan_worktrees(repo, tmp_path):
    env = isolated_env(tmp_path)
    git(repo, "worktree", "add", "-q", "-b", "scratch", (tmp_path / "scratch").as_posix())
    git(repo, "worktree", "add", "-q", "--detach", (tmp_path / "det").as_posix())
    out = run(repo, env)
    orphans = {(o["branch"], o["detached"]) for o in out["orphan_worktrees"]}
    assert ("scratch", False) in orphans and (None, True) in orphans
    assert all(o["primary"] is False for o in out["orphan_worktrees"])
