"""Subprocess tests for scripts/loop-record.sh."""
import json
from datetime import datetime, timedelta, timezone
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


def test_create_claims_suffix_when_base_id_is_taken(repo, tmp_path):
    """The noclobber claim never reuses an existing file: with the base id
    for the next few seconds already on disk, create takes the -2 suffix."""
    env = isolated_env(tmp_path)
    loops_dir = Path(rec(repo, env, "create", "clear", "#1", "main")["path"]).parent
    now = datetime.now(timezone.utc)
    taken = set()
    for s in range(0, 6):
        stamp = (now + timedelta(seconds=s)).strftime("%Y%m%d%H%M%S")
        base = f"babysit-42-{stamp}"
        (loops_dir / f"{base}.json").write_text('{"placeholder": true}')
        taken.add(base)
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x")
    assert made["id"].endswith("-2") and made["id"][:-2] in taken
    for base in taken:
        assert json.loads((loops_dir / f"{base}.json").read_text()) == {"placeholder": True}


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


def test_check_max_hours_spans_a_reopen(repo, tmp_path):
    """Correct as designed: reopen never resets `started`, so the gap
    between the checkpointing session and the reopening one counts."""
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--max-hours", "2")["id"]
    p = Path(rec(repo, env, "get", lid)["path"])
    started = (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = json.loads(p.read_text())
    data["started"] = started
    p.write_text(json.dumps(data))
    rec(repo, env, "stop", lid, "checkpoint: fresh session", "--transcript", "t/one.jsonl")
    rec(repo, env, "reopen", lid)
    assert rec(repo, env, "get", lid)["started"] == started
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: max_hours"}


def test_check_iteration_budget_ignores_skips(repo, tmp_path):
    """Clear-mode skips are bookkeeping: a cascade of them must not burn
    max_iterations."""
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "clear", "#9", "main", "--max-iterations", "2")["id"]
    for _ in range(3):
        rec(repo, env, "append", lid, "skip", "needs-design")
    rec(repo, env, "append", lid, "start", "#12")
    chk = rec(repo, env, "check", lid)
    assert chk["ok"] is True and chk["iterations"] == 1
    rec(repo, env, "append", lid, "skip", "vague body")
    rec(repo, env, "append", lid, "start", "#13")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: max_iterations"}


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


