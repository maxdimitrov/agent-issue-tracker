---
description: Discoverable entry-point for the bug-tracking skill — file a defect or regression as an agent-prompt-shaped issue in the configured tracker.
---

# /file-bug [<short description>]

A discoverable slash-command wrapper around the [`bug-tracking`](../skills/bug-tracking/SKILL.md) skill. Filing is normally skill-driven — the agent recognises trigger phrases ("file a bug", "we should track this") and follows the skill's body template. This command is that **same flow** with a name you can find in Claude Code's command palette; it adds **no behaviour** of its own. The skill is the source of truth.

Any text after the command (`/file-bug auth modal hangs on submit`) seeds the issue — it is handed to the skill as starting context, exactly as if you had typed that phrase to trigger the skill directly.

## What you should do

1. Invoke the `bug-tracking` skill (via the `Skill` tool), passing the operator's `<short description>` (if any) as starting context.
2. The skill does the rest, unchanged:
   - gathers the body in the agent-prompt shape (Goal, Locus, Skills to load, Symptom + Repro + Impact, Constraints, Acceptance, Verify);
   - applies the bail criteria (no clear locus / unbounded blast radius / open design question / no writable regression test → ask for what's missing rather than file a vague issue);
   - resolves the backend from `.claude/issue-tracker.yaml` and dispatches `create_issue` (with the `bug` label plus any area labels) through `backends/<backend>.md`.

## Relationship to siblings

| Command | Skill | When |
|---|---|---|
| `/file-bug` | `bug-tracking` | A defect or regression with a repro |
| `/file-feature` | `feature-request` | A new capability that doesn't exist yet |
| `/file-followup` | `followup-tracking` | Work deferred from in-flight effort (parent reference required) |
| `/file-epic` | `initiative-tracking` | A multi-week initiative plus its sub-issue index |

These four commands are pure entry-points; they do not diverge from their skills. To file by intent instead, just say "file a bug" — same result.
