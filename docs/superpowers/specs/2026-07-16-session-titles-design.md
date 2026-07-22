# Design: initiative-aware session titles (SessionStart hook)

- **Issue:** not yet filed — file via the plugin's own `feature-request` methodology before or with the implementation PR (operator approval required for issue creation)
- **Branch:** `feat/session-titles`
- **Date:** 2026-07-16
- **Status:** approved design — ready for `writing-plans`
- **Builds on:** v1.5.0 (`d106d6e`)

## Summary

Ship the plugin's first **hook**: a `SessionStart` hook that sets the Claude Code
session title (the VS Code tab name) whenever a session **starts or resumes** in
a project that has `.claude/issue-tracker.yaml`. The title tells the operator at
a glance which initiative/issue a tab is driving and what it was last doing:

```
#42 board-support · wiring webhook · idle 3d
WB-7657 subscription-gates · tests failing
#57 gh-projects · next #61 · idle 5d
```

The feature is **tracker-scoped and fail-open**: in a repo without
`.claude/issue-tracker.yaml` the hook exits silently, and any failure at any
stage means "leave the title alone" — never a blocked or broken session start.

A paired **mid-session nudge** lands in `initiative-tracking` and
`/resume-initiative`: hooks cannot retitle a *running* session (the platform
only allows setting `sessionTitle` from `SessionStart` on `startup`/`resume`),
so when the working focus shifts mid-session, the agent offers a paste-ready
`/rename` line instead.

## Goal

> A session that starts or resumes in a tracker-configured project titles
> itself with the issue/epic ref it is driving, a short description of what it
> was last doing, and a staleness marker — so an operator returning to many
> tabs can tell them apart without opening them. Sessions outside tracker
> projects, sessions the operator manually renamed, and every failure path are
> left untouched.

## Decisions (from brainstorm, operator-approved)

1. **Placement: bundled into `agent-issue-tracker`** — not a sibling
   marketplace plugin, not a personal settings hook. Rationale: the title
   content is tracker-aware (issue refs, epic Status blocks, `/resume-initiative`
   workflows), and the config-file gate keeps behaviour predictable for
   adopters — installing an issue tracker never touches sessions in unrelated
   repos.
2. **Title source: branch + epic + AI tail (layered).** Instant base from the
   git branch, epic Status-block enrichment via `gh` where the backend is
   GitHub, and a ≤5-word Haiku summary of the transcript tail on resume.
3. **Scope: tracker projects only.** The hook is a no-op without
   `.claude/issue-tracker.yaml`.
4. **Manual renames are sacred.** If the operator ever renames a session
   themselves, the hook never touches that session again.
5. **Jira gets no epic enrichment.** Hooks are shell processes; the Jira
   backend speaks Atlassian Remote MCP, which only the model can reach. Jira
   projects still get branch refs (`PROJ-123` parses fine from branch names)
   plus the AI tail.
6. **Start/resume only, stated honestly in docs.** No live mid-session title
   updates exist on the platform; the skill-level `/rename` nudge covers the
   gap.

## Title format spec

Compose from available parts, in this order, ` · `-separated:

| Part | Source | Presence |
| --- | --- | --- |
| `<ref> <slug>` | branch / epic match / transcript tail | whenever found |
| `<ai tail>` | Haiku over transcript tail | resume only, best-effort |
| `next <ref>` | epic Status block `- **Next up:**` | only when epic matched AND no AI tail (avoid overlong titles) |
| `idle <N>d` | transcript mtime | only when ≥ 24h stale |

- **Ref extraction from branch:** first match of a Jira key (`[A-Z][A-Z0-9]+-\d+`)
  or a GitHub issue number embedded per common conventions (`#42`,
  `42-slug`, `feat/42-slug`, `issue-42`). The **slug** is the branch name minus
  user prefix (`max/`, `feat/`, `fix/`, `docs/`) and minus the ref itself,
  truncated to 24 chars.
- **Fallback ref:** last issue-ref-shaped token (`#\d+` or `PROJ-\d+`) in the
  transcript tail.
- **Emit nothing** (leave title untouched) when neither a ref nor an AI tail
  was found — a contentless title is worse than the default.
- **Total length cap: 64 chars**, truncated at a part boundary (drop trailing
  parts, never mid-word).

## Hook wiring

New file `hooks/hooks.json` (plugin hook manifest):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session-title.sh",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

The script emits, on success:

```json
{"hookSpecificOutput": {"hookEventName": "SessionStart", "sessionTitle": "<title>"}}
```

