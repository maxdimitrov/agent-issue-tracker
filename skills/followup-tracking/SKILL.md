---
name: followup-tracking
description: >-
  How follow-ups, scope-deferrals, "later phase" work, and spun-out tasks
  are tracked — they go in the configured issue tracker (see
  `.claude/issue-tracker.yaml`) as enriched issues with the parent
  PR/branch, what has already been done in the spawning change, what has
  been tried or ruled out, related existing issues, and the reason for
  deferral. Issues here are consumed by Claude Code agents, which means
  the body is an **agent prompt**, not a human note - on top of the
  parent/prior-work blocks, the body must satisfy the same locus /
  constraints / writable-acceptance requirements as a plain bug or
  feature issue or no agent can pick it up. Use this skill whenever you
  are about to write "follow-up", "later phase", "out of scope for this
  PR", "we'll handle X in a separate change", "TODO: also do Y",
  "leaving Z for next pass", or otherwise carve scope off an in-flight
  piece of work; whenever the user says "follow-up for that", "track
  that for later", "spin that out", or "do that in a separate PR"; and
  whenever a reviewer's comment surfaces a real-but-out-of-scope
  concern. The siblings bug-tracking (defects) and feature-request (new
  capabilities) cover the type framing - this skill covers the
  *origination* (work deferred from in-flight effort) which is
  orthogonal: a follow-up can be either bug-shaped or feature-shaped.
---

# Follow-up Tracking — Issues as Agent Prompts

The canonical tracker is the one configured in the consumer project's
`.claude/issue-tracker.yaml`. The plugin's `backends/_interface.md`
documents the eight operations every backend implements;
`backends/<backend>.md` (e.g. `backends/github.md`) documents the
literal CLI / MCP invocation for each operation.

Follow-ups are not a different *tracker* — they are a different *shape
of issue*. The shape exists because a follow-up exists *because of*
another change: a PR that left scope on the floor, a review comment
that surfaced an adjacent concern, a bug fix that revealed a related
defect.

That parent context is the whole value of filing a follow-up as a
structured issue instead of a code comment or a chat message. **And
it's also what makes a follow-up agent-executable** — when the next
agent picks it up cold weeks later, the parent + prior-work + ruled-out
blocks prevent them from re-deriving discarded approaches.

## Type-orthogonal

A follow-up is either bug-shaped or feature-shaped. This skill adds
five extra blocks (Parent / What's already done / What's been tried-
ruled out / Related issues / Why deferred) on top of the appropriate
sibling skill's body:

- Deferred thing is **broken behaviour** → `bug` label, follow
  `skills/bug-tracking/` for the Symptom / Repro / Expected / Impact
  blocks.
- Deferred thing is a **missing capability or redesign** →
  `enhancement` label, follow `skills/feature-request/` for the
  What's missing / Sketch blocks.

Always add the `followup` label so the configured backend's
`list_open_issues` operation, filtered by `label: followup`, finds
them cleanly.

## Why structure matters

Same bail criteria as the sibling skills: an agent picking the issue
up cold will **bail** (refuse to work it, leave a comment, no PR) on a
fuzzy locus, unbounded scope, an open design question, or no writable
acceptance. The parent / prior-work blocks help, but they don't
substitute — they're *additional* context, not a replacement.

If the follow-up has a real open design question (common for follow-ups
spun out under time pressure), tag `needs-design` and accept that a
human brainstorm runs before any agent works it.

## When to file

File when, mid-task or mid-PR, you find yourself wanting to defer real
work and the deferral is **decision-shaped** — i.e. you have context
the next agent will not, and that context will not survive in chat or
in a code comment.

Strong triggers:

- "Out of scope for this PR but we should also..."
- "Leaving X for a follow-up — the design is unclear."
- "We tried Y, it didn't work because of Z. Should revisit when..."
- Review comment surfaces a real concern that doesn't block merge.
- A bug fix exposes a related-but-distinct defect.
- A feature ships in a minimal form and the next slice has obvious
  work.

Do **not** file when:

- You are doing the work in the current change.
- The "deferral" is a vague maybe.
- The thing is already tracked — use the backend's `list_open_issues`
  operation (optionally filtered by keyword) first. Comment on the
  existing issue with the new context.
- The thing is purely a tactical reminder for the current task — that
  belongs in your task tracker or PR description, not a permanent
  issue.

## Filing

