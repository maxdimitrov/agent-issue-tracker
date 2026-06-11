"""Replay trading-bot PR #139's frozen diff against a frozen corpus
snapshot and assert the doc-currency detector flags the two skills whose
references went stale in that PR.

This is the issue's motivating-miss proof, made hermetic: both the diff
AND the corpus are fixtures (the origin repo's version scanned live
skills at HEAD and admitted the fragility in its own docstring).
"""
from pathlib import Path

from audit_skills import _parse, doc_currency_findings

FIXTURES = Path(__file__).parent / "fixtures" / "pr139"


def test_pr139_replay_flags_expected_skills():
    diff = _parse((FIXTURES / "diff.patch").read_text(encoding="utf-8",
                                                      errors="ignore"))
    assert len(diff) == 18, "frozen PR-139 diff should parse 18 files"

    findings = doc_currency_findings(diff, docs_root=str(FIXTURES / "corpus"))
    referenced = {f.referencing_doc for f in findings}
    assert any("dashboard-maintenance" in r for r in referenced), \
        f"expected dashboard-maintenance flagged; got {referenced}"
    assert any("core-trail-architecture" in r for r in referenced), \
        f"expected core-trail-architecture flagged; got {referenced}"