def test_find_any_after_stop(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    rec(repo, env, "stop", lid, "checkpoint: fresh session")
    assert rec(repo, env, "find", "babysit", "#42") is None
    found = rec(repo, env, "find", "--any", "babysit", "#42")
    assert found["id"] == lid
    assert found["state"] == "stopped"
    assert found["stop_reason"] == "checkpoint: fresh session"


def test_find_any_breaks_started_ties_by_id(repo, tmp_path):
    """Two records sharing one `started` second: the later id (the create
    suffix) is the newest, whatever the glob order."""
    env = isolated_env(tmp_path)
    ids = []
    for _ in range(3):
        lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
        rec(repo, env, "stop", lid, "s")
        ids.append(lid)
    loops_dir = Path(rec(repo, env, "get", ids[0])["path"]).parent
    base = "babysit-42-20260101000000"
    renamed = [base, f"{base}-2", f"{base}-10"]
    for lid, new in zip(ids, renamed):
        data = json.loads((loops_dir / f"{lid}.json").read_text())
        data["id"] = new
        data["started"] = "2026-01-01T00:00:00Z"
        (loops_dir / f"{lid}.json").unlink()
        (loops_dir / f"{new}.json").write_text(json.dumps(data))
    assert rec(repo, env, "find", "--any", "babysit", "#42")["id"] == f"{base}-10"
    (loops_dir / f"{base}-10.json").unlink()
    assert rec(repo, env, "find", "--any", "babysit", "#42")["id"] == f"{base}-2"


def test_find_any_with_no_record_is_null(repo, tmp_path):
    env = isolated_env(tmp_path)
    assert rec(repo, env, "find", "--any", "babysit", "#42") is None


def test_find_any_returns_newest_regardless_of_state(repo, tmp_path):
    env = isolated_env(tmp_path)
    older = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    rec(repo, env, "stop", older, "old stop")
    newer = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    rec(repo, env, "stop", newer, "new stop")
    for lid, started in ((older, "2020-01-01T00:00:00Z"), (newer, "2021-01-01T00:00:00Z")):
        p = Path(rec(repo, env, "get", lid)["path"])
        data = json.loads(p.read_text())
        data.pop("path", None)
        data["started"] = started
        p.write_text(json.dumps(data))
    assert rec(repo, env, "find", "--any", "babysit", "#42")["id"] == newer


def test_unknown_id_and_usage(repo, tmp_path):
    env = isolated_env(tmp_path)
    assert rec(repo, env, "get", "nope", expect=1)["error"] == "no such loop"
    r = run_script(SCRIPT, args=("create", "babysit"), env=env, cwd=str(repo))
    assert r.returncode == 2


def test_corrupt_record_rc1_no_tmp_left_behind(repo, tmp_path):
    env = isolated_env(tmp_path)
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x")
    lid = made["id"]
    p = Path(made["path"])
    p.write_text("{bad")
    tmp = p.parent / (p.name + ".tmp")
    for args in (
        ("append", lid, "fix-ci", "x"),
        ("stop", lid, "some reason"),
        ("add-pr", lid, "#1"),
        ("set-cron", lid, "job1"),
        ("check", lid),
    ):
        out = rec(repo, env, *args, expect=1)
        assert out == {"error": "corrupt record", "id": lid}
        assert not tmp.exists()


@pytest.mark.parametrize("value", ["abc", "007"])
def test_create_bad_numeric_flag_rc2_leaves_no_file(repo, tmp_path, value):
    env = isolated_env(tmp_path)
    r = run_script(
        SCRIPT, args=("create", "babysit", "#1", "feat/1", "--max-iterations", value),
        env=env, cwd=str(repo),
    )
    assert r.returncode == 2
    for loops_dir in Path(env["AIT_STATE_DIR"]).glob("*/loops"):
        assert list(loops_dir.iterdir()) == []


def test_create_success_leaves_no_tmp_file(repo, tmp_path):
    env = isolated_env(tmp_path)
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x")
    p = Path(made["path"])
    assert not (p.parent / (p.name + ".tmp")).exists()


def test_list_and_find_skip_corrupt_file(repo, tmp_path):
    env = isolated_env(tmp_path)
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x")
    lid = made["id"]
    loops_dir = Path(made["path"]).parent
    (loops_dir / "zzz-corrupt.json").write_text("{not json")
    live = rec(repo, env, "list")
    assert [x["id"] for x in live] == [lid]
    assert rec(repo, env, "find", "babysit", "#42")["id"] == lid


def test_stop_records_transcript_or_null(repo, tmp_path):
    env = isolated_env(tmp_path)
    a = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    rec(repo, env, "stop", a, "checkpoint: fresh session", "--transcript", "t/one.jsonl")
    full = rec(repo, env, "get", a)
    assert full["stop_transcript"] == "t/one.jsonl"
    assert full["stop_reason"] == "checkpoint: fresh session"
    b = rec(repo, env, "create", "babysit", "#43", "feat/43-x")["id"]
    assert rec(repo, env, "get", b)["stop_transcript"] is None
    rec(repo, env, "stop", b, "merged")
    assert rec(repo, env, "get", b)["stop_transcript"] is None
    r = run_script(SCRIPT, args=("stop", b, "x", "--transcript"), env=env, cwd=str(repo))
    assert r.returncode == 2
    r = run_script(SCRIPT, args=("stop", b, "x", "--bogus", "y"), env=env, cwd=str(repo))
    assert r.returncode == 2


def test_reopen_keeps_counters(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--merge", "--max-iterations", "3")["id"]
    rec(repo, env, "append", lid, "fix-ci", "x")
    rec(repo, env, "append", lid, "wait", "", "--noop")
    rec(repo, env, "add-pr", lid, "#70")
    before = rec(repo, env, "get", lid)
    rec(repo, env, "stop", lid, "checkpoint: fresh session", "--transcript", "t/one.jsonl")
    out = rec(repo, env, "reopen", lid)
    assert out == {"id": lid, "state": "live", "iterations": 2}
    after = rec(repo, env, "get", lid)
    assert after["state"] == "live"
    assert after["stop_reason"] is None and after["stop_transcript"] is None and after["stopped"] is None
    for k in ("started", "iterations", "prs_opened", "budget", "options"):
        assert after[k] == before[k], k
    assert rec(repo, env, "find", "babysit", "#42")["id"] == lid
    chk = rec(repo, env, "check", lid)
    assert chk["ok"] is True and chk["iterations"] == 2
    rec(repo, env, "append", lid, "fix-ci", "y")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: max_iterations"}


def test_reopen_clears_cron_job_id(repo, tmp_path):
    """The checkpointing session's cron died with it; a reopened record must
    not point a later stop's CronDelete at that dead job."""
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "babysit", "#42", "feat/42-x", "--cron-id", "job77")["id"]
    rec(repo, env, "stop", lid, "checkpoint: fresh session", "--transcript", "t/one.jsonl")
    assert rec(repo, env, "get", lid)["cron_job_id"] == "job77"
    rec(repo, env, "reopen", lid)
    assert rec(repo, env, "get", lid)["cron_job_id"] is None
    assert rec(repo, env, "set-cron", lid, "job88")["cron_job_id"] == "job88"


def test_reopen_unknown_corrupt_and_usage(repo, tmp_path):
    env = isolated_env(tmp_path)
    assert rec(repo, env, "reopen", "nope", expect=1)["error"] == "no such loop"
    made = rec(repo, env, "create", "babysit", "#42", "feat/42-x")
    p = Path(made["path"])
    p.write_text("{bad")
    assert rec(repo, env, "reopen", made["id"], expect=1) == {"error": "corrupt record", "id": made["id"]}
    assert not (p.parent / (p.name + ".tmp")).exists()
    r = run_script(SCRIPT, args=("reopen",), env=env, cwd=str(repo))
    assert r.returncode == 2


# --- recurring mode (cron_job_id schtasks:...) ------------------------------

SCHED = "schtasks:Tracker Loop demo"


def _rewrite(repo, env, lid, **changes):
    p = Path(rec(repo, env, "get", lid)["path"])
    data = json.loads(p.read_text())
    data.pop("path", None)
    data.update(changes)
    p.write_text(json.dumps(data))
    return p


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_scheduled_loop_fired_20_times_idle_never_stops(repo, tmp_path):
    """Each fire: check, nothing to do (wait --noop), window line. The idle
    budget never ends a scheduled loop, and every fire reports skipped."""
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED,
              "--idle-stop-after", "2", "--max-iterations", "3")["id"]
    for _ in range(20):
        chk = rec(repo, env, "check", lid)
        assert chk["ok"] is True and chk["recurring"] is True, chk
        rec(repo, env, "append", lid, "wait", "", "--noop")
        assert rec(repo, env, "window", lid) == {
            "id": lid, "window": "skipped", "line": f"loop {lid} window skipped"}
    full = rec(repo, env, "get", lid)
    assert full["state"] == "live" and full["stop_reason"] is None
    assert rec(repo, env, "check", lid)["trailing_noops"] == 20


