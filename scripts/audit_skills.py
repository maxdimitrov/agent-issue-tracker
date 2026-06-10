"""Doc-currency + paired-rule audit for agent-readable docs.

Stdlib-only (Python 3.10+). Shipped as a plugin asset; the /audit-skills
slash command invokes it as:

    python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_skills.py" [flags]

Internal layering mirrors the origin implementation (trading-bot
scripts/audit/): pure cores (_parse, doc_currency_findings,
paired_rule_findings, format_report) and a thin I/O edge
(list_changed_files, main).

Exit codes:
  0 -- informational success (findings or no findings; always)
  1 -- operational error (bad ref, git missing, malformed rule JSON)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Sequence


# --- diff parsing -----------------------------------------------------------

@dataclass(frozen=True)
class ChangedFile:
    """One file in a diff.

    `added_lines` is the sequence of (line_no_in_new_file, content) for every
    `+` line. `status` is git's letter: A added, M modified, R renamed,
    D deleted. `rename_from` is set only for status='R'.
    """
    path: str
    added_lines: tuple[tuple[int, str], ...]
    status: str
    rename_from: str | None


_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_NEW_FILE = re.compile(r"^new file mode ")
_DELETED_FILE = re.compile(r"^deleted file mode ")
_RENAME_FROM = re.compile(r"^rename from (.+)$")
_RENAME_TO = re.compile(r"^rename to (.+)$")
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
_BINARY_MARKER = re.compile(r"^Binary files ")


def _parse(text: str) -> tuple[ChangedFile, ...]:
    """Parse a unified diff into ChangedFile records.

    Expects `git diff --unified=0` output (no context lines), but tolerates
    context-bearing diffs by counting only '+' lines.
    """
    if not text.strip():
        return ()

    files: list[ChangedFile] = []
    cur_path: str | None = None
    cur_status: str = "M"
    cur_rename_from: str | None = None
    cur_added: list[tuple[int, str]] = []
    cur_line_no: int | None = None

    def _flush() -> None:
        if cur_path is not None:
            files.append(ChangedFile(
                path=cur_path,
                added_lines=tuple(cur_added),
                status=cur_status,
                rename_from=cur_rename_from,
            ))

    for raw in text.splitlines():
        m = _DIFF_HEADER.match(raw)
        if m:
            _flush()
            cur_path = m.group(2)   # `b/` path is the post-change name
            cur_status = "M"
            cur_rename_from = None
            cur_added = []
            cur_line_no = None
            continue
        if cur_path is None:
            continue
        if _NEW_FILE.match(raw):
            cur_status = "A"
            continue
        if _DELETED_FILE.match(raw):
            cur_status = "D"
            continue
        rm = _RENAME_FROM.match(raw)
        if rm:
            cur_status = "R"
            cur_rename_from = rm.group(1)
            continue
        if _RENAME_TO.match(raw):
            continue   # path already captured from `b/<path>` in the header
        if _BINARY_MARKER.match(raw):
            continue
        hm = _HUNK_HEADER.match(raw)
        if hm:
            cur_line_no = int(hm.group(1))
            continue
        if cur_line_no is None:
            continue   # metadata lines (index, ---, +++) before first hunk
        if raw.startswith("+"):
            cur_added.append((cur_line_no, raw[1:]))
            cur_line_no += 1
        # '-' lines and ' ' (context) lines don't bump the +new-side counter
        # in --unified=0 output. Context lines don't appear with --unified=0,
        # but if they do we leave cur_line_no alone (best-effort).

    _flush()
    return tuple(files)


def list_changed_files(base_ref: str = "origin/main") -> tuple[ChangedFile, ...]:
    """Run `git diff <base_ref>...HEAD` and parse the output.

    `--unified=0` minimises context so line numbers are unambiguous;
    `--find-renames` enables status R. Raises CalledProcessError on git
    failure (bad ref, not a repo) and FileNotFoundError if git is absent.
    """
    proc = subprocess.run(
        ["git", "diff", "--unified=0", "--find-renames", f"{base_ref}...HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return _parse(proc.stdout)


# --- doc-currency detector ---------------------------------------------------

_DEFAULT_DOC_GLOBS = (
    # consumer-project layout
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/skills/*/SKILL.md",
    ".claude/agents/*.md",
    ".claude/commands/*.md",
    # plugin-dev repo layout (this repo's own shape)
    "skills/*/SKILL.md",
    "commands/*.md",
    "backends/*.md",
    "templates/*.md",
)


@dataclass(frozen=True)
class SkillFinding:
    referencing_doc: str   # repo-relative, forward-slash
    changed_file: str      # the file in the diff whose ref may be stale
    matched_form: str      # "path" | "basename" | "basename_no_ext"
    line_no: int


def doc_currency_findings(
    diff: tuple[ChangedFile, ...],
    docs_root: str = ".",
    doc_globs: tuple[str, ...] = _DEFAULT_DOC_GLOBS,
) -> tuple[SkillFinding, ...]:
    """For each changed file, scan every doc in `doc_globs` (under
    `docs_root`) for substring matches of the file's path, basename, and
    basename-without-extension. One finding per (doc, file, form).
    """
    if not diff:
        return ()

    search_forms: list[tuple[ChangedFile, list[tuple[str, str]]]] = []
    for cf in diff:
        forms: list[tuple[str, str]] = [(cf.path, "path")]
        base = os.path.basename(cf.path)
        if base and base != cf.path:
            forms.append((base, "basename"))
        stem, ext = os.path.splitext(base)
        # Length guard: a <3-char stem (db, fx) matches spuriously as a
        # substring of unrelated words; require >= 3 chars.
        if stem and ext and stem != base and len(stem) >= 3:
            forms.append((stem, "basename_no_ext"))
        search_forms.append((cf, forms))

    out: list[SkillFinding] = []
    root = Path(docs_root)
    for pattern in doc_globs:
        for doc_path in sorted(root.glob(pattern)):
            try:
                body = doc_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lines = body.splitlines()
            for cf, forms in search_forms:
                for needle, form in forms:
                    for line_no, line in enumerate(lines, start=1):
                        if needle in line:
                            rel = str(doc_path.relative_to(root)).replace("\\", "/")
                            out.append(SkillFinding(
                                referencing_doc=rel,
                                changed_file=cf.path,
                                matched_form=form,
                                line_no=line_no,
                            ))
                            break    # one match per (doc, file, form)
    return tuple(out)
