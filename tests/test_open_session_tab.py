"""Subprocess tests for scripts/open-session-tab.sh."""
import json
from urllib.parse import unquote

import pytest

from shell_helpers import SCRIPTS, env_with_path, isolated_env, make_stub, run_script

SCRIPT = SCRIPTS / "open-session-tab.sh"

# Records its argv, one per line, so the test can read back the URI it got.
CODE_STUB = 'printf "%s\\n" "$@" >"$AIT_TEST_CODE_LOG"'
URI_PREFIX = "vscode://anthropic.claude-code/open?prompt="


@pytest.fixture
def host(tmp_path):
    """VS Code host: the entrypoint env var set and a stubbed `code` first on PATH."""
    log = tmp_path / "code.log"
    stub = make_stub(tmp_path / "bin", "code", CODE_STUB)
    env = env_with_path(isolated_env(
        tmp_path, CLAUDE_CODE_ENTRYPOINT="claude-vscode",
        AIT_TEST_CODE_LOG=log.as_posix()), stub)
    env.pop("AIT_CODE_CLI", None)
    return env, log


def tab(env, *args):
    r = run_script(SCRIPT, args=args, env=env)
    assert r.returncode == 0, (r.stdout, r.stderr)
    return json.loads(r.stdout)


def test_opens_tab_with_encoded_prompt(host):
    env, log = host
    out = tab(env, "/agent-issue-tracker:work-issue #42")
    assert out["opened"] is True
    argv = log.read_text().splitlines()
    assert argv[0] == "--open-url"
    uri = argv[1]
    assert uri == out["uri"]
    assert uri.startswith(URI_PREFIX)
    encoded = uri[len(URI_PREFIX):]
    assert " " not in encoded and "#" not in encoded
    assert unquote(encoded) == "/agent-issue-tracker:work-issue #42"


def test_not_vscode_host_does_not_launch(host):
    env, log = host
    env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
    out = tab(env, "/agent-issue-tracker:work-issue #42")
    assert out == {"opened": False, "reason": "not-vscode",
                   "prompt": "/agent-issue-tracker:work-issue #42"}
    assert not log.exists()


def test_entrypoint_unset_is_not_vscode(host):
    env, log = host
    env.pop("CLAUDE_CODE_ENTRYPOINT")
    assert tab(env, "x")["reason"] == "not-vscode"
    assert not log.exists()


def test_missing_code_cli(host):
    env, log = host
    env["AIT_CODE_CLI"] = "no-such-code-cli-ait"
    out = tab(env, "x")
    assert out["opened"] is False and out["reason"] == "no-code-cli"


def test_empty_prompt(host):
    env, log = host
    assert tab(env, "")["reason"] == "empty-prompt"
    assert tab(env)["reason"] == "empty-prompt"
    assert not log.exists()


def test_prompt_too_long(host):
    env, log = host
    out = tab(env, "a" * 2001)
    assert out["opened"] is False and out["reason"] == "prompt-too-long"
    assert not log.exists()
    assert tab(env, "a" * 2000)["opened"] is True


def test_launch_failure_is_reported(host, tmp_path):
    env, _ = host
    make_stub(tmp_path / "bin", "code", "exit 3")
    out = tab(env, "x")
    assert out["opened"] is False and out["reason"] == "launch-failed"
    assert out["prompt"] == "x"


# --repo: a stub `code` that appends each call's argv as one line, prints
# $AIT_TEST_STATUS for `--status`, and (unless AIT_TEST_NO_WINDOW is set)
# "opens" the folder's window by writing a VS Code-style title line into it.
REPO_STUB = r'''
if [ "${1-}" = "--status" ]; then
  [ -f "$AIT_TEST_STATUS" ] && cat "$AIT_TEST_STATUS"
  exit 0
fi
printf '%s\n' "$*" >>"$AIT_TEST_CODE_LOG"
if [ "${1-}" != "--open-url" ] && [ -z "${AIT_TEST_NO_WINDOW-}" ]; then
  printf '    0\t  300\t 4242\twindow [2] (README.md - %s - Visual Studio Code)\n' \
    "$(basename "$1")" >>"$AIT_TEST_STATUS"
fi
'''


