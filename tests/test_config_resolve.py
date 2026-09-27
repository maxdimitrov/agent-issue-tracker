"""ait_config_resolve / ait_config_provenance: global base layer + env overrides (#7)."""
import os
from pathlib import Path

import pytest

from shell_helpers import init_repo, run_lib

OVERRIDES = ("TRACKER_BACKEND_OVERRIDE", "TRACKER_GITHUB_REPO_OVERRIDE",
             "TRACKER_JIRA_SITE_OVERRIDE", "TRACKER_JIRA_PROJECT_OVERRIDE")

PROJECT = """schema_version: 1
backend: github   # trailing comment
github:
  repo: acme/project
"""

GLOBAL = """# my global defaults
schema_version: 1
backend: jira
github:
  repo: acme/global
  default_pr_close_syntax: "Closes #N"
areas:
  - dashboard
  - backend

# budgets
loops:
  interval: 5m
"""


def _env(home, **extra):
    env = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
    env["HOME"] = Path(home).as_posix()
    env.update(extra)
    return env


def _write(root, text):
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "issue-tracker.yaml").write_text(text)


@pytest.fixture
def layout(tmp_path):
    """home/ (may hold the global file) and home/code/app (a repo)."""
    home = tmp_path / "home"
    repo = init_repo(home / "code" / "app")
    return home, repo


def resolve(repo, env):
    return run_lib("ait_config_resolve", env=env, cwd=str(repo))


def get(repo, env, key):
    return run_lib(f"ait_config_get {key}", env=env, cwd=str(repo))


def test_project_only_is_unchanged(layout):
    home, repo = layout
    _write(repo, PROJECT)
    r = resolve(repo, _env(home))
    assert r.returncode == 0
    assert r.stdout == PROJECT


def test_project_block_replaces_global_block_and_global_only_keys_are_inherited(layout):
    home, repo = layout
    _write(repo, PROJECT)
    _write(home, GLOBAL)
    out = resolve(repo, _env(home)).stdout
    assert out.startswith(PROJECT)            # project blocks first, in project order
    assert "acme/global" not in out            # whole github block came from project
    assert "Closes #N" not in out              # ...including its children
    assert "areas:\n  - dashboard\n  - backend\n" in out
    assert out.index("areas:") < out.index("loops:")   # global order kept
    assert "# budgets\nloops:\n  interval: 5m\n" in out  # comment travels with block


def test_global_header_comment_not_leaked(layout):
    home, repo = layout
    _write(repo, PROJECT)
    _write(home, GLOBAL)
    out = resolve(repo, _env(home)).stdout
    assert "# my global defaults" not in out
    assert out.count("schema_version:") == 1


def test_schema_version_mismatch_skips_global_with_warning(layout):
    home, repo = layout
    _write(repo, PROJECT)
    _write(home, GLOBAL.replace("schema_version: 1", "schema_version: 2"))
    r = resolve(repo, _env(home))
    assert r.stdout == PROJECT
    assert "WARN" in r.stderr and "schema_version" in r.stderr


def test_malformed_global_skipped_with_warning_and_clean_stdout(layout):
    home, repo = layout
    _write(repo, PROJECT)
    _write(home, "schema_version: 1\nthis is not yaml at all\n")
    r = resolve(repo, _env(home))
    assert r.returncode == 0
    assert r.stdout == PROJECT
    assert "WARN" in r.stderr and "malformed" in r.stderr


def test_global_without_project_is_not_configured(layout):
    home, repo = layout
    _write(home, GLOBAL)
    r = resolve(repo, _env(home, TRACKER_BACKEND_OVERRIDE="github"))
    assert r.returncode == 1 and r.stdout == ""


def test_cwd_at_home_uses_the_file_once(layout):
    home, _ = layout
    _write(home, GLOBAL)
    r = run_lib("ait_config_resolve", env=_env(home), cwd=str(home))
    assert r.returncode == 0
    assert r.stdout.count("areas:") == 1 and r.stderr == ""


