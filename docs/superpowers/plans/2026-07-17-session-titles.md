# Initiative-Aware Session Titles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A plugin-shipped `SessionStart` hook that titles Claude Code sessions (VS Code tab names) in tracker-configured projects from branch ref + epic Status block + a Haiku transcript-tail summary, plus a mid-session `/rename` nudge in the skills.

**Architecture:** One bash script (`hooks/session-title.sh`) behind a plugin hook manifest (`hooks/hooks.json`), gated on `.claude/issue-tracker.yaml`, fail-open at every stage, tested via pytest subprocess fixtures riding the existing `python-tests` CI job. Markdown-only changes carry the doctor checks and skill nudges.

**Tech Stack:** bash (macOS 3.2-compatible), `jq` (hard dep), `git`/`gh`/`claude` (soft deps), pytest, shellcheck.

**Spec:** `docs/superpowers/specs/2026-07-16-session-titles-design.md` — read it before starting any task.

## Global Constraints

- Script MUST always `exit 0` — a hook failure must never block a session start.
- Stdout discipline: ONLY the final JSON payload may reach stdout. Plain stdout from a SessionStart hook is injected into the session as context (verified against live hooks doc 2026-07-17). Everything else → stderr or `/dev/null`.
- Output shape (verified): `{"hookSpecificOutput":{"hookEventName":"SessionStart","sessionTitle":"<title>"}}`; honoured only when input `source` is `startup` or `resume`. Input fields (verified): `session_id`, `transcript_path`, `cwd`, `source`, optional `session_title`.
- macOS bash 3.2 + BSD userland compatibility: no `mapfile`, no associative arrays; `stat -f %m || stat -c %Y`; `shasum -a 256 || sha256sum`; `timeout` may be absent (wrap in `tmo()`).
- Title length cap: 64 chars, truncate at part boundary (drop the overflowing part and everything after). Slug cap: 24 chars.
- Emit nothing when neither a ref nor an AI tail was found.
- Env vars are internal plumbing only: `AIT_TITLE_GUARD` (recursion guard), `AIT_TITLE_NO_AI` (skip AI stage — set in all tests).
- State dir: `${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles/`.
- Read-only against the tracker: `gh issue list` only, never a write.
- New config surface: exactly one optional top-level key `session_titles:` (absent = true). No `schema_version` bump.
- Run all commands from the repo root (`agent-issue-tracker`). Base branch: `feat/session-titles`.

---

### Task 1: Hook manifest + script skeleton (guards)

**Files:**
- Create: `hooks/hooks.json`
- Create: `hooks/session-title.sh` (mode 755)
- Test: `tests/test_session_title_hook.py`

**Interfaces:**
- Produces (for later tasks): script stage layout with numbered `# --- stage N` comments; helpers `tmo()`, `file_mtime()`, `hash_key()`, `field()`; variables `payload`, `session_id`, `transcript_path`, `cwd`, `src`, `current_title`, `config`, `toplevel`, `state_dir`, `state_file`, `pin_file`.
- Produces (for tests): module-level helpers `run_hook()`, `payload_for()`, `title_of()`, fixtures `project`, `hook_env` in `tests/test_session_title_hook.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_session_title_hook.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all tests FAIL/ERROR (script does not exist yet — `FileNotFoundError` or similar).

- [ ] **Step 3: Write the manifest and the script skeleton**

Create `hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/session-title.sh\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Create `hooks/session-title.sh`:

