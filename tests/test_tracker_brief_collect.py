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

# Same as GH_STUB, except the Actions API prints a JSON error body and
# exits 1 -- ait_gh_out must discard that body (it only keeps stdout on a
# zero exit), so `ci` degrades to null with an errors[] entry rather than
# the raw error body being treated as a CI run.
GH_STUB_CI_FAIL = r'''
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
  *"actions/runs"*)           echo '{"message":"Forbidden"}'; exit 1 ;;
  *) exit 1 ;;
esac
'''

# Same as GH_STUB, except `gh pr view` prints truncated (invalid) JSON on a
# successful exit -- simulates a capped call killed mid-write. The collector
# must validate the shape before `--argjson meta`, not just check emptiness.
GH_STUB_VIEW_TRUNC = r'''
echo "$@" >> "$GH_CALLS"
case "$*" in
  *"api user"*)               echo "me" ;;
  *"pr list"*"--head"*)       if [[ "$*" == *"fix/17-old"* ]]; then echo '[{"number":50,"state":"MERGED","mergedAt":"2026-08-02T00:00:00Z","title":"[#17] landed","url":"https://github.com/acme/widgets/pull/50"}]'; else echo '[]'; fi ;;
  *"pr list"*"--state merged"*) cat "$GH_MERGED" ;;
  *"pr list"*"--state all"*)  cat "$GH_ALL" ;;
  *"pr list"*"review-requested"*) echo '[]' ;;
  *"pr list"*"mentions"*)     echo '[]' ;;
  *"pr list"*)                cat "$GH_OPEN" ;;
  *"pr view"*)                echo '{"reviewDecision":"CHANGES_REQ' ;;
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


def test_commit_run_stamps_given_collection_time(repo, tmp_path):
    env = isolated_env(tmp_path)
    collected = run(repo, env)["generated_at"]
    stamp = run(repo, env, "--commit-run", "2026-09-24T06:00:00Z")
    assert stamp["committed"] == "2026-09-24T06:00:00Z" and "warning" not in stamp
    again = run(repo, env)
    assert again["window"]["since"] == "2026-09-24T06:00:00Z"
    # The command passes the emit's generated_at straight back.
    assert run(repo, env, "--commit-run", collected)["committed"] == collected
    bad = run(repo, env, "--commit-run", "yesterday")
    assert bad["committed"] != "yesterday" and "warning" in bad
    assert json.loads(Path(bad["state_file"]).read_text())["previous_run"] == collected


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
    assert rows["#604"]["merged_pr"] is None  # "#604" must not steal "[#6041]"'s PR
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


def test_poll_loop_label_is_not_a_ledger_key(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub)
    state = Path(run(repo, env)["config"]["state_dir"])
    (state / "loops").mkdir(parents=True)
    (state / "loops" / "poll-agent-ready-1.json").write_text(json.dumps({
        "id": "poll-agent-ready-1", "mode": "poll", "ref": "agent-ready", "branch": None,
        "state": "live", "stop_reason": None, "started": "2026-09-24T01:00:00Z",
        "prs_opened": ["#71"], "iterations": []}))
    out = run(repo, env)
    rows = {r["ref"]: r for r in out["ledger"]}
    assert "agent-ready" not in rows
    assert rows["#71"]["loops"][0]["id"] == "poll-agent-ready-1"
    assert rows["#71"]["actionable"] is True
    assert [lp["id"] for lp in out["loops"]] == ["poll-agent-ready-1"]


def test_corrupt_sibling_loop_record_is_skipped(repo, tmp_path, gh):
    stub, extra = gh
    env = env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub)
    state = Path(run(repo, env)["config"]["state_dir"])
    (state / "loops").mkdir(parents=True)
    (state / "loops" / "aaa-corrupt.json").write_text("{not json")
    (state / "loops" / "babysit-604-1.json").write_text(json.dumps({
        "id": "babysit-604-1", "mode": "babysit", "ref": "#604", "branch": "feat/604-widget",
        "state": "live", "started": "2026-09-24T01:00:00Z", "prs_opened": [], "iterations": []}))
    out = run(repo, env)
    assert [lp["id"] for lp in out["loops"]] == ["babysit-604-1"]
    rows = {r["ref"]: r for r in out["ledger"]}
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


def test_ci_failure_records_error_and_nulls_ci(repo, tmp_path, gh):
    _, extra = gh
    stub = make_stub(tmp_path / "bin-ci-fail", "gh", GH_STUB_CI_FAIL)
    env = env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub)
    out = run(repo, env)
    detail = {d["number"]: d for d in out["pr_detail"]}
    assert detail[70]["ci"] is None
    assert any("actions" in e.lower() for e in out["errors"])


def test_gh_pr_view_truncated_json_does_not_crash(repo, tmp_path, gh):
    _, extra = gh
    stub = make_stub(tmp_path / "bin-view-trunc", "gh", GH_STUB_VIEW_TRUNC)
    env = env_with_path(isolated_env(tmp_path, AIT_SINCE="2026-09-24T00:00:00Z", **extra), stub)
    out = run(repo, env)
    for key in ("generated_at", "window", "viewer", "config", "worktrees", "resume_notes",
                "loops", "prs", "pr_detail", "ledger", "orphan_worktrees", "errors"):
        assert key in out
    assert out["pr_detail"] == []
    assert any("pr view" in e for e in out["errors"])


def test_pr_ref_matches_ait_ref_from_branch(repo, tmp_path):
    # release/1.8.0's leaf ("1.8.0") is a version segment, not an issue
    # number, to ait_ref_from_branch (the leading digit run isn't followed
    # by "-" or end-of-string) -- the PR-side ref computation must agree,
    # never inventing "#1" from the jq-only path the worktree side doesn't
    # take.
    open_prs = [pr(70, "[#604] widget", "feat/604-widget"),
                pr(90, "release prep", "release/1.8.0")]
    all_prs = open_prs + [pr(60, "[#6041] big widget", "feat/6041-big", "MERGED")]
    files = {"GH_OPEN": open_prs, "GH_MERGED": [], "GH_ALL": all_prs,
             "GH_VIEW": PR_VIEW, "GH_THREADS": THREADS, "GH_RUNS": RUNS}
    extra = {"GH_CALLS": (tmp_path / "gh-calls").as_posix()}
    for k, v in files.items():
        p = tmp_path / f"{k}.json"
        p.write_text(json.dumps(v))
        extra[k] = p.as_posix()
    stub = make_stub(tmp_path / "bin-rel", "gh", GH_STUB)
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    out = run(repo, env)
    assert "#1" not in {r["ref"] for r in out["ledger"]}
    alltime = {p_["number"]: p_ for p_ in out["prs"]["all_time_authored"]}
    assert alltime[90]["ref"] is None


def test_branch_ref_map_survives_multiline_jq_output(repo, tmp_path):
    # Regression: BRANCH_REFS is built from a multi-line `jq -r -n ... | .[]`
    # stream. Under a native Windows jq (the one on PATH on this machine),
    # that stream arrives \r\n-terminated when piped, and `$(...)` only
    # strips the trailing newline off the very END of the whole capture --
    # not the \r glued to every earlier line. Only the LAST branch in
    # sorted order came out clean; every other branch's map key carried a
    # stray \r and the lookup for it silently missed, falling back to a
    # (here, absent) title-only ref. "feat/500-alpha" sorts before
    # "zzz-last-branch", so it is exactly the case that broke.
    open_prs = [pr(80, "alpha work", "feat/500-alpha"),
                pr(81, "unrelated last", "zzz-last-branch")]
    files = {"GH_OPEN": open_prs, "GH_MERGED": [], "GH_ALL": open_prs,
             "GH_VIEW": PR_VIEW, "GH_THREADS": THREADS, "GH_RUNS": RUNS}
    extra = {"GH_CALLS": (tmp_path / "gh-calls").as_posix()}
    for k, v in files.items():
        p = tmp_path / f"{k}.json"
        p.write_text(json.dumps(v))
        extra[k] = p.as_posix()
    stub = make_stub(tmp_path / "bin-branchref", "gh", GH_STUB)
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    out = run(repo, env)
    rows = {r["ref"]: r for r in out["ledger"]}
    assert "#500" in rows
    assert rows["#500"]["open_pr"]["number"] == 80


def test_large_fragments_do_not_overflow_argv(repo, tmp_path):
    # Regression: running this collector against a real, active repo (100
    # all-time PRs plus deep-dive detail) printed zero bytes with exit 0 --
    # `jq: Argument list too long` on stderr -- because every fragment rode
    # to jq on argv via --argjson. The OS process argument limit (roughly
    # 32 KB on Windows) made the jq invocation itself never start. Forces
    # that path deterministically with 100 PRs, each carrying a 2 KB title,
    # so ALLTIME alone is well over 64 KB (and BRANCH_REFS, built from 100
    # distinct branches, exercises the same limit on the branch-ref map).
    big_all = [pr(1000 + i, "x" * 2048, f"feat/{1000 + i}-big") for i in range(100)]
    files = {"GH_OPEN": [], "GH_MERGED": [], "GH_ALL": big_all,
             "GH_VIEW": PR_VIEW, "GH_THREADS": THREADS, "GH_RUNS": RUNS}
    extra = {"GH_CALLS": (tmp_path / "gh-calls").as_posix()}
    for k, v in files.items():
        p = tmp_path / f"{k}.json"
        p.write_text(json.dumps(v))
        extra[k] = p.as_posix()
    stub = make_stub(tmp_path / "bin-big", "gh", GH_STUB)
    env = env_with_path(isolated_env(tmp_path, **extra), stub)
    out = run(repo, env)
    for key in ("generated_at", "window", "viewer", "config", "worktrees", "resume_notes",
                "loops", "prs", "pr_detail", "ledger", "orphan_worktrees", "errors"):
        assert key in out
    assert len(out["prs"]["all_time_authored"]) == 100