def test_scheduled_fire_that_acted_reports_window_ok(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED)["id"]
    rec(repo, env, "check", lid)
    rec(repo, env, "append", lid, "dispatch", "#12")
    assert rec(repo, env, "window", lid)["window"] == "ok"
    rec(repo, env, "check", lid)
    rec(repo, env, "append", lid, "wait-ci", "CI running")
    assert rec(repo, env, "window", lid)["line"] == f"loop {lid} window skipped"


def test_scheduled_max_iterations_spends_the_window_not_the_loop(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED,
              "--max-iterations", "2", "--max-hours", "1")["id"]
    for _ in range(3):
        rec(repo, env, "append", lid, "wait", "", "--noop")
    rec(repo, env, "append", lid, "dispatch", "#12")
    assert rec(repo, env, "check", lid)["ok"] is True
    rec(repo, env, "append", lid, "dispatch", "#13")
    spent = rec(repo, env, "check", lid)
    assert spent["ok"] is False and spent["recurring"] is True
    assert spent["reason"] == "window: max_iterations"
    assert rec(repo, env, "get", lid)["state"] == "live"
    # One window later the acting entries are in the previous window.
    now = datetime.now(timezone.utc)
    p = _rewrite(repo, env, lid, started=_iso(now - timedelta(minutes=70)))
    data = json.loads(p.read_text())
    for it in data["iterations"]:
        it["at"] = _iso(now - timedelta(minutes=65))
    p.write_text(json.dumps(data))
    again = rec(repo, env, "check", lid)
    assert again["ok"] is True and again["iterations"] == 0


