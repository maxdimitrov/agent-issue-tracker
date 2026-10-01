"""Executable spec for the /tracker-loop babysit decision table
(commands/tracker-loop.md "Mode: babysit"). First matching row wins.

The observation is the /session-brief collector JSON plus what the command
adds before consulting the table: a `kind` on each awaiting review thread,
`code` (a concrete change request) or `judgement` (a question needing a
human answer), and the merge-readiness fields on `pr` (`headRefOid`,
`mergeStateStatus`, `reviews`)."""
import json
from pathlib import Path

import pytest

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "loops").glob("babysit_*.json"))


def change_requested(reviews):
    """True when some reviewer's standing verdict is CHANGES_REQUESTED.

    A reviewer's verdict is their newest APPROVED, CHANGES_REQUESTED or
    DISMISSED review; a later COMMENTED review (a thread reply creates one)
    does not withdraw a change request.
    """
    verdict = {}
    for r in sorted(reviews or [], key=lambda r: r.get("submittedAt") or ""):
        if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            verdict[(r.get("author") or {}).get("login")] = r["state"]
    return "CHANGES_REQUESTED" in verdict.values()


def review_clear(pr, ci):
    """The "Review-clear" definition under the babysit table."""
    head = pr.get("headRefOid") or ""
    if not head or pr.get("isDraft"):  # merge readiness not read, or a draft
        return False
    if pr.get("reviewDecision") == "APPROVED":
        return True
    # No review required: nobody approves, so the PR has to be green on its
    # head by GitHub's own verdict and by the CI run the collector saw.
    sha = ci.get("sha") or ""
    return (
        pr.get("reviewDecision") == ""  # present and empty; null or absent is not
        and not change_requested(pr.get("reviews"))
        and pr.get("mergeStateStatus") in ("CLEAN", "HAS_HOOKS")
        and ci.get("conclusion") == "success"
        and sha != "" and head.startswith(sha)
    )


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
    if review_clear(pr, ci):
        return "merge" if merge else "stop:ready-to-merge"
    if ci.get("status") in ("queued", "in_progress", "waiting", "pending"):
        return "wait:ci"
    return "wait:idle"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f.stem for f in FIXTURES])
def test_babysit_table(fixture):
    case = json.loads(fixture.read_text())
    assert decide_babysit(case["observation"], merge=case.get("merge", False)) == case["expected"]


def test_merge_rows_cover_both_review_shapes():
    # #154: an approval and "no review required" (reviewDecision "") each
    # need a fixture for both merge-row outcomes.
    cases = [json.loads(f.read_text()) for f in FIXTURES]
    for expected in ("merge", "stop:ready-to-merge"):
        shapes = {c["observation"]["pr"].get("reviewDecision") for c in cases if c["expected"] == expected}
        assert shapes == {"APPROVED", ""}, expected


GREEN_NO_REVIEW = json.loads(
    (Path(__file__).parent / "fixtures" / "loops" / "babysit_no_review_green_merge.json").read_text()
)["observation"]


@pytest.mark.parametrize("field,value", [
    ("isDraft", True),
    ("reviewDecision", None),
    ("reviewDecision", "REVIEW_REQUIRED"),
    ("reviews", [{"author": {"login": "r"}, "state": "CHANGES_REQUESTED"}]),
    ("mergeStateStatus", "UNSTABLE"),
    ("mergeStateStatus", "BLOCKED"),
    ("mergeStateStatus", None),
    ("headRefOid", "0000000000000000000000000000000000000000"),
    ("headRefOid", None),
])
def test_no_review_path_needs_every_condition(field, value):
    # Each condition of the no-review branch is load-bearing: break one on an
    # otherwise green observation and the PR must stop being review-clear.
    pr = dict(GREEN_NO_REVIEW["pr"], **{field: value})
    assert review_clear(GREEN_NO_REVIEW["pr"], GREEN_NO_REVIEW["ci"])
    assert not review_clear(pr, GREEN_NO_REVIEW["ci"])


@pytest.mark.parametrize("ci", [
    {},
    {"status": "in_progress", "conclusion": None, "sha": "ea916ef"},
    {"status": "completed", "conclusion": "cancelled", "sha": "ea916ef"},
    {"status": "completed", "conclusion": "success", "sha": "cb1e777"},
    {"status": "completed", "conclusion": "success"},
])
def test_no_review_path_needs_green_ci_on_the_head(ci):
    assert not review_clear(GREEN_NO_REVIEW["pr"], ci)


def test_fixture_set_covers_every_row():
    expected = {json.loads(f.read_text())["expected"] for f in FIXTURES}
    assert expected == {"stop:done", "rebase", "fix-ci", "address-review", "stop:needs-you",
                        "merge", "stop:ready-to-merge", "wait:ci", "wait:idle"}