> **Implementation-time verification (blocking):** confirm against the live
> hooks documentation (a) the plugin hook manifest location/shape
> (`hooks/hooks.json` + `${CLAUDE_PLUGIN_ROOT}`), (b) the exact
> `sessionTitle` output field name and the `session_title` input field,
> (c) that `sessionTitle` is honoured on `source: startup` and
> `source: resume` only. These came from doc research dated 2026-07; re-verify
> before wiring, adjust mechanically if names drifted.

## Script behaviour spec — `hooks/session-title.sh`

Bash. Hard dependency: `jq` (guard-checked). Soft dependencies: `git`, `gh`,
`claude` (each stage skips if its tool is missing). Every external call runs
under `timeout`. The script **always exits 0**.

Stage order:

1. **Recursion guard.** If `$AIT_TITLE_GUARD` is set, exit. (Our own
   `claude -p` call below fires `SessionStart` hooks in its headless session;
   without this guard the hook forks itself.)
2. **Parse stdin JSON:** `session_id`, `transcript_path`, `cwd`, `source`,
   `session_title` (may be absent). Malformed stdin → exit.
3. **Config gate.** Locate `.claude/issue-tracker.yaml` at `cwd` or the git
   toplevel of `cwd`. Absent → exit. Present with a top-level
   `session_titles: false` → exit.
4. **Manual-rename gate.** State dir:
   `${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles/`.
   Per-session state file `<session_id>` holds the last title *we* set;
   sentinel file `<session_id>.pinned` means "operator renamed — hands off".
   - `.pinned` exists → exit.
   - State file exists and incoming `session_title` is non-empty and differs
     from the stored value → the operator renamed since our last write →
     write `.pinned`, exit.
   - No state file, incoming `session_title` non-empty, and it does **not**
     match the platform default pattern (`<basename cwd>-[a-z0-9]{2}`) → a
     pre-existing manual name → write `.pinned`, exit.
5. **Base ref + slug** from `git -C <cwd> branch --show-current` per the format
   spec. Fallback: transcript-tail ref grep.
6. **Epic enrichment** (config `backend: github` and `gh` present only).
   Cache file keyed by `sha256(repo-toplevel + branch)`, TTL 24h, storing
   `epic_ref`, `epic_slug`, `next_ref` (possibly all empty = negative cache).
   On miss: `timeout 5 gh issue list --label epic --state open --json
   number,title,body --limit 50`, match a body line `- **Current branch:**
   <branch>`; extract the epic number, a slug of its title, and its
   `- **Next up:**` ref. Any failure → write negative cache entry, skip.
   On match: the epic ref/slug **replace** the branch-derived pair (the epic
   is the better anchor); `next <ref>` becomes available per the format spec.
7. **AI tail** (`source == resume`, transcript exists and is non-empty,
   `claude` present, `$AIT_TITLE_NO_AI` unset). Extract the text of the last
   ~20 `user`/`assistant` entries via defensive `jq` (`2>/dev/null`, tolerate
   schema drift — the transcript format is documented as internal/unstable;
   extraction failure just drops this stage), cap at ~4000 chars, and run:
   `AIT_TITLE_GUARD=1 timeout 8 claude -p --model haiku` with a pinned prompt:
   *"Output ONLY a lowercase phrase of at most 5 words describing what this
   coding session is working on right now. No punctuation, no quotes."*
   Empty/multi-line/over-long output → drop the stage.
8. **Idle marker** from the transcript file's mtime: ≥ 24h → `idle <N>d`.
9. **Compose per the format spec.** Nothing to say → exit without output.
   Otherwise emit the `hookSpecificOutput` JSON and write the title to the
   state file.

Latency budget: heuristic-only path (fresh session, cached epic) well under
1s; resume with AI tail 2–8s, bounded by the `timeout 8` and the manifest's
15s ceiling.

## Config schema (additive, optional)

One new **optional top-level key** in `.claude/issue-tracker.yaml`:

```yaml
# Optional. Set false to disable the SessionStart session-title hook for this
# project. Default: true. (The hook is already a no-op in projects without
# this config file.)
session_titles: true
```

No `schema_version` bump — additive optional key, absent means `true`.
Documented in `examples/issue-tracker.yaml.example`.

## Failure semantics — best-effort, never blocking

- Script always exits 0; a hook failure must never block a session start.
- Each stage degrades independently: no `jq` → exit silently (doctor WARNs);
  no `gh`/network → skip enrichment via negative cache; no `claude` or model
  timeout → skip AI tail; unparseable transcript → skip AI tail and
  fallback ref.