def test_scheduled_max_hours_never_stops(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED, "--max-hours", "1")["id"]
    _rewrite(repo, env, lid, started="2020-01-01T00:00:00Z")
    chk = rec(repo, env, "check", lid)
    assert chk["ok"] is True and chk["recurring"] is True
    start = datetime.strptime(chk["window_started"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end = datetime.strptime(chk["window_ends"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert end - start == timedelta(hours=1)
    assert start <= datetime.now(timezone.utc) < end


def test_scheduled_append_keeps_two_windows(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED, "--max-hours", "1")["id"]
    now = datetime.now(timezone.utc)
    old = [{"at": _iso(now - timedelta(hours=h)), "action": "wait", "detail": "", "noop": True}
           for h in (5, 3)]
    recent = [{"at": _iso(now - timedelta(minutes=50)), "action": "dispatch", "detail": "#1", "noop": False}]
    _rewrite(repo, env, lid, started=_iso(now - timedelta(hours=6, minutes=10)), iterations=old + recent)
    out = rec(repo, env, "append", lid, "wait", "", "--noop")
    assert out["iterations"] == 2
    kept = rec(repo, env, "get", lid)["iterations"]
    assert [i["detail"] for i in kept] == ["#1", ""]


def test_check_stamps_last_fire_only_on_a_scheduled_loop(repo, tmp_path):
    env = isolated_env(tmp_path)
    plain = rec(repo, env, "create", "babysit", "#42", "feat/42-x")["id"]
    rec(repo, env, "check", plain)
    assert "last_fire" not in rec(repo, env, "get", plain)
    sched = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED)["id"]
    rec(repo, env, "check", sched)
    assert rec(repo, env, "get", sched)["last_fire"]


def test_stopped_scheduled_loop_checks_as_stopped(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED)["id"]
    rec(repo, env, "stop", lid, "operator stop")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "stopped: operator stop"}


def test_set_cron_schtasks_turns_a_record_recurring(repo, tmp_path):
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--idle-stop-after", "1")["id"]
    rec(repo, env, "append", lid, "wait", "", "--noop")
    assert rec(repo, env, "check", lid) == {"ok": False, "reason": "budget: idle_stop_after"}
    rec(repo, env, "set-cron", lid, SCHED)
    assert rec(repo, env, "check", lid)["ok"] is True


def test_window_unknown_and_usage(repo, tmp_path):
    env = isolated_env(tmp_path)
    assert rec(repo, env, "window", "nope", expect=1)["error"] == "no such loop"
    r = run_script(SCRIPT, args=("window",), env=env, cwd=str(repo))
    assert r.returncode == 2

def test_window_ignores_an_earlier_fires_entry_from_the_same_second(repo, tmp_path):
    """Fires are numbered: an acting entry from the previous fire never makes
    this fire's window ok, whatever its timestamp says."""
    env = isolated_env(tmp_path)
    lid = rec(repo, env, "create", "poll", "agent-ready", "", "--cron-id", SCHED)["id"]
    rec(repo, env, "check", lid)
    rec(repo, env, "append", lid, "dispatch", "#12")
    p = Path(rec(repo, env, "get", lid)["path"])
    data = json.loads(p.read_text())
    data["iterations"][-1]["at"] = "2999-01-01T00:00:00Z"
    p.write_text(json.dumps(data))
    rec(repo, env, "check", lid)
    rec(repo, env, "append", lid, "wait", "", "--noop")
    assert rec(repo, env, "window", lid)["window"] == "skipped"
    assert [i["fire"] for i in rec(repo, env, "get", lid)["iterations"]] == [1, 2]