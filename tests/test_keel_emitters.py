"""keel reporting: loop-record.sh and keel-emit.sh against a stub `keel`.

keel is optional. With its CLI on PATH the scripts spool events and
heartbeats through it; without it (or with AIT_KEEL=0) they behave exactly
as before. conftest turns reporting off for every other test; these turn it
back on against a stub that records each call.
"""
import json
import time
from pathlib import Path

import pytest

from shell_helpers import (SCRIPTS, env_with_path, env_without_command, git, init_repo,
                           isolated_env, make_stub, run_lib, run_script)

LOOP = SCRIPTS / "loop-record.sh"
EMIT = SCRIPTS / "keel-emit.sh"

# Records each call as one JSON array of its arguments; `beat --payload`
# exits 2 (a usage error) when KEEL_BEAT_NO_PAYLOAD is set, as a keel that
# predates the option would.
KEEL_STUB = r'''
printf '%s\037' "$@" | jq -Rsc 'split("\u001f")[:-1]' >> "$KEEL_CALLS"
if [ -n "${KEEL_SLEEP:-}" ]; then sleep "$KEEL_SLEEP"; fi
case "$1 $*" in
  "beat "*--payload*) [ -n "${KEEL_BEAT_NO_PAYLOAD:-}" ] && exit 2 ;;
esac
case "$1" in
  watermark) [ "${2:-}" = get ] && [ -n "${KEEL_WATERMARK:-}" ] && printf '%s\n' "$KEEL_WATERMARK" ;;
  brief) [ -n "${KEEL_BRIEF:-}" ] && cat "$KEEL_BRIEF" ;;
esac
exit "${KEEL_RC:-0}"
'''


@pytest.fixture
def repo(tmp_path):
    r = init_repo(tmp_path / "repo")
    (r / ".keel").mkdir()
    (r / ".keel" / "project.yaml").write_text("schema: 1\nslug: demo\norg: personal\n")
    return r


@pytest.fixture
def keel_env(tmp_path):
    """isolated_env with the stub keel first on PATH and reporting on."""
    bin_dir = make_stub(tmp_path / "keel-bin", "keel", KEEL_STUB)
    env = env_with_path(isolated_env(tmp_path), bin_dir)
    env["AIT_KEEL"] = "1"
    env["KEEL_CALLS"] = (tmp_path / "keel-calls").as_posix()
    return env


def calls(env):
    p = Path(env["KEEL_CALLS"])
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def opt(call, name):
    """The value after option `name` in one recorded call, or None."""
    return call[call.index(name) + 1] if name in call else None


def lr(repo, env, *args, expect=0):
    r = run_script(LOOP, args=args, env=env, cwd=str(repo))
    assert r.returncode == expect, (r.stdout, r.stderr)
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_create_spools_loop_created_and_a_heartbeat(repo, keel_env):
    lid = lr(repo, keel_env, "create", "poll", "agent-ready", "", "--interval", "15m")["id"]
    event, beat = calls(keel_env)
    assert event[:2] == ["event", "loop.created"]
    assert event[-1] == "--spool"
    assert opt(event, "--project") == "demo"
    assert opt(event, "--actor-kind") == "claude_session"
    assert opt(event, "--idem-key") == f"loop.created:{lid}"
    payload = json.loads(opt(event, "--payload"))
    assert payload == {"id": lid, "mode": "poll", "ref": "agent-ready", "branch": None,
                       "cron_id": None, "interval": "15m"}
    assert beat[:2] == ["beat", f"loop:{lid}"]
    assert opt(beat, "--next") == "30m"
    assert opt(beat, "--project") == "demo"
    assert json.loads(opt(beat, "--payload")) == {"cron_id": None, "mode": "poll", "ref": "agent-ready"}
    assert beat[-1] == "--spool"


