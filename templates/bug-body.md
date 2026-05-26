# Bug Body Template

This is the canonical agent-prompt body for filing a bug via the
`bug-tracking` skill. Use it verbatim — each section maps to a step an
issue-fix agent will take. Sections marked **[required]** are what an agent
reads to decide auto-fix vs bail.

To file, fill in this template and pass the result as the `body` argument to
your backend's `create_issue` operation. See `backends/<backend>.md` for the
literal invocation.

---

## Goal
<one sentence — the observable outcome after the fix. State the change in
terms an outside reader can verify, e.g. "POST /api/foo returns 200 with a
`bar` field instead of 502 when called with X.">

## Locus  **[required]**
- File(s): <repo-relative path(s), e.g. `src/api/foo.py:142`>
- Function/route: <name>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an issue-fix agent should load before editing.
Pick the ones that codify the touched subsystem.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## Symptom  **[required]**
<What you see go wrong. One or two sentences.>

## Repro  **[required]**
Exact command(s) or steps. Paste verbatim error output in a fenced block.
```bash
<exact command>
```
```
<verbatim error output>
```

## Expected
<What should happen instead. Be specific — "returns 200 with field X" beats
"works correctly".>

## Impact  **[required]**
One of your project's impact categories (e.g. `blocks-release` /
`blocks-deploy` / `degrades-UX` / `cosmetic` / `data-loss-risk`). Add one
sentence of context.

## Root cause hypothesis (optional)
<If you have a guess, write it. An issue-fix agent uses this as a starting
hypothesis but will verify before changing code.>

## Constraints
- Out of scope: <files/dirs/subsystems the fix MUST NOT touch>
- Invariants to preserve: <e.g. "do not change the X algorithm",
  "the Y route must remain mounted">
- Style: minimal fix; no drive-by refactors; match surrounding code style.

## Acceptance  **[required]**
Writable as a regression test. An issue-fix agent will write a test that
asserts each of these BEFORE changing code; the test must FAIL on the base
branch and PASS after the fix.
- [ ] <criterion 1 — observable, specific, testable>
- [ ] <criterion 2 — observable, specific, testable>

## Verify  **[required]**
Exact commands an issue-fix agent runs from the clone root to prove the fix.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, anything that helps an agent pick up cold but
isn't load-bearing. Use your backend's issue-ref syntax (e.g. `#N` for
GitHub, `PROJ-123` for Jira).>
