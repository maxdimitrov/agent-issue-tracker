"""Every commands/*.md is listed wherever the plugin enumerates its commands.

The README table, the README's two count phrases, and the manifest
descriptions in .claude-plugin/ are hand-maintained; a command added or
removed without touching them is the drift these tests catch.
"""
import json
import re

import pytest

from shell_helpers import REPO_ROOT

COMMANDS_DIR = REPO_ROOT / "commands"
README = REPO_ROOT / "README.md"
MANIFESTS = [
    REPO_ROOT / ".claude-plugin" / "plugin.json",
    REPO_ROOT / ".claude-plugin" / "marketplace.json",
]
NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
    7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
    12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
    20: "twenty",
}


def commands():
    names = sorted(p.stem for p in COMMANDS_DIR.glob("*.md"))
    assert names, "no commands found"
    return names


def readme():
    return README.read_text(encoding="utf-8")


def description_with_command_list(manifest):
    """The one description string in the manifest that enumerates commands."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "description" and isinstance(value, str) \
                        and "slash commands (" in value:
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(json.loads(manifest.read_text(encoding="utf-8")))
    assert len(found) == 1, (manifest.name, found)
    return found[0]


def test_readme_table_lists_every_command():
    text = readme()
    missing = [n for n in commands()
               if f"[`/{n}`](commands/{n}.md)" not in text]
    assert not missing, missing


def test_readme_table_has_no_stale_command():
    linked = set(re.findall(r"\]\(commands/([^)]+)\.md\)", readme()))
    stale = sorted(linked - set(commands()))
    assert not stale, stale


def test_readme_count_phrases_match():
    word = NUMBER_WORDS[len(commands())]
    text = readme()
    assert f"{word} slash commands" in text, "README intro count"
    assert f"{word.capitalize()} slash commands:" in text, "README heading count"


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.name)
def test_manifest_description_lists_every_command(manifest):
    desc = description_with_command_list(manifest)
    word = NUMBER_WORDS[len(commands())]
    assert f"{word} slash commands" in desc, manifest.name
    listed = set(re.findall(r"/([a-z][a-z0-9-]*)", desc))
    missing = sorted(set(commands()) - listed)
    stale = sorted(listed - set(commands()))
    assert not missing, (manifest.name, "missing", missing)
    assert not stale, (manifest.name, "stale", stale)
