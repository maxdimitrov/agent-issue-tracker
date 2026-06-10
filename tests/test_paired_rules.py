"""Paired-rule detector: the config-driven generalization of trading-bot's
DB-canonical subsystem detector. Zero default rules ship."""
import pytest

from audit_skills import (
    ChangedFile, PairedRule, PairedRuleFinding,
    paired_rule_findings, parse_rule,
)

DB_RULE = PairedRule(
    watch="scripts/db.py",
    pattern=r"CREATE\s+TABLE\s+(\w+)",
    expect=".claude/skills/*-architecture/SKILL.md",
    message="new table `{1}` has no matching *-architecture skill in this diff",
)


def _cf(path, added=()):
    return ChangedFile(path=path, added_lines=tuple(added),
                       status="M", rename_from=None)


def test_rule_fires_on_matching_added_line():
    diff = (_cf("scripts/db.py",
                [(100, "CREATE TABLE foo_bar (id INTEGER PRIMARY KEY)")]),)
    findings = paired_rule_findings(diff, (DB_RULE,))
    assert len(findings) == 1
    f = findings[0]
    assert f.watch == "scripts/db.py"
    assert f.line_no == 100
    assert f.entity == "foo_bar"
    assert "`foo_bar`" in f.message


def test_rule_fires_once_per_matching_line():
    diff = (_cf("scripts/db.py",
                [(10, "CREATE TABLE one (x)"), (20, "CREATE TABLE two (y)")]),)
    findings = paired_rule_findings(diff, (DB_RULE,))
    assert [f.entity for f in findings] == ["one", "two"]


def test_rule_suppressed_when_expect_glob_matches_a_changed_file():
    diff = (
        _cf("scripts/db.py", [(100, "CREATE TABLE foo_bar (id INTEGER)")]),
        _cf(".claude/skills/foo-bar-architecture/SKILL.md", [(1, "---")]),
    )
    assert paired_rule_findings(diff, (DB_RULE,)) == ()


def test_rule_noop_when_watch_file_not_in_diff():
    diff = (_cf("scripts/other.py"),)
    assert paired_rule_findings(diff, (DB_RULE,)) == ()


def test_rule_matches_case_insensitively_when_pattern_says_so():
    rule = PairedRule(watch="scripts/db.py",
                      pattern=r"(?i)create\s+table\s+(\w+)",
                      expect="docs/*.md", message="table `{1}`")
    diff = (_cf("scripts/db.py", [(50, "create table widget (x INTEGER)")]),)
    findings = paired_rule_findings(diff, (rule,))
    assert findings[0].entity == "widget"


def test_pattern_without_capture_group_gives_entity_none():
    rule = PairedRule(watch="api/routes.py", pattern=r"@app\.route",
                      expect="docs/api.md", message="new route, update docs/api.md")
    diff = (_cf("api/routes.py", [(7, '@app.route("/x")')]),)
    findings = paired_rule_findings(diff, (rule,))
    assert findings[0].entity is None
    assert findings[0].message == "new route, update docs/api.md"


def test_parse_rule_roundtrip():
    raw = ('{"watch": "scripts/db.py", "pattern": "CREATE\\\\s+TABLE\\\\s+(\\\\w+)", '
           '"expect": ".claude/skills/*-architecture/SKILL.md", "message": "table `{1}`"}')
    rule = parse_rule(raw)
    assert rule.watch == "scripts/db.py"
    assert rule.expect == ".claude/skills/*-architecture/SKILL.md"


def test_parse_rule_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_rule("{nope")


def test_parse_rule_rejects_missing_keys():
    with pytest.raises(ValueError, match="missing keys"):
        parse_rule('{"watch": "x"}')


def test_parse_rule_rejects_invalid_regex():
    with pytest.raises(ValueError, match="invalid regex"):
        parse_rule('{"watch": "x", "pattern": "(", "expect": "y", "message": "z"}')


def test_parse_rule_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_rule('["not", "an", "object"]')


def test_expect_glob_is_case_sensitive_on_every_os():
    """fnmatchcase, not fnmatch: a path differing only by case from the
    expect glob must NOT suppress the rule (fnmatch would lowercase both
    operands on Windows, making suppression OS-dependent)."""
    diff = (
        _cf("scripts/db.py", [(100, "CREATE TABLE foo_bar (id INTEGER)")]),
        _cf(".claude/skills/FOO-BAR-ARCHITECTURE/SKILL.MD", [(1, "---")]),
    )
    findings = paired_rule_findings(diff, (DB_RULE,))
    assert len(findings) == 1


def test_alternation_with_non_participating_group_1_gives_entity_none():
    """A pattern with a group that didn't participate in the match (the
    other alternation branch matched) yields entity None and an
    uninterpolated message."""
    rule = PairedRule(
        watch="scripts/db.py",
        pattern=r"(?:CREATE TABLE (\w+))|DROP TABLE",
        expect="docs/arch.md",
        message="table change detected",
    )
    diff = (_cf("scripts/db.py", [(5, "DROP TABLE old_table")]),)
    findings = paired_rule_findings(diff, (rule,))
    assert findings[0].entity is None
    assert findings[0].message == "table change detected"