Invoke the configured backend's `create_issue` operation — see
`backends/<backend>.md` where `<backend>` is the value of `backend:`
in `.claude/issue-tracker.yaml`. Pass:

- `type`: `followup`
- `title`: `<component>: <deferred work>` plus a parent reference in
  your tracker's syntax (see Title format below)
- `labels`: `[<bug or enhancement>, <area>, followup]` where `<area>`
  is one of your configured `areas:` enum and the bug-or-enhancement
  choice follows the type-orthogonal rule above
- `body`: the filled-in `templates/followup-body.md` template

**Title format:** `<component>: <deferred work>`. Optionally append a
parent reference in your tracker's syntax — e.g. `(followup #<parent>)`
on GitHub, `(followup <PROJ-N>)` on Jira. The backend module documents
the literal syntax; the skill names the *intent* (the title should
make the parent linkage visible when scanning a backend's
issue-list view).

Examples: `worker/queue: defer dead-letter retention policy`,
`cli/list: ship schema versioning for --json output`.

If the `followup` label doesn't exist on your tracker yet, your
consumer's setup process creates it once — see your backend's
configuration documentation.

## Agent-execution issue body template

The body template lives at `templates/followup-body.md` in this
plugin. Use it verbatim — each section maps to a step an agent picking
up the issue cold will take. Sections marked **[required]** are what
an agent reads to decide whether to work the issue or bail.

See `templates/followup-body.md` for the canonical skeleton with
placeholders. The template is self-contained: the five
followup-specific blocks come first, a `---` separator follows, then
the standard tail. The `<task-specific block>` pointer in the standard
tail names which sibling-template blocks to compose in
(`templates/bug-body.md` or `templates/feature-body.md`) based on
whether the deferred work is bug-shaped or feature-shaped.

### What each block unlocks

- **Parent** — orients the agent: "this exists because of #N". Lets
  the agent open the parent PR and see what shipped vs. what's open.
- **What's already done** — saves the agent from re-reading the
  entire parent diff. Two bullets of context beat 300 lines of diff.
- **What's been tried / ruled out** — the highest-value block.
  Prevents the agent from rediscovering discarded dead ends.
  *Always* include this even if it's "Nothing tried".
- **Related issues** — `list_open_issues` results frozen at file
  time. Saves the agent a search round-trip.
- **Why deferred** — tells the agent whether to pick it up at all. A
  `clarity` deferral with `needs-design` is a hard skip for
  autonomous agents.
- **Locus + Skills + Constraints + Acceptance + Verify** — same bail
  criteria as plain bugs/features. A great parent block doesn't save
  a follow-up with no acceptance criteria.

## When the parent has not landed yet

Link the follow-up by branch instead of by parent-issue-or-PR
reference — PR/issue refs are unstable until merge on some backends,
and a branch name is always stable. Once the parent merges, edit the
follow-up to swap the branch reference for the merged ref.

Use your backend's `edit_body` operation for this — read the current
body, modify the Parent block in memory, write back the whole body.
The contract documents this as a destructive whole-body replace; the
skill is responsible for the read-modify-write cycle.

## Labels

Every follow-up gets:

- One type-shape label: `bug` or `enhancement`.
- One or more area labels from the consumer's
  `.claude/issue-tracker.yaml` `areas:` enum.
- The **`followup`** label.

Triage flags (agents skip):

- `needs-design` — open design question, sketch missing.
- `needs-triage` — required fields missing.

## Closing the loop

A PR that resolves a follow-up must follow the backend's
close-on-merge convention — see `backends/<backend>.md` PR
close-on-merge section. For example, on the `github` backend the
convention is to include `Fixes #N` (for bug-shaped follow-ups) or
`Closes #N` (for feature-shaped) in the PR title or body so GitHub
auto-closes the issue when the PR merges to the default branch.
`Closes` works for both — pick the verb that matches the type-shape.

Other backends document their own conventions (e.g. Jira may
auto-close via a PR-integration hook configured outside the plugin).

Manual closures follow the same convention — use the backend's
`close_issue` operation with a one-line reason if a follow-up turns
out to be resolved another way (superseded, won't-fix, fixed-by-other-
PR).

**Note:** `link_sub_issue` is NOT used for follow-ups. Follow-ups are
not sub-issues; the parent linkage is the body's Parent block plus
the `followup` label. `link_sub_issue` is reserved for the epic →
sub-issue relationship documented in `initiative-tracking`.

