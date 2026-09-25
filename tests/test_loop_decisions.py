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
    if ci.get("status") in ("queued", "in_progress", "waiting", "pending"):
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
