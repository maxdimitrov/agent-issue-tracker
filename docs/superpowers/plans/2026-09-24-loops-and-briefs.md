# Loops and Briefs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/session-brief`, `/tracker-brief` and `/tracker-loop` to the plugin, with the shared shell library, per-project state directory, loop bookkeeping script and the eleventh backend contract operation they need.

**Architecture:** Deterministic facts come from three bash scripts (`session-brief-collect.sh`, `tracker-brief-collect.sh`, `loop-record.sh`) that always exit 0 and print one JSON object; the three command markdown files hold the judgement (verdict tables, decision tables) and dispatch tracker reads through the backend contract. Recurrence for loops is external (`/loop`, or a session cron the drivers arm with `--loop`); `/tracker-loop` itself runs exactly one iteration and keeps its counters on disk.

**Tech Stack:** bash 3.2 + BSD/GNU userland, `jq`, `gh`; pytest subprocess tests driving the scripts through Git Bash on Windows and `bash` elsewhere; markdown command files.

**Spec:** `docs/superpowers/specs/2026-09-24-loops-and-briefs-design.md`

## Global Constraints

- Scripts are bash 3.2 and BSD-userland safe (macOS), shellcheck-clean, and never `set -e`. Collectors always exit 0 and print one JSON object; missing data is `null` / `[]` / `false`.
- No script or command writes inside a consumer repo. State lives under `${AIT_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker}/<project-key>/`.
- Tracker reads go through `backends/_interface.md` operations only; git-host reads use the same `gh` calls the plugin already documents. No command calls `ScheduleWakeup`. No new command file sets `disable-model-invocation`.
- Tests run with `python -m pytest -q` from the worktree root. Bash is resolved by `tests/shell_helpers.py` (Git Bash on Windows, `bash` on PATH elsewhere, `AIT_TEST_BASH` overrides). Paths handed to scripts from tests use `.as_posix()`; `PATH` prepends use `os.pathsep`.
- Every commit uses a conventional prefix (`feat:`, `fix:`, `docs:`, `test:`, `chore:`) and ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No version bump; CHANGELOG entries go under `## [Unreleased]`.
- Work happens on branch `feat/loops-and-briefs` in worktree `F:\Claude\Projects\agent-issue-tracker\.claude\worktrees\loops-and-briefs`. Verify with `git branch --show-current` before the first edit; run git as `git -C <worktree-path> …` if the Bash tool refuses plain git.
- Markdown under `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `examples/**` is linted by markdownlint (MD013 and MD033 off): blank lines around headings, lists and fences; one H1.

## Review Focus

1. A branch with a version segment (`release/v1.8.0`) yields no ref and no ticket line — pinned in Task 1 (`test_ref_from_branch`).
2. Transcript discovery in a repo with two live sessions in sibling worktrees picks the transcript whose entries record this cwd, never the sibling's — pinned in Task 3 (`test_discovery_prefers_transcript_matching_cwd`).
3. Ledger join on refs is by equality: a PR titled `[#604] …` must not land in the `#6041` row — pinned in Task 6 (`test_ledger_joins_by_exact_ref`).
4. `gh` failing (auth, network) leaves every collector printing valid JSON with `null`/`[]` fields and one `errors[]` entry, never a crash — pinned in Task 3 (`test_gh_failure_degrades_to_null`) and Task 6 (`test_gh_failure_lists_error_and_keeps_worktrees`).
5. Loop budgets survive context compaction because `check` reads counters from the record on disk; the idle budget counts only the trailing run of no-change iterations, not the total — pinned in Task 8 (`test_check_idle_counts_trailing_noops_only`, `test_check_max_iterations_from_disk`).

---

### Task 1: Shared shell library and test helpers

**Files:**
- Create: `scripts/lib/common.sh`
- Create: `tests/shell_helpers.py`
- Test: `tests/test_common_lib.py`

**Interfaces:**
- Produces (bash, all print to stdout, return 1 when nothing found): `ait_hash`, `ait_json_str <s>`, `ait_run_capped <secs> <cmd…>`, `ait_file_mtime <path>`, `ait_iso_from_epoch <epoch>`, `ait_epoch_from_iso <iso>`, `ait_ref_from_branch <branch>`, `ait_slug_from_branch <branch>`, `ait_norm_path <path>`, `ait_main_repo [<dir>]`, `ait_project_key [<dir>]`, `ait_state_dir [<dir>]`, `ait_config_path [<dir>]`, `ait_config_get <key> [<config>]`, `ait_issue_url <ref> [<config>]`.
- Produces (python): `shell_helpers.bash_path()`, `run_script(script, args, env, cwd, stdin)`, `run_lib(snippet, env, cwd)`, `make_stub(bin_dir, name, body)`, `env_with_path(env, bin_dir)`, `isolated_env(tmp_path, **extra)`, `git(repo, *args)`, `init_repo(path)`.

- [ ] **Step 1: Write the test helpers**

Create `tests/shell_helpers.py`:

```python
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
    return subprocess.run(
        [bash_path(), str(script), *args], input=stdin, text=True,
        capture_output=True, env=env, cwd=cwd, timeout=timeout,
    )


def run_lib(snippet, env=None, cwd=None):
    """Source common.sh, then run `snippet` in the same shell."""
    cmd = f'. "{LIB.as_posix()}"; {snippet}'
    return subprocess.run(
        [bash_path(), "-c", cmd], text=True, capture_output=True,
        env=env, cwd=cwd, timeout=60,
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
    """Env with the plugin's state dir and Claude config dir under tmp_path."""
    env = dict(os.environ)
    env["AIT_STATE_DIR"] = (tmp_path / "state").as_posix()
    env["CLAUDE_CONFIG_DIR"] = (tmp_path / "claude").as_posix()
    (tmp_path / "claude" / "projects").mkdir(parents=True, exist_ok=True)
    for k in ("AIT_TRANSCRIPT", "CLAUDE_CODE_SESSION_ID", "AIT_SINCE"):
        env.pop(k, None)
    env.update(extra)
    return env


def git(repo, *args, env=None):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", "-C", str(repo), *args],
        check=True, capture_output=True, env=env,
    )


def init_repo(path, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
    git(path, "commit", "--allow-empty", "-m", "init")
    return path
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_common_lib.py`:

```python
"""Unit tests for scripts/lib/common.sh, run through bash."""
import os
import time
from pathlib import Path

import pytest

from shell_helpers import git, init_repo, run_lib

CONFIG = """schema_version: 1
backend: github   # trailing comment
github:
  repo: "acme/widgets"
  default_pr_close_syntax: "Fixes #N"
jira:
  site: example.atlassian.net
loops:
  interval: 15m
  # claim_label: agent-claimed
"""


@pytest.mark.parametrize("branch,ref", [
    ("max/WB-7657-subscription-gates", "WB-7657"),
    ("feat/42-board-support", "#42"),
    ("fix/issue-17-null-deref", "#17"),
    ("feat/board-support", ""),
    ("release/v1.8.0", ""),
    ("main", ""),
    ("PROJ-9", "PROJ-9"),
])
def test_ref_from_branch(branch, ref):
    r = run_lib(f'ait_ref_from_branch "{branch}"')
    assert r.stdout == ref
    assert r.returncode == (0 if ref else 1)


@pytest.mark.parametrize("branch,slug", [
    ("max/WB-7657-subscription-gates", "subscription-gates"),
    ("feat/42-board-support", "board-support"),
    ("fix/issue-17-null-deref", "null-deref"),
    ("feat/a-very-long-branch-name-that-keeps-going-on", "a-very-long-branch-name-"),
])
def test_slug_from_branch(branch, slug):
    assert run_lib(f'ait_slug_from_branch "{branch}"').stdout == slug


def test_json_str_escapes():
    assert run_lib('ait_json_str \'he said "hi"\'').stdout.strip() == '"he said \\"hi\\""'


def test_project_key_is_stable_across_worktrees(tmp_path):
    repo = init_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", "-b", "feat/x", wt.as_posix())
    k1 = run_lib("ait_project_key", cwd=str(repo)).stdout
    k2 = run_lib("ait_project_key", cwd=str(wt)).stdout
    assert k1 == k2
    assert k1.startswith("repo-") and len(k1) == len("repo-") + 8


def test_project_key_outside_git(tmp_path):
    d = tmp_path / "plain"
    d.mkdir()
    assert run_lib("ait_project_key", cwd=str(d)).stdout.startswith("plain-")


def test_state_dir_respects_override(tmp_path):
    repo = init_repo(tmp_path / "repo")
    env = dict(os.environ, AIT_STATE_DIR=(tmp_path / "state").as_posix())
    out = run_lib("ait_state_dir", env=env, cwd=str(repo)).stdout
    assert out.startswith((tmp_path / "state").as_posix())
    assert Path(out).is_dir()


def test_config_get_scalars_and_nested(tmp_path):
    cfg = tmp_path / "issue-tracker.yaml"
    cfg.write_text(CONFIG)
    c = cfg.as_posix()
    assert run_lib(f'ait_config_get backend "{c}"').stdout == "github"
    assert run_lib(f'ait_config_get github.repo "{c}"').stdout == "acme/widgets"
    assert run_lib(f'ait_config_get github.default_pr_close_syntax "{c}"').stdout == "Fixes #N"
    assert run_lib(f'ait_config_get jira.site "{c}"').stdout == "example.atlassian.net"
    assert run_lib(f'ait_config_get loops.interval "{c}"').stdout == "15m"
    r = run_lib(f'ait_config_get loops.claim_label "{c}"')
    assert r.stdout == "" and r.returncode == 1


def test_config_path_found_from_subdir(tmp_path):
    repo = init_repo(tmp_path / "repo")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "issue-tracker.yaml").write_text(CONFIG)
    sub = repo / "src"
    sub.mkdir()
    out = run_lib("ait_config_path", cwd=str(sub)).stdout
    assert out.replace("\\", "/").lower().endswith("repo/.claude/issue-tracker.yaml")
    assert run_lib("ait_config_path", cwd=str(tmp_path)).returncode == 1


def test_issue_url_github_and_jira(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(CONFIG)
    c = cfg.as_posix()
    assert run_lib(f'ait_issue_url "#42" "{c}"').stdout == "https://github.com/acme/widgets/issues/42"
    assert run_lib(f'ait_issue_url "other/repo#7" "{c}"').stdout == "https://github.com/other/repo/issues/7"
    assert run_lib(f'ait_issue_url "PROJ-9" "{c}"').returncode == 1
    jira = tmp_path / "j.yaml"
    jira.write_text(CONFIG.replace("backend: github", "backend: jira"))
    j = jira.as_posix()
    assert run_lib(f'ait_issue_url "PROJ-9" "{j}"').stdout == "https://example.atlassian.net/browse/PROJ-9"
    assert run_lib(f'ait_issue_url "#42" "{j}"').returncode == 1


def test_time_helpers_round_trip(tmp_path):
    f = tmp_path / "x"
    f.write_text("x")
    mt = int(run_lib(f'ait_file_mtime "{f.as_posix()}"').stdout)
    assert abs(mt - time.time()) < 120
    iso = run_lib("ait_iso_from_epoch 1700000000").stdout
    assert iso == "2023-11-14T22:13:20Z"
    assert run_lib(f'ait_epoch_from_iso "{iso}"').stdout == "1700000000"


def test_run_capped_kills_slow_command():
    r = run_lib("ait_run_capped 1 sleep 5; echo rc=$?")
    assert "rc=" in r.stdout and "rc=0" not in r.stdout
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest -q tests/test_common_lib.py`
Expected: every test errors or fails (`common.sh: No such file`).

- [ ] **Step 4: Write the library**

Create `scripts/lib/common.sh`:

```bash
#!/usr/bin/env bash
# common.sh — shared helpers for agent-issue-tracker scripts and hooks.
#
# Source it (never execute it):
#   . "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"              # from scripts/
#   . "$(cd "$(dirname "$0")" && pwd)/../scripts/lib/common.sh"   # from hooks/
#
# Contract: bash 3.2 + BSD userland safe. Every function prints its result
# on stdout; a function that finds nothing prints nothing and returns 1.
# Nothing here calls exit and nothing here sets -e, so callers keep control.

ait_hash() { if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi; }

ait_json_str() { jq -Rn --arg v "${1-}" '$v'; }

# ait_run_capped <secs> <cmd...> — timeout(1) / gtimeout, else a watchdog.
# The watchdog's stdout goes to /dev/null on purpose: holding the caller's
# command-substitution pipe open would block every call for the full cap.
ait_run_capped() {
  local cap="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$cap" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$cap" "$@"; return $?; fi
  "$@" &
  local pid=$! watcher status
  ( sleep "$cap"; kill -TERM "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  watcher=$!
  wait "$pid" 2>/dev/null
  status=$?
  kill -TERM "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $status
}

# GNU first: on Linux, BSD-style `stat -f %m` succeeds with filesystem info
# (garbage here) instead of failing, so it cannot be the probe.
ait_file_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null; }

ait_iso_from_epoch() {
  date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null
}

ait_epoch_from_iso() {
  local out
  out="$(date -u -d "$1" +%s 2>/dev/null)" \
    || out="$(date -u -j -f %Y-%m-%dT%H:%M:%SZ "$1" +%s 2>/dev/null)" \
    || return 1
  [ -n "$out" ] || return 1
  printf '%s' "$out"
}

# ait_ref_from_branch <branch> — issue ref parsed from the branch leaf:
# a Jira key, else a leading number, else an `issue-N` segment. Same rules
# the session-title hook has always used.
ait_ref_from_branch() {
  local leaf="${1##*/}" ref="" num=""
  ref="$(printf '%s' "$leaf" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)" || true
  if [ -z "$ref" ]; then
    num="$(printf '%s' "$leaf" | grep -oE '^[0-9]+' | head -1)" || true
    if [ -z "$num" ]; then
      num="$(printf '%s' "$leaf" | grep -oE '(^|-)issue-?[0-9]+' | grep -oE '[0-9]+' | head -1)" || true
    fi
    [ -n "$num" ] && ref="#$num"
  fi
  [ -n "$ref" ] || return 1
  printf '%s' "$ref"
}

ait_slug_from_branch() {
  local leaf="${1##*/}"
  printf '%s' "$leaf" \
    | sed -E 's/[A-Z][A-Z0-9]+-[0-9]+//; s/^[0-9]+//; s/(^|-)issue-?[0-9]+//' \
    | sed -E 's/^[-_]+//; s/[-_]+$//' | cut -c1-24
}

# ait_norm_path <path> — absolute, forward slashes, Windows drive form under
# MSYS (pwd -W), so one directory hashes the same from Git Bash and from a
# Windows-launched process. Non-directories are returned unchanged.
ait_norm_path() {
  local p="$1"
  [ -d "$p" ] || { printf '%s' "$p"; return 0; }
  ( cd "$p" 2>/dev/null && { pwd -W 2>/dev/null || pwd; } ) | tr '\\' '/' | tr -d '\n'
}

