"""Subprocess tests for scripts/loop-record.sh."""
import json
from pathlib import Path

import pytest

from shell_helpers import SCRIPTS, init_repo, isolated_env, run_script

SCRIPT = SCRIPTS / "loop-record.sh"


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "repo")


def rec(repo, env, *args, expect=0):
    r = run_script(SCRIPT, args=args, env=env, cwd=str(repo))
    assert r.returncode == expect, (r.stdout, r.stderr)
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_create_find_get(repo, tmp_path):
    env = isolated_env(tmp_path)
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--draft", "--max-iterations", "3")
    assert made["id"].startswith("babysit-42-")
    assert Path(made["path"]).is_file()
    full = rec(repo, env, "get", made["id"])
    assert full["state"] == "live" and full["options"]["draft"] is True and full["options"]["merge"] is False
    assert full["budget"] == {"max_iterations": 3, "max_hours": 24, "idle_stop_after": 12}
    assert full["iterations"] == [] and full["prs_opened"] == []
    assert rec(repo, env, "find", "babysit", "#42")["id"] == made["id"]
    assert rec(repo, env, "find", "clear", "#42") is None


def test_two_creates_in_one_second_get_distinct_ids(repo, tmp_path):
    env = isolated_env(tmp_path)
    a = rec(repo, env, "create", "poll", "agent-ready", "")
    b = rec(repo, env, "create", "poll", "agent-ready", "")
    assert a["id"] != b["id"]


def test_append_and_check_ok(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    out = rec(repo, env, "append", lid, "fix-ci", "pushed a1b2c3d")
    assert out == {"id": lid, "iterations": 1, "last_action": "fix-ci"}
    chk = rec(repo, env, "check", lid)
    assert chk["ok"] is True and chk["iterations"] == 1 and chk["trailing_noops"] == 0


def test_check_max_iterations_from_disk(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--max-iterations", "2")["id"]
    rec(repo, env, "append", lid, "wait", "", "--noop")
    rec(repo, env, "append", lid, "fix-ci", "x")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: max_iterations"}


def test_check_idle_counts_trailing_noops_only(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--idle-stop-after", "2")["id"]
    rec(repo, env, "append", lid, "wait", "", "--noop")
    rec(repo, env, "append", lid, "wait", "", "--noop")
    rec(repo, env, "append", lid, "fix-ci", "x")
    assert rec(repo, env, "check", lid)["ok"] is True
    rec(repo, env, "append", lid, "wait", "", "--noop")
    assert rec(repo, env, "check", lid)["ok"] is True
    rec(repo, env, "append", lid, "wait", "", "--noop")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: idle_stop_after"}


def test_check_max_hours(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--max-hours", "1")["id"]
    p = Path(rec(repo, env, "get", lid)["path"])
    data = json.loads(p.read_text())
    data.pop("path", None)
    data["started"] = "2020-01-01T00:00:00Z"
    p.write_text(json.dumps(data))
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: max_hours"}


def test_stop_set_cron_add_pr_list(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "clear", "#9", "main")["id"]
    assert rec(repo, env, "set-cron", lid, "job77")["cron_job_id"] == "job77"
    assert rec(repo, env, "add-pr", lid, "#70")["prs_opened"] == ["#70"]
    assert rec(repo, env, "add-pr", lid, "#70")["prs_opened"] == ["#70"]
    live = rec(repo, env, "list")
    assert [x["id"] for x in live] == [lid] and live[0]["cron_job_id"] == "job77"
    stopped = rec(repo, env, "stop", lid, "initiative clear")
    assert stopped == {"id": lid, "state": "stopped", "stop_reason": "initiative clear", "cron_job_id": "job77"}
    assert rec(repo, env, "list") == []
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "stopped: initiative clear"}
    assert rec(repo, env, "find", "clear", "#9") is None


def test_unknown_id_and_usage(repo, tmp_path):
    env = isolated_env(tmp_path)
    assert rec(repo, env, "get", "nope", expect=1)["error"] == "no such loop"
    r = run_script(SCRIPT, args=("create", "babysit"), env=env, cwd=str(repo))
    assert r.returncode == 2
