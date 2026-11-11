"""scripts/tracker-init-render.sh: the config /tracker-init writes, from answers.

Both /tracker-init modes render through this script (the interactive flow
writes its answers to a temp file first; `--answers <file>` passes the
caller's), so one set of answers gives one config by construction. These
tests pin the rendered shape to commands/tracker-init.md Phase 6.
"""
import re
import subprocess

import pytest

from shell_helpers import REPO_ROOT, SCRIPTS, bash_path, isolated_env, run_lib, run_script

SCRIPT = SCRIPTS / "tracker-init-render.sh"
DOC = REPO_ROOT / "commands" / "tracker-init.md"

HEADER = (
    "# .claude/issue-tracker.yaml — agent-issue-tracker schema v1\n"
    "#\n"
    "# Written by /tracker-init on 2026-10-22. Schema reference:\n"
    "# https://github.com/maxdimitrov/agent-issue-tracker/blob/main/examples/issue-tracker.yaml.example\n"
    "#\n"
    "# Run /tracker-doctor to validate this config.\n"
    "\n"
    "schema_version: 1\n"
)


def render(tmp_path, answers, expect=0):
    """(stdout, stderr), read as UTF-8 bytes: the header carries an em dash,
    and a text-mode capture would decode it with the console's code page."""
    f = tmp_path / "answers.yaml"
    f.write_text(answers, encoding="utf-8")
    r = subprocess.run([bash_path(), str(SCRIPT), f.as_posix()], capture_output=True,
                       env=isolated_env(tmp_path), stdin=subprocess.DEVNULL, timeout=60)
    out, err = r.stdout.decode("utf-8"), r.stderr.decode("utf-8")
    assert r.returncode == expect, (out, err)
    return out, err


def test_github_answers(tmp_path):
    out, _ = render(tmp_path, "backend: github\ngithub:\n  repo: acme/widgets\n"
                    "areas:\n  - backend\n  - infra\nsubsystems:\n  - ingest\ndate: 2026-10-22\n")
    assert out == HEADER + (
        "backend: github\n"
        "areas:\n  - backend\n  - infra\n"
        "subsystems:\n  - ingest\n"
        "github:\n  repo: acme/widgets\n  default_pr_close_syntax: \"Fixes #N\"\n")


def test_github_board_and_no_vocabulary(tmp_path):
    out, _ = render(tmp_path, "# answers\nbackend: github\ngithub:\n  repo: acme/widgets\n"
                    "  project: https://github.com/users/acme/projects/3\ndate: 2026-10-22\n")
    assert out == HEADER + (
        "backend: github\n"
        "github:\n  repo: acme/widgets\n  default_pr_close_syntax: \"Fixes #N\"\n"
        "  project: https://github.com/users/acme/projects/3\n")


def test_jira_answers_with_defaults_and_epic_link(tmp_path):
    out, _ = render(tmp_path, "backend: jira\njira:\n  site: https://acme.atlassian.net/\n"
                    "  cloud_id: c-1\n  project: TRADE\n  parent_link_style: epic_link\n"
                    "areas:\n  - dashboard\ndate: 2026-10-22\n")
    assert out == HEADER + (
        "backend: jira\n"
        "areas:\n  - dashboard\n"
        "jira:\n  site: acme.atlassian.net\n  cloud_id: c-1\n  project: TRADE\n"
        "  issue_types:\n    feature: Story\n    bug: Bug\n    epic: Epic\n    sub: Sub-task\n"
        "    followup: Task\n"
        "  area_field: components\n  parent_link_style: epic_link\n"
        "  epic_link_field: customfield_10014\n"
        "  done_transition: Done\n  close_on_merge_hint: \"\"\n")


def test_default_date_is_today(tmp_path):
    out, _ = render(tmp_path, "backend: github\ngithub:\n  repo: acme/widgets\n")
    assert re.search(r"Written by /tracker-init on \d{4}-\d{2}-\d{2}\. ", out)


def test_rendered_config_reads_back(tmp_path):
    out, _ = render(tmp_path, "backend: github\ngithub:\n  repo: acme/widgets\n")
    cfg = tmp_path / "issue-tracker.yaml"
    cfg.write_text(out, encoding="utf-8")
    r = run_lib(f'ait_config_get github.repo "{cfg.as_posix()}"; echo; '
                f'ait_config_get github.default_pr_close_syntax "{cfg.as_posix()}"')
    assert r.stdout.splitlines() == ["acme/widgets", "Fixes #N"]


@pytest.mark.parametrize("answers, why", [
    ("github:\n  repo: a/b\n", "backend is required"),
    ("backend: gitlab\n", "backend must be one of"),
    ("backend: github\n", "github.repo is required"),
    ("backend: github\ngithub:\n  repo: widgets\n", "owner/repo"),
    ("backend: jira\njira:\n  site: a.atlassian.net\n  project: T\n", "jira.cloud_id is required"),
    ("backend: jira\njira:\n  site: a\n  cloud_id: c\n  project: T\n  feature_type: Epic\n", "feature_type"),
    ("backend: github\ngithub:\n  repo: a/b\ndate: today\n", "date must be"),
    ("backend: github\n!!garbage\n", "flat YAML"),
])
def test_bad_answers_exit_2_with_nothing_on_stdout(tmp_path, answers, why):
    out, err = render(tmp_path, answers, expect=2)
    assert out == "" and why in err


def test_missing_file_is_a_usage_error(tmp_path):
    r = run_script(SCRIPT, args=((tmp_path / "nope.yaml").as_posix(),), env=isolated_env(tmp_path))
    assert r.returncode == 2 and r.stdout == ""


def test_the_command_doc_renders_both_modes_through_the_script():
    doc = DOC.read_text(encoding="utf-8")
    assert "--answers <file>" in doc
    assert doc.count("scripts/tracker-init-render.sh") >= 2
    # The header the doc shows is the one the script prints.
    for line in HEADER.replace("2026-10-22", "YYYY-MM-DD").splitlines():
        assert line in doc, line
