---
description: Discoverable entry-point for the feature-request skill — file an enhancement or new capability as an agent-prompt-shaped issue in the configured tracker.
---

# /file-feature [<short description>]

A discoverable slash-command wrapper around the [`feature-request`](../skills/feature-request/SKILL.md) skill. Filing is normally skill-driven — the agent recognises trigger phrases ("file a feature request", "we should add...", "it would be nice if...") and follows the skill's body template. This command is that **same flow** with a name you can find in Claude Code's command palette; it adds **no behaviour** of its own. The skill is the source of truth.

Any text after the command (`/file-feature add CSV export to the report view`) seeds the issue — it is handed to the skill as starting context, exactly as if you had typed that phrase to trigger the skill directly.

## What you should do

1. Invoke the `feature-request` skill (via the `Skill` tool), passing the operator's `<short description>` (if any) as starting context.
2. The skill does the rest, unchanged:
   - gathers the body in the agent-prompt shape (What's missing, Sketch, Locus, Constraints, Acceptance, Verify);
   - applies the bail criteria (fuzzy locus / unbounded scope / open design question → a `needs-design` issue first / fuzzy acceptance → ask rather than file a vague issue);
   - resolves the backend from `.claude/issue-tracker.yaml` and dispatches `create_issue` (with the `enhancement` label plus any area labels) through `backends/<backend>.md`.

## Relationship to siblings

| Command | Skill | When |
|---|---|---|
| `/file-bug` | `bug-tracking` | A defect or regression with a repro |
| `/file-feature` | `feature-request` | A new capability that doesn't exist yet |
| `/file-followup` | `followup-tracking` | Work deferred from in-flight effort (parent reference required) |
| `/file-epic` | `initiative-tracking` | A multi-week initiative plus its sub-issue index |

These four commands are pure entry-points; they do not diverge from their skills. To file by intent instead, just say "file a feature request" — same result.