```bash
#!/usr/bin/env bash
# session-title.sh — SessionStart hook: initiative-aware session titles.
#
# Reads the SessionStart payload on stdin. When the session lives in a project
# with .claude/issue-tracker.yaml, emits
#   {"hookSpecificOutput":{"hookEventName":"SessionStart","sessionTitle":"…"}}
# on stdout. Always exits 0 — every failure path means "leave the title alone".
# Stdout discipline: ONLY the JSON payload may reach stdout; plain stdout from
# a SessionStart hook is injected into the session as context.
#
# Spec: docs/superpowers/specs/2026-07-16-session-titles-design.md

set -u

# --- portability helpers (macOS bash 3.2 + BSD userland, and Linux) ----------
tmo() { # tmo <seconds> <cmd...> — timeout(1) if available, else run unbounded
  local s="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; else "$@"; fi
}
file_mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }
hash_key() { if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi; }

# --- stage 1: recursion + dependency guards -----------------------------------
[ -n "${AIT_TITLE_GUARD:-}" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

# --- stage 2: parse stdin ------------------------------------------------------
payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0
field() { printf '%s' "$payload" | jq -r "$1 // empty" 2>/dev/null || true; }

session_id="$(field '.session_id')"
transcript_path="$(field '.transcript_path')"
cwd="$(field '.cwd')"
src="$(field '.source')"
current_title="$(field '.session_title')"

[ -n "$session_id" ] || exit 0
[ -d "$cwd" ] || exit 0
case "$src" in startup | resume) : ;; *) exit 0 ;; esac

# --- stage 3: config gate ------------------------------------------------------
toplevel="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)" || toplevel=""
config=""
if [ -f "$cwd/.claude/issue-tracker.yaml" ]; then
  config="$cwd/.claude/issue-tracker.yaml"
elif [ -n "$toplevel" ] && [ -f "$toplevel/.claude/issue-tracker.yaml" ]; then
  config="$toplevel/.claude/issue-tracker.yaml"
fi
[ -n "$config" ] || exit 0
grep -Eq '^session_titles:[[:space:]]*false[[:space:]]*$' "$config" && exit 0

# --- stage 4: manual-rename gate ------------------------------------------------
state_dir="${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles"
mkdir -p "$state_dir" 2>/dev/null || exit 0
state_file="$state_dir/$session_id"
pin_file="$state_dir/$session_id.pinned"

[ -f "$pin_file" ] && exit 0
if [ -f "$state_file" ]; then
  last_set="$(cat "$state_file" 2>/dev/null)"
  if [ -n "$current_title" ] && [ "$current_title" != "$last_set" ]; then
    : >"$pin_file"
    exit 0
  fi
elif [ -n "$current_title" ]; then
  # A title we did not set. The platform default is "<dir>-xx"; anything else
  # is a manual name — pin the session and never touch it.
  if ! printf '%s' "$current_title" | grep -Eq "^$(basename "$cwd")-[a-z0-9]{2}$"; then
    : >"$pin_file"
    exit 0
  fi
fi

# (stages 5-9 land in later tasks)
exit 0
```

Then: `chmod +x hooks/session-title.sh`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all 8 PASS. Also run `pytest -q` (whole suite) — existing audit-skills tests still pass.

- [ ] **Step 5: Commit**

```bash
git add hooks/hooks.json hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "feat(hooks): session-title hook manifest + guard stages"
```

---

### Task 2: Base ref + slug from branch, transcript fallback, minimal emit

**Files:**
- Modify: `hooks/session-title.sh` (replace the trailing `# (stages 5-9...)` / `exit 0` block)
- Test: `tests/test_session_title_hook.py` (append)

**Interfaces:**
- Consumes: Task 1 variables (`cwd`, `transcript_path`, `state_file`).
- Produces: variables `branch`, `ref` (e.g. `WB-7657` or `#42`), `slug` (≤24 chars, may be empty); a minimal stage-9 emit block that Task 4 REPLACES wholesale.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_session_title_hook.py`)

```python
# --- Task 2: base ref + slug -------------------------------------------------

def test_jira_ref_from_branch(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t == "WB-7657 subscription-gates"


def test_github_ref_from_leading_number_branch(project, hook_env):
    git(project, "switch", "-c", "feat/42-board-support")
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t == "#42 board-support"


def test_issue_prefix_branch(project, hook_env):
    git(project, "switch", "-c", "issue-88")
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t == "#88"


def test_no_ref_anywhere_emits_nothing(project, hook_env):
    git(project, "switch", "-c", "feat/general-cleanup")
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t is None


def test_version_segment_is_not_a_ref(project, hook_env):
    # "v2" must not become "#2"
    git(project, "switch", "-c", "feat/v2-cleanup")
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t is None


def test_transcript_fallback_ref(project, hook_env):
    git(project, "switch", "-c", "feat/general-cleanup")
    (project / "transcript.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": "please fix #88 today"}}) + "\n"
    )
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t is not None and t.startswith("#88")


