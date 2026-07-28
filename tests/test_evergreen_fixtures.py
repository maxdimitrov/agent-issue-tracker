"""Executable spec for the evergreen-epic machine-block grammar.

Pins the documented rules (backends/_interface.md "Machine-block comment
convention"; templates/epic-machine-block.md; commands/resume-initiative.md
reconcile read model):

- machine-block selection: EARLIEST marker comment with author_trust true
- phases grammar: bullet-tolerant, refs only
- union membership: native children + live phase-map refs
- flags: unphased / unlinked / dead phase-map ref
- next-up: first open child, phased (map order) before unphased (native order)
- legacy detection: body carries a `## Status block` heading
"""

import json
import re
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "evergreen"
MARKER = "<!-- agent-issue-tracker:machine-block -->"

# `- **Phase 1** — goal — #12, PROJ-3, owner/repo#4` (bullet-tolerant:
# Jira's ADF round-trip flips `-` to `*`).
PHASE_LINE = re.compile(r"^[-*+] \*\*(?P<name>[^*]+)\*\* — .+ — (?P<refs>.+)$")
REF = re.compile(r"(#\d+|[A-Z][A-Z0-9]+-\d+|\S+/\S+#\d+)")


def select_machine_block(comments):
    """Earliest marker comment from a trusted author; untrusted -> warns."""
    warns = []
    for c in comments:  # read_comments returns oldest-first
        if MARKER in c["body"]:
            if c["author_trust"]:
                return c, warns
            warns.append(f"untrusted machine-block comment ignored: {c['id']}")
    return None, warns


def section(block_body, heading):
    """Lines of one `## <heading>` section, or [] when absent."""
    lines, active = [], False
    for line in block_body.splitlines():
        if line.startswith("## "):
            active = line.strip() == f"## {heading}"
            continue
        if active:
            lines.append(line)
    return lines


def parse_phases(block_body):
    """Ordered [(phase_name, [refs])]; [] when the section is absent."""
    phases = []
    for line in section(block_body, "Phases"):
        m = PHASE_LINE.match(line)
        if m:
            phases.append((m.group("name"), REF.findall(m.group("refs"))))
    return phases


def reconcile(native, phases, live):
    """Union membership. native: [{ref,title,status}] in return order.
    phases: parse_phases output. live: set of refs that view_issue resolves.
    Returns (ordered_children, findings): phased first (map order), then
    unphased (native order); flags per spec."""
    phase_refs = [r for _, refs in phases for r in refs]
    native_by_ref = {c["ref"]: c for c in native}
    children, findings = [], []
    for ref in phase_refs:
        if ref in native_by_ref:
            children.append(dict(native_by_ref[ref], flag=None))
        elif ref in live:
            children.append({"ref": ref, "status": "open", "flag": "unlinked"})
            findings.append(f"{ref}: in phase map, live, not natively linked")
        else:
            findings.append(f"{ref}: phase-map ref not found in tracker")
    for c in native:
        if c["ref"] not in phase_refs:
            children.append(dict(c, flag="unphased" if phase_refs else None))
    return children, findings


def next_up(children):
    """First open child in reconcile order, or None."""
    for c in children:
        if c["status"] == "open":
            return c["ref"]
    return None


def is_legacy(body):
    return any(l.strip() == "## Status block" for l in body.splitlines())


def load(stem):
    comments = json.loads((FIXTURES / f"{stem}_comments.json").read_text("utf-8"))
    native = json.loads((FIXTURES / f"{stem}_native_children.json").read_text("utf-8"))
    return comments, native


def test_earliest_trusted_marker_wins_and_shadow_is_ignored():
    comments, _ = load("a")
    block, warns = select_machine_block(comments)
    assert block["id"] == 11  # the plugin's block, posted first
    assert warns == []  # attacker comment is LATER; never reached


def test_untrusted_marker_before_real_block_warns_and_is_skipped():
    comments, _ = load("b")
    block, warns = select_machine_block(comments)
    assert block["id"] == 22  # trusted block wins despite earlier untrusted
    assert warns == ["untrusted machine-block comment ignored: 21"]


def test_phases_parse_names_and_refs_only():
    comments, _ = load("a")
    block, _ = select_machine_block(comments)
    assert parse_phases(block["body"]) == [
        ("Phase 0", ["#201", "#131"]),
        ("Phase 1", ["#132", "PROJ-9"]),
    ]


