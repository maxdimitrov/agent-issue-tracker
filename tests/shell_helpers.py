"""Helpers for driving the plugin's bash scripts from pytest.

On Linux/macOS `bash` on PATH is used. On Windows the WSL launcher shadows
Git Bash on PATH, so Git's own bash.exe is preferred; AIT_TEST_BASH overrides.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
LIB = SCRIPTS / "lib" / "common.sh"

_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"


def bash_path():
    override = os.environ.get("AIT_TEST_BASH")
    if override:
        return override
    if sys.platform == "win32" and os.path.exists(_GIT_BASH):
        return _GIT_BASH
    found = shutil.which("bash")
    if not found:
        raise RuntimeError("no bash found; set AIT_TEST_BASH")
    return found


def run_script(script, args=(), env=None, cwd=None, stdin=None, timeout=90):
    # Explicit stdin (DEVNULL when no input is given) avoids inheriting the
    # parent's STD_INPUT_HANDLE: on Windows that handle intermittently goes
    # invalid across rapid sequential Popen calls under pytest's capture
    # machinery, and inheriting it raises a sporadic WinError 6.
    extra = {} if stdin is not None else {"stdin": subprocess.DEVNULL}
    return subprocess.run(
        [bash_path(), str(script), *args], input=stdin, text=True,
        capture_output=True, env=env, cwd=cwd, timeout=timeout, **extra,
    )


def run_lib(snippet, env=None, cwd=None):
    """Source common.sh, then run `snippet` in the same shell."""
    cmd = f'. "{LIB.as_posix()}"; {snippet}'
    return subprocess.run(
        [bash_path(), "-c", cmd], text=True, capture_output=True,
        env=env, cwd=cwd, timeout=60, stdin=subprocess.DEVNULL,
    )


def make_stub(bin_dir, name, body):
    """Executable `name` in bin_dir whose body runs under bash."""
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    p = bin_dir / name
    p.write_text(f"#!/usr/bin/env bash\n{body}\n")
    p.chmod(0o755)
    return bin_dir


def env_with_path(env, bin_dir):
    env = dict(env)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return env


def isolated_env(tmp_path, **extra):
    """Env with the plugin's state dir and Claude config dir under tmp_path.

    gh auth is stripped too (an empty GH_CONFIG_DIR, no token env vars), so
    a test without a gh stub sees an unauthenticated gh -- exactly as in CI
    -- instead of making real API calls with the developer's credentials.
    """
    env = dict(os.environ)
    env["AIT_STATE_DIR"] = (tmp_path / "state").as_posix()
    env["CLAUDE_CONFIG_DIR"] = (tmp_path / "claude").as_posix()
    (tmp_path / "claude" / "projects").mkdir(parents=True, exist_ok=True)
    env["GH_CONFIG_DIR"] = (tmp_path / "gh-config").as_posix()
    (tmp_path / "gh-config").mkdir(parents=True, exist_ok=True)
    for k in ("AIT_TRANSCRIPT", "CLAUDE_CODE_SESSION_ID", "AIT_SINCE",
              "GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN"):
        env.pop(k, None)
    env.update(extra)
    return env


def git(repo, *args, env=None):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", "-C", str(repo), *args],
        check=True, capture_output=True, env=env, stdin=subprocess.DEVNULL,
    )


def init_repo(path, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", "-b", branch, str(path)],
        check=True, capture_output=True, stdin=subprocess.DEVNULL,
    )
    git(path, "commit", "--allow-empty", "-m", "init")
    return path


def env_without_command(env, tmp_path, name):
    """`env` with every PATH dir that holds `name` (or `name`.exe) hidden.

    On Windows the tools this plugin shells out to (gh, jq) each live in a
    directory of their own, so that directory is simply dropped. Elsewhere
    they usually share /usr/bin with bash, git and coreutils, so that
    directory is replaced by a symlink farm of everything in it except
    `name`.

    HOME points at an empty directory too: Git for Windows' bash launcher
    prepends $HOME/bin to PATH on its own, which would bring back a tool
    installed there.
    """
    env = dict(env)
    home = Path(tmp_path) / f"home-without-{name}"
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    kept = []
    farm_n = 0
    for d in env.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        hits = [os.path.join(d, n) for n in (name, name + ".exe")]
        if not any(os.path.exists(h) for h in hits):
            kept.append(d)
            continue
        if sys.platform == "win32":
            continue
        farm = Path(tmp_path) / f"path-without-{name}-{farm_n}"
        farm_n += 1
        farm.mkdir(parents=True, exist_ok=True)
        for entry in os.listdir(d):
            if entry in (name, name + ".exe"):
                continue
            link = farm / entry
            if not link.exists():
                try:
                    link.symlink_to(os.path.join(d, entry))
                except OSError:
                    pass
        kept.append(str(farm))
    env["PATH"] = os.pathsep.join(kept)
    return env
