"""Executable spec for /resume-initiative's drift-reconciliation grammar.

Pins the documented rules (commands/resume-initiative.md "Drift
reconciliation"; skills/initiative-tracking "Scope probe") the same way
test_doc_currency.py pins the audit script:

- mirror-line grammar: bullet-tolerant, checked AND unchecked lines
- scope-probe extraction: first fenced block under `## Scope probe`
- category-1 diff: native children absent from the mirror
- forward probe diff: literal case-sensitive substring matching
"""

import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "drift"

# The documented mirror-line grammar: `-`/`*`/`+` bullet (Jira's ADF
# round-trip flips `-` to `*`), checkbox, ref (no spaces), em-dash.
MIRROR_LINE = re.compile(r"^[-*+] \[([ x])\] (\S+) — ")


def parse_mirror_refs(body: str) -> dict:
    """All `## Children` mirror refs -> checked flag (checked AND unchecked)."""
    refs = {}
    in_children = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_children = line.strip() == "## Children"
            continue
        if in_children:
            m = MIRROR_LINE.match(line)
            if m:
                refs[m.group(2)] = m.group(1) == "x"
    return refs


def parse_mirror_lines(body: str) -> list:
    """Raw mirror lines, for probe substring matching."""
    lines = []
    in_children = False
    for line in body.splitlines():
        if line.startswith("## "):
            in_children = line.strip() == "## Children"
            continue
        if in_children and MIRROR_LINE.match(line):
            lines.append(line)
    return lines


def parse_scope_probe(body: str):
    """Command inside the FIRST fenced code block under `## Scope probe`.

    Returns None when the section is absent; raises ValueError when the
    section exists but holds no fenced block (documented soft-warn case).
    """
    in_probe = False
    in_fence = False
    command_lines = []
    for line in body.splitlines():
        if line.startswith("## "):
            if in_probe:
                break
            in_probe = line.strip() == "## Scope probe"
            continue
        if not in_probe:
            continue
        if line.startswith("```"):
            if in_fence:
                return "\n".join(command_lines)
            in_fence = True
            continue
        if in_fence:
            command_lines.append(line)
    if in_probe:
        raise ValueError("## Scope probe declared but no fenced command block found")
    return None


def unmirrored_children(mirror: dict, native: list) -> list:
    """Category 1: native children (open AND closed) missing from the mirror."""
    return [child for child in native if child["ref"] not in mirror]


def probe_unenumerated(items: list, mirror_lines: list, child_titles: list) -> list:
    """Forward probe diff: items matching no mirror line and no live child title."""
    haystacks = mirror_lines + child_titles
    return [
        item
        for item in items
        if item and not any(item in hay for hay in haystacks)
    ]


def load(stem: str):
    body = (FIXTURES / f"{stem}_epic_body.md").read_text(encoding="utf-8")
    native = json.loads(
        (FIXTURES / f"{stem}_native_children.json").read_text(encoding="utf-8")
    )
    return body, native


def test_fixture_a_flags_only_the_unmirrored_live_child():
    body, native = load("a")
    mirror = parse_mirror_refs(body)
    # Checked (closed) mirror lines count toward the mirror set: #201 is
    # closed AND mirrored, so it must not flag.
    assert mirror == {"#201": True, "#131": False, "#132": False}
    findings = unmirrored_children(mirror, native)
    assert [f["ref"] for f in findings] == ["#145"]
    assert findings[0]["title"] == "migrate FooTests"


def test_fixture_a_has_no_probe():
    body, _ = load("a")
    assert parse_scope_probe(body) is None


def test_fixture_b_probe_extracts_first_fenced_block():
    body, _ = load("b")
    assert parse_scope_probe(body) == "git ls-files 'Tests/*Tests.swift'"


def test_fixture_b_probe_surfaces_exactly_the_unenumerated_items():
    body, native = load("b")
    # Mirror and native agree — category 1 is clean.
    assert unmirrored_children(parse_mirror_refs(body), native) == []
    items = [
        line.strip()
        for line in (FIXTURES / "b_probe_output.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    unenumerated = probe_unenumerated(
        items,
        parse_mirror_lines(body),
        [child["title"] for child in native if child["status"] == "open"],
    )
    assert unenumerated == [
        "Tests/CheckoutTests.swift",
        "Tests/InventoryTests.swift",
    ]


def test_fixture_c_consistent_epic_yields_zero_findings():
    body, native = load("c")
    assert unmirrored_children(parse_mirror_refs(body), native) == []
    assert parse_scope_probe(body) is None


def test_bullet_glyph_is_tolerated():
    # Jira's ADF round-trip flips `-` to `*`; the grammar must not care.
    for glyph in "-*+":
        line = f"{glyph} [ ] PROJ-9 — migrate widget (Phase 1)"
        m = MIRROR_LINE.match(line)
        assert m and m.group(2) == "PROJ-9"


def test_probe_section_without_fence_is_the_documented_error():
    body = "## Scope probe\nJust prose, no fence.\n"
    try:
        parse_scope_probe(body)
    except ValueError as err:
        assert "no fenced command block" in str(err)
    else:
        raise AssertionError("expected ValueError for fence-less probe section")