def test_emitted_title_is_recorded_in_state(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    title_of(run_hook(payload_for(project, session_id="rec1"), hook_env))
    assert (state_dir_of(hook_env) / "rec1").read_text() == "WB-7657 subscription-gates"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_title_hook.py -v -k "ref or state or emits"`
Expected: the 7 new tests FAIL (no title is ever emitted yet); Task 1 tests still PASS.

- [ ] **Step 3: Implement**

In `hooks/session-title.sh`, replace the final two lines

```bash
# (stages 5-9 land in later tasks)
exit 0
```

with:

```bash
# --- stage 5: base ref + slug from branch, transcript fallback -----------------
branch="$(git -C "$cwd" branch --show-current 2>/dev/null)" || branch=""
ref=""
slug=""
if [ -n "$branch" ]; then
  leaf="${branch##*/}"
  ref="$(printf '%s' "$leaf" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)" || true
  if [ -z "$ref" ]; then
    num="$(printf '%s' "$leaf" | grep -oE '^[0-9]+' | head -1)" || true
    [ -z "$num" ] && num="$(printf '%s' "$leaf" | grep -oE '(^|-)issue-?[0-9]+' | grep -oE '[0-9]+' | head -1)" || true
    [ -n "$num" ] && ref="#$num"
  fi
  slug="$(printf '%s' "$leaf" \
    | sed -E 's/[A-Z][A-Z0-9]+-[0-9]+//; s/^[0-9]+//; s/(^|-)issue-?[0-9]+//' \
    | sed -E 's/^[-_]+//; s/[-_]+$//' | cut -c1-24)"
fi
if [ -z "$ref" ] && [ -f "$transcript_path" ]; then
  ref="$(tail -c 200000 "$transcript_path" 2>/dev/null \
    | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | tail -1)" || true
  slug=""
fi

# --- stage 9: compose + emit (REPLACED WHOLESALE by Task 4) ---------------------
[ -n "$ref" ] || exit 0
title="$ref"
[ -n "$slug" ] && title="$ref $slug"
printf '%s' "$title" >"$state_file"
jq -cn --arg t "$title" '{hookSpecificOutput:{hookEventName:"SessionStart",sessionTitle:$t}}'
exit 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all 15 PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "feat(hooks): branch/transcript ref extraction + minimal title emit"
```

---

### Task 3: Manual-rename respect, end-to-end

**Files:**
- Test: `tests/test_session_title_hook.py` (append; script changes only if a test exposes a gap)

**Interfaces:**
- Consumes: Task 1 gate code, Task 2 emit (state write).

- [ ] **Step 1: Write the failing-or-passing tests** (append)

```python
# --- Task 3: manual-rename respect ------------------------------------------

def test_rename_after_our_title_pins_forever(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    sid = "cycle1"
    # 1st run: we set the title.
    assert title_of(run_hook(payload_for(project, session_id=sid), hook_env)) is not None
    # 2nd run: user renamed since — incoming title differs from what we set.
    r = run_hook(
        payload_for(project, session_id=sid, session_title="my epic notes"), hook_env
    )
    assert r.stdout == ""
    assert (state_dir_of(hook_env) / f"{sid}.pinned").exists()
    # 3rd run: pinned stays pinned even with no incoming title.
    r = run_hook(payload_for(project, session_id=sid), hook_env)
    assert r.stdout == ""


def test_unchanged_incoming_title_retitles(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    sid = "cycle2"
    first = title_of(run_hook(payload_for(project, session_id=sid), hook_env))
    # Incoming title equals what we set → not a manual rename → re-emit fine.
    second = title_of(
        run_hook(payload_for(project, session_id=sid, session_title=first), hook_env)
    )
    assert second == first
    assert not (state_dir_of(hook_env) / f"{sid}.pinned").exists()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_session_title_hook.py -v -k "pins_forever or retitles"`
Expected: PASS (the Task 1 gate already implements this). If either FAILS, fix the stage-4 gate in `hooks/session-title.sh` until green — the gate logic is the spec's decision 4; the tests are authoritative.

- [ ] **Step 3: Commit**

```bash
git add tests/test_session_title_hook.py
git commit -m "test(hooks): manual-rename pin cycle end-to-end"
```

---

### Task 4: Final compose — idle marker, parts loop, 64-char cap

**Files:**
- Modify: `hooks/session-title.sh` (replace the whole stage-9 block from Task 2)
- Test: `tests/test_session_title_hook.py` (append)

**Interfaces:**
- Consumes: `ref`, `slug`, `transcript_path`, `state_file`.
- Produces: variables `epic_next` and `ai_tail` (initialised empty here; populated by Tasks 5/6), `idle`; the FINAL stage-9 compose. Later tasks insert stages 6-8 BETWEEN stage 5 and stage 9 without touching stage 9 again.

- [ ] **Step 1: Write the failing tests** (append)

```python
# --- Task 4: compose, idle marker, cap ----------------------------------------

def backdate(path, days):
    ts = time.time() - days * 86400 - 3600
    os.utime(path, (ts, ts))


def test_idle_marker_appended(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    tp = project / "transcript.jsonl"
    tp.write_text(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
    backdate(tp, 3)
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t == "WB-7657 subscription-gates · idle 3d"


def test_fresh_transcript_has_no_idle_marker(project, hook_env):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    (project / "transcript.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n"
    )
    t = title_of(run_hook(payload_for(project), hook_env))
    assert t == "WB-7657 subscription-gates"
```

Also add `import time` to the imports at the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_title_hook.py -v -k idle`
Expected: `test_idle_marker_appended` FAILS (no idle suffix yet); the fresh-transcript test passes already.

- [ ] **Step 3: Implement**

In `hooks/session-title.sh`, replace the ENTIRE stage-9 block from Task 2 (everything from `# --- stage 9:` to the final `exit 0`) with:

```bash
# --- stage 6: epic enrichment (populated in a later task) ----------------------
epic_next=""

# --- stage 7: AI tail (populated in a later task) -------------------------------
ai_tail=""

# --- stage 8: idle marker --------------------------------------------------------
idle=""
if [ -f "$transcript_path" ]; then
  m="$(file_mtime "$transcript_path")" || m=""
  if [ -n "$m" ]; then
    days=$((($(date +%s) - m) / 86400))
    [ "$days" -ge 1 ] && idle="idle ${days}d"
  fi
fi

# --- stage 9: compose + emit ------------------------------------------------------
[ -n "$ref$ai_tail" ] || exit 0
anchor="$ref"
if [ -n "$ref" ] && [ -n "$slug" ]; then anchor="$ref $slug"; fi

title=""
for part in "$anchor" "$ai_tail" "${epic_next:+next $epic_next}" "$idle"; do
  [ -n "$part" ] || continue
  # ai_tail beats "next <ref>": once ai_tail is in, drop epic_next.
  case "$part" in "next "*) [ -n "$ai_tail" ] && continue ;; esac
  if [ -n "$title" ]; then candidate="$title · $part"; else candidate="$part"; fi
  [ "${#candidate}" -le 64 ] || break
  title="$candidate"
done
[ -n "$title" ] || exit 0

printf '%s' "$title" >"$state_file"
jq -cn --arg t "$title" '{hookSpecificOutput:{hookEventName:"SessionStart",sessionTitle:$t}}'
exit 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all 19 PASS (every earlier test must still pass against the new compose).

- [ ] **Step 5: Commit**

```bash
git add hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "feat(hooks): final title compose with idle marker and 64-char cap"
```

---

### Task 5: Epic enrichment via gh, with 24h cache

**Files:**
- Modify: `hooks/session-title.sh` (fill the stage-6 block)
- Test: `tests/test_session_title_hook.py` (append)

**Interfaces:**
- Consumes: `config`, `branch`, `toplevel`, `state_dir`, helpers `tmo()`, `hash_key()`, `file_mtime()`; sets `ref`, `slug`, `epic_next` consumed by stage 9.
- Produces: cache files under `$state_dir/epic-cache/<key>` holding one TSV line `epic_ref<TAB>epic_title<TAB>next_ref-line` (empty file = negative cache).
- Test stub contract: a `gh` stub on PATH that appends a line to `$GH_STUB_CALLS` and cats `$GH_STUB_JSON`.

- [ ] **Step 1: Write the failing tests** (append)

```python
# --- Task 5: epic enrichment ----------------------------------------------------

EPIC_JSON = json.dumps([{
    "number": 42,
    "title": "epic: board support",
    "body": (
        "intro\n"
        "- **Phase:** Phase 1 · 1/3 sub-issues closed\n"
        "- **Next up:** #61 — webhook retries\n"
        "- **Current branch:** feat/board-support\n"
        "- **Last updated:** 2026-07-01\n"
    ),
}])


@pytest.fixture
def gh_stub(tmp_path, hook_env):
    calls = tmp_path / "gh-calls"
    data = tmp_path / "gh.json"
    data.write_text(EPIC_JSON)
    stub_bin = make_stub(
        tmp_path, "gh", 'echo "$@" >> "$GH_STUB_CALLS"\ncat "$GH_STUB_JSON"'
    )
    hook_env["GH_STUB_CALLS"] = str(calls)
    hook_env["GH_STUB_JSON"] = str(data)
    return stub_bin, calls


def test_epic_match_replaces_ref_and_adds_next(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    t = title_of(run_hook(payload_for(project), hook_env, stub_bin=stub_bin))
    assert t == "#42 board-support · next #61"


def test_epic_lookup_is_cached(project, hook_env, gh_stub):
    stub_bin, calls = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    run_hook(payload_for(project, session_id="c1"), hook_env, stub_bin=stub_bin)
    run_hook(payload_for(project, session_id="c2"), hook_env, stub_bin=stub_bin)
    assert len(calls.read_text().splitlines()) == 1


def test_no_epic_match_keeps_branch_title(project, hook_env, gh_stub):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    t = title_of(run_hook(payload_for(project), hook_env, stub_bin=stub_bin))
    assert t == "WB-7657 subscription-gates"


def test_gh_failure_fails_open(project, hook_env, tmp_path):
    # feat/board-support carries no ref shape of its own, so with gh broken
    # there is no enrichment and no base ref → the hook must emit nothing.
    stub_bin = make_stub(tmp_path, "gh", "exit 1")
    git(project, "switch", "-c", "feat/board-support")
    t = title_of(run_hook(payload_for(project), hook_env, stub_bin=stub_bin))
    assert t is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_title_hook.py -v -k epic`
Expected: `test_epic_match_replaces_ref_and_adds_next` and `test_epic_lookup_is_cached` FAIL; the other two pass by construction.

- [ ] **Step 3: Implement**

In `hooks/session-title.sh`, replace the stage-6 block

```bash
# --- stage 6: epic enrichment (populated in a later task) ----------------------
epic_next=""
```

with:

```bash
# --- stage 6: epic enrichment (GitHub backend only; 24h cache; read-only) -------
epic_next=""
backend="$(grep -E '^backend:' "$config" 2>/dev/null | head -1 | awk '{print $2}')" || backend=""
if [ "$backend" = "github" ] && [ -n "$branch" ] && command -v gh >/dev/null 2>&1; then
  cache_dir="$state_dir/epic-cache"
  mkdir -p "$cache_dir" 2>/dev/null || true
  key="$(printf '%s|%s' "${toplevel:-$cwd}" "$branch" | hash_key | cut -c1-16)"
  cache_file="$cache_dir/$key"
  fresh=""
  if [ -f "$cache_file" ]; then
    cm="$(file_mtime "$cache_file")" || cm=0
    [ $(($(date +%s) - cm)) -lt 86400 ] && fresh=1
  fi
  if [ -z "$fresh" ]; then
    epics_json="$(cd "$cwd" && tmo 5 gh issue list --label epic --state open \
      --json number,title,body --limit 50 2>/dev/null)" || epics_json=""
    if [ -n "$epics_json" ]; then
      printf '%s' "$epics_json" | jq -r --arg b "$branch" '
        [.[] | select(.body | contains("- **Current branch:** " + $b))][0] // empty
        | [("#" + (.number | tostring)), .title,
           ((.body | capture("- \\*\\*Next up:\\*\\* (?<n>[^\n]+)").n) // "")]
        | @tsv' >"$cache_file" 2>/dev/null || : >"$cache_file"
    else
      : >"$cache_file"
    fi
  fi
  if [ -s "$cache_file" ]; then
    e_ref="$(cut -f1 "$cache_file" 2>/dev/null)"
    e_title="$(cut -f2 "$cache_file" 2>/dev/null)"
    e_next_line="$(cut -f3 "$cache_file" 2>/dev/null)"
    if [ -n "$e_ref" ]; then
      ref="$e_ref"
      slug="$(printf '%s' "$e_title" | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/^epic: *//; s/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-24)"
      epic_next="$(printf '%s' "$e_next_line" \
        | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | head -1)" || true
    fi
  fi
fi
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all 23 PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "feat(hooks): epic Status-block enrichment via gh with 24h cache"
```

---

### Task 6: AI tail via claude -p (haiku)

**Files:**
- Modify: `hooks/session-title.sh` (fill the stage-7 block)
- Test: `tests/test_session_title_hook.py` (append)

**Interfaces:**
- Consumes: `src`, `transcript_path`, `AIT_TITLE_NO_AI`, `AIT_TITLE_GUARD`, `tmo()`; sets `ai_tail` consumed by stage 9 (which already suppresses `next <ref>` when `ai_tail` is set).
- Test stub contract: a `claude` stub on PATH that drains stdin and prints a phrase.

- [ ] **Step 1: Write the failing tests** (append)

```python
# --- Task 6: AI tail -------------------------------------------------------------

TRANSCRIPT = "\n".join([
    json.dumps({"type": "user", "message": {"content": "let's wire the webhook"}}),
    json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": "wiring the board webhook now"}]}}),
]) + "\n"


def ai_env(hook_env):
    env = dict(hook_env)
    env.pop("AIT_TITLE_NO_AI")
    return env


def claude_stub(tmp_path, phrase="wiring board webhook"):
    return make_stub(tmp_path, "claude", f'cat > /dev/null\necho "{phrase}"')


def test_ai_tail_on_resume(project, hook_env, tmp_path):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    (project / "transcript.jsonl").write_text(TRANSCRIPT)
    stub = claude_stub(tmp_path)
    t = title_of(run_hook(payload_for(project, source="resume"), ai_env(hook_env), stub_bin=stub))
    assert t == "WB-7657 subscription-gates · wiring board webhook"


def test_no_ai_tail_on_startup(project, hook_env, tmp_path):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    (project / "transcript.jsonl").write_text(TRANSCRIPT)
    stub = claude_stub(tmp_path)
    t = title_of(run_hook(payload_for(project, source="startup"), ai_env(hook_env), stub_bin=stub))
    assert t == "WB-7657 subscription-gates"


def test_no_ai_env_flag_respected(project, hook_env, tmp_path):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    (project / "transcript.jsonl").write_text(TRANSCRIPT)
    stub = claude_stub(tmp_path)
    t = title_of(run_hook(payload_for(project, source="resume"), hook_env, stub_bin=stub))
    assert t == "WB-7657 subscription-gates"


def test_overlong_ai_output_is_dropped(project, hook_env, tmp_path):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates")
    (project / "transcript.jsonl").write_text(TRANSCRIPT)
    stub = claude_stub(tmp_path, "this is a rambling seven word answer here")
    t = title_of(run_hook(payload_for(project, source="resume"), ai_env(hook_env), stub_bin=stub))
    assert t == "WB-7657 subscription-gates"


def test_ai_tail_suppresses_next_ref(project, hook_env, gh_stub, tmp_path):
    stub_bin, _ = gh_stub
    git(project, "switch", "-c", "feat/board-support")
    (project / "transcript.jsonl").write_text(TRANSCRIPT)
    claude_bin = claude_stub(tmp_path)
    env = ai_env(hook_env)
    env["PATH"] = f"{claude_bin}:{env['PATH']}"
    t = title_of(run_hook(payload_for(project, source="resume"), env, stub_bin=stub_bin))
    assert t == "#42 board-support · wiring board webhook"


def test_cap_drops_overflowing_part_and_after(project, hook_env, tmp_path):
    git(project, "switch", "-c", "max/WB-7657-subscription-gates-and-billing")
    tp = project / "transcript.jsonl"
    tp.write_text(TRANSCRIPT)
    backdate(tp, 2)
    stub = claude_stub(tmp_path, "reworking the whole subscription")
    t = title_of(run_hook(payload_for(project, source="resume"), ai_env(hook_env), stub_bin=stub))
    # anchor (31) + tail (32) + separators > 64 → tail and idle both dropped.
    assert t == "WB-7657 subscription-gates-and-b"
```

Note the last assertion pins the 24-char slug cap too: `subscription-gates-and-billing` → `subscription-gates-and-b`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_session_title_hook.py -v -k "ai or cap_drops"`
Expected: `test_ai_tail_on_resume`, `test_ai_tail_suppresses_next_ref` FAIL; the startup/no-ai/overlong/cap tests pass by construction (no AI stage exists yet). After Step 3 ALL must pass.

- [ ] **Step 3: Implement**

In `hooks/session-title.sh`, replace the stage-7 block

```bash
# --- stage 7: AI tail (populated in a later task) -------------------------------
ai_tail=""
```

with:

```bash
# --- stage 7: AI tail (resume only; hard-bounded; recursion-guarded) -------------
ai_tail=""
if [ "$src" = "resume" ] && [ -z "${AIT_TITLE_NO_AI:-}" ] && [ -s "$transcript_path" ] \
  && command -v claude >/dev/null 2>&1; then
  excerpt="$(jq -r '
      select(.type == "user" or .type == "assistant") | .message.content
      | if type == "string" then .
        elif type == "array" then (.[] | select(type == "object" and .type == "text") | .text)
        else empty end' "$transcript_path" 2>/dev/null | tail -n 40 | tail -c 4000)" || excerpt=""
  if [ -n "$excerpt" ]; then
    prompt="Output ONLY a lowercase phrase of at most 5 words describing what this coding session is working on right now. No punctuation, no quotes."
    ai_tail="$(printf '%s\n\n<session-excerpt>\n%s\n</session-excerpt>\n' "$prompt" "$excerpt" \
      | AIT_TITLE_GUARD=1 tmo 8 claude -p --model haiku 2>/dev/null)" || ai_tail=""
    ai_tail="$(printf '%s' "$ai_tail" | head -1 \
      | sed -E "s/^[\"' ]+//; s/[\"' .]+\$//" | cut -c1-40)"
    words="$(printf '%s' "$ai_tail" | wc -w | tr -d ' ')"
    [ "${words:-0}" -gt 5 ] && ai_tail=""
  fi
fi
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_session_title_hook.py -v`
Expected: all 29 PASS. Run `pytest -q` for the full suite.

- [ ] **Step 5: Commit**

```bash
git add hooks/session-title.sh tests/test_session_title_hook.py
git commit -m "feat(hooks): haiku transcript-tail summary on resume"
```

---

### Task 7: Shellcheck — CI job + clean script

**Files:**
- Modify: `.github/workflows/ci.yml` (append job)
- Modify: `hooks/session-title.sh` (only if shellcheck flags anything)

- [ ] **Step 1: Run shellcheck locally**

Run: `shellcheck hooks/session-title.sh` (install via `brew install shellcheck` if absent)
Expected: warnings are plausible (e.g. SC2155 declare-and-assign, SC2181). Fix each in place — prefer restructuring over `# shellcheck disable=` comments; a disable comment needs a one-line justification.

- [ ] **Step 2: Re-run until clean**

Run: `shellcheck hooks/session-title.sh && echo CLEAN`
Expected: `CLEAN`

- [ ] **Step 3: Run the pytest suite again**

Run: `pytest tests/test_session_title_hook.py -q`
Expected: all PASS (shellcheck fixes must not change behaviour).

- [ ] **Step 4: Add the CI job** (append to `.github/workflows/ci.yml` after the `python-tests` job, same indentation level)

```yaml
  shellcheck:
    name: Shellcheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Shellcheck hook scripts
        run: shellcheck hooks/*.sh
```

- [ ] **Step 5: Validate the workflow YAML**

Run: `yamllint -d relaxed .github/workflows/ci.yml`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml hooks/session-title.sh
git commit -m "ci: shellcheck job for hook scripts"
```

---

### Task 8: Docs sweep — doctor checks, nudges, config, README, manifests, changelog

**Files:**
- Modify: `commands/tracker-doctor.md`, `skills/initiative-tracking/SKILL.md`, `commands/resume-initiative.md`, `examples/issue-tracker.yaml.example`, `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `CONTRIBUTING.md`

All edits are markdown/JSON prose; read each file first and match its existing structure and tone. Exact content below; placement is described relative to existing sections.

- [ ] **Step 1: `commands/tracker-doctor.md`** — append a new check phase after the last existing check phase, following the file's `[PASS]`/`[WARN]` formatting:

```markdown
### Phase 4 — session-title hook prerequisites (WARN-only)

The SessionStart session-title hook is cosmetic; nothing here may FAIL.

1. `jq` on PATH → `[PASS] jq found`. Missing → `[WARN] session-title hook
   inactive: jq not found` + install hint (`brew install jq` / `apt install jq`).
2. State dir `${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles/`
   creatable/writable → `[PASS]`; else `[WARN]` with the path.
3. Config sets `session_titles: false` → `[PASS-WITH-NOTE] session titles
   disabled by config`.
```

- [ ] **Step 2: `skills/initiative-tracking/SKILL.md`** — add a short section (place it near the maintenance/lifecycle material, after reading the file):

```markdown
## Session titles

Sessions in a configured project are auto-titled at start/resume by the
plugin's SessionStart hook (`<ref> <slug> · <what it was doing> · idle Nd`).
Hooks cannot retitle a running session — so when the working focus shifts to
a different issue/epic mid-session, or the issue being driven completes,
offer the operator a paste-ready rename line, e.g.:

    /rename #42 board-support — done

Agents cannot run `/rename`; only the operator can paste it. Offer once per
focus shift, not on every message. If the operator manually renames a
session, the hook never overwrites their name.
```

- [ ] **Step 3: `commands/resume-initiative.md`** — in Mode 2, after the step where the node is shown to the operator (step 2), append one bullet to the "Show the operator" list:

```markdown
   - If the current session title does not already name this node's ref, a
     paste-ready rename line the operator can apply immediately (the
     SessionStart hook catches up on next resume): `` /rename <ref> <slug> ``
```

- [ ] **Step 4: `examples/issue-tracker.yaml.example`** — after the `triage:` block, add:

```yaml
# Optional. Set false to disable the SessionStart session-title hook for this
# project (the hook is already a no-op in projects without this config file).
# Default: true.
session_titles: true
```

- [ ] **Step 5: `README.md`** — two edits. (a) Extend the intro line's component enumeration to mention the hook (read the current line; it enumerates six skills + nine commands — append ", one session-title hook"). (b) Add a section after "Configuration":

```markdown
## Session titles

In a configured project, a `SessionStart` hook titles each Claude Code
session (the VS Code tab name) at start/resume: issue/epic ref from the git
branch, the epic's next-up child when the GitHub backend can resolve it, a
≤5-word Haiku summary of what the session was last doing, and an `idle Nd`
staleness marker. Example: `#42 board-support · wiring webhook · idle 3d`.

Fail-open by design: no `.claude/issue-tracker.yaml` → no-op; manual renames
are never overwritten; any failure (no `jq`, no network, no `gh`) leaves the
title alone. Disable per-project with `session_titles: false`. Titles update
only at start/resume — mid-session focus shifts get a paste-ready `/rename`
suggestion from the `initiative-tracking` skill instead. Jira projects get
branch refs + AI summaries but no epic enrichment (hooks cannot reach MCP).
```

- [ ] **Step 6: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`** — in both `description` strings, after "…nine slash commands (…)", insert: `, one SessionStart hook (initiative-aware session titles)`. Do NOT bump `version` (happens at release time per repo convention).

- [ ] **Step 7: `CHANGELOG.md`** — under `## [Unreleased]`, add:

```markdown
### Added

- **Initiative-aware session titles — the plugin's first hook.** A
  `SessionStart` hook (`hooks/hooks.json` + `hooks/session-title.sh`) titles
  sessions in tracker-configured projects at start/resume:
  `<ref> <slug> · <AI tail> · idle Nd`, from the git branch, the epic Status
  block (`- **Current branch:**` match via `gh`, 24h cache, GitHub backend
  only — hooks cannot reach MCP for Jira), and a ≤5-word Haiku summary of
  the transcript tail. Fail-open everywhere: no config → no-op; manual
  renames pin the session forever; every dependency (`jq` hard; `git`/`gh`/
  `claude` soft) degrades to "leave the title alone"; the script always
  exits 0. New optional top-level config key `session_titles:` (default
  true; no `schema_version` bump). `/tracker-doctor` gains a WARN-only
  prerequisite phase; `initiative-tracking` + `/resume-initiative` gain a
  paste-ready `/rename` nudge for mid-session focus shifts (hooks cannot
  retitle a running session). Tested via pytest subprocess fixtures
  (`tests/test_session_title_hook.py`) riding the existing `python-tests`
  CI job, plus a new `shellcheck` job. No backend-contract change. Design:
  `docs/superpowers/specs/2026-07-16-session-titles-design.md`.
```

- [ ] **Step 8: `CONTRIBUTING.md`** — in the Release process smoke list, append the next-numbered smoke:

```markdown
N. **Session-title hook** — in a real configured repo, resume a stale
   session and confirm the tab title carries `<ref> <slug>` (+ `idle Nd`);
   manually rename it, resume again, confirm the hook left the manual name
   untouched.
```

(Replace `N.` with the actual next number after reading the current list.)

- [ ] **Step 9: Lint the prose**

Run: `yamllint -d relaxed . && npx markdownlint-cli2 "README.md" "CONTRIBUTING.md" "CHANGELOG.md" "examples/**/*.md"`
Expected: both exit 0 (the markdownlint globs mirror the CI job's).

- [ ] **Step 10: Commit**

```bash
git add commands/tracker-doctor.md skills/initiative-tracking/SKILL.md \
  commands/resume-initiative.md examples/issue-tracker.yaml.example README.md \
  .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md CONTRIBUTING.md
git commit -m "docs: session-title hook — doctor phase, rename nudges, config key, README"
```

---

### Task 9: Full verification + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Full automated pass**

Run, from repo root:

```bash
pytest -q
shellcheck hooks/*.sh
yamllint -d relaxed .
npx markdownlint-cli2 "README.md" "CONTRIBUTING.md" "CHANGELOG.md" "examples/**/*.md"
```

Expected: all four exit 0.

- [ ] **Step 2: Backend-contract sanity**

Run the CI backend-contract check locally (copy the inline script from `.github/workflows/ci.yml`), or verify by inspection that no `` ### `op` `` heading was added/removed in `backends/`.
Expected: PASS (this feature touches no backend files).

- [ ] **Step 3: Manual smoke (operator-visible)**

1. In a real configured repo, symlink or copy this branch into the plugin cache OR run with `claude --plugin-dir` pointing at the repo (per Claude Code plugin dev docs), on a branch like `max/WB-1234-something`.
2. Start a session → tab title becomes `WB-1234 something`.
3. Exit; `claude --resume` the session → title gains the AI tail.
4. `/rename my own name`, exit, resume → title stays `my own name`; a `.pinned` file exists in `~/.cache/agent-issue-tracker/session-titles/`.
5. Record outcomes in the PR description (these are the release-gate smoke evidence).

- [ ] **Step 4: Final commit if anything moved, then push**

```bash
git status --short   # expect clean
git push -u origin feat/session-titles
```

Do NOT open a PR or file the tracking issue without operator approval.