def test_scheduled_loop_beats_with_its_cron_id_as_a_runner(repo, keel_env):
    lid = lr(repo, keel_env, "create", "poll", "agent-ready", "",
             "--cron-id", "schtasks:Tracker Loop demo", "--interval", "1h")["id"]
    event, beat = calls(keel_env)
    assert opt(event, "--actor-kind") == "runner"
    assert json.loads(opt(event, "--payload"))["cron_id"] == "schtasks:Tracker Loop demo"
    assert opt(beat, "--next") == "60m"
    assert json.loads(opt(beat, "--payload"))["cron_id"] == "schtasks:Tracker Loop demo"
    assert beat[1] == f"loop:{lid}"


def test_append_spools_loop_iteration_only_for_non_noops(repo, keel_env):
    lid = lr(repo, keel_env, "create", "babysit", "#42", "feat/42-x")["id"]
    before = len(calls(keel_env))
    lr(repo, keel_env, "append", lid, "wait", "", "--noop")
    assert len(calls(keel_env)) == before
    lr(repo, keel_env, "append", lid, "fix-ci", "pushed a1b2c3d")
    (event,) = calls(keel_env)[before:]
    assert event[:2] == ["event", "loop.iteration"]
    payload = json.loads(opt(event, "--payload"))
    assert payload["id"] == lid and payload["action"] == "fix-ci" and payload["detail"] == "pushed a1b2c3d"


def test_stop_spools_loop_stopped_with_the_reason(repo, keel_env):
    lid = lr(repo, keel_env, "create", "clear", "#9", "main")["id"]
    lr(repo, keel_env, "stop", lid, "initiative clear")
    event = calls(keel_env)[-1]
    assert event[:2] == ["event", "loop.stopped"]
    payload = json.loads(opt(event, "--payload"))
    assert payload["id"] == lid and payload["reason"] == "initiative clear"
    assert opt(event, "--idem-key").startswith(f"loop.stopped:{lid}:")


def test_check_beats_a_live_loop_and_not_a_stopped_one(repo, keel_env):
    lid = lr(repo, keel_env, "create", "babysit", "#42", "feat/42-x")["id"]
    n = len(calls(keel_env))
    lr(repo, keel_env, "check", lid)
    assert [c[0] for c in calls(keel_env)[n:]] == ["beat"]
    lr(repo, keel_env, "stop", lid, "merged")
    n = len(calls(keel_env))
    lr(repo, keel_env, "check", lid)
    assert calls(keel_env)[n:] == []


def test_reopen_beats(repo, keel_env):
    lid = lr(repo, keel_env, "create", "babysit", "#42", "feat/42-x")["id"]
    lr(repo, keel_env, "stop", lid, "checkpoint: fresh session")
    n = len(calls(keel_env))
    lr(repo, keel_env, "reopen", lid)
    assert [c[:2] for c in calls(keel_env)[n:]] == [["beat", f"loop:{lid}"]]


def test_beat_falls_back_without_payload_on_an_older_keel(repo, keel_env):
    env = dict(keel_env, KEEL_BEAT_NO_PAYLOAD="1")
    lid = lr(repo, env, "create", "poll", "agent-ready", "")["id"]
    beats = [c for c in calls(env) if c[0] == "beat"]
    assert len(beats) == 2
    assert "--payload" in beats[0] and "--payload" not in beats[1]
    assert beats[1][:2] == ["beat", f"loop:{lid}"]


def test_no_project_yaml_means_no_project_flag(tmp_path, keel_env):
    bare = init_repo(tmp_path / "bare")
    lr(bare, keel_env, "create", "poll", "agent-ready", "")
    assert all("--project" not in c for c in calls(keel_env))


def test_a_failing_or_hanging_keel_never_changes_the_result(repo, keel_env):
    env = dict(keel_env, KEEL_RC="1")
    made = lr(repo, env, "create", "babysit", "#42", "feat/42-x")
    assert set(made) == {"id", "path"}
    slow = dict(keel_env, KEEL_SLEEP="20", AIT_KEEL_TIMEOUT="1")
    started = time.monotonic()
    out = lr(repo, slow, "append", made["id"], "fix-ci", "x")
    assert out == {"id": made["id"], "iterations": 1, "last_action": "fix-ci"}
    assert time.monotonic() - started < 15