# ait_main_repo [<dir>] — root of the main checkout shared by all worktrees.
ait_main_repo() {
  local d="${1:-.}" gcd
  gcd="$(git -C "$d" rev-parse --git-common-dir 2>/dev/null)" || return 1
  [ -n "$gcd" ] || return 1
  case "$gcd" in /* | [A-Za-z]:*) ;; *) gcd="$d/$gcd" ;; esac
  gcd="$(ait_norm_path "$gcd")"
  printf '%s' "${gcd%/*}"
}

# ait_project_key [<dir>] — <basename>-<sha256(main repo path)[0:8]>.
ait_project_key() {
  local d="${1:-.}" root name h
  root="$(ait_main_repo "$d")" || root="$(ait_norm_path "$d")"
  name="$(basename "$root" | tr -cd 'A-Za-z0-9._-' | cut -c1-40)"
  h="$(printf '%s' "$root" | ait_hash | cut -c1-8)"
  printf '%s-%s' "${name:-project}" "$h"
}

ait_state_dir() {
  local root="${AIT_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker}"
  local dir="$root/$(ait_project_key "${1:-.}")"
  mkdir -p "$dir" 2>/dev/null
  printf '%s' "$dir"
}

ait_config_path() {
  local d="${1:-.}" top
  if [ -f "$d/.claude/issue-tracker.yaml" ]; then
    printf '%s' "$d/.claude/issue-tracker.yaml"
    return 0
  fi
  top="$(git -C "$d" rev-parse --show-toplevel 2>/dev/null)" || top=""
  if [ -n "$top" ] && [ -f "$top/.claude/issue-tracker.yaml" ]; then
    printf '%s' "$top/.claude/issue-tracker.yaml"
    return 0
  fi
  return 1
}

# ait_config_get <key> [<config>] — `backend`, `github.repo`, `loops.interval`.
# A flat reader for the plugin's own schema: a top-level `key: value`, or a
# two-space-indented `sub: value` under `section:`. Quoted values keep
# everything inside the quotes; unquoted values lose a trailing ` # comment`.
# Not a YAML parser, and not meant to be one.
ait_config_get() {
  local key="$1" cfg="${2:-}" section="" sub="" val=""
  [ -n "$cfg" ] || cfg="$(ait_config_path)" || return 1
  case "$key" in
    *.*)
      section="${key%%.*}"
      sub="${key#*.}"
      val="$(awk -v s="$section" -v k="$sub" '
        /^[A-Za-z_]+:/ { insec = ($0 ~ "^" s ":"); next }
        insec && $0 ~ "^  " k ":" { sub("^  " k ":[ \t]*", ""); print; exit }' "$cfg")"
      ;;
    *)
      val="$(awk -v k="$key" '$0 ~ "^" k ":" { sub("^" k ":[ \t]*", ""); print; exit }' "$cfg")"
      ;;
  esac
  val="$(printf '%s' "$val" | sed -E 's/^"([^"]*)".*$/\1/; t; s/^'"'"'([^'"'"']*)'"'"'.*$/\1/; t; s/[[:space:]]+#.*$//; s/[[:space:]]+$//')"
  [ -n "$val" ] || return 1
  printf '%s' "$val"
}

# ait_issue_url <ref> [<config>] — tracker URL for a ref, or nothing.
ait_issue_url() {
  local ref="$1" cfg="${2:-}" backend repo site
  [ -n "$cfg" ] || cfg="$(ait_config_path)" || return 1
  backend="$(ait_config_get backend "$cfg")" || return 1
  case "$backend" in
    github)
      repo="$(ait_config_get github.repo "$cfg")" || return 1
      case "$ref" in
        \#[0-9]*) printf 'https://github.com/%s/issues/%s' "$repo" "${ref#\#}" ;;
        */*\#[0-9]*) printf 'https://github.com/%s/issues/%s' "${ref%%#*}" "${ref##*#}" ;;
        *) return 1 ;;
      esac
      ;;
    jira)
      site="$(ait_config_get jira.site "$cfg")" || return 1
      case "$ref" in
        [A-Z]*-[0-9]*) printf 'https://%s/browse/%s' "$site" "$ref" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}

true
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest -q tests/test_common_lib.py`
Expected: all pass. If `test_run_capped_kills_slow_command` reports `rc=0`, the watchdog path is not killing the child; check `timeout` resolution on the machine before touching the function.

- [ ] **Step 6: Shellcheck**

Run: `shellcheck scripts/lib/common.sh` (skip if shellcheck is not installed locally; CI runs it in Task 11).
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add scripts/lib/common.sh tests/shell_helpers.py tests/test_common_lib.py
git commit -m "feat(scripts): shared shell library for briefs, loops and the title hook"
```

---

### Task 2: Session-title hook sources the library; hook tests run on Windows

**Files:**
- Modify: `hooks/session-title.sh` (helpers block at the top; stage 5 branch parsing)
- Modify: `tests/test_session_title_hook.py` (`run_hook`, `make_stub`, path formatting only)

**Interfaces:**
- Consumes: `ait_ref_from_branch`, `ait_slug_from_branch`, `ait_file_mtime`, `ait_hash` from Task 1.
- Produces: nothing new. The hook's emitted titles must not change.

- [ ] **Step 1: Make the hook tests runnable on this machine**

In `tests/test_session_title_hook.py`, replace the `run_hook` body and the `make_stub` helper so they use the shared bash resolver, and pass posix paths:

```python
from shell_helpers import bash_path


def run_hook(payload, env, stub_bin=None):
    if stub_bin is not None:
        env = dict(env)
        env["PATH"] = str(stub_bin) + os.pathsep + env["PATH"]
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [bash_path(), str(HOOK)], input=data, text=True, capture_output=True,
        env=env, timeout=30
    )
```

In `hook_env`, use `env["XDG_CACHE_HOME"] = (tmp_path / "cache").as_posix()`. In `payload_for`, use `(proj / "transcript.jsonl").as_posix()` and `proj.as_posix()`. Leave every assertion alone.

- [ ] **Step 2: Run the hook tests before touching the hook**

Run: `python -m pytest -q tests/test_session_title_hook.py`
Expected: all pass on this machine. If a test fails only because a path is compared in Windows form, fix the comparison in the test with `.as_posix()` or `.lower()`; do not change the hook for it. If a test fails for any other reason, stop and report.

- [ ] **Step 3: Source the library from the hook**

In `hooks/session-title.sh`, replace the helper block (`file_mtime` and `hash_key` definitions; keep `tmo`) with:

```bash
tmo() { # tmo <seconds> <cmd...> — timeout(1) if available, else run unbounded
  local s="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; else "$@"; fi
}

# --- stage 0: shared helpers (fail-open when the plugin tree is incomplete) --
_ait_lib="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../scripts/lib/common.sh"
[ -f "$_ait_lib" ] || exit 0
# shellcheck source=../scripts/lib/common.sh
. "$_ait_lib"
```

Then replace every `file_mtime` call with `ait_file_mtime` and every `hash_key` call with `ait_hash`, and replace the stage-5 branch block with:

```bash
branch="$(git -C "$cwd" branch --show-current 2>/dev/null)" || branch=""
ref=""
slug=""
if [ -n "$branch" ]; then
  ref="$(ait_ref_from_branch "$branch")" || ref=""
  slug="$(ait_slug_from_branch "$branch")"
fi
```

- [ ] **Step 4: Run the hook tests again**

Run: `python -m pytest -q tests/test_session_title_hook.py tests/test_common_lib.py`
Expected: all pass, same titles as before.

- [ ] **Step 5: Commit**

```bash
git add hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "refactor(hook): source ref and slug parsing from scripts/lib/common.sh"
```

---

### Task 3: `scripts/session-brief-collect.sh`

**Files:**
- Create: `scripts/session-brief-collect.sh`
- Test: `tests/test_session_brief_collect.py`

**Interfaces:**
- Consumes: every `ait_*` function from Task 1.
- Produces: one JSON object on stdout with keys `session`, `repo`, `git`, `ticket`, `pr`, `ci`, `review`, `handoff`, `loop`, `config`. Exact shape is in the script's emit block below; `commands/session-brief.md` (Task 4) and `commands/tracker-loop.md` (Task 9) read it.
- Reads loop records written by `scripts/loop-record.sh` (Task 8) at `<state-dir>/loops/*.json`; only the fields `state`, `branch`, `id`, `mode`, `ref`, `iterations[]`, `cron_job_id`, `started`, `stop_reason` are used.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_session_brief_collect.py`:

```python
"""Subprocess tests for scripts/session-brief-collect.sh."""
import json
from pathlib import Path

import pytest

from shell_helpers import (SCRIPTS, env_with_path, git, init_repo, isolated_env,
                           make_stub, run_script)

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
    git(repo, "add", "a.txt")
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
        stamp = __import__("datetime").datetime.utcfromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S.000Z")
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


def test_gh_failure_degrades_to_null(repo, tmp_path):
    stub = make_stub(tmp_path / "bin", "gh", "exit 1")
    out = run(repo, env_with_path(isolated_env(tmp_path), stub))
    assert out["repo"]["gh_available"] is True
    assert out["pr"] is None and out["ci"] is None and out["review"] is None
    assert out["ticket"]["key"] == "#42"


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
    transcript(projects / "p-a" / "other.jsonl", cwd=str(sibling), user_turns=9)
    transcript(projects / "p-b" / "mine.jsonl", cwd=str(repo), user_turns=4)
    out = run(repo, env)
    assert out["session"]["transcript_source"] == "discovered"
    assert out["session"]["transcript"].endswith("mine.jsonl")
    assert out["session"]["turns_user"] == 4


def test_discovery_finds_nothing_when_no_cwd_matches(repo, tmp_path):
    env = isolated_env(tmp_path)
    projects = Path(env["CLAUDE_CONFIG_DIR"]) / "projects"
    transcript(projects / "p-a" / "other.jsonl", cwd=str(tmp_path / "elsewhere"))
    assert run(repo, env)["session"] is None


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q tests/test_session_brief_collect.py`
Expected: every test fails (script missing).

- [ ] **Step 3: Write the collector**

Create `scripts/session-brief-collect.sh`:

```bash
#!/usr/bin/env bash
# session-brief-collect.sh — deterministic facts for /session-brief.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout. Missing
# data is null / [] / false, never an error and never a hang. Read-only with
# respect to git, the git host and the repo; the only write is mkdir -p on
# the state directory so the resume note has somewhere to land.
#
# Env:
#   AIT_STATE_DIR      state root (default ${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker)
#   AIT_TIMEOUT        per-network-call cap in seconds (default 15)
#   AIT_TRANSCRIPT     explicit transcript path (skips discovery)
#   CLAUDE_CONFIG_DIR  where the Claude config tree lives (default $HOME/.claude)

set -uo pipefail
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

CAP="${AIT_TIMEOUT:-15}"

if ! command -v jq >/dev/null 2>&1; then
  printf '{"error":"jq not found on PATH","session":null,"repo":null,"git":null,"ticket":null,"pr":null,"ci":null,"review":null,"handoff":null,"loop":null,"config":null}\n'
  exit 0
fi
have_gh=false
command -v gh >/dev/null 2>&1 && have_gh=true

CWD="$(ait_norm_path "$PWD")"
CONFIG="$(ait_config_path "$PWD")" || CONFIG=""
BACKEND=""
[ -n "$CONFIG" ] && { BACKEND="$(ait_config_get backend "$CONFIG")" || BACKEND=""; }
STATE_DIR="$(ait_state_dir "$PWD")"

# ------------------------------------------------------------- repo / git
IS_GIT=false; ROOT=null; ROOT_RAW=""; IS_WORKTREE=false; MAIN_REPO=null; MAIN_RAW=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  IS_GIT=true
  ROOT_RAW="$(ait_norm_path "$(git rev-parse --show-toplevel 2>/dev/null)")"
  ROOT="$(ait_json_str "$ROOT_RAW")"
  MAIN_RAW="$(ait_main_repo "$PWD")" || MAIN_RAW="$ROOT_RAW"
  MAIN_REPO="$(ait_json_str "$MAIN_RAW")"
  [ "$MAIN_RAW" != "$ROOT_RAW" ] && IS_WORKTREE=true
fi

