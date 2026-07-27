# Design — Evergreen epics: derive child state from native linkage, drop the body mirror

Issue: #100. Date: 2026-07-27. Status: approved for implementation (interactive brainstorm; all four design forks resolved with the operator).

## Problem

The epic body is today the canonical index: `initiative-tracking` writes a `## Status block` plus a hand-maintained `## Children` task-list mirror into the body, and every child close triggers a read-modify-write of that body. The mirror rots the instant a child is added, renamed, or closed without the ceremony — the exact "stale info for future agents" failure the tracker's native linkage does not have. On Jira the body **is** the description field, so the mirror collides head-on with the evergreen-description convention. The plugin already preaches the fix in its adoption flow ("never infer the child set from the epic body's prose — query the tracker") but the steady-state file/maintain path doesn't follow it.

## Fork resolutions

### Fork #1 — comment capability → **Option (a): two new contract ops, 8 → 10**

`read_comments` + `upsert_comment` join the contract. Rationale:

- `view_issue`'s output shape stays untouched — no churn in its many documented consumers. Comments are fetched only where wanted (resume's epic nodes, #56's display), not on every issue read.
- #86's lean-contract objection (fork #1 there) was about **non-uniform implementability**: GitHub has no native issue-level status, so `transition_issue` could not be a uniform op. Comments ARE first-class and uniform on both backends (`gh issue view --json comments` / `gh issue comment`; `getJiraIssue fields:["comment"]` / `addCommentToJiraIssue`), so that objection does not apply here.
- Option (b) (fold read into `view_issue`) saves one op but makes every `view_issue` call pay comment volume and rewrites the contract output cited across the docs. Option (c) (phase labels) loses human phase names, adds a label vocabulary, does nothing for absorbed #56, and leaves the decision log / parent pointer / current-branch signal homeless in the body — defeating the evergreen goal.
- Op-parity CI, `/tracker-doctor`, and CONTRIBUTING updates are mechanical (two new `` ### `op` `` headings per backend module).

### Fork #2 — machine-block contents → **everything non-derivable moves to the comment**

The operator resolved all four placement questions the same way: the description is **purely** evergreen, and the marker-tagged machine-block comment holds ALL non-derivable structure —

| Section | Contents | Notes |
|---|---|---|
| `## Phases` | phase name + ordered child **refs** only — no titles, no status | order within a phase is the phase map's order |
| `## Parent epic` | immediate parent ref + one-line title | sub-epics only; a root has no such section |
| `## Current branch` | branch name or absent | the #86/#88 in-progress fallback signal's new home |
| `## Scope probe` | prose line + first fenced code block = the probe command | show-before-run gate unchanged |
| `## Decision log` | append-only dated entries | appended via read-modify-write upsert |

The spoofing exposure of comment space (anyone can comment on a public GitHub issue; only author/maintainers can edit a description) was raised explicitly and accepted, mitigated by the trust rule below plus the probe's existing show-before-run gate.

### Fork #3 — phase-map refs vs native child set → **union and flag `unlinked`**

Child set = native children (`list_child_issues`) ∪ live phase-map refs. A phase-map-only ref that is live renders flagged `unlinked` with a fix pointer (`link_sub_issue` where the backend allows). This is what keeps Jira trees deeper than the Epic → Story/Task → Sub-task ceiling working at all under the new model — those edges cannot be natively linked, so a strict-native child set would silently drop them. A phase-map ref whose `view_issue` returns not-found stays a drift finding. This preserves old invariant 6's spirit (native linkage is best-effort augmentation; structure the tracker cannot carry still counts).

### Fork #4 — flat-epic ordering → **native return order**

For an epic with no phase map (and for unphased children generally), children order = `list_child_issues`' return order as-is. On GitHub the sub-issue list order is operator-reorderable in the UI and the API returns that order; Jira returns rank order — so the tracker itself is the priority signal, consistent with "derive from native linkage". Documented per backend.

## The three-part shape

### 1. Description — evergreen

`## Goal`, `## Scope` (in + out), `## Success criteria` (outcome-based), `## Design spec` (path + branch + commit). Edited only when the initiative's goal or scope genuinely changes — never per child. No `## Status block`, no `## Phases`, no `## Children`. `templates/epic-body.md` is rewritten to exactly this shape.

### 2. Machine-block comment — the non-derivable remainder

One comment carrying the HTML sentinel `<!-- agent-issue-tracker:machine-block -->` (invisible in GitHub's rendered view) and the five optional sections from Fork #2. The comment is **absent entirely** when every section would be empty — a flat root epic with nothing in flight carries zero machine cruft. New file `templates/epic-machine-block.md` specifies the format.

**Trust rule (machine-block selection).** The machine block is the **earliest** marker-carrying comment from a **trusted** author. `read_comments` returns an `author_trust` field mapped per backend: GitHub — trusted iff `authorAssociation` ∈ {OWNER, MEMBER, COLLABORATOR}; Jira — trusted by default (org-internal instances), documented as a trust-model note. Marker comments from untrusted authors are ignored with a one-line WARN naming the comment. Earliest-wins means a legitimately-upserted block, created at file/adopt time, can never be shadowed by a later attacker comment; the author check covers the window before any block exists. The scope probe additionally keeps its show-before-run gate as the last line of defense.

### 3. Derived live at read time

Child set, titles, per-child open/closed status, direct-child counts, rolled-up leaf counts, and next-up are computed by `/resume-initiative` from `list_child_issues` + per-child `view_issue` on every read. They are never written into any body or comment. Closing a child therefore requires **no write anywhere** — the next resume reflects it.

## Contract changes (`backends/_interface.md`)

Two new operations (contract grows 8 → 10):

### `read_comments`

- **Inputs:** `ref`
- **Output:** list of `{id, author, author_trust, body, created}` in chronological order. `author_trust` is a boolean the backend derives (GitHub: `authorAssociation`; Jira: documented default-true).
- GitHub: `gh issue view N --json comments` (fields: `id`, `author`, `authorAssociation`, `body`, `createdAt`). Jira: `getJiraIssue({cloudId, issueIdOrKey, fields: ["comment"]})`.

### `upsert_comment`

- **Inputs:** `ref`, `marker` (literal sentinel string), `body` (full replacement text, marker included)
- **Output:** (void)
- Semantics: find the earliest trusted comment containing `marker`; if found, replace its body wholesale; else create a new comment. **Destructive whole-comment replace** — cross-backend invariant 2 (read-modify-write) extends to comments verbatim.
- GitHub: locate via `read_comments`, then `gh api -X PATCH repos/OWNER/REPO/issues/comments/<id> -f body=…`; create via `gh issue comment`. Jira: `addCommentToJiraIssue`, with `commentId` for the update path.

`list_child_issues` is re-annotated as **load-bearing for resume** (it was adoption/drift-only). The optional-affordances section notes the in-progress fallback signal moved from the Status block to the machine block's `## Current branch`.

## Resume read model (`commands/resume-initiative.md`)

Per epic node: `view_issue` + `read_comments` + `list_child_issues` (three calls; the old model made two plus a body parse). Then:

- **Membership:** Fork #3's union. Flags: native-but-not-in-phase-map → `unphased`; phase-map-only-but-live → `unlinked`; phase-map-ref-not-found → drift finding. Visible drift, never silent-wrong.
- **Ordering / next-up:** phase-map order for phased children (phases in listed order, refs in listed order within a phase), native return order for unphased children and flat epics. Next-up = first **open** leaf in that order, drilling through sub-epics exactly as today. Unphased children sort after phased ones; if the only open children are unphased, next-up is the first of those (flagged).
- **Root detection (Mode 1):** an epic node is a root iff its machine block has no `## Parent epic` section (legacy nodes: body block, as today). Costs one `read_comments` per epic node returned by `list_open_issues` — acceptable at typical open-epic counts (<20), documented like the existing N+1 note.
- **Traversal:** depth cap, cycle guard, mixed-backend skip unchanged on all three descent paths; the parent breadcrumb now reads `## Parent epic` from each hop's machine block (legacy fallback: body block).
- **#56 absorbed:** Modes 2/3 also surface **non-machine** comments — the latest few (display cap ~5) plus a total count — for the named node and the resolved next-up leaf, so decisions/blockers posted as comments are visible on resume.
- **Legacy reader:** a body containing `## Status block` selects the old-shape parse path, exactly today's behaviour (Status block + `## Children` mirror + body `## Parent epic` + body `## Scope probe`). No forced migration; legacy epics resume correctly indefinitely.
- **`--adopt <ref>` (new):** converts a legacy epic in place: (1) `list_child_issues` + mirror diff; natively link live mirror-only children where the backend allows; (2) build the machine block from the body's `## Phases` / mirror phase annotations, carry over `## Decision log`, `## Scope probe`, `## Parent epic`, and the Status block's `Current branch` (when not `none`); (3) rewrite the description to the evergreen shape — Goal and Design spec carried over, Scope/Success criteria folded from the body narrative, any unfoldable remainder preserved under a `## Notes (pre-adoption)` appendix (preserve, don't destroy); (4) drop `## Status block`, `## Phases`, `## Children` from the body. Read-modify-write on both the body and the comment. Adoption is operator-invoked, per node (a sub-epic is adopted by naming it).

## Writers

| Event | Old model | New model |
|---|---|---|
| Epic filed | body with Status block + empty mirror | evergreen body; machine block posted only if phases/parent are known at file time |
| Child filed | `create_issue` + `link_sub_issue` + body mirror append | `create_issue` + `link_sub_issue`; phase-map append via `upsert_comment` only when the epic is phased |
| Work starts (`/work-issue` Step 3; #88's `--start`) | `edit_body`: Status block `Current branch` + `Last updated` | `upsert_comment`: machine block `## Current branch` (legacy parent: old path unchanged) |
| Decision recorded | body `## Decision log` append via `edit_body` | machine block `## Decision log` append via `upsert_comment` |
| **Child closes** | read-modify-write of parent body (counts, Next up, mirror flip, date) | **nothing** — derived on next read |
| Epic goal/scope changes | `edit_body` | `edit_body` (the one remaining description write) |

All comment writes are best-effort: WARN and continue, never block the run, the worktree, or the filing.

## Files touched

| File | Change |
|---|---|
| `backends/_interface.md` | two new op sections; "eight operations" → ten (all references); machine-block comment convention; `list_child_issues` load-bearing note; invariant 2 extended to comments |
| `backends/github.md` | literal `read_comments` / `upsert_comment` calls; `authorAssociation` trust mapping; flat-order note (sub-issue list order) |
| `backends/jira.md` | literal calls (`getJiraIssue fields:["comment"]`; `addCommentToJiraIssue` + `commentId` update); trust note; rank-order note |
| `templates/epic-body.md` | rewritten to the evergreen shape |
| `templates/epic-machine-block.md` | **new** — marker + five-section format |
| `skills/initiative-tracking/SKILL.md` | Filing / Status block / Creating sub-issues / Children mirror / Maintenance sections rewritten around derive-live; "does not depend on native linkage" invariant relaxed; adoption section re-pointed at `--adopt` |
| `commands/resume-initiative.md` | reconcile read model (all modes); union membership; flags; ordering; comment surfacing (#56); legacy reader; `--adopt` |
| `commands/work-issue.md` | Step 3 start-side sync targets the machine block for new-shape parents (legacy: unchanged) |
| `hooks/session-title.sh` | epic-by-branch match + Next-up extraction: read the machine block (comments API) for new-shape epics; body fallback for legacy |
| `tests/test_session_title_hook.py` | fixtures for both shapes |
| `tests/` (drift/fixture suites) | new-shape fixtures: union membership, `unphased` / `unlinked` flags, legacy reader, trust rule |
| `README.md`, `CHANGELOG.md` | epic-shape documentation + evergreen-convention note |

CI: op-parity passes mechanically once both backend modules carry the two new headings; CONTRIBUTING's op enumeration updates alongside; markdownlint / shellcheck surfaces unchanged.

## Failure semantics

- `read_comments` fails on a node → WARN; the node renders **without** phases / probe / branch / parent-breadcrumb (children still derive natively — union degrades to native-only); block-dependent drift checks skipped for that node. Never blocks resume.
- No qualifying machine block → all children render `unphased`; that is correct rendering, not an error.
- Untrusted marker comment → ignored with a WARN naming it.
- `upsert_comment` fails → WARN and continue (start-side sync, phase-map append, decision-log append are all best-effort).
- `list_child_issues` fails → soft-warn, skip that node's derivation, render what the phase map alone provides, flagged.
- Probe semantics (non-zero exit, missing fence, Mode 1 never runs it) unchanged.

## Relationship to #85 / #86 / #87 / #56 / #88

- **#85 (shipped)** — drift reconciliation built the muscle this design promotes: `list_child_issues` per node, mirror-vs-native diff, report-never-repair. The new model keeps the report-only posture for *findings* (`unlinked`, dead refs) while making the tracker the membership source outright; Part 2 (scope probe) and Part 3 (follow-up offers) carry over with the probe relocated to the machine block.
- **#86 (shipped)** — the start-side sync and per-backend in-progress affordances are preserved; only the fallback signal's storage moves (Status block line → machine-block `## Current branch`). The lean-contract precedent from its fork #1 was weighed in Fork #1 here and found inapplicable: comments are uniformly implementable, status transitions were not.
- **#87 (superseded)** — close-side reconcile-on-read is moot by construction: there is no close-side body edit left to automate. Derived state reflects closure on the next read with zero writes. Close #87 as superseded by #100 when this ships.
- **#56 (absorbed)** — resume now reads comments natively (`read_comments`) and surfaces non-machine comments for the resumed node and next-up leaf; the "contract field vs display affordance" question #56 left open is resolved as a contract op.
- **#88 (compatible, untouched)** — `--start`'s in-progress affordance parity work proceeds unchanged; where it writes the fallback signal, it targets the machine block on new-shape parents exactly as `/work-issue` does.

## Out of scope

Per the issue's constraints: `bug-tracking` / `feature-request` / `followup-tracking` skills and their single-issue templates (leaf children keep their body `## Parent epic` block — the asymmetry is deliberate: leaf bodies are agent prompts, not indexes, and are out of scope here); native-linkage mechanics; the nesting model; any per-consumer config knob (evergreen is the new default on both backends). No forced migration of legacy epics.

## Testing

- pytest fixtures for the new-shape parse path: union membership, `unphased` / `unlinked` flags, earliest-trusted-marker selection (incl. untrusted-shadow and post-hoc-attacker cases), flat-epic native ordering, next-up with mixed phased/unphased children.
- Legacy-reader regression fixtures: today's Status-block epics parse byte-for-byte as before.
- `--adopt` round-trip fixture: legacy body in → evergreen body + machine block out; grep-asserts no `## Status block` / `## Children` in the produced description (acceptance #1).
- Session-title hook fixtures for both shapes.
- CI mirror: op-parity grep with 10 ops, markdownlint, shellcheck.
