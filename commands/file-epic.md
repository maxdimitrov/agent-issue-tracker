---
description: Discoverable entry-point for the initiative-tracking skill — open a multi-week epic plus its sub-issue index, with a parseable Status block.
---

# /file-epic [<short description>]

A discoverable slash-command wrapper around the [`initiative-tracking`](../skills/initiative-tracking/SKILL.md) skill. Filing is normally skill-driven — the agent recognises trigger phrases ("open an epic", "this is a multi-week initiative", "let's break this into phases") and follows the skill's body template. This command is that **same flow** with a name you can find in Claude Code's command palette; it adds **no behaviour** of its own. The skill is the source of truth.

Any text after the command (`/file-epic observability rollout across the worker fleet`) seeds the initiative — it is handed to the skill as starting context, exactly as if you had typed that phrase to trigger the skill directly.

## What you should do

1. Invoke the `initiative-tracking` skill (via the `Skill` tool), passing the operator's `<short description>` (if any) as starting context.
2. The skill does the rest, unchanged:
   - confirms the scope is genuinely multi-week and spans more than one PR (single-issue scope belongs in `/file-bug` or `/file-feature`, not an epic);
   - files the epic body with the canonical four-line **Status block** (`**Phase:**`, `**Next up:**`, `**Current branch:**`, `**Last updated:**`), the `## Children` task-list mirror (the cross-backend source of truth for the sub-issue index), the design-spec pointer, and the phase breakdown;
   - files each sub-issue and links it to the epic, mirroring the link in the `## Children` list;
   - resolves the backend from `.claude/issue-tracker.yaml` and dispatches `create_issue` / `link_sub_issue` (with the `epic` label) through `backends/<backend>.md`.

Once filed, [`/resume-initiative`](resume-initiative.md) walks the epic tree and points at the next-up child.

## Relationship to siblings

| Command | Skill | When |
|---|---|---|
| `/file-bug` | `bug-tracking` | A defect or regression with a repro |
| `/file-feature` | `feature-request` | A new capability that doesn't exist yet |
| `/file-followup` | `followup-tracking` | Work deferred from in-flight effort (parent reference required) |
| `/file-epic` | `initiative-tracking` | A multi-week initiative plus its sub-issue index |

These four commands are pure entry-points; they do not diverge from their skills. To file by intent instead, just say "open an epic" — same result.