@pytest.mark.parametrize("var,key,value", [
    ("TRACKER_BACKEND_OVERRIDE", "backend", "jira"),
    ("TRACKER_GITHUB_REPO_OVERRIDE", "github.repo", "sandbox/repo"),
    ("TRACKER_JIRA_SITE_OVERRIDE", "jira.site", "staging.atlassian.net"),
    ("TRACKER_JIRA_PROJECT_OVERRIDE", "jira.project", "SBX"),
])
@pytest.mark.xfail(strict=True, reason="path-free ait_config_get lands in Task 2")
def test_each_override(layout, var, key, value):
    home, repo = layout
    _write(repo, PROJECT)
    r = get(repo, _env(home, **{var: value}), key)
    assert r.returncode == 0 and r.stdout == value


@pytest.mark.xfail(strict=True, reason="path-free ait_config_get lands in Task 2")
def test_override_keeps_siblings(layout):
    home, repo = layout
    _write(repo, PROJECT + '  default_pr_close_syntax: "Fixes #N"\n')
    env = _env(home, TRACKER_GITHUB_REPO_OVERRIDE="sandbox/repo")
    assert get(repo, env, "github.repo").stdout == "sandbox/repo"
    assert get(repo, env, "github.default_pr_close_syntax").stdout == "Fixes #N"
    assert resolve(repo, env).stdout.count("repo:") == 1


def test_override_creates_missing_section(layout):
    home, repo = layout
    _write(repo, PROJECT)
    out = resolve(repo, _env(home, TRACKER_JIRA_SITE_OVERRIDE="x.atlassian.net")).stdout
    assert out.endswith("jira:\n  site: x.atlassian.net\n")


@pytest.mark.xfail(strict=True, reason="path-free ait_config_get lands in Task 2")
def test_override_appends_to_section_followed_by_comment(layout):
    home, repo = layout
    _write(repo, "schema_version: 1\njira:\n  site: a.example\n\n# later\nloops:\n  interval: 5m\n")
    env = _env(home, TRACKER_JIRA_PROJECT_OVERRIDE="SBX")
    assert get(repo, env, "jira.project").stdout == "SBX"
    assert get(repo, env, "jira.site").stdout == "a.example"
    assert get(repo, env, "loops.interval").stdout == "5m"


@pytest.mark.xfail(strict=True, reason="path-free ait_config_get lands in Task 2")
def test_override_value_with_hash_round_trips(layout):
    home, repo = layout
    _write(repo, PROJECT)
    env = _env(home, TRACKER_GITHUB_REPO_OVERRIDE="odd#name")
    assert get(repo, env, "github.repo").stdout == "odd#name"


def test_empty_override_is_unset(layout):
    home, repo = layout
    _write(repo, PROJECT)
    assert resolve(repo, _env(home, TRACKER_BACKEND_OVERRIDE="")).stdout == PROJECT


def test_other_tracker_vars_are_ignored(layout):
    home, repo = layout
    _write(repo, PROJECT)
    env = _env(home, TRACKER_LOOPS_INTERVAL_OVERRIDE="1m", TRACKER_AREAS_OVERRIDE="x")
    assert resolve(repo, env).stdout == PROJECT


def test_provenance_sources(layout):
    home, repo = layout
    _write(repo, PROJECT)
    _write(home, GLOBAL)
    r = run_lib("ait_config_provenance", env=_env(home, TRACKER_GITHUB_REPO_OVERRIDE="s/r"),
                cwd=str(repo))
    assert r.returncode == 0
    rows = dict(line.split("\t", 1) for line in r.stdout.splitlines())
    assert rows["backend"].startswith("project:")
    assert rows["backend"].replace("\\", "/").endswith("app/.claude/issue-tracker.yaml")
    assert rows["areas"].startswith("global:")
    assert rows["loops"].startswith("global:")
    assert rows["github.repo"] == "env:TRACKER_GITHUB_REPO_OVERRIDE"
    assert "schema_version" in rows and rows["schema_version"].startswith("project:")


def test_provenance_not_configured(layout):
    home, repo = layout
    r = run_lib("ait_config_provenance", env=_env(home), cwd=str(repo))
    assert r.returncode == 1 and r.stdout == ""
