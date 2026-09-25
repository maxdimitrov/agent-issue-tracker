"""Subprocess tests for scripts/session-brief-collect.sh."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shell_helpers import (SCRIPTS, env_with_path, env_without_command, git, init_repo,
                           isolated_env, make_stub, run_script)

SCRIPT = SCRIPTS / "session-brief-collect.sh"
CONFIG = "schema_version: 1\nbackend: github\ngithub:\n  repo: acme/widgets\n"

PR_JSON = json.dumps({
    "number": 57, "url": "https://github.com/acme/widgets/pull/57", "state": "OPEN",
    "isDraft": False, "mergeable": "MERGEABLE", "baseRefName": "main",
    "updatedAt": "2026-09-24T08:00:00Z", "title": "widget", "reviewDecision": "REVIEW_REQUIRED",
})
RUNS_JSON = json.dumps({"workflow_runs": [
    {"id": 2, "name": "Claude Code", "status": "completed", "conclusion": "skipped",
     "html_url": "https://x/runs/2", "head_sha": "abcdef0123", "created_at": "2026-09-24T08:05:00Z"},
    {"id": 1, "name": "CI", "status": "completed", "conclusion": "failure",
     "html_url": "https://x/runs/1", "head_sha": "abcdef0123", "created_at": "2026-09-24T08:00:00Z"},
]})
JOBS_JSON = json.dumps({"jobs": [{"name": "pytest", "conclusion": "failure", "html_url": "https://x/jobs/9"}]})
THREADS_JSON = json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [
    {"isResolved": False, "isOutdated": False, "path": "a.py", "line": 3,
     "comments": {"totalCount": 1, "nodes": [{"author": {"login": "reviewer"}, "body": "rename this", "createdAt": "2026-09-24T07:00:00Z"}]}},
    {"isResolved": True, "isOutdated": False, "path": "b.py", "line": 9,
     "comments": {"totalCount": 2, "nodes": [{"author": {"login": "reviewer"}, "body": "old", "createdAt": "2026-09-23T07:00:00Z"},
                                             {"author": {"login": "me"}, "body": "done", "createdAt": "2026-09-23T08:00:00Z"}]}},
]}}}}})

GH_STUB = r'''
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     cat "$GH_PR" ;;
  *"actions/runs/1/jobs"*) cat "$GH_JOBS" ;;
  *"actions/runs"*) cat "$GH_RUNS" ;;
  *"api user"*)    echo "me" ;;
  *"graphql"*)     cat "$GH_THREADS" ;;
  *) exit 1 ;;
esac
'''


def run(cwd, env):
    r = run_script(SCRIPT, env=env, cwd=str(cwd))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture
def repo(tmp_path):
    repo = init_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "issue-tracker.yaml").write_text(CONFIG)
    git(repo, "switch", "-q", "-c", "feat/42-widget")
    (repo / "a.txt").write_text("a")
    git(repo, "add", "a.txt", ".claude/issue-tracker.yaml")
    git(repo, "commit", "-q", "-m", "add a")
    return repo


@pytest.fixture
def gh(tmp_path):
    files = {"GH_PR": PR_JSON, "GH_RUNS": RUNS_JSON, "GH_JOBS": JOBS_JSON, "GH_THREADS": THREADS_JSON}
    extra = {}
    for k, v in files.items():
        p = tmp_path / f"{k}.json"
        p.write_text(v)
        extra[k] = p.as_posix()
    return make_stub(tmp_path / "bin", "gh", GH_STUB), extra


def transcript(path, cwd, branch="feat/42-widget", user_turns=3, compactions=0, hours=1.0):
    lines = []
    base = 1_758_700_000
    for i in range(user_turns):
        t = base + int(i * hours * 3600 / max(user_turns - 1, 1))
        stamp = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        lines.append({"type": "user", "timestamp": stamp, "cwd": cwd, "gitBranch": branch,
                      "message": {"content": f"prompt {i}"}})
        lines.append({"type": "assistant", "timestamp": stamp, "cwd": cwd, "gitBranch": branch,
                      "message": {"content": [{"type": "text", "text": "ok"}]}})
    for _ in range(compactions):
        lines.append({"type": "summary", "isCompactSummary": True})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return path


def test_outside_git_is_valid_json(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    out = run(d, isolated_env(tmp_path))
    assert out["repo"]["is_git"] is False
    assert out["git"]["branch"] is None and out["pr"] is None and out["session"] is None
    assert out["handoff"]["resume_path"].endswith("/resume/plain.md")


def test_git_and_ticket_from_branch(repo, tmp_path):
    (repo / "b.txt").write_text("b")
    out = run(repo, isolated_env(tmp_path))
    assert out["repo"]["is_git"] is True and out["repo"]["is_worktree"] is False
    assert out["git"]["branch"] == "feat/42-widget"
    assert out["git"]["dirty_count"] == 1 and out["git"]["dirty_files"][0]["path"] == "b.txt"
    assert out["git"]["last_commit"]["subject"] == "add a"
    assert out["ticket"] == {"key": "#42", "url": "https://github.com/acme/widgets/issues/42"}
    assert out["handoff"]["resume_path"].endswith("/resume/42.md")
    assert out["handoff"]["exists"] is False
    assert out["config"]["backend"] == "github"


def test_base_from_origin_head(repo, tmp_path):
    bare = tmp_path / "origin.git"
    __import__("subprocess").run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", bare.as_posix())
    git(repo, "push", "-q", "origin", "main", "feat/42-widget")
    git(repo, "remote", "set-head", "origin", "main")
    out = run(repo, isolated_env(tmp_path))
    assert out["git"]["base"] == "main"
    assert out["git"]["ahead"] == 1 and out["git"]["behind"] == 0
    assert out["git"]["commits"][0]["subject"] == "add a"


def test_worktree_is_detected(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "fix/7-x", wt.as_posix())
    out = run(wt, isolated_env(tmp_path))
    assert out["repo"]["is_worktree"] is True
    assert out["repo"]["main_repo"].lower() == repo.as_posix().lower()
    assert out["ticket"]["key"] == "#7"


def test_pr_ci_review_from_gh(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    out = run(repo, env)
    assert out["repo"]["gh_available"] is True and out["repo"]["viewer"] == "me"
    assert out["pr"]["number"] == 57
    assert out["ci"]["workflow"] == "CI" and out["ci"]["conclusion"] == "failure"
    assert out["ci"]["failed_jobs"] == [{"name": "pytest", "url": "https://x/jobs/9"}]
    assert len(out["ci"]["all_workflows"]) == 2
    threads = out["review"]["threads"]
    assert out["review"]["awaiting_you_count"] == 1
    assert threads[0]["awaiting_you"] is True and threads[0]["excerpt"] == "rename this"
    assert threads[1]["resolved"] is True and threads[1]["awaiting_you"] is False
    assert out["repo"]["gh_ok"] is True and out["errors"] == []


def test_gh_failure_degrades_to_null(repo, tmp_path):
    stub = make_stub(tmp_path / "bin", "gh", "exit 1")
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["repo"]["gh_available"] is True
    assert out["pr"] is None and out["ci"] is None and out["review"] is None
    assert out["ticket"]["key"] == "#42"
    # A failed gh is not "no PR": gh_ok is false and each failed step is named.
    assert out["repo"]["gh_ok"] is False
    assert "gh api user failed (auth?)" in out["errors"]
    assert "gh pr view failed" in out["errors"]


GH_NO_PR_STUB = r'''
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     echo 'no pull requests found for branch "feat/42-widget"' >&2; exit 1 ;;
  *"actions/runs"*) echo '{"workflow_runs":[]}' ;;
  *"api user"*)    echo "me" ;;
  *) exit 1 ;;
esac
'''


def test_no_pr_for_branch_is_not_an_error(repo, tmp_path):
    stub = make_stub(tmp_path / "bin", "gh", GH_NO_PR_STUB)
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["pr"] is None
    assert out["repo"]["gh_ok"] is True
    assert out["errors"] == []


GH_NO_USER_STUB = r'''
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     cat "$GH_PR" ;;
  *"actions/runs/1/jobs"*) cat "$GH_JOBS" ;;
  *"actions/runs"*) cat "$GH_RUNS" ;;
  *"api user"*)    exit 1 ;;
  *"graphql"*)     cat "$GH_THREADS" ;;
  *) exit 1 ;;
esac
'''


def test_unknown_viewer_marks_no_thread_awaiting_you(repo, tmp_path, gh):
    # With `gh api user` failing, ME is empty; an unresolved thread must not
    # be reported as awaiting the (unknown) viewer.
    _, extra = gh
    stub = make_stub(tmp_path / "bin", "gh", GH_NO_USER_STUB)
    out = run(repo, env_with_path(isolated_env(tmp_path, **extra), stub))
    assert out["repo"]["gh_ok"] is False and out["repo"]["viewer"] is None
    assert out["errors"] == ["gh api user failed (auth?)"]
    assert out["review"]["open_count"] == 1
    assert out["review"]["awaiting_you_count"] == 0
    assert all(t["awaiting_you"] is False for t in out["review"]["threads"])


GH_ERROR_STUB = r'''
err='{"data":null,"errors":[{"message":"x"}]}'
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     echo "$err"; exit 1 ;;
  *"actions/runs"*) echo "$err"; exit 1 ;;
  *"api user"*)    echo "me" ;;
  *"graphql"*)     echo "$err"; exit 1 ;;
  *) exit 1 ;;
esac
'''


def test_gh_error_body_on_nonzero_exit_degrades_to_null(repo, tmp_path):
    # gh writes error bodies to stdout even when it exits non-zero. A naive
    # `cmd || echo ""` still captures that body via command substitution, so
    # this must not turn into a well-formed-looking pr/ci/review payload.
    stub = make_stub(tmp_path / "bin", "gh", GH_ERROR_STUB)
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["repo"]["gh_available"] is True
    assert out["pr"] is None and out["ci"] is None and out["review"] is None


GH_STUB_REVIEW_ERROR = r'''
err='{"data":null,"errors":[{"message":"x"}]}'
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     cat "$GH_PR" ;;
  *"actions/runs/1/jobs"*) cat "$GH_JOBS" ;;
  *"actions/runs"*) cat "$GH_RUNS" ;;
  *"api user"*)    echo "me" ;;
  *"graphql"*)     echo "$err"; exit 1 ;;
  *) exit 1 ;;
esac
'''


def test_review_graphql_error_degrades_to_null(repo, tmp_path, gh):
    # pr/ci succeed (so pr_number is set and the graphql call actually
    # fires); only the graphql call itself returns an error body + exit 1.
    _, extra = gh
    stub = make_stub(tmp_path / "bin", "gh", GH_STUB_REVIEW_ERROR)
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    out = run(repo, env)
    assert out["pr"]["number"] == 57
    assert out["ci"]["conclusion"] == "failure"
    assert out["review"] is None
    assert out["errors"] == ["gh graphql review threads failed"]


def test_session_from_explicit_transcript(repo, tmp_path):
    t = transcript(tmp_path / "t.jsonl", cwd=str(repo), user_turns=30, compactions=1, hours=3.0)
    out = run(repo, isolated_env(tmp_path, AIT_TRANSCRIPT=t.as_posix()))
    s = out["session"]
    assert s["transcript_source"] == "env"
    assert s["turns_user"] == 30 and s["turns_assistant"] == 30
    assert s["compaction_markers"] == 1
    assert s["branches_seen"] == ["feat/42-widget"] and s["tickets_seen"] == ["#42"]
    assert 2.9 <= s["span_hours"] <= 3.1
    assert s["first_prompt"] == "prompt 0" and s["last_prompt"] == "prompt 29"


def test_discovery_prefers_transcript_matching_cwd(repo, tmp_path):
    env = isolated_env(tmp_path)
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    other = transcript(projects / "p-a" / "other.jsonl", cwd=str(sibling), user_turns=9)
    mine = transcript(projects / "p-b" / "mine.jsonl", cwd=str(repo), user_turns=4)
    # The sibling is the newest file, so only the cwd filter can pick mine.
    now = time.time()
    os.utime(mine, (now - 300, now - 300))
    os.utime(other, (now - 10, now - 10))
    out = run(repo, env)
    assert out["session"]["transcript_source"] == "discovered"
    assert out["session"]["transcript"].endswith("mine.jsonl")
    assert out["session"]["turns_user"] == 4


def test_discovery_finds_nothing_when_no_cwd_matches(repo, tmp_path):
    env = isolated_env(tmp_path)
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    transcript(projects / "p-a" / "other.jsonl", cwd=str(tmp_path / "elsewhere"))
    assert run(repo, env)["session"] is None


def test_discovery_does_not_borrow_main_repo_transcript_from_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "fix/9-y", wt.as_posix())
    env = isolated_env(tmp_path)
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    # Only the main repo's cwd is recorded; the worktree has no transcript
    # of its own, and must not fall back to the main checkout's session.
    transcript(projects / "p-a" / "main.jsonl", cwd=str(repo), user_turns=5)
    assert run(wt, env)["session"] is None


def test_tickets_seen_matches_library_issue_branch(repo, tmp_path):
    t = transcript(tmp_path / "t.jsonl", cwd=str(repo), branch="fix/issue-12", user_turns=3)
    out = run(repo, isolated_env(tmp_path, AIT_TRANSCRIPT=t.as_posix()))
    assert out["session"]["tickets_seen"] == ["#12"]


def test_tickets_seen_excludes_version_segment_branch(repo, tmp_path):
    t = transcript(tmp_path / "t.jsonl", cwd=str(repo), branch="release/1.8.0", user_turns=3)
    out = run(repo, isolated_env(tmp_path, AIT_TRANSCRIPT=t.as_posix()))
    assert out["session"]["tickets_seen"] == []


def test_live_loop_record_for_branch_is_surfaced(repo, tmp_path):
    env = isolated_env(tmp_path)
    first = run(repo, env)
    loops = Path(first["config"]["state_dir"]) / "loops"
    loops.mkdir(parents=True)
    (loops / "babysit-42-1.json").write_text(json.dumps({
        "id": "babysit-42-1", "mode": "babysit", "ref": "#42", "branch": "feat/42-widget",
        "state": "live", "stop_reason": None, "cron_job_id": "abc123", "started": "2026-09-24T09:00:00Z",
        "iterations": [{"at": "2026-09-24T09:15:00Z", "action": "fix-ci", "noop": False}],
    }))
    (loops / "stopped.json").write_text(json.dumps({
        "id": "s", "mode": "babysit", "ref": "#42", "branch": "feat/42-widget", "state": "stopped",
        "iterations": [],
    }))
    out = run(repo, env)
    assert out["loop"]["id"] == "babysit-42-1"
    assert out["loop"]["iterations"] == 1 and out["loop"]["last_action"] == "fix-ci"
    assert out["loop"]["cron_job_id"] == "abc123"


def test_corrupt_sibling_loop_record_is_skipped(repo, tmp_path):
    env = isolated_env(tmp_path)
    loops = Path(run(repo, env)["config"]["state_dir"]) / "loops"
    loops.mkdir(parents=True)
    (loops / "aaa-corrupt.json").write_text("{not json")
    (loops / "babysit-42-1.json").write_text(json.dumps({
        "id": "babysit-42-1", "mode": "babysit", "ref": "#42", "branch": "feat/42-widget",
        "state": "live", "started": "2026-09-24T09:00:00Z", "iterations": [],
    }))
    out = run(repo, env)
    assert out["loop"]["id"] == "babysit-42-1"


def test_session_from_session_id_env(repo, tmp_path):
    env = isolated_env(tmp_path, CLAUDE_CODE_SESSION_ID="abc-123")
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    # The cwd does not match, so only the session-id lookup can find it.
    t = transcript(projects / "p-x" / "abc-123.jsonl", cwd=str(tmp_path / "elsewhere"), user_turns=2)
    out = run(repo, env)
    assert out["session"]["transcript_source"] == "session-id"
    assert out["session"]["transcript"].endswith("abc-123.jsonl")
    assert out["session"]["turns_user"] == 2
    assert t.is_file()


def test_discovery_ignores_transcripts_older_than_30_minutes(repo, tmp_path):
    env = isolated_env(tmp_path)
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    old = transcript(projects / "p-a" / "old.jsonl", cwd=str(repo), user_turns=2)
    then = time.time() - 3600
    os.utime(old, (then, then))
    assert run(repo, env)["session"] is None


def test_base_probed_when_origin_head_unset(repo, tmp_path):
    bare = tmp_path / "origin.git"
    __import__("subprocess").run(["git", "init", "-q", "--bare", str(bare)], check=True)
    git(repo, "remote", "add", "origin", bare.as_posix())
    # origin/main = init (2 behind HEAD), origin/master = "add a" (1 behind):
    # the candidate this branch diverged from last wins.
    git(repo, "push", "-q", "origin", "main", "HEAD:refs/heads/master")
    (repo / "b.txt").write_text("b")
    git(repo, "add", "b.txt")
    git(repo, "commit", "-q", "-m", "add b")
    git(repo, "fetch", "-q", "origin")
    # Newer git records origin/HEAD on fetch; drop it so the probe runs.
    git(repo, "remote", "set-head", "origin", "--delete")
    assert not (repo / ".git" / "refs" / "remotes" / "origin" / "HEAD").exists()
    out = run(repo, isolated_env(tmp_path))
    assert out["git"]["base"] == "master"
    assert out["git"]["ahead"] == 1 and out["git"]["behind"] == 0
    assert [c["subject"] for c in out["git"]["commits"]] == ["add b"]


def test_detached_head(repo, tmp_path, gh):
    stub, extra = gh
    git(repo, "checkout", "-q", "--detach")
    out = run(repo, env_with_path(isolated_env(tmp_path, **extra), stub))
    assert out["git"]["detached"] is True
    assert out["git"]["branch"] and "/" not in out["git"]["branch"]
    assert out["ticket"]["key"] is None
    assert out["pr"] is None and out["errors"] == []


def test_gh_missing_from_path(repo, tmp_path):
    env = env_without_command(isolated_env(tmp_path), tmp_path, "gh")
    out = run(repo, env)
    assert out["repo"]["gh_available"] is False and out["repo"]["gh_ok"] is False
    assert out["pr"] is None and out["ci"] is None and out["review"] is None
    assert out["errors"] == ["gh unavailable -- PR data skipped"]
    assert out["ticket"]["key"] == "#42"


def test_jq_missing_from_path(repo, tmp_path):
    env = env_without_command(isolated_env(tmp_path), tmp_path, "jq")
    out = run(repo, env)
    assert out["error"] == "jq not found on PATH"
    assert out["errors"] == ["jq not found on PATH"] and out["session"] is None


GH_LOG_STUB = r'''
echo "$@" >> "$GH_CALLS"
case "$*" in
  *"repo view"*)   echo "acme/widgets" ;;
  *"pr view"*)     echo 'no pull requests found' >&2; exit 1 ;;
  *"actions/runs"*) echo '{"workflow_runs":[]}' ;;
  *"api user"*)    echo "me" ;;
  *) exit 1 ;;
esac
'''


def test_actions_branch_query_is_url_encoded(repo, tmp_path):
    git(repo, "switch", "-q", "-c", "feat/a+b#1")
    calls = tmp_path / "gh-calls"
    stub = make_stub(tmp_path / "bin", "gh", GH_LOG_STUB)
    out = run(repo, env_with_path(isolated_env(tmp_path, GH_CALLS=calls.as_posix()), stub))
    assert out["errors"] == []
    runs = [ln for ln in calls.read_text().splitlines() if "actions/runs" in ln]
    assert runs and "branch=feat%2Fa%2Bb%231&per_page=30" in runs[0]


def test_staged_rename_reports_new_path(repo, tmp_path):
    git(repo, "mv", "a.txt", "renamed.txt")
    out = run(repo, isolated_env(tmp_path))
    files = out["git"]["dirty_files"]
    assert files == [{"status": "R ", "path": "renamed.txt", "orig_path": "a.txt"}]