BRANCH=null; BRANCH_RAW=""; DETACHED=false; BASE=null; BASE_RAW=""; ON_BASE=false
AHEAD=0; BEHIND=0; DIRTY_COUNT=0; DIRTY_FILES='[]'; LAST_COMMIT=null; COMMITS='[]'
if [ "$IS_GIT" = true ]; then
  if BRANCH_RAW="$(git symbolic-ref --short -q HEAD 2>/dev/null)"; then
    BRANCH="$(ait_json_str "$BRANCH_RAW")"
  else
    DETACHED=true
    BRANCH_RAW="$(git rev-parse --short HEAD 2>/dev/null || echo "")"
    BRANCH="$(ait_json_str "$BRANCH_RAW")"
  fi
  # origin/HEAD names the default branch when the clone recorded it; else
  # probe the usual names and take the one this branch diverged from last.
  BASE_RAW="$(git symbolic-ref --short -q refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')" || BASE_RAW=""
  if [ -z "$BASE_RAW" ]; then
    best=-1
    for c in develop staging master main production; do
      git show-ref --verify --quiet "refs/remotes/origin/$c" || continue
      n="$(git rev-list --count "origin/$c..HEAD" 2>/dev/null || echo "")"
      [ -z "$n" ] && continue
      if [ "$best" -lt 0 ] || [ "$n" -lt "$best" ]; then best="$n"; BASE_RAW="$c"; fi
    done
  fi
  if [ -n "$BASE_RAW" ]; then
    BASE="$(ait_json_str "$BASE_RAW")"
    [ "$BRANCH_RAW" = "$BASE_RAW" ] && ON_BASE=true
    counts="$(git rev-list --left-right --count "origin/$BASE_RAW...HEAD" 2>/dev/null || echo "")"
    if [ -n "$counts" ]; then
      BEHIND="$(printf '%s' "$counts" | awk '{print $1}')"
      AHEAD="$(printf '%s' "$counts" | awk '{print $2}')"
    fi
    COMMITS="$(git log --format='%h%x1f%s' "origin/$BASE_RAW..HEAD" 2>/dev/null | head -20 \
      | jq -Rn '[inputs | split("\u001f") | {sha: .[0], subject: .[1]}]')"
  fi
  DIRTY_FILES="$(git status --porcelain 2>/dev/null | head -25 \
    | jq -Rn '[inputs | {status: .[0:2], path: .[3:]}]')"
  DIRTY_COUNT="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  LAST_COMMIT="$(git log -1 --format='%h%x1f%s%x1f%cr%x1f%an' 2>/dev/null \
    | jq -Rn 'input? // "" | if . == "" then null else split("\u001f")
        | {sha: .[0], subject: .[1], when: .[2], author: .[3]} end')"
fi

# ------------------------------------------------------------------ ticket
TICKET=null; TICKET_URL=null; TICKET_KEY=""
if [ -n "$BRANCH_RAW" ] && [ "$DETACHED" = false ]; then
  TICKET_KEY="$(ait_ref_from_branch "$BRANCH_RAW")" || TICKET_KEY=""
fi
if [ -n "$TICKET_KEY" ]; then
  TICKET="$(ait_json_str "$TICKET_KEY")"
  if [ -n "$CONFIG" ]; then
    url="$(ait_issue_url "$TICKET_KEY" "$CONFIG")" || url=""
    [ -n "$url" ] && TICKET_URL="$(ait_json_str "$url")"
  fi
fi

# --------------------------------------------------------- PR / CI / review
PR=null; PR_NUMBER=""; CI=null; REVIEW=null; ME=""; NWO=""; NWO_JSON=null
if [ "$IS_GIT" = true ] && [ "$have_gh" = true ] && [ "$DETACHED" = false ]; then
  NWO="$(ait_run_capped "$CAP" gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")"
  [ -n "$NWO" ] && NWO_JSON="$(ait_json_str "$NWO")"

  # statusCheckRollup is deliberately absent: the checks scope is Apps-only,
  # so a fine-grained PAT 403s the whole query. CI comes from the Actions API.
  PR_JSON="$(ait_run_capped "$CAP" gh pr view --json number,url,state,isDraft,mergeable,baseRefName,updatedAt,title,reviewDecision 2>/dev/null || echo "")"
  if [ -n "$PR_JSON" ] && jq -e 'type == "object"' >/dev/null 2>&1 <<<"$PR_JSON"; then
    PR="$PR_JSON"
    PR_NUMBER="$(jq -r '.number // empty' <<<"$PR_JSON")"
  fi

  if [ -n "$NWO" ] && [ -n "$BRANCH_RAW" ]; then
    RUNS="$(ait_run_capped "$CAP" gh api "repos/$NWO/actions/runs?branch=$BRANCH_RAW&per_page=30" 2>/dev/null || echo "")"
    if [ -n "$RUNS" ]; then
      # Newest run per workflow, then a primary. The single newest run is
      # often a skipped bot workflow, not the test suite anyone cares about.
      CI="$(jq '
        [ (.workflow_runs // [])[] | {
            id, workflow: .name, status, conclusion,
            run_url: .html_url, sha: (.head_sha[0:7]), when: .created_at
          } ]
        | group_by(.workflow) | map(sort_by(.when) | last) | sort_by(.when) | reverse
        as $runs
        | ($runs | map(select(.conclusion != "skipped" and .conclusion != "cancelled"))) as $real
        | (($real | map(select(.workflow == "CI")) | first)
           // ($real | map(select(.workflow | test("test|build|ci"; "i"))) | first)
           // ($real | first) // ($runs | first)) as $primary
        | if $primary == null then null else $primary + {all_workflows: $runs} end' <<<"$RUNS" 2>/dev/null || echo null)"
      [ -n "$CI" ] || CI=null
      RUN_ID="$(jq -r '.id // empty' <<<"$CI" 2>/dev/null)"
      CONCL="$(jq -r '.conclusion // empty' <<<"$CI" 2>/dev/null)"
      if [ -n "$RUN_ID" ] && [ "$CONCL" = "failure" ]; then
        FAILED="$(ait_run_capped "$CAP" gh api "repos/$NWO/actions/runs/$RUN_ID/jobs" 2>/dev/null \
          | jq '[(.jobs // [])[] | select(.conclusion == "failure") | {name, url: .html_url}]' 2>/dev/null || echo "[]")"
        CI="$(jq --argjson f "${FAILED:-[]}" '. + {failed_jobs: $f}' <<<"$CI")"
      fi
    fi
  fi

  # Resolved state lives only in GraphQL — the REST comments API can't see it.
  if [ -n "$NWO" ] && [ -n "$PR_NUMBER" ]; then
    ME="$(ait_run_capped "$CAP" gh api user -q .login 2>/dev/null || echo "")"
    OWNER="${NWO%%/*}"
    REPO="${NWO##*/}"
    THREADS="$(ait_run_capped "$CAP" gh api graphql \
      -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
        reviewThreads(first:60){nodes{isResolved isOutdated path line
          comments(first:25){totalCount nodes{author{login} body createdAt}}}}}}}' \
      -F o="$OWNER" -F r="$REPO" -F n="$PR_NUMBER" 2>/dev/null || echo "")"
    if [ -n "$THREADS" ]; then
      REVIEW="$(jq --arg me "$ME" '
        [ (.data.repository.pullRequest.reviewThreads.nodes // [])[] | {
            resolved: .isResolved,
            outdated: .isOutdated,
            path: .path,
            line: .line,
            author: (.comments.nodes[0].author.login // null),
            excerpt: ((.comments.nodes[0].body // "") | gsub("\\s+"; " ") | .[0:180]),
            replies: ((.comments.totalCount // 1) - 1),
            last_author: (.comments.nodes[-1].author.login // null),
            created: (.comments.nodes[0].createdAt // null)
          } ]
        | map(. + {awaiting_you: ((.resolved | not) and (.last_author != $me))})
        | {threads: ., open_count: (map(select(.resolved | not)) | length),
           resolved_count: (map(select(.resolved)) | length),
           awaiting_you_count: (map(select(.awaiting_you)) | length)}' <<<"$THREADS" 2>/dev/null || echo null)"
      [ -n "$REVIEW" ] || REVIEW=null
    fi
  fi
fi

# -------------------------------------------------------------- transcript
# The harness exposes no session id to Bash. Resolve best-effort, in order:
# explicit env, the undocumented session-id env, then the newest transcript
# whose recent entries record THIS cwd (so sibling-worktree sessions of the
# same repo never read each other's transcript).
TRANSCRIPT=""; SOURCE=""
matches_cwd() { # <file> <normalised-lowercase-path>
  tail -c 300000 "$1" 2>/dev/null \
    | jq -R -r 'fromjson? | .cwd // empty' 2>/dev/null | tail -50 \
    | tr '\\' '/' | tr '[:upper:]' '[:lower:]' | grep -Fxq "$2"
}
if [ -n "${AIT_TRANSCRIPT:-}" ] && [ -f "$AIT_TRANSCRIPT" ]; then
  TRANSCRIPT="$AIT_TRANSCRIPT"; SOURCE="env"
elif [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
  for f in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$CLAUDE_CODE_SESSION_ID".jsonl; do
    [ -f "$f" ] && { TRANSCRIPT="$f"; SOURCE="session-id"; break; }
  done
fi
if [ -z "$TRANSCRIPT" ]; then
  projects="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
  want="$(printf '%s' "$CWD" | tr '[:upper:]' '[:lower:]')"
  main_l="$(printf '%s' "$MAIN_RAW" | tr '[:upper:]' '[:lower:]')"
  if [ -d "$projects" ]; then
    cands="$(find "$projects" -mindepth 2 -maxdepth 2 -name '*.jsonl' -mmin -30 2>/dev/null \
      | while IFS= read -r f; do printf '%s\t%s\n' "$(ait_file_mtime "$f")" "$f"; done \
      | sort -rn | cut -f2-)"
    for target in "$want" "$main_l"; do
      [ -n "$target" ] || continue
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        if matches_cwd "$f" "$target"; then TRANSCRIPT="$f"; SOURCE="discovered"; break; fi
      done <<EOF
$cands
EOF
      [ -n "$TRANSCRIPT" ] && break
    done
  fi
fi

SESSION=null
if [ -n "$TRANSCRIPT" ]; then
  BYTES="$(wc -c < "$TRANSCRIPT" | tr -d ' ')"
  SESSION="$(jq -Rn '[inputs | fromjson?]' "$TRANSCRIPT" 2>/dev/null \
    | jq --arg src "$SOURCE" --arg path "$TRANSCRIPT" --argjson bytes "${BYTES:-0}" '
    def ts: (.timestamp // empty) | sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch empty);
    def txt: if (.message.content | type) == "string" then .message.content
             else ([(.message.content // [])[] | select(type == "object" and .type == "text") | .text] | join(" ")) end;
    def is_prompt: .type == "user" and (.toolUseResult | not) and (.isMeta != true) and (.isSidechain != true);
    def refof: ((capture("(?<k>[A-Z][A-Z0-9]+-[0-9]+)") | .k)
                // ((split("/") | last) | capture("^(?<n>[0-9]+)") | "#" + .n));
    ([.[] | select(is_prompt) | txt | gsub("\\s+"; " ")] | map(select(length > 0))) as $p
    | {
        transcript: $path, transcript_source: $src, transcript_bytes: $bytes,
        title: ([.[] | select(.type == "ai-title") | .aiTitle] | last),
        turns_user: ($p | length),
        turns_assistant: ([.[] | select(.type == "assistant" and (.isSidechain != true))] | length),
        first_prompt: ($p | first | if . == null then null else .[0:400] end),
        last_prompt: ($p | last | if . == null then null else .[0:400] end),
        started: ([.[] | ts] | min),
        last_activity: ([.[] | ts] | max),
        branches_seen: ([.[] | .gitBranch // empty | select(. != "" and . != "HEAD")] | unique),
        cwds_seen: ([.[] | .cwd // empty | select(. != "")] | unique),
        compaction_markers: ([.[] | select((.isCompactSummary == true) or (.type == "summary") or (.subtype == "compact_boundary"))] | length)
      }
    | . + {span_hours: (if .started and .last_activity
             then (((.last_activity - .started) / 360 | floor) / 10) else null end)}
    | . + {tickets_seen: ([.branches_seen[] | refof] | unique)}
  ' 2>/dev/null || echo null)"
  [ -n "$SESSION" ] || SESSION=null
fi

# ----------------------------------------------------------------- handoff
if [ -n "$TICKET_KEY" ]; then
  SLUG="$(printf '%s' "$TICKET_KEY" | tr '/#' '--' | sed 's/^-*//' | tr -cd 'A-Za-z0-9._-')"
elif [ "$IS_GIT" = true ]; then
  SLUG="$(printf '%s-%s' "$(basename "$ROOT_RAW")" "$BRANCH_RAW" | tr '/ ' '--' | tr -cd 'A-Za-z0-9._-')"
else
  SLUG="$(basename "$CWD" | tr -cd 'A-Za-z0-9._-')"
fi
[ -z "$SLUG" ] && SLUG="session"
mkdir -p "$STATE_DIR/resume" 2>/dev/null
RESUME_PATH="$STATE_DIR/resume/$SLUG.md"
RESUME_EXISTS=false; RESUME_AGE=null
if [ -f "$RESUME_PATH" ]; then
  RESUME_EXISTS=true
  RESUME_AGE="$(ait_json_str "$(ait_iso_from_epoch "$(ait_file_mtime "$RESUME_PATH")")")"
fi

# -------------------------------------------------------------------- loop
LOOP=null
if [ -d "$STATE_DIR/loops" ] && [ -n "$BRANCH_RAW" ]; then
  LOOP="$(cat "$STATE_DIR"/loops/*.json 2>/dev/null | jq -s --arg b "$BRANCH_RAW" '
    [.[] | select(.state == "live" and .branch == $b)] | first // null
    | if . == null then null else {
        id, mode, ref, started, cron_job_id, stop_reason,
        iterations: ((.iterations // []) | length),
        last_action: ((.iterations // []) | last | .action // null)
      } end' 2>/dev/null || echo null)"
  [ -n "$LOOP" ] || LOOP=null
fi

# -------------------------------------------------------------------- emit
jq -n \
  --argjson session "${SESSION:-null}" \
  --argjson pr "${PR:-null}" \
  --argjson ci "${CI:-null}" \
  --argjson review "${REVIEW:-null}" \
  --argjson loop "${LOOP:-null}" \
  --argjson dirty_files "${DIRTY_FILES:-[]}" \
  --argjson commits "${COMMITS:-[]}" \
  --argjson last_commit "${LAST_COMMIT:-null}" \
  --argjson root "${ROOT:-null}" \
  --argjson main_repo "${MAIN_REPO:-null}" \
  --argjson nwo "${NWO_JSON:-null}" \
  --argjson branch "${BRANCH:-null}" \
  --argjson base "${BASE:-null}" \
  --argjson ticket "${TICKET:-null}" \
  --argjson ticket_url "${TICKET_URL:-null}" \
  --argjson resume_age "${RESUME_AGE:-null}" \
  --arg cwd "$CWD" \
  --arg resume_path "$RESUME_PATH" \
  --arg me "$ME" \
  --arg config_path "$CONFIG" \
  --arg backend "$BACKEND" \
  --arg state_dir "$STATE_DIR" \
  --argjson is_git "$IS_GIT" \
  --argjson is_worktree "$IS_WORKTREE" \
  --argjson detached "$DETACHED" \
  --argjson on_base "$ON_BASE" \
  --argjson ahead "${AHEAD:-0}" \
  --argjson behind "${BEHIND:-0}" \
  --argjson dirty_count "${DIRTY_COUNT:-0}" \
  --argjson gh "$have_gh" \
  --argjson resume_exists "$RESUME_EXISTS" \
  '{
    session: $session,
    repo: {cwd: $cwd, root: $root, is_git: $is_git, is_worktree: $is_worktree,
           main_repo: $main_repo, name_with_owner: $nwo, gh_available: $gh,
           viewer: (if $me == "" then null else $me end)},
    git: {branch: $branch, base: $base, on_base: $on_base, detached: $detached,
          ahead: $ahead, behind: $behind, dirty_count: $dirty_count,
          dirty_files: $dirty_files, last_commit: $last_commit, commits: $commits},
    ticket: {key: $ticket, url: $ticket_url},
    pr: $pr,
    ci: $ci,
    review: $review,
    handoff: {resume_path: $resume_path, exists: $resume_exists, written: $resume_age},
    loop: $loop,
    config: {path: (if $config_path == "" then null else $config_path end),
             backend: (if $backend == "" then null else $backend end),
             state_dir: $state_dir}
  }'

exit 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q tests/test_session_brief_collect.py`
Expected: all pass. Known trip-wires if one fails: `test_base_from_origin_head` needs `git remote set-head` to have written `refs/remotes/origin/HEAD` (check with `git symbolic-ref refs/remotes/origin/HEAD`); `test_worktree_is_detected` compares lower-cased posix paths, so a failure there is a real normalisation bug in `ait_norm_path`, not test noise.

- [ ] **Step 5: Shellcheck and commit**

Run: `shellcheck scripts/session-brief-collect.sh` (if installed). Expected: clean; SC2016 (single quotes in jq programs) may be silenced with a `# shellcheck disable=SC2016` line above the script's first jq call if it fires.

```bash
git add scripts/session-brief-collect.sh tests/test_session_brief_collect.py
git commit -m "feat(scripts): session-brief collector"
```

---

### Task 4: `/session-brief` command

**Files:**
- Create: `commands/session-brief.md`

**Interfaces:**
- Consumes: the JSON from `scripts/session-brief-collect.sh` (Task 3); `view_issue` from `backends/_interface.md`.
- Produces: the resume note format at `handoff.resume_path`, read cold by a later session, and the verdict table that `commands/tracker-loop.md` (Task 9) cites as its checkpoint.

- [ ] **Step 1: Write the command file**

Create `commands/session-brief.md`:

````markdown
---
description: Catch up on the current session — issue link, branch, PR, CI, review threads awaiting you, what was in flight, and a verdict on keep going / compact / fresh session, with a resume note written for a cold start.
---

# /session-brief

Orient the operator in the session they are **currently in** — resumed after a weekend, or long enough that they have lost the thread. Answers five questions in order: what am I working on, what state is it in, what needs me, what did I already resolve, and should I keep going here or start clean.

**This command is read-only.** Never commit, push, comment on a PR, transition an issue, or edit source. The only file written is the resume note, outside every repo. If the operator wants an action taken, they will ask in the next turn.

## Step 1 — Collect the facts

One call:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/session-brief-collect.sh"
```

The script always exits 0 and always prints valid JSON. Everything in that JSON is ground truth; everything else in the brief comes from your own memory of this conversation. Keep the two straight — never report a PR number, CI result, or branch state from recollection when the JSON has it, and never invent a value the JSON returned as `null`.

When `config.backend` is set and `ticket.key` is non-null, enrich the ticket with one `view_issue({ref: ticket.key})` through the configured backend (`backends/<backend>.md`) for its title and status. A not-found is reported on the ticket line, not hidden.

Degrade, don't fail:

| JSON says | Do this |
|---|---|
| `repo.is_git: false` | Brief the session only. Say there is no repo here; skip WHERE / PR / CI. |
| `repo.gh_available: false` | Say git-host state is unavailable; brief git + session. |
| `pr: null` | "No PR yet" — a real and useful fact, not an error. Say it on the PR line rather than dropping the line. |
| `ci: null` | No runs for this branch. Don't imply CI passed. |
| `session: null` | No transcript found. Brief repo state only; skip the verdict and say why. `session.transcript_source` of `discovered` means a heuristic match — say so in one clause when the verdict is a close call. |
| `git.detached: true` | Report detached HEAD prominently — it is usually a surprise. |
| `config.backend: null` | No `.claude/issue-tracker.yaml`. The ticket line carries the key only. |

## Step 2 — Print the brief

Fixed section order. Terse — values, not sentences. **Omit any line whose data is null** rather than printing "unknown". Use real markdown links for paths so they are clickable.

**Never emit the header block inside a code fence.** A fence renders every link and path in it as dead text. The layout below is shown fenced so the placeholders are readable here — your output must be plain markdown, aligned with the same column positions.

**The ticket and PR links are mandatory, every time.** A brief whose whole job is to re-orient someone is useless if they have to go hunting for the two URLs they need. Take them verbatim from `ticket.url` and `pr.url`; never reconstruct either from a key or number. The only reason to omit one is that the JSON returned it as null, and then you say so on that line.

```
<TICKET> · <session title>
<ticket url>
<pr url>

WHERE      <cwd, marked (worktree) if repo.is_worktree>
           <branch> · <ahead> ahead, <behind> behind <base> · <dirty_count> dirty
PR         [#<n>](<pr url>) <state><, draft><, reviewDecision> · CI [<workflow> <conclusion>](<ci run_url>)
LOOP       <mode> <ref> · iteration <n> · last <last_action> · cron <armed|none>
LAST TASK  <what you were doing, one line>
           last commit <when> — <subject>

NEEDS YOU
  ...

ALREADY RESOLVED
  ...

VERDICT    <keep going | /compact | fresh session> — <reason>
```

**LOOP** appears only when `loop` is non-null: a live `/tracker-loop` record for this branch. `cron armed` when `loop.cron_job_id` is set.

**LAST TASK** is the one section that is yours, not the script's. State what was actually in flight, cross-checked against `git.last_commit` and `git.dirty_files`. If `session.compaction_markers > 0` and you no longer hold the detail, say so plainly — "session was compacted; reconstructing from git state and last prompt" — and fall back to `session.last_prompt` plus the dirty files. Never fabricate continuity you don't have.

**NEEDS YOU** — every item that blocks progress, most-blocking first:

- `review.threads[]` where `awaiting_you` — show `author`, `path:line`, `excerpt`. These are unresolved threads where someone other than you spoke last.
- `ci.conclusion == "failure"` — name the failed jobs from `ci.failed_jobs`.
- `git.behind > 0` by a large margin — needs a base sync before it can merge.
- `git.dirty_count > 0` — uncommitted work that would be lost.
- `pr.state == "OPEN"` with `reviewDecision == "APPROVED"` — ready to merge, waiting on you.
- `pr.mergeable == "CONFLICTING"` — conflicts to resolve.
- `loop.stop_reason` naming NEEDS YOU — the loop stopped for a judgement call; repeat what it asked.

**ALREADY RESOLVED** exists so the operator doesn't re-litigate something last-week-them already closed. Sources: `review.threads[]` where `resolved` is true, plus what you remember fixing in this session. If there is nothing to report, omit the whole section — don't pad it.

Note `pr.state` of `MERGED` or `CLOSED` loudly. A merged PR on a branch that is far behind usually means the work shipped and the session is finished, which changes the verdict to a fresh session.

## Step 3 — The verdict

Three outcomes. Signals come from `session`: `turns_user`, `span_hours`, `compaction_markers`, `branches_seen`, `tickets_seen`.

| Condition | Verdict |
|---|---|
| `turns_user` < 25, `span_hours` < 2, no compaction, one ticket in `tickets_seen` | **keep going** |
| `turns_user` ≥ 25 or `span_hours` ≥ 2 — and still the same ticket/branch | **/compact** |
| `tickets_seen` or `branches_seen` has more than one, and the next task belongs to a different one | **fresh session** |
| `compaction_markers` ≥ 1 and `turns_user` ≥ 25 since | **fresh session** |
| The next task is cleanly separable — new ticket, different repo | **fresh session** |
| `pr.state == "MERGED"` and nothing left in NEEDS YOU | **fresh session** — this work is done |

Why `/compact` rather than fresh when the work is coherent: compaction keeps recent turns verbatim and drops old tool output, so mid-ticket detail survives. A fresh session is better when the *shape* of the work changed, because then the old detail is ballast — and compacting an already-compacted session loses more than a clean handoff does.

Always give the reason, never a bare verdict. The thresholds live in this one table so they are easy to retune. `/tracker-loop` applies this same table as its per-iteration checkpoint.

**Honesty constraint:** no tool exposes real context-window usage to a command. This verdict is a proxy from turn count, elapsed time, and compaction markers. Say that when it is a close call, and point the operator at `/context` for the real number. Never phrase it as if you measured the context window.

## Step 4 — Write the resume note

Write to `handoff.resume_path` from the JSON — under the plugin's state directory, outside any repo, so it can't dirty a working tree. Overwrite in place; the timestamped header is the version marker. Then print the same block so it is usable immediately without opening the file.

```markdown
# Resume: <TICKET or branch> — written <YYYY-MM-DD HH:MM>

cd <cwd>

Resume <TICKET> (<ticket url>) on branch `<branch>`, PR #<n> (<pr url>).

**Done so far:** <2-4 bullets of what actually landed — commits, decisions made>

**Next action:** <the single most specific next step, with file:line if known>

**Open threads to answer:**
- <author> on <path:line> — <excerpt>

**Loop:** re-arm with `/loop /agent-issue-tracker:tracker-loop <mode> <ref>`   ← only when `loop` was non-null

**Constraints / gotchas:** <repo rules and traps that would bite a cold start — base branch, formatting rule, anything learned the hard way this session>
```

Both URLs are required here too — this note is read cold, by a session with no memory of the work, so an unlinked key or PR number is a dead end.

Then tell the operator, in one line, that it is at that path and what to do with it: paste it as the first message of a new session.

If `handoff.exists` is true and `handoff.written` is older than this session, mention the previous note is being replaced — it may describe a different stage of the work.

## Red flags

| Thought | Reality |
|---|---|
| "I'll just describe the PR state from memory" | Resumed sessions have stale recollections. The JSON is truth. |
| "The operator knows their own ticket and PR number" | They asked to be re-oriented. Link both, every time, from `ticket.url` and `pr.url`. |
| "The header block looks tidier fenced" | A fence makes every link in it unclickable. Plain markdown, aligned columns. |
| "CI is probably fine" | `ci: null` means no runs found, not passing. Say which. |
| "Newest workflow run is the CI result" | The script already picks a primary; the newest run is often a skipped bot workflow. Use `ci.workflow` / `ci.conclusion` as given. |
| "The session feels long, I'll say the context is nearly full" | You cannot see context usage. Use the countable signals and say they are a proxy. |
| "There are no resolved threads so I'll write 'nothing to report'" | Omit the section. Don't pad. |
| "I'll fix the failing test while I'm here" | Read-only command. Report, then stop. |
````

- [ ] **Step 2: Sanity-run the collector from the plugin tree**

Run from the worktree root: `bash scripts/session-brief-collect.sh | jq '.ticket, .git.branch, .handoff.resume_path'` (use Git Bash on Windows).
Expected: `{"key": null, ...}` or a ref for the current branch, the branch name, and a path under the cache dir ending in `/resume/<slug>.md`.

- [ ] **Step 3: Commit**

```bash
git add commands/session-brief.md
git commit -m "feat(commands): /session-brief"
```

---

### Task 5: Contract operation `list_updated_issues`

**Files:**
- Modify: `backends/_interface.md` (Operations intro count; new `### \`list_updated_issues\`` block after `list_child_issues`; "The ten operations above" sentence)
- Modify: `backends/github.md` (new operation block after `list_child_issues`)
- Modify: `backends/jira.md` (new operation block after `list_child_issues`)
- Modify: `CONTRIBUTING.md:56` (op list), `README.md:170` ("ten-operation")
- Test: `tests/test_backend_contract.py`

**Interfaces:**
- Produces: `list_updated_issues({since, involving_me})` → `[{ref, title, status, updated, url}]`, used by `commands/tracker-brief.md` (Task 7).

- [ ] **Step 1: Write the failing test**

Create `tests/test_backend_contract.py`:

```python
"""Local mirror of the CI backend-contract job: every `### `op`` heading in
backends/_interface.md must appear in every backend module."""
import re
from pathlib import Path

BACKENDS = Path(__file__).resolve().parents[1] / "backends"
OP = re.compile(r"^### `([a-z_]+)`$", re.M)


def ops(path):
    return set(OP.findall(path.read_text(encoding="utf-8")))


def test_every_backend_implements_every_contract_op():
    contract = ops(BACKENDS / "_interface.md")
    assert contract, "no operation headings in _interface.md"
    for backend in ("github.md", "jira.md"):
        missing = contract - ops(BACKENDS / backend)
        assert not missing, f"{backend} missing {sorted(missing)}"


def test_contract_has_list_updated_issues():
    assert "list_updated_issues" in ops(BACKENDS / "_interface.md")
```

- [ ] **Step 2: Run it to verify the second test fails**

Run: `python -m pytest -q tests/test_backend_contract.py`
Expected: `test_contract_has_list_updated_issues` fails; the parity test passes.

- [ ] **Step 3: Add the operation to the contract**

In `backends/_interface.md`, change `Ten operations.` to `Eleven operations.` in the Operations intro, change `The ten operations above are the entire contract` to `The eleven operations above are the entire contract`, and `the ten ops stay ten` to `the eleven ops stay eleven`. Insert after the `list_child_issues` block (before `### \`view_issue\``):

```markdown
### `list_updated_issues`

**Purpose:** List issues with activity inside a time window — the read `/tracker-brief` uses to answer "what moved in the tracker while I was away". Comment-level activity is NOT part of this op; callers pair it with `read_comments` on the returned refs.

**Inputs:**
- `since` — ISO-8601 UTC timestamp; only issues updated at or after it are returned
- `involving_me` (optional, default `true`) — restrict to issues the viewer is assigned to, reported, watches, or is mentioned in, as the backend defines involvement

**Output:** list of `{ref, title, status, updated, url}` entries, newest `updated` first, capped at 50 by the backend. `updated` is ISO-8601 UTC; `url` is the issue's browser URL.

**Note:** `involving_me` is best-effort per backend — GitHub's `involves:` qualifier and Jira's assignee/reporter/watcher trio are not the same set. Callers treat the result as "probably relevant", not authoritative.

---
```

- [ ] **Step 4: Add the GitHub implementation**

In `backends/github.md`, insert after the `list_child_issues` block:

````markdown
### `list_updated_issues`

```bash
gh issue list \
  --repo "$GITHUB_REPO" \
  --state all \
  --search "updated:>=${SINCE_DATE} involves:@me" \
  --json number,title,state,updatedAt,url \
  --limit 50 \
  --jq '.[] | "#\(.number)\t\(.title)\t\(.state)\t\(.updatedAt)\t\(.url)"'
```

`SINCE_DATE` is the `since` input truncated to `YYYY-MM-DD` — GitHub's search qualifier is date-granular, so the caller filters the returned `updated` values against the full timestamp. Drop `involves:@me` when `involving_me` is false. Results come back newest-updated first by default.

---
````

- [ ] **Step 5: Add the Jira implementation**

In `backends/jira.md`, insert after the `list_child_issues` block:

````markdown
### `list_updated_issues`

List issues with activity inside a window.

```
searchJiraIssuesUsingJql({
  cloudId: <jira.cloud_id>,
  jql: 'project = "<jira.project>" AND updated >= "<since as yyyy-MM-dd HH:mm>" [AND (assignee = currentUser() OR reporter = currentUser() OR watcher = currentUser())] ORDER BY updated DESC',
  maxResults: 50
})
```

**Filter assembly:**
- `since` → `updated >= "<yyyy-MM-dd HH:mm>"` (Jira's JQL date literal has minute granularity; render in the site's timezone or accept the minute of slop)
- `involving_me` true → append the parenthesised assignee / reporter / watcher clause

Two traps: `commentedByUser()` is not valid JQL on Jira Cloud and throws a syntax error; `comment ~ "<display name>"` parses but always returns zero because mentions are stored as accountId markup. Assignee / reporter / watcher is the reliable involvement surface.

The backend module translates the MCP response to `[{ref, title, status, updated, url}]` with `url = https://<jira.site>/browse/<key>`.

**Live verification:** deferred — this operation cannot be exercised from the development machine (no Atlassian connector in that session). It joins the Jira smoke list for the next release gate.

---
````

- [ ] **Step 6: Update the counts in CONTRIBUTING and README**

`CONTRIBUTING.md` line 56: `ten operations (` → `eleven operations (`, and add `list_updated_issues` after `list_child_issues` in the parenthesised list. `README.md` line 170: `The ten-operation contract` → `The eleven-operation contract`.

- [ ] **Step 7: Run the tests**

Run: `python -m pytest -q tests/test_backend_contract.py`
Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add backends/_interface.md backends/github.md backends/jira.md CONTRIBUTING.md README.md tests/test_backend_contract.py
git commit -m "feat(backends): list_updated_issues contract operation (10 -> 11)"
```

---

### Task 6: `scripts/tracker-brief-collect.sh`

**Files:**
- Create: `scripts/tracker-brief-collect.sh`
- Test: `tests/test_tracker_brief_collect.py`

**Interfaces:**
- Consumes: every `ait_*` function from Task 1; loop records from Task 8 (fields `id`, `mode`, `ref`, `branch`, `state`, `stop_reason`, `started`, `iterations[]`, `prs_opened[]`); resume notes written by Task 4 (first line `# Resume: <ref or branch> — written …`).
- Produces: one JSON object with keys `generated_at`, `window`, `viewer`, `config`, `worktrees`, `resume_notes`, `loops`, `prs`, `pr_detail`, `ledger`, `orphan_worktrees`, `errors`; `--commit-run` prints `{committed, state_file}`. `commands/tracker-brief.md` (Task 7) reads it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tracker_brief_collect.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest -q tests/test_tracker_brief_collect.py`
Expected: every test fails (script missing).

- [ ] **Step 3: Write the collector**

Create `scripts/tracker-brief-collect.sh`:

```bash
#!/usr/bin/env bash
# tracker-brief-collect.sh — deterministic local + git-host facts for /tracker-brief.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout. Missing
# data is null / [] / false, never an error and never a hang.
#
# Read-only EXCEPT `--commit-run`, which stamps the window file. Tracker
# activity (issues, comments) is NOT collected here — the command reads it
# through the backend contract ops — so `ledger[].tracker_status` is left
# null for the command to fill.
#
# Usage:
#   tracker-brief-collect.sh                 # emit facts (read-only)
#   tracker-brief-collect.sh --commit-run    # stamp last_run=now
#
# Env:
#   AIT_STATE_DIR    state root (default ${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker)
#   AIT_TIMEOUT      per-call cap, seconds (default 20)
#   AIT_SINCE        ISO-8601 override for the window start
#   AIT_STALE_DAYS   worktree staleness threshold (default 14)
#   AIT_MAX_PR_DEEP  max PRs to fetch review threads + CI for (default 12)

set -uo pipefail
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

CAP="${AIT_TIMEOUT:-20}"
STALE_DAYS="${AIT_STALE_DAYS:-14}"
MAX_PR_DEEP="${AIT_MAX_PR_DEEP:-12}"
ERRORS='[]'
note_err() { ERRORS="$(jq -c --arg e "$1" '. + [$e]' <<<"$ERRORS" 2>/dev/null || echo "$ERRORS")"; }
iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
is_array() { jq -e 'type == "array"' >/dev/null 2>&1 <<<"$1"; }

if ! command -v jq >/dev/null 2>&1; then
  printf '{"fatal":"jq not installed","generated_at":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 0
fi

STATE_DIR="$(ait_state_dir "$PWD")"
STATE="$STATE_DIR/tracker-brief.json"
CONFIG="$(ait_config_path "$PWD")" || CONFIG=""
BACKEND=""; GH_REPO=""; JIRA_SITE=""
if [ -n "$CONFIG" ]; then
  BACKEND="$(ait_config_get backend "$CONFIG")" || BACKEND=""
  GH_REPO="$(ait_config_get github.repo "$CONFIG")" || GH_REPO=""
  JIRA_SITE="$(ait_config_get jira.site "$CONFIG")" || JIRA_SITE=""
fi

# ------------------------------------------------------------ --commit-run
if [ "${1:-}" = "--commit-run" ]; then
  NOW="$(iso_now)"
  PREV="$(jq -r '.last_run // empty' "$STATE" 2>/dev/null)"
  jq -n --arg now "$NOW" --arg prev "${PREV:-}" \
    '{last_run: $now, previous_run: (if $prev == "" then null else $prev end)}' \
    >"$STATE.tmp" 2>/dev/null && mv "$STATE.tmp" "$STATE" 2>/dev/null
  jq -n --arg now "$NOW" --arg p "$STATE" '{committed: $now, state_file: $p}'
  exit 0
fi

# ------------------------------------------------------------------ window
NOW_EPOCH="$(date -u +%s)"
LAST_RUN="$(jq -r '.last_run // empty' "$STATE" 2>/dev/null)"
FIRST_RUN=true
if [ -n "${AIT_SINCE:-}" ]; then
  SINCE="$AIT_SINCE"; FIRST_RUN=false
elif [ -n "$LAST_RUN" ]; then
  SINCE="$LAST_RUN"; FIRST_RUN=false
else
  SINCE="$(ait_iso_from_epoch $((NOW_EPOCH - 86400)))"
fi
SINCE_EPOCH="$(ait_epoch_from_iso "$SINCE")" || SINCE_EPOCH=0
if [ "$SINCE_EPOCH" -gt 0 ]; then
  WIN_DAYS=$(( (NOW_EPOCH - SINCE_EPOCH) / 86400 ))
else
  WIN_DAYS=1; note_err "could not parse window start '$SINCE'"
fi
SUMMARIZE=false; [ "$WIN_DAYS" -gt 5 ] && SUMMARIZE=true
SINCE_DATE="${SINCE%%T*}"

# ------------------------------------------------------------ repo / viewer
IS_GIT=false; NWO=""; TOP=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  IS_GIT=true
  TOP="$(ait_norm_path "$(git rev-parse --show-toplevel 2>/dev/null)")"
  origin="$(git remote get-url origin 2>/dev/null || echo "")"
  case "$origin" in
    *github.com*)
      NWO="$(printf '%s' "$origin" \
        | sed -E 's#^(git@github\.com:|ssh://git@github\.com/|https://github\.com/)##; s#\.git$##; s#/$##')" ;;
  esac
fi
GH_OK=false; GH_LOGIN=""
if [ -z "$NWO" ]; then
  note_err "no GitHub origin remote — PR data skipped"
elif ! command -v gh >/dev/null 2>&1; then
  note_err "gh unavailable — PR data skipped"
else
  GH_LOGIN="$(ait_run_capped "$CAP" gh api user --jq .login 2>/dev/null)" || GH_LOGIN=""
  if [ -n "$GH_LOGIN" ]; then GH_OK=true; else note_err "gh api user failed (auth?) — PR data skipped"; fi
fi

# --------------------------------------------------------------- worktrees
WORKTREES='[]'
if [ "$IS_GIT" = true ]; then
  idx=0
  while IFS=$'\t' read -r wpath wbranch wdet; do
    [ -n "$wpath" ] || continue
    wpath="$(ait_norm_path "$wpath")"
    primary=false; [ "$idx" -eq 0 ] && primary=true
    idx=$((idx + 1))
    ref=""; [ -n "$wbranch" ] && { ref="$(ait_ref_from_branch "$wbranch")" || ref=""; }
    dirty="$(git -C "$wpath" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    le="$(git -C "$wpath" log -1 --format=%ct 2>/dev/null)"; [ -n "$le" ] || le=0
    lastsub="$(git -C "$wpath" log -1 --format=%s 2>/dev/null)"
    lastc=""; [ "$le" -gt 0 ] && lastc="$(ait_iso_from_epoch "$le")"
    age=0; [ "$le" -gt 0 ] && age=$(( (NOW_EPOCH - le) / 86400 ))
    stale=false
    if [ "$primary" = false ] && [ "$age" -ge "$STALE_DAYS" ] && [ "${dirty:-0}" -eq 0 ]; then stale=true; fi
    touched=false; [ "$le" -ge "$SINCE_EPOCH" ] && touched=true
    # Ask the git host whether this branch landed. `git merge-base --is-ancestor`
    # is NOT usable: squash/rebase merges rewrite the SHA, so a branch whose PR
    # merged still reports "not an ancestor". The branch->PR lookup has no such
    # blind spot.
    landed=null
    if [ "$GH_OK" = true ] && [ -n "$wbranch" ] && [ "$primary" = false ]; then
      landed="$(ait_run_capped "$CAP" gh pr list --repo "$NWO" --head "$wbranch" --state all \
        --limit 5 --json number,state,mergedAt,title,url 2>/dev/null \
        | jq -c '([.[] | select(.state == "MERGED")][0]) // .[0] // null' 2>/dev/null)"
      [ -n "$landed" ] || landed=null
    fi
    WORKTREES="$(jq -c --arg path "$wpath" --arg branch "$wbranch" --arg ref "$ref" \
      --arg lastsub "$lastsub" --arg lastc "$lastc" \
      --argjson dirty "${dirty:-0}" --argjson age "$age" --argjson detached "$wdet" \
      --argjson stale "$stale" --argjson primary "$primary" --argjson touched "$touched" \
      --argjson landed "$landed" \
      '. + [{path: $path, branch: (if $branch == "" then null else $branch end),
             ref: (if $ref == "" then null else $ref end), detached: $detached,
             primary: $primary, dirty_count: $dirty,
             last_commit: (if $lastc == "" then null else $lastc end),
             last_subject: (if $lastsub == "" then null else $lastsub end),
             idle_days: $age, stale: $stale, touched_in_window: $touched,
             landed_pr: $landed}]' <<<"$WORKTREES")"
  done < <(git worktree list --porcelain 2>/dev/null | awk '
    /^worktree /{ if (p != "") print p "\t" b "\t" d; p = substr($0, 10); b = ""; d = "false" }
    /^branch /  { b = substr($0, 8); sub("^refs/heads/", "", b) }
    /^detached/ { d = "true" }
    END         { if (p != "") print p "\t" b "\t" d }')
fi

# --------------------------------------------------------------------- PRs
# Every list is scoped to THIS repo's origin. `gh pr list` is used rather than
# `gh search prs`: the search index lags and `--state=all` is invalid there.
PR_FIELDS='number,title,url,state,isDraft,updatedAt,createdAt,author,headRefName'
gh_prs() { ait_run_capped "$CAP" gh pr list --repo "$NWO" --limit 40 --json "$PR_FIELDS" "$@" 2>/dev/null; }
REF_JQ='
  def leaf: split("/") | last;
  def refof:
    ((.headRefName // "") | leaf) as $l
    | ([$l | scan("[A-Z][A-Z0-9]+-[0-9]+")] | first)
      // ([$l | scan("^[0-9]+")] | first | if . then "#" + . else null end)
      // ([$l | scan("(?:^|-)issue-?([0-9]+)") | .[0]] | first | if . then "#" + . else null end)
      // ([(.title // "") | scan("[A-Z][A-Z0-9]+-[0-9]+")] | first)
      // ([(.title // "") | scan("#[0-9]+")] | first)
      // null;
  def with_refs: map(. + {ref: refof});
'
AUTHORED='[]'; REVREQ='[]'; MENTIONS='[]'; MERGED='[]'; ALLTIME='[]'
if [ "$GH_OK" = true ]; then
  AUTHORED="$(gh_prs --author @me --state open)"
  is_array "$AUTHORED" || { note_err "gh pr list (authored) unusable"; AUTHORED='[]'; }
  REVREQ="$(gh_prs --search 'review-requested:@me' --state open)"
  is_array "$REVREQ" || { note_err "gh pr list (review-requested) unusable"; REVREQ='[]'; }
  MENTIONS="$(gh_prs --search 'mentions:@me' --state open)"
  is_array "$MENTIONS" || { note_err "gh pr list (mentions) unusable"; MENTIONS='[]'; }
  MERGED="$(gh_prs --author @me --state merged --search "merged:>=$SINCE_DATE")"
  is_array "$MERGED" || { note_err "gh pr list (merged) unusable"; MERGED='[]'; }
  # Unwindowed on purpose: a PR merged weeks ago whose issue never closed is
  # drift, and a windowed list cannot see it.
  ALLTIME="$(ait_run_capped "$CAP" gh pr list --repo "$NWO" --author @me --state all --limit 100 --json "$PR_FIELDS" 2>/dev/null)"
  is_array "$ALLTIME" || { note_err "gh pr list (all-time) unusable"; ALLTIME='[]'; }
  AUTHORED="$(jq -c "$REF_JQ with_refs" <<<"$AUTHORED")"
  REVREQ="$(jq -c "$REF_JQ with_refs" <<<"$REVREQ")"
  MENTIONS="$(jq -c "$REF_JQ with_refs" <<<"$MENTIONS")"
  MERGED="$(jq -c "$REF_JQ with_refs" <<<"$MERGED")"
  ALLTIME="$(jq -c "$REF_JQ with_refs" <<<"$ALLTIME")"
fi

# Deep detail for PRs that are mine or awaiting me. `gh pr checks` and
# statusCheckRollup 403 on a fine-grained PAT (checks is Apps-only), so CI
# comes from the Actions API, which actions:read covers.
DEEP='[]'
if [ "$GH_OK" = true ]; then
  TARGETS="$(jq -c -s 'add | unique_by(.url) | .[0:'"$MAX_PR_DEEP"']' <(echo "$AUTHORED") <(echo "$REVREQ") 2>/dev/null || echo '[]')"
  while IFS=$'\t' read -r num url title pref; do
    [ -n "$num" ] || continue
    meta="$(ait_run_capped "$CAP" gh pr view "$num" --repo "$NWO" \
      --json reviewDecision,headRefName,isDraft,mergeable,updatedAt,comments,reviews 2>/dev/null)"
    [ -n "$meta" ] || { note_err "gh pr view failed for $NWO#$num"; continue; }
    owner="${NWO%%/*}"; name="${NWO##*/}"
    threads="$(ait_run_capped "$CAP" gh api graphql -f query='
      query($owner:String!,$name:String!,$num:Int!){
        repository(owner:$owner,name:$name){
          pullRequest(number:$num){
            reviewThreads(first:100){nodes{
              isResolved isOutdated
              comments(first:1){nodes{author{login} body url createdAt}}}}}}}' \
      -F owner="$owner" -F name="$name" -F num="$num" 2>/dev/null)"
    unresolved=0; threadlist='[]'
    if [ -n "$threads" ]; then
      unresolved="$(jq '[.data.repository.pullRequest.reviewThreads.nodes[]? | select(.isResolved == false)] | length' <<<"$threads" 2>/dev/null || echo 0)"
      threadlist="$(jq -c '[.data.repository.pullRequest.reviewThreads.nodes[]?
        | select(.isResolved == false)
        | {author: (.comments.nodes[0].author.login // null), url: (.comments.nodes[0].url // null),
           created: (.comments.nodes[0].createdAt // null), outdated: .isOutdated,
           excerpt: ((.comments.nodes[0].body // "")[0:280])}]' <<<"$threads" 2>/dev/null || echo '[]')"
    fi
    head="$(jq -r '.headRefName // empty' <<<"$meta")"
    ci_status=null
    if [ -n "$head" ]; then
      runs="$(ait_run_capped "$CAP" gh api "repos/$NWO/actions/runs?branch=$head&per_page=1" 2>/dev/null)"
      if [ -n "$runs" ]; then
        ci_status="$(jq -c '(.workflow_runs[0] // {})
          | {status: (.status // null), conclusion: (.conclusion // null), name: (.name // null),
             run_url: (.html_url // null), started: (.run_started_at // null)}' <<<"$runs" 2>/dev/null || echo null)"
      else
        note_err "actions API failed for $NWO ($head)"
      fi
    fi
    new_comments="$(jq -c --arg since "$SINCE" --arg me "$GH_LOGIN" \
      '[((.comments // []) + (.reviews // []))[]
        | select((.createdAt // .submittedAt // "") > $since)
        | select((.author.login // "") != $me)
        | {author: (.author.login // null), created: (.createdAt // .submittedAt),
           url: (.url // null), state: (.state // null), excerpt: ((.body // "")[0:280])}]' <<<"$meta" 2>/dev/null || echo '[]')"
    DEEP="$(jq -c --arg nwo "$NWO" --argjson num "$num" --arg url "$url" --arg title "$title" \
      --arg head "$head" --arg pref "$pref" --argjson unresolved "${unresolved:-0}" \
      --argjson threads "$threadlist" --argjson ci "${ci_status:-null}" \
      --argjson newc "${new_comments:-[]}" --argjson meta "$meta" \
      '. + [{repo: $nwo, number: $num, url: $url, title: $title, headRefName: $head,
             ref: (if $pref == "" then null else $pref end),
             review_decision: ($meta.reviewDecision // null), is_draft: ($meta.isDraft // false),
             mergeable: ($meta.mergeable // null), updated: ($meta.updatedAt // null),
             unresolved_threads: $unresolved, threads: $threads, ci: $ci, new_comments: $newc}]' <<<"$DEEP")"
  done < <(jq -r '.[] | [(.number | tostring), .url, .title, (.ref // "")] | @tsv' <<<"$TARGETS" 2>/dev/null)
fi

# ------------------------------------------------------------ resume notes
RESUME='[]'
if [ -d "$STATE_DIR/resume" ]; then
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    first="$(head -1 "$f" 2>/dev/null)"
    ref="$(printf '%s' "$first" | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | head -1)" || ref=""
    mt="$(ait_file_mtime "$f")"; [ -n "$mt" ] || mt=0
    age=$(( (NOW_EPOCH - mt) / 86400 ))
    RESUME="$(jq -c --arg p "$f" --arg s "$(basename "$f" .md)" --arg r "$ref" \
      --arg w "$(ait_iso_from_epoch "$mt")" --argjson age "$age" \
      '. + [{path: $p, slug: $s, ref: (if $r == "" then null else $r end), written: $w, age_days: $age}]' <<<"$RESUME")"
  done < <(find "$STATE_DIR/resume" -maxdepth 1 -name '*.md' 2>/dev/null | sort)
fi

# ------------------------------------------------------------------- loops
LOOPS='[]'
if [ -d "$STATE_DIR/loops" ]; then
  LOOPS="$(cat "$STATE_DIR"/loops/*.json 2>/dev/null | jq -s -c --arg since "$SINCE" '
    [.[] | {id, mode, ref, branch, state, stop_reason, started,
            iterations_count: ((.iterations // []) | length),
            last_action: ((.iterations // []) | last | .action // null),
            actions_in_window: [(.iterations // [])[] | select(.at >= $since and .noop != true)],
            prs_opened: (.prs_opened // [])}]' 2>/dev/null || echo '[]')"
  [ -n "$LOOPS" ] || LOOPS='[]'
fi

# ------------------------------------------------------------------ ledger
# Join every surface on an EXTRACTED ref compared for equality — never a
# substring test: "#604" is inside "[#6041] ..." and would steal that PR.
LEDGER="$(jq -n --argjson wt "$WORKTREES" --argjson rn "$RESUME" --argjson lp "$LOOPS" \
  --argjson at "$ALLTIME" --argjson dp "$DEEP" \
  --arg backend "$BACKEND" --arg gh_repo "$GH_REPO" --arg jira "$JIRA_SITE" '
  def url($k):
    if $backend == "github" and $gh_repo != "" and ($k | startswith("#"))
      then "https://github.com/" + $gh_repo + "/issues/" + ($k | ltrimstr("#"))
    elif $backend == "jira" and $jira != "" and ($k | test("^[A-Z][A-Z0-9]+-[0-9]+$"))
      then "https://" + $jira + "/browse/" + $k
    else null end;
  ([ ($wt[] | .ref), ($rn[] | .ref), ($lp[] | .ref), ($at[] | .ref) ] | map(select(. != null)) | unique) as $keys
  | [ $keys[] as $k
      | ([$at[] | select(.ref == $k)]) as $prs
      | ([$lp[] | select(.ref == $k)]) as $loops
      | { ref: $k, ticket_url: url($k),
          worktree:    ([$wt[] | select(.ref == $k)] | first // null),
          resume_note: ([$rn[] | select(.ref == $k)] | first // null),
          loops: $loops,
          open_pr:   ([$prs[] | select(.state == "OPEN")] | first // null),
          merged_pr: ([$prs[] | select(.state == "MERGED")] | first // null),
          closed_pr: ([$prs[] | select(.state == "CLOSED")] | first // null),
          detail:    ([$dp[] | select(.ref == $k)] | first // null),
          tracker_status: null }
      # All-time PR history pulls in every issue ever shipped. A row is only
      # worth a verdict when something is still lying around.
      | .actionable = (.worktree != null or .resume_note != null or .open_pr != null
                       or any(.loops[]; .state == "live")) ]' 2>/dev/null)"
LEDGER="${LEDGER:-[]}"

ORPHANS="$(jq -c '[.[] | select(.primary == false and (.detached == true or .ref == null))]' <<<"$WORKTREES" 2>/dev/null || echo '[]')"

jq -n \
  --arg generated "$(iso_now)" --arg since "$SINCE" --arg last "${LAST_RUN:-}" \
  --arg state "$STATE" --arg state_dir "$STATE_DIR" --arg config "$CONFIG" \
  --arg backend "$BACKEND" --arg nwo "$NWO" --arg login "$GH_LOGIN" \
  --argjson first "$FIRST_RUN" --argjson days "$WIN_DAYS" --argjson summ "$SUMMARIZE" \
  --argjson ghok "$GH_OK" --argjson stale_days "$STALE_DAYS" \
  --argjson wt "$WORKTREES" --argjson rn "$RESUME" --argjson lp "$LOOPS" \
  --argjson au "$AUTHORED" --argjson rr "$REVREQ" --argjson mn "$MENTIONS" \
  --argjson mg "$MERGED" --argjson at "$ALLTIME" --argjson dp "$DEEP" \
  --argjson ledger "$LEDGER" --argjson orphans "$ORPHANS" --argjson errors "$ERRORS" \
  '{
    generated_at: $generated,
    window: {since: $since, last_run: (if $last == "" then null else $last end),
             first_run: $first, days: $days, summarize_mode: $summ, state_file: $state},
    viewer: {gh_login: (if $login == "" then null else $login end), gh_available: $ghok},
    config: {path: (if $config == "" then null else $config end),
             backend: (if $backend == "" then null else $backend end),
             repo: (if $nwo == "" then null else $nwo end),
             state_dir: $state_dir, stale_days: $stale_days},
    worktrees: $wt,
    resume_notes: $rn,
    loops: $lp,
    prs: {authored_open: $au, review_requested: $rr, mentions: $mn,
          merged_in_window: $mg, all_time_authored: $at},
    pr_detail: $dp,
    ledger: $ledger,
    orphan_worktrees: $orphans,
    errors: $errors
  }'

exit 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest -q tests/test_tracker_brief_collect.py`
Expected: all pass. If `test_worktrees_stale_dirty_and_landed` reports `idle_days == 0`, the commit did not take `GIT_COMMITTER_DATE`; the `git()` helper must pass `env` through (it does in Task 1's helper — check the fixture merged `OLD` into a full env copy).

- [ ] **Step 5: Shellcheck and commit**

Run: `shellcheck scripts/tracker-brief-collect.sh` (if installed). Expected: clean apart from SC2016 on jq programs, which may be disabled file-wide with a `# shellcheck disable=SC2016` directive under the shebang.

```bash
git add scripts/tracker-brief-collect.sh tests/test_tracker_brief_collect.py
git commit -m "feat(scripts): tracker-brief collector"
```

---

### Task 7: `/tracker-brief` command

**Files:**
- Create: `commands/tracker-brief.md`

**Interfaces:**
- Consumes: the JSON from `scripts/tracker-brief-collect.sh` (Task 6); `list_updated_issues`, `read_comments`, `view_issue` from the contract (Task 5).
- Produces: the verdict vocabulary (`Needs action`, `Status drift`, `Waiting`, `Closeable`, `Stale`, `No code artifact`) that README (Task 11) documents.

- [ ] **Step 1: Write the command file**

Create `commands/tracker-brief.md`:

````markdown
---
description: Inbound digest for this project since the last run — tracker activity, PRs awaiting you, CI, worktrees, resume notes and loop records joined into one ledger with a verdict per issue.
---

# /tracker-brief

Answers one question: **what moved in this project while I was away, and what wants me now?** Inbound only. The state of the current Claude conversation is `/session-brief`'s job.

Read-only except the window stamp at the end. Never comments, closes, merges, or removes a worktree — it prints the exact command for each of those and stops.

## Step 0 — Collect the deterministic facts

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/tracker-brief-collect.sh" > "${TMPDIR:-/tmp}/tracker-brief.json"
jq -c '.window, .viewer, .config, .errors' "${TMPDIR:-/tmp}/tracker-brief.json"
```

The script always exits 0 and always prints one JSON object. It covers this repo's worktrees, PRs on the git host (authored, review-requested, mentions, merged in window, all-time authored), per-PR review threads + comments + CI, the resume notes `/session-brief` wrote, `/tracker-loop` records, and a `ledger` joining all of it on issue ref. It does **not** read the tracker — a shell script has no backend access — so tracker activity is gathered in Step 1 and `ledger[].tracker_status` in Step 2.

Read `.window`: `since` is the lookback start, `days` its span, `summarize_mode` true past five days (compress hard — a post-holiday run must not emit a wall of text). Read `.errors` and carry each into the brief's last line; a degraded source is reported, never silently blank.

## Step 1 — Tracker activity

Through the configured backend (`backends/<backend>.md`), never a raw CLI or MCP call:

1. `list_updated_issues({since: window.since})` — issues that moved in the window.
2. For the first 20 of those, `read_comments({ref})`; keep comments with `created >= since` whose author is not the viewer. These are the "someone said something on my issue" items.

With no `.claude/issue-tracker.yaml` (`config.backend: null`), skip this step and say so; the brief is then git-host + worktrees only.

## Step 2 — Fill the ledger

For every `ledger[]` row with `actionable == true`, `view_issue({ref})` and set `tracker_status` to its `status`. Rows with `actionable == false` are history (a shipped PR whose issue is closed and nothing left on disk) and are neither fetched nor printed.

Then one verdict per actionable row, first match wins:

| Verdict | Condition | Print |
|---|---|---|
| **Needs action** | `detail.unresolved_threads > 0`, `detail.new_comments` non-empty, `detail.ci.conclusion == "failure"`, `detail.review_decision == "CHANGES_REQUESTED"`, or a loop with `stop_reason` naming NEEDS YOU | The specific thing, linked |
| **Status drift** | `merged_pr` set and `tracker_status` is open; or `tracker_status` closed and `open_pr` set | Which side is stale, and the close / reopen command |
| **Waiting** | `open_pr` set, review required, nothing unresolved | Who it is waiting on — no operator action |
| **Closeable** | `merged_pr` set and `tracker_status` closed, with a `worktree` or `resume_note` still on disk | `git worktree remove <path>` and the resume-note path to delete |
| **Stale** | `worktree.stale == true` | `worktree.landed_pr` state: `MERGED` → shipped, free it; `CLOSED` → closed unmerged, confirm before discarding; `OPEN` → still in flight; `null` → genuine abandonment |
| **No code artifact** | `resume_note` or a live loop, but no worktree and no PR | List it; do not force a verdict |

Status drift is expected to be common: GitHub's `Closes #a, #b` auto-closes only the first ref. Judge "closed" on the backend's status, not on a resolution field.

Never use `git merge-base --is-ancestor` to prove a branch landed. Squash and rebase merges rewrite the SHA, so a branch whose PR merged reports "not an ancestor". Trust `landed_pr`, which asked the git host about the branch directly.

`orphan_worktrees[]` (detached, or no ref) are listed after the ledger with their path and last subject; the primary checkout is never among them.

## Step 3 — Loops

`loops[]` are `/tracker-loop` records. For each `live` one, print mode, ref, iteration count, last action, and `actions_in_window`. For each `stopped` one whose `stop_reason` is set, print the reason — a loop that stopped on NEEDS YOU is a Needs-action item and is already in the ledger row.

## Step 4 — Output

Terminal, in this order and nothing else:

1. **Needs you** — merged and ranked across tracker comments, PR threads, CI, drift, and loop stops. The only section that must be read.
2. **Status drift** — one line per row, with the command that fixes it.
3. **Closeable / stale** — one line per row, with the `git worktree remove` line.
4. **Loops** — one line per live loop.
5. **Degraded** — one line per `errors[]` entry; omit the section when empty.

When the `Artifact` tool exists in this session, also publish the full brief (the five sections above plus the tracker activity list, the PR lists, and the complete ledger table) titled `Tracker Brief`, and keep that title stable across days so it stays one recognisable page. No daily log file is written.

Then stamp the window so the next run picks up exactly here:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/tracker-brief-collect.sh" --commit-run
```

Stamp **only after** the brief is written. Stamping a failed run silently skips that window forever.

## Known traps

| Trap | Why it bites |
|---|---|
| `gh pr checks` / `statusCheckRollup` | 403 on a fine-grained PAT. The collector already used the Actions API |
| `git merge-base --is-ancestor` as landed-proof | False negative on squash/rebase merges. Use `landed_pr` |
| Verdicting every ledger row | The PR join is all-time. Filter `actionable` first |
| Stamping `--commit-run` before the brief is written | That window is skipped permanently |
| Reading the tracker with `gh issue list` or an MCP call directly | Backend-agnostic means contract ops only; `backends/<backend>.md` has the literal call |
| Treating an empty `errors[]`-less section as "nothing happened" | Say what was checked so an absence reads as a result |
````

- [ ] **Step 2: Sanity-run the collector from the plugin tree**

Run from the worktree root: `bash scripts/tracker-brief-collect.sh | jq '.window, (.worktrees | length), (.ledger | length), .errors'`.
Expected: a window object, at least 1 worktree, a ledger array, and an errors array (possibly listing a gh auth issue).

- [ ] **Step 3: Commit**

```bash
git add commands/tracker-brief.md
git commit -m "feat(commands): /tracker-brief"
```

---

### Task 8: Loop bookkeeping script and decision-table spec

**Files:**
- Create: `scripts/loop-record.sh`
- Create: `tests/fixtures/loops/babysit_*.json` (nine files, listed below)
- Test: `tests/test_loop_record.py`, `tests/test_loop_decisions.py`

**Interfaces:**
- Consumes: `ait_state_dir` from Task 1.
- Produces: the record file shape at `<state-dir>/loops/<id>.json` (read by Tasks 3 and 6) and these subcommands, every one printing JSON on stdout:
  - `create <mode> <ref> <branch> [--merge] [--draft] [--cron-id <id>] [--max-iterations N] [--max-hours N] [--idle-stop-after N] [--interval <s>]` → `{id, path}`
  - `find <mode> <ref>` → live record or `null`
  - `check <id>` → `{ok: true, iterations, hours, trailing_noops}` or `{ok: false, reason}`
  - `append <id> <action> <detail> [--noop]` → `{id, iterations, last_action}`
  - `add-pr <id> <pr-ref>`, `set-cron <id> <job-id>` → `{id, ...}`
  - `stop <id> <reason>` → `{id, state, stop_reason, cron_job_id}`
  - `get <id>` → the record; `list` → live records summarised
  - exit 0 on success, 1 for an unknown id, 2 for a usage error
- Produces: the babysit decision order pinned by `tests/test_loop_decisions.py`, which `commands/tracker-loop.md` (Task 9) must reproduce verbatim.

- [ ] **Step 1: Write the failing record tests**

Create `tests/test_loop_record.py`:

```python
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
```

- [ ] **Step 2: Write the failing decision-table tests and fixtures**

Create `tests/test_loop_decisions.py`:

```python
"""Executable spec for the /tracker-loop babysit decision table
(commands/tracker-loop.md "Mode: babysit"). First matching row wins.

The observation is the /session-brief collector JSON plus a `kind` the
command assigns to each awaiting review thread before consulting the table:
`code` (a concrete change request) or `judgement` (a question needing a
human answer)."""
import json
from pathlib import Path

import pytest

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "loops").glob("babysit_*.json"))


def decide_babysit(obs, merge=False):
    pr = obs.get("pr") or {}
    ci = obs.get("ci") or {}
    threads = (obs.get("review") or {}).get("threads") or []
    awaiting = [t for t in threads if t.get("awaiting_you")]
    if pr.get("state") in ("MERGED", "CLOSED"):
        return "stop:done"
    if pr.get("mergeable") == "CONFLICTING":
        return "rebase"
    if ci.get("conclusion") == "failure":
        return "fix-ci"
    if any(t.get("kind") == "code" for t in awaiting):
        return "address-review"
    if any(t.get("kind") == "judgement" for t in awaiting):
        return "stop:needs-you"
    if pr.get("reviewDecision") == "APPROVED":
        return "merge" if merge else "stop:ready-to-merge"
    if ci.get("status") == "in_progress":
        return "wait:ci"
    return "wait:idle"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_babysit_table(fixture):
    case = json.loads(fixture.read_text())
    assert decide_babysit(case["observation"], merge=case.get("merge", False)) == case["expected"]


def test_fixture_set_covers_every_row():
    expected = {json.loads(f.read_text())["expected"] for f in FIXTURES}
    assert expected == {"stop:done", "rebase", "fix-ci", "address-review", "stop:needs-you",
                        "merge", "stop:ready-to-merge", "wait:ci", "wait:idle"}
```

Create the nine fixtures under `tests/fixtures/loops/`:

`babysit_merged.json`
```json
{"observation": {"pr": {"state": "MERGED", "mergeable": "CONFLICTING"}, "ci": {"conclusion": "failure"}}, "expected": "stop:done"}
```

`babysit_conflict_beats_ci.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "CONFLICTING"}, "ci": {"conclusion": "failure"}}, "expected": "rebase"}
```

`babysit_ci_failure.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE"}, "ci": {"status": "completed", "conclusion": "failure", "failed_jobs": [{"name": "pytest"}]}, "review": {"threads": [{"awaiting_you": true, "kind": "code"}]}}, "expected": "fix-ci"}
```

`babysit_code_thread.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "CHANGES_REQUESTED"}, "ci": {"conclusion": "success"}, "review": {"threads": [{"awaiting_you": true, "kind": "judgement"}, {"awaiting_you": true, "kind": "code"}]}}, "expected": "address-review"}
```

`babysit_judgement_thread.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "APPROVED"}, "ci": {"conclusion": "success"}, "review": {"threads": [{"awaiting_you": true, "kind": "judgement"}, {"awaiting_you": false, "kind": "code"}]}}, "expected": "stop:needs-you"}
```

`babysit_approved_no_merge.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "APPROVED"}, "ci": {"conclusion": "success"}}, "expected": "stop:ready-to-merge"}
```

`babysit_approved_merge.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "APPROVED"}, "ci": {"conclusion": "success"}}, "merge": true, "expected": "merge"}
```

`babysit_ci_running.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "REVIEW_REQUIRED"}, "ci": {"status": "in_progress", "conclusion": null}}, "expected": "wait:ci"}
```

`babysit_idle.json`
```json
{"observation": {"pr": {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "REVIEW_REQUIRED"}, "ci": {"status": "completed", "conclusion": "success"}, "review": {"threads": []}}, "expected": "wait:idle"}
```

- [ ] **Step 3: Run the tests to verify the record tests fail and the decision tests pass**

Run: `python -m pytest -q tests/test_loop_record.py tests/test_loop_decisions.py`
Expected: `test_loop_record.py` fails (script missing); `test_loop_decisions.py` passes (it is an executable spec of the table Task 9 writes).

- [ ] **Step 4: Write the bookkeeping script**

Create `scripts/loop-record.sh`:

```bash
#!/usr/bin/env bash
# loop-record.sh — bookkeeping for /tracker-loop. One JSON record per loop
# under <state-dir>/loops/<id>.json; every subcommand prints JSON on stdout.
# Budgets are enforced from the record on disk, so a loop survives a context
# compaction with its counters intact.
#
# Usage:
#   loop-record.sh create <mode> <ref> <branch> [--merge] [--draft] [--cron-id <id>]
#                  [--max-iterations N] [--max-hours N] [--idle-stop-after N] [--interval <s>]
#   loop-record.sh find <mode> <ref>              # live record with that mode+ref, or null
#   loop-record.sh check <id>                     # {"ok":true,...} or {"ok":false,"reason":...}
#   loop-record.sh append <id> <action> <detail> [--noop]
#   loop-record.sh add-pr <id> <pr-ref>
#   loop-record.sh set-cron <id> <job-id>
#   loop-record.sh stop <id> <reason>
#   loop-record.sh get <id>
#   loop-record.sh list                           # live records, summarised
#
# Exit 0 on success, 1 when the record does not exist, 2 on a usage error.

set -uo pipefail
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

DIR="$(ait_state_dir "$PWD")/loops"
mkdir -p "$DIR" 2>/dev/null
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
usage() { printf '{"error":"usage: %s"}\n' "$1" >&2; exit 2; }
path_of() { printf '%s/%s.json' "$DIR" "$1"; }
require() { [ -f "$(path_of "$1")" ] || { printf '{"error":"no such loop","id":"%s"}\n' "$1"; exit 1; }; }
# modify <id> <jq options and filter...> — read-modify-write, atomic.
modify() {
  local id="$1" p
  shift
  p="$(path_of "$id")"
  jq "$@" "$p" >"$p.tmp" && mv "$p.tmp" "$p"
}
all_records() { cat "$DIR"/*.json 2>/dev/null | jq -s '.' 2>/dev/null || echo '[]'; }

cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
  create)
    [ $# -ge 3 ] || usage "create <mode> <ref> <branch> [flags]"
    mode="$1"; ref="$2"; branch="$3"; shift 3
    [ -n "$mode" ] && [ -n "$ref" ] || usage "create <mode> <ref> <branch> [flags]"
    merge=false; draft=false; cron=""; maxi=50; maxh=24; idle=12; interval="15m"
    while [ $# -gt 0 ]; do
      case "$1" in
        --merge) merge=true ;;
        --draft) draft=true ;;
        --cron-id) cron="${2:-}"; shift ;;
        --max-iterations) maxi="${2:-50}"; shift ;;
        --max-hours) maxh="${2:-24}"; shift ;;
        --idle-stop-after) idle="${2:-12}"; shift ;;
        --interval) interval="${2:-15m}"; shift ;;
        *) usage "unknown flag $1" ;;
      esac
      shift
    done
    slug="$(printf '%s' "$ref" | tr '/#' '--' | sed 's/^-*//' | tr -cd 'A-Za-z0-9._-')"
    base="$(printf '%s-%s-%s' "$mode" "${slug:-x}" "$(date -u +%Y%m%d%H%M%S)")"
    id="$base"; n=2
    while [ -f "$(path_of "$id")" ]; do id="$base-$n"; n=$((n + 1)); done
    jq -n --arg id "$id" --arg mode "$mode" --arg ref "$ref" --arg branch "$branch" \
      --arg now "$(now)" --arg cron "$cron" --arg interval "$interval" \
      --argjson merge "$merge" --argjson draft "$draft" \
      --argjson maxi "$maxi" --argjson maxh "$maxh" --argjson idle "$idle" \
      '{id: $id, mode: $mode, ref: $ref, branch: (if $branch == "" then null else $branch end),
        started: $now, state: "live", stop_reason: null, stopped: null,
        cron_job_id: (if $cron == "" then null else $cron end),
        options: {merge: $merge, draft: $draft, interval: $interval},
        budget: {max_iterations: $maxi, max_hours: $maxh, idle_stop_after: $idle},
        iterations: [], prs_opened: []}' >"$(path_of "$id")"
    jq -c --arg p "$(path_of "$id")" '{id, path: $p}' "$(path_of "$id")"
    ;;
  find)
    [ $# -ge 2 ] || usage "find <mode> <ref>"
    all_records | jq -c --arg m "$1" --arg r "$2" \
      '[.[] | select(.state == "live" and .mode == $m and .ref == $r)] | first // null'
    ;;
  check)
    [ $# -ge 1 ] || usage "check <id>"
    require "$1"
    jq -c --argjson now "$(date -u +%s)" '
      def epoch: sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch 0);
      (.iterations | length) as $n
      | (($now - (.started | epoch)) / 3600) as $hours
      | ([.iterations | reverse[] | (.noop == true)] | index(false) // $n) as $trailing
      | if .state != "live" then {ok: false, reason: ("stopped: " + (.stop_reason // "unknown"))}
        elif $n >= .budget.max_iterations then {ok: false, reason: "budget: max_iterations"}
        elif $hours >= .budget.max_hours then {ok: false, reason: "budget: max_hours"}
        elif $trailing >= .budget.idle_stop_after then {ok: false, reason: "budget: idle_stop_after"}
        else {ok: true, iterations: $n, hours: (($hours * 10 | floor) / 10), trailing_noops: $trailing} end' \
      "$(path_of "$1")"
    ;;
  append)
    [ $# -ge 2 ] || usage "append <id> <action> <detail> [--noop]"
    id="$1"; action="$2"; detail="${3:-}"; noop=false
    [ "${4:-}" = "--noop" ] && noop=true
    [ "$detail" = "--noop" ] && { detail=""; noop=true; }
    require "$id"
    modify "$id" --arg at "$(now)" --arg a "$action" --arg d "$detail" --argjson n "$noop" \
      '.iterations += [{at: $at, action: $a, detail: $d, noop: $n}]'
    jq -c '{id, iterations: (.iterations | length), last_action: (.iterations | last | .action)}' "$(path_of "$id")"
    ;;
  add-pr)
    [ $# -ge 2 ] || usage "add-pr <id> <pr-ref>"
    require "$1"
    modify "$1" --arg pr "$2" '.prs_opened = ((.prs_opened // []) + [$pr] | unique)'
    jq -c '{id, prs_opened}' "$(path_of "$1")"
    ;;
  set-cron)
    [ $# -ge 2 ] || usage "set-cron <id> <job-id>"
    require "$1"
    modify "$1" --arg j "$2" '.cron_job_id = $j'
    jq -c '{id, cron_job_id}' "$(path_of "$1")"
    ;;
  stop)
    [ $# -ge 2 ] || usage "stop <id> <reason>"
    require "$1"
    modify "$1" --arg r "$2" --arg at "$(now)" '.state = "stopped" | .stop_reason = $r | .stopped = $at'
    jq -c '{id, state, stop_reason, cron_job_id}' "$(path_of "$1")"
    ;;
  get)
    [ $# -ge 1 ] || usage "get <id>"
    require "$1"
    jq -c '. + {path: $p}' --arg p "$(path_of "$1")" "$(path_of "$1")"
    ;;
  list)
    all_records | jq -c '[.[] | select(.state == "live")
      | {id, mode, ref, branch, started, cron_job_id, prs_opened,
         iterations: (.iterations | length), last_action: (.iterations | last | .action // null)}]'
    ;;
  *) usage "create|find|check|append|add-pr|set-cron|stop|get|list" ;;
esac
exit 0
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest -q tests/test_loop_record.py tests/test_loop_decisions.py`
Expected: all pass. `test_check_max_hours` reaches into the record via `rglob`; if it cannot find the file, `AIT_STATE_DIR` is not being honoured by `ait_state_dir`.

- [ ] **Step 6: Shellcheck and commit**

Run: `shellcheck scripts/loop-record.sh` (if installed). Expected: clean apart from SC2016 on jq programs.

```bash
git add scripts/loop-record.sh tests/test_loop_record.py tests/test_loop_decisions.py tests/fixtures/loops
git commit -m "feat(scripts): loop-record bookkeeping and babysit decision-table spec"
```

---

### Task 9: `/tracker-loop` command

**Files:**
- Create: `commands/tracker-loop.md`

**Interfaces:**
- Consumes: `scripts/session-brief-collect.sh` JSON (Task 3), `scripts/loop-record.sh` subcommands (Task 8), the `/session-brief` verdict table (Task 4), `/resume-initiative` next-up derivation and `/work-issue` pipeline (existing), contract ops `list_open_issues`, `view_issue`, `add_label`.
- Produces: the loop modes and stop reasons that `/work-issue --loop` and `/resume-initiative --loop` (Task 10) arm, and the pacing-hint line.

- [ ] **Step 1: Write the command file**

Create `commands/tracker-loop.md`. The babysit table below must match `tests/test_loop_decisions.py::decide_babysit` row for row; that test is the executable spec.

````markdown
---
description: Run ONE iteration of an unattended loop — babysit a PR to green, clear an epic leaf by leaf, or poll a label and dispatch /work-issue — with budgets and stop conditions kept on disk. Recurrence comes from /loop or a session cron.
---

# /tracker-loop <mode> [ref] [--merge | --draft] | status | stop [<id>]

One iteration per invocation. `/tracker-loop` never schedules itself and never calls `ScheduleWakeup`; recurrence is external:

| Recurrence | How |
|---|---|
| Self-paced (preferred) | `/loop /agent-issue-tracker:tracker-loop babysit #42` — the harness picks each delay; this command ends every iteration with a **pacing hint** the self-paced loop follows |
| Fixed interval | `/loop 15m /agent-issue-tracker:tracker-loop poll` |
| Armed by a driver | `/work-issue #42 --start --loop` or `/resume-initiative #9 --start --loop` creates a session cron that fires this command (see those commands) |

Session crons expire after seven days and end with the conversation; `/schedule` (cloud routines) is the documented answer for longer-lived automation and is not wrapped here.

## Modes

```
/tracker-loop babysit [<pr-number> | <issue-ref>] [--merge]
/tracker-loop clear <epic-ref> [--draft | --merge]
/tracker-loop poll [--label <name>] [--draft | --merge]
/tracker-loop status
/tracker-loop stop [<loop-id>]
```

`--draft` and `--merge` are mutually exclusive; refuse with a one-line message if both are passed. They pass straight through to the `/work-issue` invocations a loop makes and to the babysit merge rule.

## Configuration

Optional `loops:` block in `.claude/issue-tracker.yaml` (defaults shown; `examples/issue-tracker.yaml.example` documents it):

```yaml
loops:
  interval: 15m          # cron cadence for --loop; poll idle cadence
  max_iterations: 50
  max_hours: 24
  idle_stop_after: 12    # consecutive no-change iterations
  pr_mode: draft         # draft | ready — PRs opened by unattended loops
  poll_label: agent-ready
  # claim_label: agent-claimed
  # max_concurrent: 1
```

Read each key with `"${CLAUDE_PLUGIN_ROOT}/scripts/lib/common.sh"`'s `ait_config_get loops.<key>`; an unset key takes the default above.

## The iteration skeleton (every mode)

All bookkeeping goes through `"${CLAUDE_PLUGIN_ROOT}/scripts/loop-record.sh"` (`LR` below). Every subcommand prints JSON.

1. **Load or create the record.** `LR find <mode> <ref>`; when `null`, `LR create <mode> <ref> <branch> [--merge] [--draft] --max-iterations … --max-hours … --idle-stop-after … --interval …` with the configured budgets. `<branch>` is the current branch for `babysit`, the epic ref's slug for `clear`, and `""` for `poll`. Refuse to create a second live loop of the same mode and ref; report the existing id instead.
2. **Budget check.** `LR check <id>`. On `ok: false`, go to step 8 with the `reason`.
3. **Collect.** Run `"${CLAUDE_PLUGIN_ROOT}/scripts/session-brief-collect.sh"` for the current branch (`SB` below). Modes `clear` and `poll` also read the tracker in their own step.
4. **Decide.** The mode's table yields exactly one action, or `wait`, or `stop <reason>`.
5. **Act.** Perform that one action through the existing skills and commands. Never two actions in one iteration.
6. **Checkpoint.** Apply the `/session-brief` verdict table (`commands/session-brief.md` Step 3) to `SB.session`. A `fresh session` verdict writes the resume note exactly as `/session-brief` Step 4 does, including the `**Loop:**` re-arm line, then goes to step 8 with reason `checkpoint: fresh session`.
7. **Record and report.** `LR append <id> <action> "<detail>" [--noop]` — `--noop` for `wait`. Then print one line:

   `loop <id> · <mode> <ref> · iteration <n> · <action or noop> · next: <pacing hint>`

8. **Stop.** `LR stop <id> "<reason>"`; if the printed `cron_job_id` is set, `CronDelete` it. Print the reason. When the reason is NEEDS YOU, print the NEEDS YOU block (author, path:line, excerpt) exactly as `/session-brief` would. A stopped loop is over; `/loop` running this command again sees `ok: false` at step 2 and stops again, cheaply.

## Mode: babysit

Work source: `SB.pr` for the current branch, or — when a ref was given and the current branch has no PR — the branch of the PR `gh pr list --repo <nwo> --head <branch>` resolves for that ref's worktree (`.claude/worktrees/<branch-with-slash-as-plus>`); enter that worktree first.

Before the table, classify every `SB.review.threads[]` with `awaiting_you == true` as `code` (a concrete, actionable change request: rename, split, add a test, handle a case) or `judgement` (a question, a design objection, or anything a reasonable engineer would want the author to answer in prose).

| Observation (first match wins) | Action |
|---|---|
| `pr.state` is `MERGED` or `CLOSED` | **stop: done** |
| `pr.mergeable == "CONFLICTING"` | **rebase** onto `git.base`, resolve, push |
| `ci.conclusion == "failure"` | **fix-ci**: `superpowers:systematic-debugging` on `ci.failed_jobs`, `superpowers:test-driven-development` for the fix, push |
| an awaiting thread classified `code` | **address-review**: make the change, push, reply on the thread naming the commit SHA, resolve the thread |
| an awaiting thread classified `judgement` | **stop: needs-you** — quote author, path:line, excerpt |
| `pr.reviewDecision == "APPROVED"` and `--merge` | **merge**: `gh pr merge --squash --auto` (falls back to a direct squash merge only where auto-merge is unavailable), then **stop: done** |
| `pr.reviewDecision == "APPROVED"`, no `--merge` | **stop: ready-to-merge** — the operator's call |
| `ci.status == "in_progress"` | **wait** (hint: CI) |
| anything else | **wait** (hint: idle; counts toward `idle_stop_after`) |

Replies to humans are always code-backed: a pushed commit plus a comment naming it. The loop never argues a review point in prose; that is a NEEDS YOU.

## Mode: clear

Work source: `/resume-initiative <epic-ref>`'s next-up derivation (`commands/resume-initiative.md` "Deriving child state" and "Tree traversal"), reused as written — depth cap, cycle guard, and legacy branch included.

| Observation (first match wins) | Action |
|---|---|
| no open leaf | **stop: initiative clear** |
| the next leaf carries the `needs_design_label`, or its body fails the agent-prompt bail criteria (`skills/feature-request/SKILL.md`) | **skip**: comment on the leaf naming the gap, `LR append … skip`, move to the next open leaf in the same iteration; after three consecutive skips, **stop: three skips** |
| the next leaf already has an open PR | run **one babysit iteration** against it (enter its worktree; table above) instead of starting a new leaf |
| the next leaf is workable | **start**: `/work-issue <leaf> --start` with `--draft` / `--merge` passed through; `LR add-pr <id> <pr-ref>` when it opens a PR. That PR is this loop's babysit target on later iterations |

The checkpoint after each leaf is the reason this mode exists: a long clearing run compacts or hands off instead of degrading.

## Mode: poll

Work source: `list_open_issues({label: <poll_label>})` through the configured backend.

**Claimed** issues are skipped. An issue is claimed when any of:

- a worktree for its ref exists (`.claude/worktrees/` naming from `/work-issue` Step 3, or a `worktrees[]` entry in `tracker-brief-collect.sh` output whose `ref` matches),
- an open PR in this repo references it (`gh pr list --repo <nwo> --state open --search "<ref>"`),
- another live loop record names it (`LR list`, any record whose `ref` or `prs_opened` matches),
- it carries `loops.claim_label`, when that key is set.

Per iteration:

1. For each PR in this record's `prs_opened` that is still open (oldest first), run **one babysit iteration** against it, entering its worktree. A babysit stop reason of `done` drops that PR from consideration; `needs-you` stops the whole loop.
2. If fewer than `max_concurrent` (default 1) of this record's PRs are open, take the **oldest unclaimed** issue, apply `claim_label` via `add_label` when configured, and **dispatch** `/work-issue <ref> --start` with `--draft` when `loops.pr_mode` is `draft` (the default) or `--merge` when passed. `LR add-pr <id> <pr-ref>` once the PR exists.
3. Nothing to do → **wait** (hint: `loops.interval`).

No `remove_label` operation exists in the contract, so a `claim_label` stays on the issue until a human removes it or the issue closes. Two machines polling the same label without a `claim_label` can collide; the local claim signals do not cross machines.

## Pacing hint

The last line of every iteration. A self-paced `/loop` follows it; a fixed-interval loop ignores it.

| State | Hint |
|---|---|
| CI in progress | the duration of that workflow's last completed run (`ci.all_workflows[]` `when` deltas are not exposed — use the run's `run_started_at`/`updated_at` from `gh run view <id> --json startedAt,updatedAt`), floor 3m, cap 30m |
| a fix was just pushed | 5m — CI is about to start |
| waiting on a reviewer | 30m |
| poll found nothing | `loops.interval` |
| clear just started a leaf | none — the leaf's pipeline ran inline in this turn; next hint is 5m |
| stopped | none — say `stopped` |

## `status` and `stop`

- `status`: `LR list`, printed one line per live loop (`id · mode ref · iteration n · last action · cron armed|none`), followed by the last three stopped records with their reasons (`ls <state-dir>/loops`, `LR get`).
- `stop [<id>]`: with an id, `LR stop <id> "operator stop"` and `CronDelete` its `cron_job_id` if set. Without an id and exactly one live loop, stop that one; with several, list them and ask which.

## Safety rails

- Never merge without `--merge`; never open a ready PR on red (`/work-issue` Step 5 already refuses); never force-push.
- One action per iteration; a NEEDS YOU always stops the loop over continuing.
- Every tracker write goes through contract ops (`add_label`, comments via `upsert_comment` only where a machine block is involved; plain leaf comments use the backend's documented comment call); every git-host write is one `/work-issue` already documents.
- Budgets are enforced from the record on disk (`LR check`), before acting.
- `/tracker-loop stop`, `CronDelete`, and `Esc` on a `/loop` all end a loop; the record says which when it was `stop`.

## Failure modes

- **`LR find`/`create` cannot write the state dir** → report the path and stop; nothing else runs.
- **`SB.pr` is null in babysit** → no PR on this branch; stop with reason `no PR` and print the `/work-issue` line that would open one.
- **The tracker is unreachable in clear/poll** → the backend reports it; stop with the reason and point at `/tracker-doctor`. Do not fall back to `gh issue` or an MCP call.
- **`/work-issue` bails on a leaf** (vague body, needs-design) → that is the `skip` row; the comment it leaves is the record.
- **Iteration exceeds the session cron's interval** (a full `/work-issue` pipeline can) → the harness skips fires while the REPL is busy and does not catch up; nothing to do, the next fire picks up from the record.
````

- [ ] **Step 2: Cross-check the table against the executable spec**

Read `tests/test_loop_decisions.py::decide_babysit` and confirm the nine rows appear in the command's babysit table in the same order with the same outcomes (`stop:done`, `rebase`, `fix-ci`, `address-review`, `stop:needs-you`, `merge`, `stop:ready-to-merge`, `wait:ci`, `wait:idle`). Run `python -m pytest -q tests/test_loop_decisions.py` — still green.

- [ ] **Step 3: Commit**

```bash
git add commands/tracker-loop.md
git commit -m "feat(commands): /tracker-loop iteration command (babysit, clear, poll)"
```

---

### Task 10: `--loop` on the drivers, `loops:` config, `/tracker-doctor` validation

**Files:**
- Modify: `commands/work-issue.md` (Invocation modes table; new "Step 7 — Arm the loop"; Failure modes)
- Modify: `commands/resume-initiative.md` (Invocation modes table; Mode 3 tail)
- Modify: `examples/issue-tracker.yaml.example` (new `loops:` block after `session_titles`)
- Modify: `commands/tracker-doctor.md` (Phase 1: one WARN-only bullet and one FAIL row for the `loops:` block)

**Interfaces:**
- Consumes: `/tracker-loop` modes and `loop-record.sh create` / `set-cron` (Tasks 8–9); `CronCreate`.
- Produces: the `loops:` schema keys (`interval`, `max_iterations`, `max_hours`, `idle_stop_after`, `pr_mode`, `poll_label`, `claim_label`, `max_concurrent`) that `/tracker-loop` reads.

- [ ] **Step 1: Add the `loops:` block to the config example**

In `examples/issue-tracker.yaml.example`, after the `session_titles: true` line and its comment, insert:

```yaml
# Optional. Budgets and defaults for /tracker-loop and the --loop flag on
# /work-issue and /resume-initiative. Every key optional; defaults shown.
loops:
  interval: 15m            # cron cadence for --loop; poll idle cadence
  max_iterations: 50       # per loop record
  max_hours: 24            # wall-clock since the loop started
  idle_stop_after: 12      # consecutive no-change iterations before stopping
  pr_mode: draft           # draft | ready — PRs opened by unattended loops
  poll_label: agent-ready  # label /tracker-loop poll dispatches on
  # claim_label: agent-claimed   # applied on dispatch; never removed (no remove_label op)
  # max_concurrent: 1            # PRs a poll loop keeps open at once
```

- [ ] **Step 2: Teach `/tracker-doctor` about the block**

In `commands/tracker-doctor.md` Phase 1, add a row to the checks table after the `Jira-only: jira.issue_types` row:

```markdown
| `loops.*` well-formed (only when `loops:` is present) | `interval` matches `^[0-9]+[smhd]$`; `max_iterations`, `max_hours`, `idle_stop_after`, `max_concurrent` are positive integers; `pr_mode` is `draft` or `ready`; no unknown keys | "invalid loops config: `<key>`: `<value>` (expected `<rule>`)" |
```

And add a fifth WARN-only bullet:

```markdown
- `loops:` absent — fine; `/tracker-loop` uses its built-in defaults (`examples/issue-tracker.yaml.example` documents them). Surfaced only so an operator who expected a custom `poll_label` notices it is not set.
```

- [ ] **Step 3: Add `--loop` to `/work-issue`**

In `commands/work-issue.md`:

Title line: `# /work-issue <ref> [--start] [--draft | --merge] [--loop]`.

Invocation modes table, add a row:

```markdown
| `/work-issue <ref> --loop` | Modifier (combinable with `--start`, `--draft`, `--merge`). After Step 6 opens the PR, Step 7 arms a session cron that runs `/agent-issue-tracker:tracker-loop babysit <ref>` at `loops.interval` until the PR merges, is approved, or needs a judgement call. |
```

After the "### Step 6 — Finish" section, add:

````markdown
### Step 7 — Arm the loop (`--loop` only)

Only when `--loop` was passed and Step 6 opened a PR:

1. `LR="${CLAUDE_PLUGIN_ROOT}/scripts/loop-record.sh"`; `$LR create babysit <ref> <branch> [--merge] [--draft] --interval <loops.interval> --max-iterations <…> --max-hours <…> --idle-stop-after <…>` with values from the `loops:` block (`ait_config_get loops.<key>` from `scripts/lib/common.sh`; defaults in `commands/tracker-loop.md`).
2. `CronCreate` a recurring job at `loops.interval` on an off-minute (the tool's guidance), prompt `/agent-issue-tracker:tracker-loop babysit <ref>`; then `$LR set-cron <id> <job-id>`.
3. Tell the operator, in three lines: the loop id and cadence; that session crons expire after seven days and end with the conversation; and that `/loop /agent-issue-tracker:tracker-loop babysit <ref>` (self-paced) or `/schedule` are the alternatives.

`--loop` without a PR (verification failed, no `--draft`) arms nothing and says so.
````

Failure modes, add:

```markdown
- **`--loop` but `CronCreate` is unavailable** (cron disabled by `CLAUDE_CODE_DISABLE_CRON`, or not in the tool surface) → stop the record with reason `no cron`, print the `/loop …` line for the operator to run by hand, and continue; the PR is already open.
```

- [ ] **Step 4: Add `--loop` to `/resume-initiative`**

In `commands/resume-initiative.md`:

Title line: `# /resume-initiative [epic-ref] [--start] [--adopt] [--loop]`.

Invocation modes table, add a row:

```markdown
| `/resume-initiative <ref> --start --loop` | As `--start`, then arm a session cron running `/agent-issue-tracker:tracker-loop clear <ref>` at `loops.interval`, so the initiative keeps being worked leaf by leaf after this turn ends. `--loop` without `--start` is refused with a one-line message. |
```

At the end of the Mode 3 section (after the brainstorming handoff paragraph), add:

````markdown
**`--loop`.** After the handoff paragraph above has run, arm the clearing loop: `"${CLAUDE_PLUGIN_ROOT}/scripts/loop-record.sh" create clear <ref> <epic-slug> [--draft] [--merge] --interval <loops.interval> …` with the `loops:` budgets, then `CronCreate` a recurring job at `loops.interval` on an off-minute with prompt `/agent-issue-tracker:tracker-loop clear <ref>`, then `loop-record.sh set-cron <id> <job-id>`. Report the loop id, the seven-day cron expiry, and the `/loop` / `/schedule` alternatives — the same three lines `/work-issue` Step 7 prints. If `CronCreate` is unavailable, stop the record with reason `no cron` and print the `/loop` line instead.
````

- [ ] **Step 5: Verify the tests still pass and the docs are consistent**

Run: `python -m pytest -q`
Expected: all pass (no code changed in this task).

Run: `grep -n "loops" examples/issue-tracker.yaml.example commands/tracker-doctor.md commands/work-issue.md commands/resume-initiative.md | wc -l`
Expected: at least 8 matching lines across the four files.

- [ ] **Step 6: Commit**

```bash
git add commands/work-issue.md commands/resume-initiative.md commands/tracker-doctor.md examples/issue-tracker.yaml.example
git commit -m "feat(commands): --loop on /work-issue and /resume-initiative, loops config block"
```

---

### Task 11: Docs, packaging, CI, changelog, skill audit

**Files:**
- Modify: `README.md` (intro counts; commands table; new "## Briefs and loops" section before "## Walkthroughs")
- Modify: `CONTRIBUTING.md` (smoke gate items 9 and 10; "eight smoke scenarios" → "ten")
- Modify: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (description text only, no version change)
- Modify: `.github/workflows/ci.yml` (shellcheck globs)
- Modify: `CHANGELOG.md` (`## [Unreleased]`)
- Modify: `skills/initiative-tracking/SKILL.md` (short "## Loops" section before "## Session titles")

**Interfaces:**
- Consumes: everything shipped in Tasks 1–10.

- [ ] **Step 1: README**

Line 3: `Six skills, nine slash commands, one session-title hook` → `Six skills, twelve slash commands, one session-title hook`. "Nine slash commands:" heading text → "Twelve slash commands:". Add three rows to the commands table after `/audit-skills`:

```markdown
| [`/session-brief`](commands/session-brief.md) | Catch up on the current session — issue + PR links, CI, review threads awaiting you, a keep-going / compact / fresh verdict, and a resume note |
| [`/tracker-brief`](commands/tracker-brief.md) | Inbound digest since the last run — tracker activity, PRs, worktrees, resume notes and loop records joined into one ledger with a verdict per issue |
| [`/tracker-loop`](commands/tracker-loop.md) | One iteration of an unattended loop — babysit a PR, clear an epic, or poll a label — with budgets on disk; recurrence via `/loop` or `--loop` |
```

Insert before `## Walkthroughs`:

```markdown
## Briefs and loops

Two briefs and one loop runtime, all backed by scripts that always exit 0 and print JSON, with state under `${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker/<project-key>/` and never inside a repo.

- **`/session-brief`** re-orients you in the session you are in: what you were doing, what needs you (review threads, red CI, conflicts), what is already resolved, and whether to keep going, `/compact`, or start fresh — with a resume note written for a cold start.
- **`/tracker-brief`** is the morning read: what moved in the tracker and on the git host since the last run, joined to your worktrees and resume notes, with one verdict per issue — Needs action, Status drift (a merged PR whose issue never closed), Waiting, Closeable, Stale, or No code artifact.
- **`/tracker-loop`** runs one iteration of an unattended loop. Three modes: `babysit` watches a PR to green and addresses code-level review comments; `clear` works an epic leaf by leaf through `/work-issue`; `poll` dispatches `/work-issue` on issues carrying a label. Recurrence is the harness's: `/loop /agent-issue-tracker:tracker-loop babysit #42` (self-paced) or `/loop 15m …` (fixed), or pass `--loop` to `/work-issue` / `/resume-initiative --start` to arm a session cron. Budgets (`loops:` in the config) are enforced from the record on disk, a judgement question from a reviewer always stops the loop, and nothing merges without `--merge`.
```

- [ ] **Step 2: CONTRIBUTING smoke gate**

Line 27: `the eight smoke scenarios` → `the ten smoke scenarios`. After item 8 add:

```markdown
9. **Briefs** — in a real configured repo on a branch with an open PR, `/session-brief` prints both links, the PR/CI line, and writes the resume note under the cache dir; `/tracker-brief` runs twice and the second run's window starts at the first run's stamp.
10. **Babysit loop** — `/loop /agent-issue-tracker:tracker-loop babysit <pr>` against a PR with a deliberately red CI: the first iteration pushes a fix, a later one reports `wait`, and `/tracker-loop stop` ends it with the record marked stopped.
```

- [ ] **Step 3: Plugin manifests**

In both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, change `nine slash commands (/tracker-init, /tracker-doctor, /resume-initiative, /work-issue, /audit-skills, /file-bug, /file-feature, /file-followup, /file-epic)` to `twelve slash commands (/tracker-init, /tracker-doctor, /resume-initiative, /work-issue, /audit-skills, /file-bug, /file-feature, /file-followup, /file-epic, /session-brief, /tracker-brief, /tracker-loop)`. Leave `version` alone.

- [ ] **Step 4: CI shellcheck**

In `.github/workflows/ci.yml`, change `run: shellcheck hooks/*.sh` to `run: shellcheck hooks/*.sh scripts/*.sh scripts/lib/*.sh`. If shellcheck is installed locally, run that exact command and fix findings; SC2016 may be disabled per file for jq programs, nothing else.

- [ ] **Step 5: Initiative-tracking skill pointer**

In `skills/initiative-tracking/SKILL.md`, before `## Session titles`, add:

```markdown
## Loops

An initiative can be worked unattended: `/resume-initiative <ref> --start --loop` arms a session cron that runs `/tracker-loop clear <ref>` at the configured cadence, taking the next-up leaf through `/work-issue` each iteration, babysitting the PR it opened, skipping `needs-design` leaves with a comment, and stopping on a judgement question, an exhausted budget, or a `fresh session` checkpoint verdict. `commands/tracker-loop.md` is the contract; nothing in the epic body or machine block changes for it.
```

- [ ] **Step 6: CHANGELOG**

Under `## [Unreleased]`, add (keep any existing entries above it):

```markdown
### Added

- **`/session-brief`, `/tracker-brief`, `/tracker-loop`** — ports of the
  operator's personal session/morning briefs, re-rooted on the configured
  tracker backend and `.claude/worktrees/`, plus a one-iteration loop
  runtime with three modes (`babysit`, `clear`, `poll`), budgets kept on
  disk, and recurrence from `/loop` or a `--loop`-armed session cron on
  `/work-issue` and `/resume-initiative --start`. State lives under
  `${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker/<project-key>/`.
- **Backend contract 10 → 11: `list_updated_issues`** — issues with
  activity since a timestamp, optionally restricted to the viewer.
  GitHub via `gh issue list --search "updated:>=… involves:@me"`; Jira
  via JQL `updated >= …` (live verification deferred to the next Jira
  smoke).
- **`scripts/lib/common.sh`** — shared ref/slug parsing (the session-title
  hook now sources it), project key, state dir, flat config reader and
  issue-URL rendering. Shellcheck now covers `scripts/`.
- **`loops:` config block** (optional) — validated by `/tracker-doctor`.
```

- [ ] **Step 7: Full test run, skill audit, markdown lint**

Run: `python -m pytest -q`
Expected: all pass.

Run: `python scripts/audit_skills.py --base main`
Expected: exit 0; read the findings and fix any doc that references a file or function this branch renamed (none are expected — nothing was removed).

Run (if `npx` is available): `npx --yes markdownlint-cli2 README.md CONTRIBUTING.md CHANGELOG.md "examples/**/*.md"`
Expected: no findings. Otherwise, eyeball the three edited files for blank lines around headings, lists and fences.

- [ ] **Step 8: Commit**

```bash
git add README.md CONTRIBUTING.md CHANGELOG.md .claude-plugin/plugin.json .claude-plugin/marketplace.json .github/workflows/ci.yml skills/initiative-tracking/SKILL.md
git commit -m "docs: briefs and loops — README, CONTRIBUTING smoke gate, manifests, CHANGELOG"
```

---

## Followups to file after merge (not part of this plan)

- personal-skills: shrink `session-brief` and `morning-brief` to wrappers over the plugin commands plus the email, Slack, Calendar and phishing feeds.
- Jira live smoke for `list_updated_issues`.
- A `remove_label` contract op, if `claim_label` proves useful.
- `/tracker-brief` daily log file, if anyone misses it.