- Worst case of every path: the title stays whatever it was.

## `/tracker-doctor` — new WARN-only check

Appended to the existing check phases, GitHub- and Jira-agnostic:

- `jq` on PATH → `[PASS]`; missing → `[WARN] session-title hook inactive: jq
  not found` + install hint.
- State dir writable → `[PASS]`; else `[WARN]`.
- `session_titles: false` → `[PASS-WITH-NOTE] session titles disabled by
  config`.

Never `[FAIL]` — the feature is cosmetic; doctor's informational discipline
(always exit 0) is unchanged.

## Mid-session nudge — skill/command additions

- **`skills/initiative-tracking/SKILL.md`** — new short "Session titles"
  section: when the session's working focus shifts to a different issue/epic,
  or the epic/leaf being driven completes, offer the operator a paste-ready
  rename line, e.g. `` /rename #42 board-support — done ``. State plainly
  that agents cannot rename sessions; only the operator can paste it.
- **`commands/resume-initiative.md`** — after Mode 2/3 resolve the target
  node, offer the same paste-ready line when the current session title does
  not already name that ref (the hook will catch up on next resume; the nudge
  makes it immediate).

## Files touched

| File | Change |
| --- | --- |
| `hooks/hooks.json` | new — plugin hook manifest |
| `hooks/session-title.sh` | new — the hook script |
| `tests/test_session_title_hook.py` | new — pytest fixtures driving the script via subprocess (rides the existing `python-tests` CI job) |
| `examples/issue-tracker.yaml.example` | `session_titles` key |
| `commands/tracker-doctor.md` | WARN-only prerequisite checks |
| `skills/initiative-tracking/SKILL.md` | "Session titles" nudge section |
| `commands/resume-initiative.md` | rename-nudge line |
| `.github/workflows/ci.yml` | new `shellcheck` job over `hooks/*.sh` |
| `README.md` | "Session titles" section + component counts |
| `.claude-plugin/plugin.json` / `marketplace.json` | descriptions gain "one hook"; version bump at release time |
| `CHANGELOG.md` | `[Unreleased]` entry |
| `CONTRIBUTING.md` | release-gate smoke: resumed session in a configured repo gets titled |

No backend-contract change — the eight operations are untouched; the CI
op-parity check stays green.

## Invariants preserved

- The hook writes nothing into any tracker — read-only against `gh`.
- `.claude/issue-tracker.yaml` remains the only configuration surface (the
  two env vars — `AIT_TITLE_GUARD`, `AIT_TITLE_NO_AI` — are internal
  plumbing/test switches, not operator configuration).
- Best-effort discipline matches the GitHub-Projects-board precedent: a
  cosmetic feature's failure never blocks a core operation.

## Verification plan

pytest (subprocess-driven, `AIT_TITLE_NO_AI=1`, temp git repos + synthetic
stdin payloads + fake transcripts):

1. No config file → no output, exit 0.
2. `session_titles: false` → no output.
3. Branch `max/WB-7657-subscription-gates` → title starts `WB-7657
   subscription-gates`.
4. Epic fixture (stubbed `gh` on PATH printing a canned JSON body with
   `- **Current branch:**` match) → epic ref replaces branch ref; `next #N`
   present; second run hits the cache (stub records call count).
5. Manual-rename respect: run once (title recorded), feed back a *different*
   `session_title` → no output + `.pinned` created; third run → still no
   output.
6. Recursion guard: `AIT_TITLE_GUARD=1` → immediate exit, no output.
7. Idle marker: transcript mtime backdated 3 days → `· idle 3d`.
8. Malformed stdin / unreadable transcript / missing `jq` (PATH stripped) →
   exit 0, no output.
9. 64-char cap: overlong parts truncate at a part boundary.

shellcheck clean. Manual smoke (release gate): in a real configured repo,
resume a stale session and observe the tab title; manually rename it, resume
again, confirm the hook left it alone.

## Out of scope / follow-ups

- Jira epic enrichment (needs an MCP-reachable path from a shell hook — none
  exists).
- Live mid-session title updates (no platform API; revisit if `sessionTitle`
  ever becomes writable from `Stop`/`PostToolUse` hooks).
- Titles in non-tracker projects (operator-declined; a personal
  `~/.claude/settings.json` hook could reuse the same script later).
- A second marketplace plugin form factor.

## Open questions

None blocking. The two implementation-time verification items (hook manifest
shape; `sessionTitle`/`session_title` field names and honoured sources) are
listed under "Hook wiring" and resolve mechanically against live docs.
