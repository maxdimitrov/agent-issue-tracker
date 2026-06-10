"""Markdown report formatter tests."""
from audit_skills import (
    DiffSummary, SkillFinding, PairedRuleFinding, format_report,
)

SUMMARY = DiffSummary(base_ref="origin/main", changed=3)


def test_no_findings_report():
    text = format_report((), (), SUMMARY, rules_configured=False)
    assert "[audit-skills] Doc-currency scan vs origin/main (3 changed files)" in text
    assert "No findings" in text
    assert "Exit 0 (informational; PR not blocked)." in text


def test_singular_file_word():
    text = format_report((), (), DiffSummary(base_ref="main", changed=1),
                         rules_configured=False)
    assert "(1 changed file)" in text


def test_doc_findings_grouped_by_referencing_doc():
    doc = (
        SkillFinding(referencing_doc="skills/b/SKILL.md",
                     changed_file="scripts/x.py", matched_form="path", line_no=9),
        SkillFinding(referencing_doc="skills/a/SKILL.md",
                     changed_file="scripts/x.py", matched_form="basename", line_no=4),
        SkillFinding(referencing_doc="skills/a/SKILL.md",
                     changed_file="lib/y.py", matched_form="path", line_no=12),
    )
    text = format_report(doc, (), SUMMARY, rules_configured=False)
    a_pos = text.index("skills/a/SKILL.md:")
    b_pos = text.index("skills/b/SKILL.md:")
    assert a_pos < b_pos                      # sorted by doc
    assert "L4" in text and "L9" in text and "L12" in text
    assert "(basename)" in text and "(path)" in text


def test_paired_section_shown_when_rules_configured():
    text = format_report((), (), SUMMARY, rules_configured=True)
    assert "Paired rules:" in text
    assert "(no paired-rule findings)" in text


def test_paired_section_hidden_when_no_rules_configured():
    text = format_report((), (), SUMMARY, rules_configured=False)
    assert "Paired rules:" not in text


def test_paired_findings_listed():
    paired = (PairedRuleFinding(watch="scripts/db.py", line_no=100,
                                entity="foo_bar",
                                message="new table `foo_bar` has no skill"),)
    text = format_report((), paired, SUMMARY, rules_configured=True)
    assert "scripts/db.py L100: new table `foo_bar` has no skill" in text
    assert "Exit 0 (informational; PR not blocked)." in text
