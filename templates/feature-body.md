# Feature Body Template

This is the canonical agent-prompt body for filing a feature request via
the `feature-request` skill. Use it verbatim — each section maps to a
step an agent picking up the issue cold will take. Sections marked
**[required]** are what an agent reads to decide whether to work the
issue or bail.

To file, fill in this template and pass the result as the `body` argument
to your backend's `create_issue` operation. See `backends/<backend>.md`
for the literal invocation.

---

## Goal
<one sentence — the capability after the change exists. State it as an
observable outcome an outside reader can verify, e.g. "`cli/list`
supports `--json` output and emits one JSON object per row as NDJSON,
matching the existing table output's field set.">

## Locus  **[required]**
- File(s) to add/modify: <repo-relative paths, e.g. `cli/list.py:42`>
- New file(s): <if any, e.g. `cli/_format_json.py`>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an agent should load before editing. Pick the
ones that codify the touched subsystem and any cross-cutting conventions
(output formatting, persistence, UI design) the change touches.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## What's missing  **[required]**
<What does the project not do today? One sentence. Be specific —
"`cli/list` cannot emit machine-readable output" beats "needs better
output support".>

## Why
<The workflow this unblocks or the question it answers. Without this
context, future-you cannot judge whether the idea is still worth
building.>

## Sketch  **[required]**
The shape of the solution. Bullet points are fine. If you don't have a
sketch, write `Open — needs design pass` and tag `needs-design` — an
agent will not work the issue until a sketch exists.

- <step or component 1>
- <step or component 2>

## Constraints  **[required]**
- Out of scope: <files/dirs/subsystems the change MUST NOT touch>
- Invariants to preserve: <e.g. "default behaviour byte-identical when
  the new flag is not passed", "existing route X stays mounted">
- Dependencies: <other issues/PRs that must merge first; "none" if
  standalone>
- Style: minimal change; no drive-by refactors; match surrounding code
  style.

## Acceptance  **[required]**
Writable as a test or a verifiable observation. An agent will write
tests (or a manual-verify script) that assert each of these BEFORE
changing code; they must pass after the change ships.
- [ ] <criterion 1 — observable, specific, testable>
- [ ] <criterion 2 — observable, specific, testable>

## Verify  **[required]**
Exact commands an agent runs from the clone root to prove the change.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, links to docs the agent should read, anything
that helps it pick up cold but isn't load-bearing. Use your backend's
issue-ref syntax (e.g. `#N` for GitHub, `PROJ-123` for Jira).>
