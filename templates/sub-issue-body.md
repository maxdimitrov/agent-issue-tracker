# Sub-issue Body Template

This is the canonical agent-prompt body for filing a sub-issue of
an epic via the `initiative-tracking` skill. **A sub-issue is
either feature-shaped or bug-shaped** — this template is a thin
compose-by-reference wrapper around the type-appropriate sibling
template.

This pattern (compose, not self-contained) is a deliberate
divergence from `templates/followup-body.md`. Followup bodies have
five extra blocks specific to the follow-up shape, so a
self-contained template was the honest expression. A sub-issue
adds ONE extra block (`## Parent epic`) on top of an otherwise
ordinary feature or bug body, so composition is the honest
expression and avoids drift if the sibling templates change.

## How to compose

1. Pick the sibling template that matches the sub-issue's
   type-shape:
   - The sub-issue adds a **new capability or redesign** -> use
     `templates/feature-body.md` as the base. Load the
     `feature-request` skill for the agent-prompt requirements.
   - The sub-issue fixes a **defect or regression** -> use
     `templates/bug-body.md` as the base. Load the `bug-tracking`
     skill for the agent-prompt requirements.

2. Use the title prefix convention: `<phase-name>: <capability>`.
   The phase prefix makes `list_open_issues` show phase membership
   without needing the epic body. Example titles:
   - `Phase 1: backend interface contract + GitHub backend`
   - `Phase 2: port initiative-tracking skill`

3. Fill in the sibling template normally — Goal / Locus / Skills
   to load / What's missing OR Symptom / Sketch / Constraints /
   Acceptance / Verify (the exact field set depends on which
   sibling template).

4. Append the `## Parent epic` block (literal — exactly the
   skeleton below) to the end of the filled-in sibling body. This
   block links the sub-issue back to its epic and is what
   distinguishes a sub-issue body from a plain feature or bug body.

5. Pass the result as the `body` argument to your backend's
   `create_issue` operation with `type: sub`. See
   `backends/<backend>.md` for the literal invocation. After the
   sub-issue is filed, invoke the backend's `link_sub_issue`
   operation to establish native parent-child linkage.

---

## Parent epic
<epic-ref> — <one-line epic title> (Phase <N>)

<optional: one sentence on which slice of the epic this sub-issue
covers. Keep it short — the epic body's `## Phases` section has
the full breakdown.>