@pytest.fixture
def repo_host(tmp_path):
    log, status = tmp_path / "code.log", tmp_path / "status.txt"
    stub = make_stub(tmp_path / "bin", "code", REPO_STUB)
    env = env_with_path(isolated_env(
        tmp_path, CLAUDE_CODE_ENTRYPOINT="claude-vscode",
        AIT_TEST_CODE_LOG=log.as_posix(), AIT_TEST_STATUS=status.as_posix(),
        AIT_WINDOW_WAIT="3", AIT_WINDOW_SETTLE="0"), stub)
    env.pop("AIT_CODE_CLI", None)
    repo = tmp_path / "Trading"
    repo.mkdir()
    return env, log, status, repo


def calls(log):
    return log.read_text().splitlines() if log.exists() else []


def test_repo_opens_the_folder_window_before_the_tab(repo_host):
    env, log, _, repo = repo_host
    out = tab(env, "--repo", repo.as_posix(), "Fix the dashboard-api")
    assert out["opened"] is True and out["repo"] == repo.as_posix()
    first, second = calls(log)
    assert first == repo.as_posix()
    assert second.startswith("--open-url " + URI_PREFIX)
    assert unquote(second[len("--open-url " + URI_PREFIX):]) == "Fix the dashboard-api"


def test_repo_already_open_is_focused_then_gets_the_tab(repo_host):
    env, log, status, repo = repo_host
    status.write_text("    0\t  300\t 4242\twindow [1] (Trading - Visual Studio Code)\n")
    env["AIT_TEST_NO_WINDOW"] = "1"
    out = tab(env, "--repo", repo.as_posix(), "x")
    assert out["opened"] is True
    assert [c.split(" ")[0] for c in calls(log)] == [repo.as_posix(), "--open-url"]


def test_window_that_never_appears_gets_no_uri(repo_host):
    """Firing anyway would type the prompt into whichever window has focus."""
    env, log, _, repo = repo_host
    env["AIT_TEST_NO_WINDOW"] = "1"
    env["AIT_WINDOW_WAIT"] = "1"
    out = tab(env, "--repo", repo.as_posix(), "x")
    assert out == {"opened": False, "reason": "window-not-ready", "prompt": "x", "repo": repo.as_posix()}
    assert calls(log) == [repo.as_posix()]


def test_a_title_that_only_contains_the_name_does_not_count(repo_host):
    """`Trading-old` or `MyTrading` must not pass for the `Trading` window."""
    env, log, status, repo = repo_host
    status.write_text("    0\t  300\t 4242\twindow [1] (x - Trading-old - Visual Studio Code)\n"
                      "    0\t  300\t 4243\twindow [2] (MyTrading - Visual Studio Code)\n")
    env["AIT_TEST_NO_WINDOW"] = "1"
    env["AIT_WINDOW_WAIT"] = "1"
    assert tab(env, "--repo", repo.as_posix(), "x")["reason"] == "window-not-ready"


@pytest.mark.parametrize("args", [("--repo", "/no/such/dir-ait", "x"), ("--repo",)])
def test_missing_repo_launches_nothing(repo_host, args):
    env, log, _, _ = repo_host
    out = tab(env, *args)
    assert out["opened"] is False and out["reason"] == "no-such-repo"
    assert calls(log) == []


def test_repo_still_checks_the_host_first(repo_host):
    env, log, _, repo = repo_host
    env["CLAUDE_CODE_ENTRYPOINT"] = "cli"
    out = tab(env, "--repo", repo.as_posix(), "x")
    assert out["reason"] == "not-vscode" and out["repo"] == repo.as_posix()
    assert calls(log) == []


def test_repo_trailing_slash_matches_the_folder_name(repo_host):
    env, log, _, repo = repo_host
    assert tab(env, "--repo", repo.as_posix() + "/", "x")["opened"] is True
