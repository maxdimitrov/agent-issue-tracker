# Followup Body Template

This is the canonical agent-prompt body for filing a followup via the
`followup-tracking` skill. Use it verbatim — each section maps to a step
an agent picking up the issue cold will take. The five
**followup-specific** blocks come first (Parent / What's already done /
What's been tried-ruled out / Related issues / Why deferred); a `---`
separator follows; then the seven standard agent-prompt blocks shared
with the `bug-tracking` and `feature-request` siblings.

Sections marked **[required]** are what an agent reads to decide
whether to work the issue or bail.

To file, fill in this template and pass the result as the `body`
argument to your backend's `create_issue` operation. See
`backends/<backend>.md` for the literal invocation.

---

## Parent  **[required]**
What this spun out of. Link the parent PR, the parent issue, the
branch, or the conversation. Use your backend's issue-ref syntax
(`#N` for GitHub, `PROJ-123` for Jira, etc.) — the backend module
renders the syntax; the skill names the intent.
- Spun out of: <parent PR or issue ref, or branch `<branch-name>` if
  not yet merged>
- Discussion: <file:line ref, or "<one-line summary>" if chat-only>
- Date deferred: <YYYY-MM-DD>

## What's already done  **[required]**
Two or three bullets — the load-bearing facts from the parent change
that the next agent needs without re-reading the parent diff.
- <fact 1>
- <fact 2>

## What's been tried / ruled out  **[required]**
Approaches considered in the parent work and discarded, with one-line
reasons. If nothing was tried, write `Nothing tried - design is open`
and tag `needs-design`.
- Tried <X>: rejected because <Y>
- Considered <X>: <reason>

## Related issues
Output of your backend's `list_open_issues` operation filtered to the
same area (optionally by keyword if your backend supports it).
"No related issues found" is a valid entry — it tells the next agent
the search has been done.

## Why deferred  **[required]**
One of:
- **scope** — work was ready, just too large for the parent PR.
- **clarity** — open design question; tag `needs-design`.
- **dependency** — blocked on <issue / PR / external ref>.
- **time** — capacity, not unreadiness.

The next agent uses this to judge whether the deferral was about
capacity (do it now if you have time) or unreadiness (don't touch
until the dependency or design lands).

---

## Goal
<one sentence — the observable outcome after the followup ships. State
the change in terms an outside reader can verify.>

## Locus  **[required]**
- File(s): <repo-relative path(s), e.g. `src/api/foo.py:142`>
- Function/route: <name>
- Subsystem: <one of your configured `subsystems:` enum from
  `.claude/issue-tracker.yaml`>

## Skills to load  **[required]**
List the project skills an agent should load before editing. Pick the
ones that codify the touched subsystem.
- <your-subsystem-architecture-skill>
- <your-relevant-domain-skill>

## <task-specific block>
If the followup is a **bug**: add Symptom / Repro / Expected / Impact
blocks per `templates/bug-body.md`.

If the followup is a **feature**: add What's missing / Sketch blocks
per `templates/feature-body.md`.

## Constraints  **[required]**
- Out of scope: <files/dirs/subsystems the change MUST NOT touch>
- Invariants to preserve: <e.g. "do not change the X algorithm",
  "the Y route must remain mounted">
- Dependencies: <other issues/PRs that must merge first; "none" if
  standalone>
- Style: minimal change; no drive-by refactors; match surrounding code
  style.

## Acceptance  **[required]**
Writable as a test or verifiable observation. An agent will write
tests (or a manual-verify script) that assert each of these BEFORE
changing code; they must pass after the change ships.
- [ ] <criterion 1 - observable, specific, testable>
- [ ] <criterion 2 - observable, specific, testable>

## Verify  **[required]**
Exact commands an agent runs from the clone root to prove the change.
```bash
<your project's targeted test command, e.g. `pytest -q tests/test_foo.py`>
<your project's full-suite command, e.g. `pytest -q`>
# add any build-verification commands your project requires
```

## Notes (optional)
<Related issues, prior PRs, links to docs the agent should read,
anything that helps it pick up cold but isn't load-bearing. Use your
backend's issue-ref syntax (e.g. `#N` for GitHub, `PROJ-123` for
Jira).>