## When a follow-up compounds

A single follow-up is one issue. But sometimes the deferred scope
keeps growing — the "one cleanup" turns out to be 3+ independent
sub-issues. At that point it has outgrown a follow-up and become an
initiative; switch to `initiative-tracking`. **Where** it lands
depends on its origin:

- The follow-up was spun out of **standalone** work (not part of any
  initiative) → promote it to a **root epic**. Supersede the
  follow-up with a one-line "superseded by `<epic-ref>`" close
  comment.
- The follow-up was spun out of work that is **already a child of an
  epic** (e.g. a deferred review-comment from a sub-issue's PR) →
  file it as a **sub-epic under that existing parent**, not as a new
  root. Keep the follow-up's context in the sub-epic body. This
  keeps the initiative tree intact instead of fragmenting one effort
  across two unrelated roots. See `initiative-tracking`'s "Nested
  initiatives".

A follow-up that stays at 1–2 sub-tasks is **not** an initiative —
leave it as a single follow-up issue with a checklist in its body.

## At the start of work

The backend's `list_open_issues` operation filtered by
`{label: followup}` shows the deferred-scope backlog — useful before
starting a new feature in an area, since a related follow-up may
already exist. Filter additionally by `needs-design` to see the
follow-ups that still need a human brainstorm pass before any agent
can work them.

## Example — a well-formed follow-up

A follow-up spun out of the `cli/list --json` feature (from the
`feature-request` example): the initial PR shipped the `--json` flag
without schema versioning. The next slice — adding a `--schema-version`
flag — was deferred.

````markdown
## Parent
- Spun out of: `#<PR ref>` (cli/list --json feature; merged
  YYYY-MM-DD)
- Discussion: review thread on `cli/list.py:render_list`
- Date deferred: 2026-MM-DD

## What's already done
- Initial PR shipped `cli list --json` emitting NDJSON, one JSON
  object per row, matching the existing table field set.
- Default behaviour (no flag) is byte-identical to before.

## What's been tried / ruled out
- Tried embedding a `_schema_version` field in each row: rejected
  because consumers parsing line-by-line shouldn't pay for the
  field on every line.
- Considered a `--schema-version` flag that emits a header line:
  this is the recommended path for the follow-up.

## Related issues
- `list_open_issues` filtered by `cli` area: no other open
  follow-ups in `cli/list`.

## Why deferred
scope — the schema-versioning sub-design was clean enough to ship,
but the initial PR was already at the size limit reviewers prefer.
A separate change keeps the diff readable.

---

## Goal
`cli/list --json` emits an optional header line declaring the schema
version when `--schema-version` is passed, letting downstream
automation lock against a known shape.

## Locus
- File: `cli/list.py:render_list`
- New helper: `cli/_format_json.py:emit_header`
- Subsystem: cli   # from your configured `subsystems:` enum

## Skills to load
- <your-cli-architecture-skill>
- <your-output-format-conventions-skill>

## What's missing
There is no way for a downstream consumer to assert it was given a
shape it understands. `awk` parsers pin against field positions and
break silently when the field set changes.

## Sketch
- Add `cli/_format_json.py:emit_header(version) -> str` returning a
  single NDJSON object like `{"_schema_version": "1"}`.
- `cli/list.py:render_list` emits the header BEFORE the first row
  when `--schema-version` is passed.
- Default behaviour (no `--schema-version` flag) is byte-identical
  to the post-`#<PR ref>` baseline.

## Constraints
- Out of scope: changing field names or types in existing rows
  (would be a breaking change to the post-#<PR ref> baseline).
- Invariants: omitting `--schema-version` produces output
  byte-identical to today.
- Style: minimal change; no drive-by refactors.

## Acceptance
- [ ] `cli list --json --schema-version` prints `{"_schema_version":
  "1"}` as the FIRST line, followed by NDJSON rows.
- [ ] `cli list --json` (no `--schema-version`) output is
  byte-identical to the post-#<PR ref> baseline.
- [ ] Header line is valid NDJSON (parses as a single JSON object on
  one line).

## Verify
```bash
pytest -q tests/test_cli_list.py
pytest -q
```
````

---

See also: `skills/bug-tracking/` (defect-shaped sibling),
`skills/feature-request/` (capability-shaped sibling),
`initiative-tracking` (multi-issue epics — when follow-ups compound
into an initiative).
