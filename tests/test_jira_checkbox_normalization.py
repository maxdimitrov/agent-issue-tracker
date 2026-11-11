"""Executable spec for the Jira backend's escaped-checkbox normalization.

Descriptions written by older Atlassian MCP revisions stored task-list
lines as plain bullets with literal brackets; they read back as
`* \\[x\\] <text>`. backends/jira.md (`view_issue`, invariant 1) documents
the rewrite that turns them back into `- [x] <text>` before the body is
returned. These tests pin that the documented pattern is the one used here,
and that a normalized legacy body parses like a fresh one.
"""
import re
from pathlib import Path

from shell_helpers import REPO_ROOT
from test_drift_fixtures import parse_mirror_refs

JIRA_DOC = REPO_ROOT / "backends" / "jira.md"
FIXTURE = Path(__file__).parent / "fixtures" / "drift" / "g_epic_body.md"

# Verbatim from backends/jira.md `view_issue`.
PATTERN = r"^(\s*)[*-] \\?\[([ xX])\\?\] "
REPLACEMENT = r"\1- [\2] "
ESCAPED_LINE = re.compile(PATTERN)


def normalize(body: str) -> str:
    """Rewrite escaped checkbox lines outside fenced code blocks."""
    out = []
    in_fence = False
    for line in body.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            line = ESCAPED_LINE.sub(REPLACEMENT, line)
        out.append(line)
    return "\n".join(out)


def body() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_documented_pattern_and_replacement_are_pinned():
    doc = JIRA_DOC.read_text(encoding="utf-8")
    assert f"`{PATTERN}`" in doc
    assert f"`{REPLACEMENT}`" in doc


def test_escaped_lines_are_invisible_to_the_mirror_grammar():
    # The defect: only the one real task-list line is seen.
    assert parse_mirror_refs(body()) == {"PROJ-13": False}


def test_normalized_body_parses_every_child():
    assert parse_mirror_refs(normalize(body())) == {
        "PROJ-11": True,
        "PROJ-12": False,
        "PROJ-13": False,
    }


def test_only_escaped_checkbox_lines_change():
    before = body().split("\n")
    after = normalize(body()).split("\n")
    changed = [(b, a) for b, a in zip(before, after) if b != a]
    assert changed == [
        ("* \\[x\\] PROJ-11 — ledger schema (Phase 0) — closed 2026-06-20",
         "- [x] PROJ-11 — ledger schema (Phase 0) — closed 2026-06-20"),
        ("* \\[ \\] PROJ-12 — extract ledger writer (Phase 1)",
         "- [ ] PROJ-12 — extract ledger writer (Phase 1)"),
    ]


def test_code_fence_content_is_left_alone():
    assert "* \\[ \\] literal text inside a code fence stays escaped" \
        in normalize(body())


def test_normalization_is_idempotent():
    once = normalize(body())
    assert normalize(once) == once
