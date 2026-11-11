"""Subprocess tests for hooks/nudge.sh (SessionStart resume + Stop nudges)."""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from shell_helpers import bash_path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "nudge.sh"

CONFIG_GITHUB = "schema_version: 1\nbackend: github\ngithub:\n  repo: acme/widgets\n"
CONFIG_JIRA = ("schema_version: 1\nbackend: jira\njira:\n  site: x.atlassian.net\n"
               "  project: PROJ\n")
DEFERRAL = "Done. The retry policy is out of scope for this PR; I'll leave it."


def git(proj, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
         "-C", str(proj), *args],
        check=True, capture_output=True, stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(proj)], check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)
    git(proj, "commit", "--allow-empty", "-m", "init")
    (proj / ".claude").mkdir()
    (proj / ".claude" / "issue-tracker.yaml").write_text(CONFIG_GITHUB)
    return proj


@pytest.fixture
def hook_env(tmp_path):
    env = dict(os.environ)
    for k in ("AIT_NUDGES", "AIT_NUDGES_OFF"):
        env.pop(k, None)
    env["XDG_CACHE_HOME"] = (tmp_path / "cache").as_posix()
    env["AIT_STATE_DIR"] = (tmp_path / "state").as_posix()
    env["CLAUDE_PLUGIN_DATA"] = (tmp_path / "plugin-data").as_posix()
    env["HOME"] = (tmp_path / "home").as_posix()
    env["GH_CONFIG_DIR"] = (tmp_path / "gh-config").as_posix()
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    (tmp_path / "gh-config").mkdir(parents=True, exist_ok=True)
    return env


def rec_bash(cmd, name="Bash", sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain, "message": {"content": [
        {"type": "tool_use", "name": name, "input": {"command": cmd}}]}}


def rec_skill(skill):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}]}}


def rec_user(text):
    return {"type": "user", "message": {"content": text}}


def write_transcript(proj, records, garbage_first=False):
    p = proj / "transcript.jsonl"
    lines = ['{"type": "assistant", "mess'] if garbage_first else []
    lines += [json.dumps(r) for r in records]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


WORKED = [rec_user("fix it"), rec_bash("git commit -m 'x'")]


def stop_payload(proj, session_id="s1", message=DEFERRAL, **kw):
    p = {
        "session_id": session_id,
        "transcript_path": (proj / "transcript.jsonl").as_posix(),
        "cwd": proj.as_posix(),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": message,
    }
    p.update(kw)
    return p


def run_hook(payload, env, stub_bin=None):
    if stub_bin is not None:
        env = dict(env)
        env["PATH"] = str(stub_bin) + os.pathsep + env["PATH"]
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([bash_path(), str(HOOK)], input=data, text=True,
                          encoding="utf-8", capture_output=True, env=env, timeout=60)


def message_of(result):
    """The systemMessage, or None when the hook stayed silent."""
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    if not out:
        return None
    doc = json.loads(out)
    assert list(doc) == ["systemMessage"], doc
    assert doc["systemMessage"].startswith("[tracker] ")
    return doc["systemMessage"]


def silent(result):
    return result.returncode == 0 and result.stdout == ""


# --- deferral ---------------------------------------------------------------

def test_deferral_fires_once_per_session(project, hook_env):
    write_transcript(project, WORKED)
    m = message_of(run_hook(stop_payload(project), hook_env))
    assert m == "[tracker] Scope was deferred this turn and nothing was filed -- /file-followup?"
    assert silent(run_hook(stop_payload(project), hook_env))


def test_deferral_new_session_fires_again(project, hook_env):
    write_transcript(project, WORKED)
    assert message_of(run_hook(stop_payload(project, session_id="a"), hook_env))
    assert message_of(run_hook(stop_payload(project, session_id="b"), hook_env))


@pytest.mark.parametrize("message", [
    "We'll handle the Jira path in a separate PR.",
    "Leaving the banner for a follow-up.",
    "That belongs in a later phase.",
    "I filed nothing yet but this needs a follow-up issue.",
    "Deferring the cache rework to a follow-up.",
    "Let's do that in a follow up PR.",
    "We’ll handle the banner later.",
])
def test_deferral_lexicon_matches(project, hook_env, message):
    write_transcript(project, WORKED)
    assert message_of(run_hook(stop_payload(project, message=message), hook_env))


@pytest.mark.parametrize("message", [
    "Added the follow-up handling to the parser.",
    "TODO list updated.",
    "All done, tests pass.",
])
def test_deferral_bare_words_do_not_match(project, hook_env, message):
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project, message=message), hook_env))


def test_deferral_needs_work_signal(project, hook_env):
    write_transcript(project, [rec_user("let's design"), rec_bash("ls")])
    assert silent(run_hook(stop_payload(project), hook_env))