def test_aitkeel0_turns_reporting_off(repo, keel_env):
    env = dict(keel_env, AIT_KEEL="0")
    lid = lr(repo, env, "create", "poll", "agent-ready", "")["id"]
    lr(repo, env, "append", lid, "start", "#12")
    lr(repo, env, "stop", lid, "operator stop")
    assert calls(env) == []


def test_without_keel_on_path_records_and_output_are_unchanged(repo, tmp_path):
    """The same sequence with keel absent and AIT_KEEL unset: no keel field
    in the record, the same JSON on stdout as with reporting off."""
    base = isolated_env(tmp_path)
    off = dict(base, AIT_KEEL="0")
    absent = env_without_command(base, tmp_path, "keel")
    absent.pop("AIT_KEEL", None)
    outs = []
    for env in (off, absent):
        lid = lr(repo, env, "create", "babysit", "#42", "feat/42-x", "--max-iterations", "3")["id"]
        seq = [lr(repo, env, "append", lid, "fix-ci", "x"),
               lr(repo, env, "check", lid),
               lr(repo, env, "stop", lid, "merged")]
        full = lr(repo, env, "get", lid)
        for k in ("id", "path", "started", "stopped"):
            full.pop(k)
        for it in full["iterations"]:
            it.pop("at")
        outs.append(([{k: v for k, v in s.items() if k != "id"} for s in seq], full))
    assert outs[0] == outs[1]
    assert "last_fire" not in outs[1][1]


def test_keel_emit_spools_a_work_event(repo, keel_env):
    r = run_script(EMIT, args=("work.started", "ref=#42", "branch=feat/42-x"), env=keel_env, cwd=str(repo))
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    (event,) = calls(keel_env)
    assert event[:2] == ["event", "work.started"]
    assert opt(event, "--project") == "demo"
    assert opt(event, "--actor-kind") == "claude_session"
    assert json.loads(opt(event, "--payload")) == {"ref": "#42", "branch": "feat/42-x"}
    assert event[-1] == "--spool"


def test_keel_emit_is_silent_without_keel(repo, tmp_path):
    env = env_without_command(isolated_env(tmp_path), tmp_path, "keel")
    env.pop("AIT_KEEL", None)
    r = run_script(EMIT, args=("work.done", "ref=#42"), env=env, cwd=str(repo))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    r = run_script(EMIT, args=(), env=env, cwd=str(repo))
    assert (r.returncode, r.stdout) == (0, "")


def test_keel_project_reads_the_main_checkout_from_a_linked_worktree(repo, tmp_path):
    """A runner worktree without the (untracked here) file still finds the
    primary checkout's slug."""
    git(repo, "worktree", "add", "-q", "-b", "runner", (tmp_path / "runner").as_posix())
    r = run_lib("ait_keel_project .", cwd=str(tmp_path / "runner"))
    assert (r.returncode, r.stdout) == (0, "demo")
    r = run_lib("ait_keel_project .", cwd=str(tmp_path))
    assert r.returncode == 1 and r.stdout == ""


# --- tracker-brief-collect.sh ------------------------------------------------

BRIEF = SCRIPTS / "tracker-brief-collect.sh"
CONFIG = "schema_version: 1\nbackend: github\ngithub:\n  repo: acme/widgets\n"
KEEL_BRIEF_JSON = [{"project": "demo", "generated_at": "2026-10-22T08:00:00+00:00", "facts": [],
                    "heartbeats": [], "runs": [], "from_cache": True, "cache_age_seconds": 120,
                    "findings": [{"severity": "warn", "check_id": "job.missed", "title": "nightly missed",
                                  "fingerprint": "job.missed:demo:nightly", "state": "open"}]}]


@pytest.fixture
def brief_repo(repo):
    (repo / ".claude").mkdir()
    (repo / ".claude" / "issue-tracker.yaml").write_text(CONFIG)
    return repo


