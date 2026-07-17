"""Subprocess tests for hooks/session-title.sh (SessionStart hook)."""
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "session-title.sh"

CONFIG_GITHUB = "schema_version: 1\nbackend: github\ngithub:\n  repo: acme/widgets\n"


def git(proj, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(proj), *args],
        check=True, capture_output=True,
    )


@pytest.fixture
def project(tmp_path):
    """Temp git repo with a committed main branch and a tracker config."""
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    git(proj, "commit", "--allow-empty", "-m", "init")
    (proj / ".claude").mkdir()
    (proj / ".claude" / "issue-tracker.yaml").write_text(CONFIG_GITHUB)
    return proj


@pytest.fixture
def hook_env(tmp_path):
    """Isolated cache dir; AI stage disabled for determinism."""
    env = dict(os.environ)
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["AIT_TITLE_NO_AI"] = "1"
    env.pop("AIT_TITLE_GUARD", None)
    return env


def payload_for(proj, session_id="s1", source="startup", **kw):
    p = {
        "session_id": session_id,
        "transcript_path": str(proj / "transcript.jsonl"),
        "cwd": str(proj),
        "hook_event_name": "SessionStart",
        "source": source,
    }
    p.update(kw)
    return p


def run_hook(payload, env, stub_bin=None):
    if stub_bin is not None:
        env = dict(env)
        env["PATH"] = f"{stub_bin}:{env['PATH']}"
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [str(HOOK)], input=data, text=True, capture_output=True, env=env, timeout=30
    )


def title_of(result):
    """Parse the emitted title, or None when the hook stayed silent."""
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    if not out:
        return None
    doc = json.loads(out)
    assert doc["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    return doc["hookSpecificOutput"]["sessionTitle"]


def state_dir_of(env):
    return Path(env["XDG_CACHE_HOME"]) / "agent-issue-tracker" / "session-titles"


def make_stub(tmp_path, name, body):
    """Drop an executable stub named `name` into a bin dir; return the dir."""
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir(exist_ok=True)
    p = stub_bin / name
    p.write_text(f"#!/usr/bin/env bash\n{body}\n")
    p.chmod(0o755)
    return stub_bin


# --- Task 1: gates ----------------------------------------------------------

def test_recursion_guard_exits_silently(project, hook_env):
    env = dict(hook_env, AIT_TITLE_GUARD="1")
    r = run_hook(payload_for(project), env)
    assert r.returncode == 0 and r.stdout == ""


def test_malformed_stdin_is_silent(project, hook_env):
    r = run_hook("this is not json {", hook_env)
    assert r.returncode == 0 and r.stdout == ""


def test_no_config_file_is_a_noop(tmp_path, hook_env):
    bare = tmp_path / "bare"
    bare.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(bare)], check=True)
    r = run_hook(payload_for(bare), hook_env)
    assert r.returncode == 0 and r.stdout == ""


def test_session_titles_false_disables(project, hook_env):
    cfg = project / ".claude" / "issue-tracker.yaml"
    cfg.write_text(cfg.read_text() + "session_titles: false\n")
    r = run_hook(payload_for(project), hook_env)
    assert r.returncode == 0 and r.stdout == ""


def test_ignored_sources_are_noops(project, hook_env):
    for source in ("clear", "compact"):
        r = run_hook(payload_for(project, source=source), hook_env)
        assert r.returncode == 0 and r.stdout == ""


def test_broken_jq_fails_open(project, hook_env, tmp_path):
    stub_bin = make_stub(tmp_path, "jq", "exit 1")
    r = run_hook(payload_for(project), hook_env, stub_bin=stub_bin)
    assert r.returncode == 0 and r.stdout == ""


def test_preexisting_manual_title_gets_pinned(project, hook_env):
    r = run_hook(
        payload_for(project, session_id="pin1", session_title="my special session"),
        hook_env,
    )
    assert r.returncode == 0 and r.stdout == ""
    assert (state_dir_of(hook_env) / "pin1.pinned").exists()


def test_platform_default_title_is_not_pinned(project, hook_env):
    # "<basename cwd>-xx" is the platform default naming pattern — not manual.
    r = run_hook(
        payload_for(project, session_id="pin2", session_title="proj-3f"),
        hook_env,
    )
    assert r.returncode == 0
    assert not (state_dir_of(hook_env) / "pin2.pinned").exists()


def test_default_title_with_regex_metachar_dirname(tmp_path):
    # "proj+abc-3f" must be recognized as the platform default for dir "proj+abc".
    proj = tmp_path / "proj+abc"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True)
    git(proj, "commit", "--allow-empty", "-m", "init")
    (proj / ".claude").mkdir()
    (proj / ".claude" / "issue-tracker.yaml").write_text(CONFIG_GITHUB)
    env = dict(os.environ)
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["AIT_TITLE_NO_AI"] = "1"
    r = run_hook(payload_for(proj, session_id="meta1", session_title="proj+abc-3f"), env)
    assert r.returncode == 0
    assert not (Path(env["XDG_CACHE_HOME"]) / "agent-issue-tracker" / "session-titles" / "meta1.pinned").exists()