def test_deferral_gh_pr_create_is_work(project, hook_env):
    write_transcript(project, [rec_bash("gh pr create --title x", name="PowerShell")])
    assert message_of(run_hook(stop_payload(project), hook_env))


def test_deferral_git_dash_c_commit_counts(project, hook_env):
    write_transcript(project, [rec_bash("git -C F:/wt/feat+x commit -m 'y'", name="PowerShell")])
    assert message_of(run_hook(stop_payload(project), hook_env))


def test_deferral_sidechain_work_does_not_count(project, hook_env):
    write_transcript(project, [rec_bash("git commit -m x", sidechain=True)])
    assert silent(run_hook(stop_payload(project), hook_env))


@pytest.mark.parametrize("filed", [
    rec_bash("gh issue create --title x --body y"),
    rec_skill("agent-issue-tracker:file-followup"),
    rec_skill("agent-issue-tracker:followup-tracking"),
    rec_user("/file-followup the retry policy"),
    {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "mcp__claude_ai_Atlassian__createJiraIssue",
         "input": {"summary": "x"}}]}},
])
def test_deferral_silent_when_filed(project, hook_env, filed):
    write_transcript(project, WORKED + [filed])
    assert silent(run_hook(stop_payload(project), hook_env))


@pytest.mark.parametrize("field", ["last_assistant_message", "hook_event_name", "session_id"])
def test_array_typed_payload_field_is_never_executed(project, hook_env, field):
    payload = stop_payload(project, session_id="abc")
    payload[field] = ["Stop" if field == "hook_event_name" else "x", "echo", "INJECTED"]
    assert silent(run_hook(payload, hook_env))


def test_deferral_silent_after_slash_command_filing(project, hook_env):
    write_transcript(project, WORKED + [rec_user(
        "<command-message>agent-issue-tracker:file-followup</command-message>\n"
        "<command-name>/agent-issue-tracker:file-followup</command-name>")])
    assert silent(run_hook(stop_payload(project), hook_env))


def test_deferral_tolerates_garbage_lines(project, hook_env):
    write_transcript(project, WORKED, garbage_first=True)
    assert message_of(run_hook(stop_payload(project), hook_env))


def test_deferral_windows_style_paths(project, hook_env):
    write_transcript(project, WORKED)
    p = stop_payload(project, cwd=str(project),
                     transcript_path=str(project / "transcript.jsonl"))
    assert message_of(run_hook(p, hook_env))


def test_deferral_stop_hook_active_is_silent(project, hook_env):
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project, stop_hook_active=True), hook_env))


def test_deferral_missing_message_is_silent(project, hook_env):
    write_transcript(project, WORKED)
    p = stop_payload(project)
    del p["last_assistant_message"]
    assert silent(run_hook(p, hook_env))


def test_deferral_missing_transcript_is_silent(project, hook_env):
    p = stop_payload(project)
    del p["transcript_path"]
    assert silent(run_hook(p, hook_env))


# --- gates ------------------------------------------------------------------

def test_no_config_is_silent(project, hook_env):
    (project / ".claude" / "issue-tracker.yaml").unlink()
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project), hook_env))


def test_ait_nudges_zero_is_silent(project, hook_env):
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project), dict(hook_env, AIT_NUDGES="0")))


def test_nudges_false_config_is_silent(project, hook_env):
    cfg = project / ".claude" / "issue-tracker.yaml"
    cfg.write_text(cfg.read_text() + "nudges: false\n")
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project), hook_env))


def test_nudges_off_list_disables_deferral(project, hook_env):
    write_transcript(project, WORKED)
    env = dict(hook_env, AIT_NUDGES_OFF="resume, deferral")
    assert silent(run_hook(stop_payload(project), env))


def test_malformed_stdin_is_silent(hook_env):
    assert silent(run_hook("not json {", hook_env))


def test_bad_session_id_is_silent(project, hook_env):
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project, session_id="../x"), hook_env))


def test_unwritable_state_dir_is_silent(project, hook_env, tmp_path):
    write_transcript(project, WORKED)
    blocker = tmp_path / "plugin-data"
    blocker.mkdir(exist_ok=True)
    (blocker / "nudges").write_text("not a dir")
    assert silent(run_hook(stop_payload(project), hook_env))


def test_unknown_event_is_silent(project, hook_env):
    write_transcript(project, WORKED)
    assert silent(run_hook(stop_payload(project, hook_event_name="PreToolUse"), hook_env))


def test_unset_home_and_cache_vars_do_not_crash(project, hook_env):
    write_transcript(project, WORKED)
    env = {k: v for k, v in hook_env.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "XDG_CACHE_HOME", "HOME")}
    r = run_hook(stop_payload(project), env)
    assert r.returncode == 0, r.stderr


# --- resume -----------------------------------------------------------------

from shell_helpers import run_lib  # noqa: E402