def collect(repo, env, *args):
    r = run_script(BRIEF, args=args, env=env, cwd=str(repo))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_brief_without_keel_has_no_keel_key(brief_repo, tmp_path):
    env = env_without_command(isolated_env(tmp_path), tmp_path, "keel")
    env.pop("AIT_KEEL", None)
    out = collect(brief_repo, env)
    assert "keel" not in out
    committed = collect(brief_repo, env, "--commit-run", "2026-10-01T00:00:00Z")
    assert set(committed) == {"committed", "state_file"}


def test_brief_window_starts_at_a_later_keel_watermark(brief_repo, keel_env, tmp_path):
    collect(brief_repo, dict(keel_env, AIT_KEEL="0"), "--commit-run", "2026-10-01T00:00:00Z")
    brief_file = tmp_path / "keel-brief.json"
    brief_file.write_text(json.dumps(KEEL_BRIEF_JSON))
    env = dict(keel_env, KEEL_WATERMARK="2026-10-20T09:30:00Z", KEEL_BRIEF=brief_file.as_posix())
    out = collect(brief_repo, env)
    assert out["window"]["since"] == "2026-10-20T09:30:00Z"
    assert out["window"]["first_run"] is False
    k = out["keel"]
    assert k["project"] == "demo" and k["watermark"] == "2026-10-20T09:30:00Z"
    assert k["window_from_keel"] is True and k["error"] is None
    assert k["watermark_scope"].startswith("tracker-brief/repo-")
    assert k["findings"] == KEEL_BRIEF_JSON[0]["findings"]
    assert k["cache_age_seconds"] == 120
    gets = [c for c in calls(env) if c[:2] == ["watermark", "get"]]
    assert gets == [["watermark", "get", "tracker-brief", k["watermark_scope"].split("/", 1)[1]]]
    assert all(c[:2] != ["watermark", "set"] for c in calls(env))
    brief_calls = [c for c in calls(env) if c[0] == "brief"]
    assert brief_calls == [["brief", "--project", "demo", "--json", "--cached"]]


def test_brief_keeps_a_later_local_stamp(brief_repo, keel_env):
    collect(brief_repo, dict(keel_env, AIT_KEEL="0"), "--commit-run", "2026-10-21T00:00:00Z")
    out = collect(brief_repo, dict(keel_env, KEEL_WATERMARK="2026-10-20T09:30:00Z"))
    assert out["window"]["since"] == "2026-10-21T00:00:00Z"
    assert out["keel"]["window_from_keel"] is False
    assert out["keel"]["findings"] is None and out["keel"]["error"]


def test_brief_aitsince_wins_and_skips_the_watermark(brief_repo, keel_env):
    out = collect(brief_repo, dict(keel_env, AIT_SINCE="2026-10-02T00:00:00Z",
                                   KEEL_WATERMARK="2026-10-20T09:30:00Z"))
    assert out["window"]["since"] == "2026-10-02T00:00:00Z"
    assert out["keel"]["watermark"] is None
    assert all(c[:2] != ["watermark", "get"] for c in calls(keel_env))


def test_brief_ignores_a_malformed_watermark(brief_repo, keel_env):
    out = collect(brief_repo, dict(keel_env, KEEL_WATERMARK="yesterday"))
    assert out["window"]["first_run"] is True
    assert any("keel watermark" in e for e in out["errors"])


def test_commit_run_sets_the_keel_watermark(brief_repo, keel_env):
    out = collect(brief_repo, keel_env, "--commit-run", "2026-10-22T07:00:00Z")
    assert out["committed"] == "2026-10-22T07:00:00Z" and out["keel_watermark"] == "set"
    (sets,) = [c for c in calls(keel_env) if c[:2] == ["watermark", "set"]]
    assert sets[2] == "tracker-brief" and sets[4] == "2026-10-22T07:00:00Z"
    assert "--spool" not in sets
    failed = collect(brief_repo, dict(keel_env, KEEL_RC="1"), "--commit-run", "2026-10-22T08:00:00Z")
    assert failed["committed"] == "2026-10-22T08:00:00Z" and failed["keel_watermark"] == "failed"