def test_union_flags_unlinked_and_unphased():
    comments, native = load("a")
    block, _ = select_machine_block(comments)
    phases = parse_phases(block["body"])
    live = {"#201", "#131", "#132", "PROJ-9", "#145"}
    children, findings = reconcile(native, phases, live)
    flags = {c["ref"]: c["flag"] for c in children}
    assert flags["PROJ-9"] == "unlinked"      # phase-map only, live
    assert flags["#145"] == "unphased"        # native only
    assert flags["#131"] is None
    assert any("PROJ-9" in f for f in findings)


def test_dead_phase_ref_is_a_finding_not_a_child():
    comments, native = load("a")
    block, _ = select_machine_block(comments)
    phases = parse_phases(block["body"]) + [("Phase 2", ["#999"])]
    children, findings = reconcile(native, phases, {"#201", "#131", "#132", "PROJ-9"})
    assert all(c["ref"] != "#999" for c in children)
    assert "#999: phase-map ref not found in tracker" in findings


def test_next_up_prefers_phase_order_then_unphased_native_order():
    comments, native = load("a")
    block, _ = select_machine_block(comments)
    children, _ = reconcile(native, parse_phases(block["body"]),
                            {"#201", "#131", "#132", "PROJ-9", "#145"})
    # #201 closed; #131 is the first open phased child.
    assert next_up(children) == "#131"


def test_flat_epic_uses_native_return_order():
    _, native = load("b")
    children, findings = reconcile(native, [], {c["ref"] for c in native})
    assert findings == []
    assert [c["ref"] for c in children] == [c["ref"] for c in native]
    assert all(c["flag"] is None for c in children)  # no map -> nothing unphased
    assert next_up(children) == native[1]["ref"]  # native[0] is closed in fixture


def test_no_qualifying_block_means_flat():
    block, warns = select_machine_block(
        [{"id": 1, "author": "x", "author_trust": False, "body": MARKER, "created": "t"}])
    assert block is None and len(warns) == 1


def test_legacy_detection_is_the_status_block_heading():
    legacy = (FIXTURES / "legacy_epic_body.md").read_text("utf-8")
    assert is_legacy(legacy)
    assert not is_legacy("## Goal\nx\n## Scope\nIn:\n- y\n")


LEGACY_MOVED = ("## Status block", "## Phases", "## Children")


def adopt_split(body):
    """Reference for /resume-initiative --adopt's mechanical half: strip the
    moved sections from the description; carry `## Phases` lines and the
    Status block's Current branch into machine-block sections. (Scope /
    Success-criteria folding is judgment work — not pinned here.)"""
    kept, moved, heading = [], {}, None
    for line in body.splitlines():
        if line.startswith("## "):
            heading = line.strip()
        if heading in LEGACY_MOVED:
            moved.setdefault(heading, []).append(line)
        else:
            kept.append(line)
    block = [MARKER, ""]
    if moved.get("## Phases"):
        block.extend(moved["## Phases"])
    for line in moved.get("## Status block", []):
        m = re.search(r"\*\*Current branch:\*\* (\S+)", line)
        if m and m.group(1) != "none":
            block.extend(["## Current branch", f"- {m.group(1)}"])
    return "\n".join(kept), "\n".join(block)


def test_adopt_round_trip_strips_moved_sections_and_builds_block():
    legacy = (FIXTURES / "legacy_epic_body.md").read_text("utf-8")
    evergreen, block = adopt_split(legacy)
    for heading in LEGACY_MOVED:
        assert not any(l.strip() == heading for l in evergreen.splitlines())
    assert not is_legacy(evergreen)          # acceptance #1's grep, as code
    assert MARKER in block
    assert "## Phases" in block
    assert "## Current branch" in block      # fixture branch != none


def test_phase_line_bullet_glyph_is_tolerated():
    # Jira's ADF round-trip flips `-` to `*`; the grammar must not care.
    for glyph in "-*+":
        line = f"{glyph} **Phase 1** — rollout — #132, PROJ-9"
        m = PHASE_LINE.match(line)
        assert m and REF.findall(m.group("refs")) == ["#132", "PROJ-9"]