EPIC_JSON = json.dumps([{
    "number": 42, "title": "epic: board support",
    "body": "- **Next up:** #61 - webhook retries\n- **Current branch:** feat/board-support\n",
}])


def resume_payload(proj, session_id="r1", source="resume"):
    return {"session_id": session_id, "transcript_path": (proj / "t.jsonl").as_posix(),
            "cwd": proj.as_posix(), "hook_event_name": "SessionStart", "source": source}


@pytest.fixture
def gh_stub(tmp_path, hook_env):
    calls = tmp_path / "gh-calls"
    data = tmp_path / "gh.json"
    data.write_text(EPIC_JSON)
    stub_bin = tmp_path / "stub-bin"
    stub_bin.mkdir()
    gh = stub_bin / "gh"
    gh.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{calls.as_posix()}"\ncat "{data.as_posix()}"\n')
    gh.chmod(0o755)
    return stub_bin, calls


def put_crumb(proj, env, branch, child, epic, title):
    r = run_lib(f"ait_branch_epic_put '{branch}' '{child}' '{epic}' '{title}'", env=env, cwd=proj)
    assert r.returncode == 0, r.stderr


def test_resume_via_gh_lookup(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    m = message_of(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))
    assert m == ('[tracker] Resuming on epic #42 "epic: board support" -- next up: #61. '
                 '/session-brief for the full picture.')


def test_resume_once_per_session(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    assert message_of(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))
    assert silent(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))


def test_resume_via_breadcrumb_on_jira(project, hook_env, gh_stub):
    stub_bin, calls = gh_stub
    (project / ".claude" / "issue-tracker.yaml").write_text(CONFIG_JIRA)
    git(project, "switch", "-c", "feat/obs-rollout")
    put_crumb(project, hook_env, "feat/obs-rollout", "PROJ-12", "PROJ-7", "Obs rollout")
    m = message_of(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))
    assert m == ('[tracker] Resuming PROJ-12 on epic PROJ-7 "Obs rollout". '
                 '/session-brief for the full picture.')
    assert not calls.exists()


def test_resume_breadcrumb_without_child(project, hook_env):
    (project / ".claude" / "issue-tracker.yaml").write_text(CONFIG_JIRA)
    git(project, "switch", "-c", "feat/obs-rollout")
    put_crumb(project, hook_env, "feat/obs-rollout", "", "PROJ-7", "Obs rollout")
    m = message_of(run_hook(resume_payload(project), hook_env))
    assert m.startswith('[tracker] Resuming on epic PROJ-7 "Obs rollout".')


def test_resume_jira_without_breadcrumb_is_silent(project, hook_env, gh_stub):
    stub_bin, calls = gh_stub
    (project / ".claude" / "issue-tracker.yaml").write_text(CONFIG_JIRA)
    git(project, "switch", "-c", "feat/board-support")
    assert silent(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))
    assert not calls.exists()


def test_resume_no_epic_match_is_silent(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/unrelated")
    assert silent(run_hook(resume_payload(project), hook_env, stub_bin=stub_bin))


def test_resume_old_breadcrumb_ignored(project, hook_env, tmp_path):
    (project / ".claude" / "issue-tracker.yaml").write_text(CONFIG_JIRA)
    git(project, "switch", "-c", "feat/obs-rollout")
    put_crumb(project, hook_env, "feat/obs-rollout", "PROJ-12", "PROJ-7", "Obs")
    old = time.time() - 31 * 86400
    for f in (tmp_path / "state").rglob("branch-epic/*"):
        os.utime(f, (old, old))
    assert silent(run_hook(resume_payload(project), hook_env))


def test_resume_startup_is_silent(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    assert silent(run_hook(resume_payload(project, source="startup"), hook_env, stub_bin=stub_bin))


def test_resume_off_list(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    env = dict(hook_env, AIT_NUDGES_OFF="resume")
    assert silent(run_hook(resume_payload(project), env, stub_bin=stub_bin))


def test_resume_prunes_old_markers(project, hook_env, gh_stub, tmp_path):
    stub_bin, _ = gh_stub
    markers = tmp_path / "plugin-data" / "nudges"
    markers.mkdir(parents=True)
    stale = markers / "old-session.deferral"
    stale.write_text("")
    old = time.time() - 31 * 86400
    os.utime(stale, (old, old))
    git(project, "switch", "-c", "feat/board-support")
    run_hook(resume_payload(project), hook_env, stub_bin=stub_bin)
    assert not stale.exists()


def test_resume_shares_title_hook_cache(project, hook_env, gh_stub):
    stub_bin, calls = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    run_hook(resume_payload(project, session_id="x1"), hook_env, stub_bin=stub_bin)
    run_hook(resume_payload(project, session_id="x2"), hook_env, stub_bin=stub_bin)
    assert len(calls.read_text().splitlines()) == 1
