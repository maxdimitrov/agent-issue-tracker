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
