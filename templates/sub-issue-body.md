# Sub-issue Body Template

This is the canonical agent-prompt body for filing a sub-issue of
an epic via the `initiative-tracking` skill. **A sub-issue is
feature-shaped, bug-shaped, or epic-shaped** — this template is a
thin compose-by-reference wrapper around the type-appropriate base
template.

- **Leaf sub-issue** (the common case) — feature- or bug-shaped,
  directly workable by an agent. Base: `templates/feature-body.md`
  or `templates/bug-body.md`.
- **Sub-epic** (a child that itself decomposes into 3+ children) —
  epic-shaped, an index over its own sub-issues, not directly
  workable. Base: `templates/epic-body.md`. See the
  `initiative-tracking` skill's "Nested initiatives" section for
  when a child earns sub-epic status.

This pattern (compose, not self-contained) is a deliberate
divergence from `templates/followup-body.md`. Followup bodies have
five extra blocks specific to the follow-up shape, so a
self-contained template was the honest expression. A sub-issue
adds ONE extra block (`## Parent epic`) on top of an otherwise
ordinary feature, bug, or epic body, so composition is the honest
expression and avoids drift if the base templates change.

## How to compose

1. Pick the base template that matches the sub-issue's
   type-shape:
   - The sub-issue adds a **new capability or redesign** -> use
     `templates/feature-body.md` as the base. Load the
     `feature-request` skill for the agent-prompt requirements.
   - The sub-issue fixes a **defect or regression** -> use
     `templates/bug-body.md` as the base. Load the `bug-tracking`
     skill for the agent-prompt requirements.
   - The sub-issue is itself a **multi-child sub-initiative** -> use
     `templates/epic-body.md` as the base (it doubles as the
     sub-epic body). The result is an index, not a leaf prompt; its
     own children are filed as further sub-issues under it. Load the
     `initiative-tracking` skill.

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
   `create_issue` operation. Use `type: sub` for a leaf sub-issue,
   or `type: epic` for a sub-epic (so it carries the `epic` label
   that marks it as a recursable node). See `backends/<backend>.md`
   for the literal invocation. After the sub-issue is filed, invoke
   the backend's `link_sub_issue` operation to establish native
   parent-child linkage, and add the child to the parent's
   `## Children` mirror (marked `▸ sub-epic` if it is one).

---

## Parent epic
<parent-ref> — <one-line parent title> (Phase <N>)

<optional: one sentence on which slice of the parent this sub-issue
covers. Keep it short — the parent's `## Phases` section has the
full breakdown.>

The heading stays `## Parent epic` for backward-compatibility, but
`<parent-ref>` names this sub-issue's **immediate** parent — which
may itself be a sub-epic, not the root of the initiative. In a
nested tree, follow `## Parent epic` refs upward to walk to the
root; `/resume-initiative` walks the `## Children` mirrors downward
from the root.
