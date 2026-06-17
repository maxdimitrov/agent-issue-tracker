---
description: Discoverable entry-point for the followup-tracking skill — file work deferred from in-flight effort as an agent-prompt-shaped issue, with a parent reference.
---

# /file-followup [<short description>]

A discoverable slash-command wrapper around the [`followup-tracking`](../skills/followup-tracking/SKILL.md) skill. Filing is normally skill-driven — the agent recognises trigger phrases ("follow-up for that", "out of scope for this PR", "spin that out", "we'll handle X in a separate change") and follows the skill's body template. This command is that **same flow** with a name you can find in Claude Code's command palette; it adds **no behaviour** of its own. The skill is the source of truth.

Any text after the command (`/file-followup harden the retry path deferred from #42`) seeds the issue — it is handed to the skill as starting context, exactly as if you had typed that phrase to trigger the skill directly.

## What you should do

1. Invoke the `followup-tracking` skill (via the `Skill` tool), passing the operator's `<short description>` (if any) as starting context.
2. The skill does the rest, unchanged:
   - gathers the body in the agent-prompt shape, with the follow-up-specific blocks first (Parent PR/branch — **required**, What's already done, What's been tried or ruled out, Related issues, Why deferred), followed by the standard agent-prompt tail for the follow-up's underlying shape — a follow-up is itself bug-shaped (Symptom + Repro + Impact) or feature-shaped (What's missing + Sketch) — plus Goal, Locus, Skills to load, Constraints, Acceptance, Verify;
   - applies the bail criteria, including the origination-specific one — a follow-up with no resolvable parent is just a plain bug or feature, so route it to `/file-bug` or `/file-feature` instead;
   - resolves the backend from `.claude/issue-tracker.yaml` and dispatches `create_issue` (with the `followup` label plus its underlying type/area labels) through `backends/<backend>.md`.

## Relationship to siblings

| Command | Skill | When |
|---|---|---|
| `/file-bug` | `bug-tracking` | A defect or regression with a repro |
| `/file-feature` | `feature-request` | A new capability that doesn't exist yet |
| `/file-followup` | `followup-tracking` | Work deferred from in-flight effort (parent reference required) |
| `/file-epic` | `initiative-tracking` | A multi-week initiative plus its sub-issue index |

Follow-up is *orthogonal* to type — a follow-up is itself bug-shaped or feature-shaped; this command captures the origination (deferred-from-in-flight-work) and the required parent reference. These four commands are pure entry-points; they do not diverge from their skills. To file by intent instead, just say "spin that out as a follow-up" — same result.
