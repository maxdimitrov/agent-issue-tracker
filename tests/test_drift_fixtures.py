"""Executable spec for /resume-initiative's drift-reconciliation grammar.

Pins the documented rules (commands/resume-initiative.md "Drift
reconciliation"; skills/initiative-tracking "Scope probe") the same way
test_doc_currency.py pins the audit script:

- mirror-line grammar: bullet-tolerant, checked AND unchecked lines
- scope-probe extraction: first fenced block under `## Scope probe`
- category-1 diff: native children absent from the mirror
- status drift: a mirror checkbox that contradicts the child's live state
- stale count: the Status block's stored `N/M` against the live count
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


def is_settled(child: dict, backend: str, merged_status=None):
    """Whether a checked mirror line is right for this live child.

    True / False when the tracker says so; None when it cannot be told
    (a Jira record with no status category) -- never guessed from a name.

    - github: `status` is `closed`, in either case (`list_child_issues`
      returns `closed`, `view_issue` returns `CLOSED`).
    - jira: the status category is Done, or the child sits in the merged
      status (`jira.merged_transition`), where `/work-issue --finish` has
      already checked its line.
    """
    status = child["status"]
    if backend == "github":
        return status.casefold() == "closed"
    if merged_status and status.casefold() == merged_status.casefold():
        return True
    category = child.get("status_category")
    if category is None:
        return None
    return category == "done"


def status_drift(mirror: dict, live: dict, backend: str, merged_status=None) -> list:
    """Mirror lines whose checkbox contradicts the child's live state.

    `live` maps ref -> the child record the run holds; a mirror ref absent
    from it (a checked mirror-only line in Mode 1) and a child of unknown
    state yield no finding.
    """
    findings = []
    for ref, checked in mirror.items():
        child = live.get(ref)
        settled = None if child is None else is_settled(child, backend, merged_status)
        if settled is not None and settled != checked:
            findings.append({"ref": ref, "checked": checked, "status": child["status"]})
    return findings


# The Status block's Phase line: matched on its bold label, bullet-tolerant,
# and on the documented `<int>/<int> sub-issues closed` tail, so a slash in
# the phase name is not mistaken for the count.
PHASE_COUNT = re.compile(r"^[-*+] \*\*Phase:\*\* .*?(\d+)/(\d+) sub-issues closed")


def stored_count(body: str):
    """`(closed, total)` from the Status block's Phase line; None when absent."""
    for line in body.splitlines():
        m = PHASE_COUNT.match(line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def live_count(mirror: dict, live: dict, backend: str, merged_status=None) -> tuple:
    """`(settled, total)` over the mirror's lines, by live state; the checkbox
    stands in for a child whose live state is unknown or was not fetched."""
    settled_total = 0
    for ref, checked in mirror.items():
        child = live.get(ref)
        settled = None if child is None else is_settled(child, backend, merged_status)
        settled_total += checked if settled is None else settled
    return settled_total, len(mirror)


def stale_count(body: str, mirror: dict, live: dict, backend: str, merged_status=None):
    """The one-line count finding: `(stored, live)` when they differ, else None."""
    stored = stored_count(body)
    current = live_count(mirror, live, backend, merged_status)
    if stored is None or stored == current:
        return None
    return stored, current


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


def by_ref(children: list) -> dict:
    return {child["ref"]: child for child in children}


MERGED = "Ready for Release"  # this consumer's jira.merged_transition


def test_fixture_c_consistent_epic_has_no_status_findings():
    body, native = load("c")
    mirror = parse_mirror_refs(body)
    assert status_drift(mirror, by_ref(native), "github") == []
    assert stale_count(body, mirror, by_ref(native), "github") is None


def test_fixture_d_flags_both_directions_of_status_drift():
    body, native = load("d")
    mirror = parse_mirror_refs(body)
    # Membership is consistent (other/repo#9 is a live mirror-only child,
    # which is not drift), which is why the report used to stay silent.
    assert unmirrored_children(mirror, native) == []
    findings = status_drift(mirror, by_ref(native), "github")
    assert findings == [
        {"ref": "#302", "checked": False, "status": "closed"},  # closed, line still [ ]
        {"ref": "#303", "checked": True, "status": "open"},     # reopened, line still [x]
    ]


def test_fixture_d_reports_the_stale_count_once():
    body, native = load("d")
    mirror = parse_mirror_refs(body)
    assert stored_count(body) == (2, 5)
    assert stale_count(body, mirror, by_ref(native), "github") == ((2, 5), (3, 5))


def test_fixture_d_mode_1_does_not_fetch_the_checked_mirror_only_child():
    # other/repo#9 is checked and not natively linked. Mode 1 holds no record
    # for it: no finding, and its checkbox stands in for it in the count.
    body, native = load("d")
    mirror = parse_mirror_refs(body)
    assert "other/repo#9" in mirror and "other/repo#9" not in by_ref(native)
    assert [f["ref"] for f in status_drift(mirror, by_ref(native), "github")] == ["#302", "#303"]
    assert live_count(mirror, by_ref(native), "github") == (3, 5)


def test_fixture_d_mode_2_fetches_the_checked_mirror_only_child():
    # Mode 2/3 make one view_issue for it; GitHub's view_issue reports the
    # state in upper case.
    body, native = load("d")
    mirror = parse_mirror_refs(body)
    still_closed = by_ref(native + [{"ref": "other/repo#9", "title": "shared queue client", "status": "CLOSED"}])
    assert [f["ref"] for f in status_drift(mirror, still_closed, "github")] == ["#302", "#303"]
    reopened = by_ref(native + [{"ref": "other/repo#9", "title": "shared queue client", "status": "OPEN"}])
    assert status_drift(mirror, reopened, "github")[0] == {
        "ref": "other/repo#9", "checked": True, "status": "OPEN"}
    assert live_count(mirror, reopened, "github") == (2, 5)


def test_fixture_e_jira_merged_status_matches_a_checked_line():
    body, native = load("e")
    mirror = parse_mirror_refs(body)
    findings = status_drift(mirror, by_ref(native), "jira", merged_status=MERGED)
    assert [(f["ref"], f["checked"], f["status"]) for f in findings] == [
        ("PROJ-13", False, "Done"),               # Done, line still [ ]
        ("PROJ-15", True, "In Progress"),         # reopened, line still [x]
        ("PROJ-16", False, "Ready for Release"),  # merged, --finish never checked it
    ]
    # PROJ-17 is "Done" by name only: no category in the record, no finding.
    assert stale_count(body, mirror, by_ref(native), "jira", merged_status=MERGED.lower()) == ((3, 7), (4, 7))


def test_fixture_e_without_a_merged_status_only_done_settles():
    body, native = load("e")
    mirror = parse_mirror_refs(body)
    findings = status_drift(mirror, by_ref(native), "jira")
    assert [f["ref"] for f in findings] == ["PROJ-12", "PROJ-13", "PROJ-15"]
    assert stale_count(body, mirror, by_ref(native), "jira") == ((3, 7), (2, 7))


def test_fixture_f_epic_as_finish_leaves_it_has_no_findings():
    # /work-issue --finish moved PROJ-22 to the merged status, checked its
    # line and recounted Phase as settled/total: resume must agree with it.
    body, native = load("f")
    mirror = parse_mirror_refs(body)
    assert status_drift(mirror, by_ref(native), "jira", merged_status=MERGED) == []
    assert stale_count(body, mirror, by_ref(native), "jira", merged_status=MERGED) is None
    # Without the merged status configured the checked line is ahead of the ticket.
    assert [f["ref"] for f in status_drift(mirror, by_ref(native), "jira")] == ["PROJ-22"]


def test_is_settled_never_guesses_from_a_status_name():
    assert is_settled({"status": "Done"}, "jira") is None
    assert is_settled({"status": "Closed", "status_category": "done"}, "jira") is True
    assert is_settled({"status": "To Do", "status_category": "new"}, "jira") is False
    for closed in ("closed", "CLOSED"):
        assert is_settled({"status": closed}, "github") is True
    for opened in ("open", "OPEN"):
        assert is_settled({"status": opened}, "github") is False


def test_stored_count_reads_the_documented_tail():
    for glyph in "-*+":
        assert stored_count(f"{glyph} **Phase:** Phase 1a · 2/4 sub-issues closed") == (2, 4)
    # A slash in the phase name is not the count (fixture f's Phase line).
    body, _ = load("f")
    assert stored_count(body) == (2, 3)
    assert stored_count("## Goal\nNo status block here.\n") is None
    assert stored_count("- **Phase:** Phase 1 of 2, no count yet") is None
    assert stale_count("## Goal\n", {"#1": True}, {}, "github") is None


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
