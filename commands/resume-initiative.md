---
description: Show open epic initiatives and the next-up child issue; optionally start work on the next child.
---

# /resume-initiative [epic-ref] [--start]

Pick up where multi-week initiative work was left off. Invokes the configured backend's `list_open_issues({label: 'epic'})` operation to list open initiatives with their progress, and points at the next-up child issue. Optionally enters the worktree for the next child or creates one if absent. The configured backend is determined by `.claude/issue-tracker.yaml` in the consumer project.

This command is generic — it works for any initiative tracked via the `initiative-tracking` skill, not just the engine/operator split.

Initiatives may be **nested** — a child of an epic can itself be an epic (a "sub-epic") with its own children. This command walks the whole tree: it lists **root** initiatives, recurses through sub-epics, and resolves "next up" down to the next workable **leaf**, reporting the path it drilled (`root ▸ sub-epic ▸ leaf`). Traversal is bounded by a depth cap and a visited-ref cycle guard so it always terminates — see "Tree traversal (shared rules)".

After the worktree is created, `/resume-initiative --start` hands off to `superpowers:brainstorming` inline so the standard agent workflow (brainstorm → plan → execute) starts immediately in the same session. Do NOT stop and tell the operator to open a new window — `EnterWorktree` already switched the session's CWD into the worktree.

Named `/resume-initiative` (not `/resume`) to avoid shadowing Claude Code's built-in `/resume`, which resumes a prior conversation.

## Invocation modes

| Invocation | Behaviour |
|---|---|
| `/resume-initiative` | List all open **root** initiatives + their next-up leaf (rolled up across the tree). Pick one. |
| `/resume-initiative <ref>` | Load epic (or sub-epic) `<ref>`. Show phase progress, the child tree, and the next-up leaf. |
| `/resume-initiative <ref> --start` | Load `<ref>`, resolve next-up down to a leaf, enter that leaf's worktree, and hand off to `superpowers:brainstorming` inline. (Sets the leaf's GitHub Projects board Status to In Progress if `github.project` is configured.) |

`<ref>` may be a root epic OR any sub-epic — the command treats whatever node you name as the subtree root and walks down from there.

## Tree traversal (shared rules)

All three modes walk the initiative tree using these rules.

**Three descent paths.** Traversal follows the tree along three kinds of edge, and the depth-cap, cycle-guard, and mixed-backend rules below apply to **all three** identically — not just to child enumeration:

1. **Child enumeration** — descending a node's `## Children` mirror (Mode 2 step 3).
2. **Next-up drill** — following one node's `- **Next up:**` ref into a sub-epic to read ITS `Next up`, repeating to find a leaf (Mode 1 step 4, Mode 2 step 5, Mode 3 step 1).
3. **Parent breadcrumb** — following `## Parent epic` refs upward to the root (Mode 2 step 2).

Each path is a recursion; each MUST apply the guards on every hop.

- **Node detection.** A child is a **sub-epic** (recurse into it) if it carries the `epic` label — this is authoritative. The `▸ sub-epic` marker on its `## Children` line is a human hint; trust the label. Any other child is a **leaf** (do not recurse).
- **Root detection.** A node is a **root** if its body has no `## Parent epic` block. `list_open_issues({label: 'epic'})` returns every epic node (roots AND sub-epics); filter to roots by absence of `## Parent epic`. (The native `parent?` from `view_issue` is a secondary signal where the backend supplies it — GitHub does not on a plain read; rely on the body block.)
- **Per-node parse.** Each epic node — root or sub-epic — carries its own Status block (the four canonical field labels, matched on the **bold label** and tolerant of the leading list-bullet character `-`/`*`/`+`) and its own `## Children` mirror of its **direct** children only. Parse each node the same way; the full tree is the recursion over per-node mirrors.
- **Depth cap.** Maintain a `depth` counter initialised to `0` at the path's starting node. On **every** hop along **any** of the three descent paths, check `depth < MAX_DEPTH` (`MAX_DEPTH = 10`) BEFORE descending; if `depth >= MAX_DEPTH`, stop that branch, render the deepest reached node with a `…(depth cap reached)` suffix, and do not recurse further. Otherwise increment `depth` and recurse. The three paths each carry their own counter (a deep child subtree does not consume the breadcrumb's budget).
- **Cycle guard.** Keep a `visited` set of refs seen on the current path. On **every** hop along **any** of the three descent paths, check the next ref BEFORE descending: if it is already in `visited`, stop that branch with a one-line warning (`cycle: <ref> already visited`) and do not recurse — treat the ref as terminal (a leaf, for the Next-up drill). This is what stops an `A → next-up B → next-up A` loop or a `## Children`-plus-native-linkage loop from recursing forever. Add each ref to `visited` as you enter it.
- **Rolled-up progress is read-only.** Compute subtree leaf totals (`<closed-leaves>/<total-leaves>`) by walking the tree at read time for display. NEVER write a rolled-up count back into a body — bodies store direct-child counts only (per `initiative-tracking`).
- **Mixed-backend / unparseable nodes.** On **every** hop along **any** of the three descent paths, if the next ref's syntax doesn't match the configured backend, or the node it points at is missing a Status block / can't be fetched, log a one-line soft warning (`skipping <ref> — ref syntax doesn't match the configured backend`, or `…— no machine-readable status`) and skip it: for child enumeration drop that child; for the Next-up drill stop the drill and treat the last good node's pointer as the leaf; for the breadcrumb stop walking and render the root marker as `unknown`. Never crash.

## Drift reconciliation (per node)

An epic's enumerated scope drifts between freeze and execution: children
get filed or natively linked without a mirror update, mirror entries go
dead, and (for enumerate-the-work epics) new in-scope artifacts land
after the batch list was written. Every Mode 2 node parse runs a
reconciliation pass and prints a **drift report** above the child tree;
a fully-consistent node prints **nothing**. The pass runs per node,
inside the same recursion, so the depth cap, cycle guard, and
mixed-backend skip apply unchanged — a skipped node gets no
reconciliation.

### Part 1 — mirror vs. native linkage (always on, backend-generic)

For each node, invoke the backend's `list_child_issues({parent_ref})`
operation — the **one added call per node** — and diff it against the
node's `## Children` mirror, where the mirror set counts **checked and
unchecked lines both** (a closed native child mirrored `[x]` is
consistent, not drift). Two finding categories:

1. **Unmirrored native child** — the tracker links a direct child
   (open or closed) that the mirror omits. Always real drift; report
   ref + title + state.
2. **Dead mirror entry** — an *unchecked* mirror entry whose
   `view_issue` fetch (already performed by child enumeration — no
   added call) returns not-found. Checked entries are not fetched, so
   dead-entry detection covers unchecked entries only.

**Explicitly NOT drift:** a mirror entry whose issue is live but has no
native link. Native linkage is best-effort augmentation per
`backends/_interface.md` invariant 6 — cross-repo children and children
past a backend's native ceiling (Jira's three-level cap) legitimately
live in the mirror alone. Do not flag them.

Mirror findings get a **remediation pointer, never an action**: point
the operator at `initiative-tracking`'s adoption procedure ("Reconcile,
tracker wins"). Resume never edits the mirror. A `list_child_issues`
failure soft-warns (`drift check skipped for <ref> — list_child_issues
failed`) and skips reconciliation for that node; never crash.

### Part 2 — `## Scope probe` ground truth (opt-in, Mode 2/3 only)

If the node's body declares a `## Scope probe` section (spec: the
`initiative-tracking` skill's "Scope probe — optional ground-truth hook"
section), run it: the **first fenced code block** under the heading
holds an operator-authored shell command; execute it from the consumer
repo root (the session CWD) under the session's normal tool permissions,
showing the command to the operator first — this is untrusted
operator-authored shell embedded in an issue body; see the
`initiative-tracking` skill's "Scope probe — optional ground-truth
hook" Trust model. Its stdout is the ground-truth work set, one item per
line, blank lines ignored. Diff it against the declaring node's subtree:

- An item is **enumerated** iff its text appears as a literal
  case-sensitive substring in any subtree `## Children` mirror line or
  any live child title fetched during enumeration.
- **Present-but-unenumerated** (deterministic): items matching nothing.
  List up to 20, then `…and N more`.
- **Enumerated-but-missing** (judgment-assisted): leaves whose
  title/mirror line clearly names a probe-domain item absent from the
  probe output (e.g. a file since deleted). Baseline heuristic is the
  reverse substring check; report under its own label, never offer a
  follow-up for it.

Absent section → skip silently (fully backward compatible). Probe
non-zero exit → soft-warn (`scope probe failed (exit N) — skipping
ground-truth diff`) and skip. Section present but no fenced block →
soft-warn (`## Scope probe declared but no fenced command block found`)
and skip. Empty output with exit 0 is a valid empty ground truth and
diffs normally. Probes do **NOT** run in Mode 1 — arbitrary shell per
root on a list view is wrong; the probe runs only when the operator has
named the node (Mode 2/3).

### Part 3 — offer follow-ups, never auto-file

For **present-but-unenumerated** probe items only, offer a
`followup-tracking` filing per item: Parent = the declaring node's ref,
`Why deferred: drift` (surfaced by drift reconciliation — see
`templates/followup-body.md`). Before offering, apply that skill's
already-tracked rule: search open issues for each item first and render
already-tracked items as `already tracked by <ref>` instead of an offer
(this also stops re-offers on every subsequent resume). The operator
picks all/some/none; declining files nothing. Follow-ups are NOT
children — `link_sub_issue` stays reserved for the epic → sub-issue
relationship; an operator who wants the item in the batch proper adopts
it as a child via `initiative-tracking` instead.

### Report shape

```text
Drift report — #123 engine/operator split
  ⚠ #145 — "migrate FooTests" (open) — in tracker, missing from ## Children mirror
  ⚠ #131 (mirror entry) — no live issue in the tracker
  ⚠ probe: 4 items present but unenumerated:
      Tests/AccountTests.swift
      Tests/BillingTests.swift
      Tests/CheckoutTests.swift
      Tests/InventoryTests.swift
  → mirror findings: reconcile via initiative-tracking's adoption procedure (tracker wins)
  → unenumerated items: file follow-ups? [all / pick / none]
```

Sub-epic findings carry the sub-epic's ref prefix. No findings and no
probe → print nothing.

## What you should do

### Mode 1 — no argument: list open root initiatives

1. Invoke the configured backend's `list_open_issues({label: 'epic'})` operation; see `backends/<backend>.md` for the literal invocation. The returned list contains `[{ref, title, status}, ...]` entries — **every** epic node, roots and sub-epics alike. For each, call `view_issue({ref})` to fetch the full body. (The N+1 cost is acceptable — open-epic count is typically <20.)

2. **Filter to roots.** Drop any node whose body contains a `## Parent epic` block — those are sub-epics and will appear under their root, not as their own top-level entry (see "Tree traversal"). The survivors are the root initiatives.

3. For each root, parse its body for the **Status block** (a markdown section the `initiative-tracking` skill maintains). Match each line on its canonical **bold field label**, tolerant of the leading list-bullet character (`-`/`*`/`+`) — the Atlassian Remote MCP rewrites a leading `-` bullet to `*` on the ADF round-trip, so do not key the match on a literal `- ` (see the `initiative-tracking` skill's "Status block — exact field spec" table):
   - `- **Phase:**` — e.g. `Phase 1a · 2/4 sub-issues closed` (this is the root's **direct-child** count)
   - `- **Next up:**` — `<ref> — <title>` or literal `none`, where `<ref>` is one of `#<N>` (same repo), `owner/repo#<N>` (cross-repo GitHub), or `PROJ-123` (Jira)
   - `- **Current branch:**` — branch name or literal `none`
   - `- **Last updated:**` — `YYYY-MM-DD`

4. **Resolve next-up to a leaf and roll up progress.** If a root's `Next up` ref is itself a sub-epic (carries `epic`), drill into it per "Tree traversal" until you reach a leaf, and remember the path. Separately, walk the subtree to compute the rolled-up `<closed-leaves>/<total-leaves>` for display. Honour all three "Tree traversal" guards (depth cap, cycle guard, mixed-backend skip) on every hop of both the Next-up drill and the subtree walk.

   During the same walk, run the drift reconciliation **Part 1** diff per
   node (see "Drift reconciliation (per node)"; probes never run in
   Mode 1) and count findings across the subtree.

5. Render a compact list to the operator — show the root's direct-child phase count, the rolled-up leaf count, and the next-up **leaf** (with its drill path when nested). Append `· ⚠ drift: <N>` to a root's line when its subtree has N > 0 mirror-vs-native findings; N = 0 renders nothing:
   ```
   #123  engine/operator split      Phase 1a · 2/4 direct · 6/14 leaves   Next: #126 reserve-ledger schema · ⚠ drift: 2
   PROJ-150  observability rollout  Phase 0  · 1/3 direct · 1/9 leaves    Next: PROJ-150 ▸ PROJ-161 ▸ PROJ-164 metrics emitter
   ```

6. Ask the operator which initiative to resume. On their reply, recurse into Mode 2 with the chosen `<ref>`.

### Mode 2 — `<ref>`: load and display one node + its subtree

1. Invoke `view_issue({ref})` where `<ref>` may be `#N` (GitHub), `owner/repo#N` (cross-repo GitHub), or `PROJ-123` (Jira). See `backends/<backend>.md` for the literal call signature. The returned `{ref, title, body, labels[], status, parent?}` carries the body needed for Status-block parsing. Seed the `visited` set with this ref.

2. Show the operator:
   - The node's title + design-spec link (read from the body's `## Design spec` section — the first non-blank line under that heading is the spec path; the `initiative-tracking` skill's "Epic body template" pins the convention)
   - If the body has a `## Parent epic` block, this node is a **sub-epic** — show the breadcrumb up to the root (follow `## Parent epic` refs upward — the **parent-breadcrumb** descent path, so apply the depth cap, cycle guard, and mixed-backend skip on each hop per "Tree traversal"; on a cycle or unparseable parent ref, stop and render the root marker as `unknown`) so the operator knows where in the tree they are
   - Phase breakdown with status (from the body's `## Phases` section)
   - Current branch / worktree (from the Status block's `- **Current branch:**` line)
   - Next-up — resolved down to a **leaf** (see step 5)
   - If the current session title does not already name this node's ref, a
     paste-ready rename line the operator can apply immediately (the
     SessionStart hook catches up on next resume): `` /rename <ref> <slug> ``

3. **Enumerate the child subtree.** The canonical source at each node is its `## Children` task-list mirror. For each unchecked `- [ ] <ref> — <title>` line, parse the ref:

   **Three ref shapes:**
   - `#N` (bare) — same repo as the epic; use the configured `github.repo` on GitHub
   - `owner/repo#N` — explicit cross-repo GitHub ref; use that `owner/repo`, NOT the configured one
   - `PROJ-123` — Jira issue key (project-scoped)

   For each child ref, call `view_issue({ref})` for its title + status + labels. **If the child carries the `epic` label it is a sub-epic** — add it to `visited` and recurse into step 3 on its own `## Children` mirror, honouring the depth cap and cycle guard ("Tree traversal"). Otherwise it is a leaf. Build an indented tree, annotating each epic node with its direct-child count and a rolled-up leaf count:
   ```
   #123 engine/operator split            2/4 direct · 6/14 leaves
   ├─ #126 reserve-ledger schema         (leaf, open)
   ├─ #130 worker/queue redesign ▸ sub-epic   1/3 direct · 3/7 leaves
   │  ├─ #131 extract retry-policy table (leaf, open)  ← next-up leaf
   │  └─ #134 dead-letter handling       (leaf, open)
   └─ #140 docs pass                     (leaf, open)
   ```
   **Mixed-backend handling:** if a `PROJ-123`-shaped ref appears under a `github`-configured repo (or vice versa), log a one-line soft warning ("skipping child `<ref>` — ref syntax doesn't match the configured backend") and continue. Do NOT crash. Native sub-issue linkage MAY be queried as optional display augmentation, but the task-list mirror is the canonical cross-backend index per `skills/initiative-tracking/SKILL.md`.

4. **Run drift reconciliation and print the report.** Per "Drift
   reconciliation (per node)": Part 1 (mirror vs. `list_child_issues`)
   for every node visited in step 3's recursion, Part 2 (the
   `## Scope probe`, when declared) for the named node and any sub-epic
   declaring its own, then Part 3's follow-up offer for
   present-but-unenumerated items. Print the drift report **above the
   child tree**; a fully-consistent subtree with no probe prints
   nothing.

5. **Resolve `Next up` to a leaf.** Read this node's `- **Next up:**` line. If it names a sub-epic, descend into that sub-epic's Status block and read ITS `Next up`, repeating until the ref is a leaf (or `none`). This is the **Next-up-drill** descent path — before each descent apply the guards from "Tree traversal" on the next ref: cycle guard (if the ref is already in `visited`, stop the drill and treat the current pointer as terminal — this defeats an `A → next-up B → next-up A` loop), depth cap, and mixed-backend skip (on a mismatched/unparseable Next-up ref, stop the drill). If a sub-epic's own `Next up` is `none` while it still has open leaves elsewhere, do not start the sub-epic — fall back to offering the operator a specific open leaf from its subtree. Record the drill path (`#123 ▸ #130 ▸ #131`) and surface the leaf + path to the operator.

6. Ask the operator: "Start the next-up leaf, pick a specific leaf, drill into a sub-epic, or stop?" Wait for their reply.
   - **Start next-up / a specific leaf** → recurse into Mode 3 with that leaf's ref (creates the worktree AND starts the brainstorm inline; do NOT stop after the worktree is created).
   - **Drill into a sub-epic** → recurse into Mode 2 with the sub-epic's ref (treat it as the subtree root).

### Mode 3 — `<ref> --start`: enter the worktree for the next leaf

1. Run Mode 2 to resolve the next-up **leaf** — drilling through any intermediate sub-epics per "Tree traversal" (step 5 of Mode 2). The target MUST be a leaf (a non-`epic`-labelled child); a sub-epic is never directly startable. If the resolved `Next up` is the literal `none`, the subtree has no open leaves, or no leaf can be located, STOP — report `no next-up leaf to start; <ref> has no open leaves` and exit. Do NOT attempt worktree creation from nothing. Report the drill path (`<ref> ▸ … ▸ <leaf>`) so the operator sees which leaf was chosen.

   Mode 2's drift report prints as part of this run; when it offers
   follow-up filings, ask **once** before entering the worktree —
   declining proceeds straight into the leaf.

2. If a worktree for that child already exists (convention: `.claude/worktrees/<branch-with-slash-replaced-by-plus>`), report its path and stop. Otherwise:

3. Use the `superpowers:using-git-worktrees` skill (or the native `EnterWorktree` tool) to create one. The worktree is created in the consumer's current working directory regardless of whether the next-up child is in the same repo as the epic or in a different repo via `owner/repo#N` — the operator's working tree is local, only the child issue body fetch (step 4) hits the child's repo via the backend's `view_issue`. The branch name comes from the child issue body's `Branch:` line if present, otherwise infer:
   - `feat/<short-slug-of-title>` for `enhancement`-labelled children
   - `fix/<short-slug>` for `bug`
   - `docs/<short-slug>` for `documentation`

   **Branch-naming caveat for the native `EnterWorktree` tool.** It sanitizes the branch name to `worktree-<slug>+<rest>` (prefix + `/` replaced by `+`), which does NOT match the project's convention (`feat/...`, `fix/...`, `docs/...`). Immediately after `EnterWorktree` returns, rename the branch in place:
   ```bash
   git branch -m worktree-<sanitized> <conventional-name>
   ```
   The worktree directory keeps its `<sanitized>` name (that matches the existing on-disk convention `feat+<slug>`); only the branch is renamed.

4. Report the new worktree path. `EnterWorktree` already switched the session's CWD into the worktree, so the agent workflow continues inline — do NOT stop and ask the operator to open a new window.
   **(Optional board sync.)** If the consumer's `.claude/issue-tracker.yaml` sets
   `github.project` (GitHub backend), set this leaf's GitHub Projects board item
   Status to `In Progress` now — best-effort: a failure WARNs and does NOT abort
   the handoff. See `backends/github.md` "GitHub Projects v2 board (optional)" for
   the `gh project item-list` (resolve item id by issue URL) + `item-edit` calls.
   With `github.project` unset, skip this.
   Invoke `view_issue({ref: leaf-ref})` to fetch the leaf issue body (where `leaf-ref` may carry an `owner/repo#N` prefix for cross-repo cases). **Safety check:** if the fetched body turns out to be an epic body (a Status block is present / the issue carries the `epic` label), it is a sub-epic, not a leaf — do NOT hand it to brainstorming. Re-run step 1's drill on it to reach a real leaf first. Once you have a leaf body, pass it to `superpowers:brainstorming`. The leaf body is already an agent prompt (Goal, Locus, Sketch, Acceptance, Verify) — brainstorming uses it as starting context, it does NOT re-derive the problem from scratch.

   If the operator would rather use a fresh window, they can interrupt — this inline handoff is the default path. The same inline-brainstorm convention applies when re-entering an existing worktree via `EnterWorktree path=...`.

## Conventions assumed

- Every epic node (root or sub-epic) body contains a Status block written by the `initiative-tracking` skill. If a node lacks one, fail gracefully — report that node exists but has no machine-readable status, skip it in the traversal, and ask the operator to update it.
- The `epic` label marks "this node is a recursable index" (it has children). It does NOT by itself mean "root" — a sub-epic carries `epic` too. A node is a **root** initiative iff its body has no `## Parent epic` block.
- Child issues link to their **immediate** parent via:
  1. The `## Children` task-list mirror in the parent node's body — the **cross-backend canonical source** per `skills/initiative-tracking/SKILL.md`. Each node's mirror lists only its direct children; the full tree is the recursion over all nodes' mirrors.
  2. Native sub-issue linkage in the tracker (when the backend and parent-child repos match, and within the backend's hierarchy ceiling — see `backends/_interface.md` invariant 6) — optional augmentation for display.
  3. A `## Parent epic` block in the child body (per `templates/sub-issue-body.md`) — names the immediate parent, which may be a sub-epic.

## Failure modes

- Backend authentication or reachability failure → the configured backend reports a reachability failure. Run `/tracker-doctor` to diagnose the setup; see `backends/<backend>.md` setup section and re-invoke.
- `view_issue` returns not-found for the supplied ref → check the ref syntax matches the configured backend (`#42` vs `PROJ-123` vs `owner/repo#42`).
- No open epics → tell the operator. Do not crash.
- The chosen epic body is missing required fields → report which fields are missing; suggest the operator runs the `initiative-tracking` skill to rewrite it.
- `--start` invoked but the resolved `Next up` leaf is `none` or the subtree has no open leaves → report "no next-up leaf to start" and exit; do not create a worktree from nothing.
- Child ref syntax mismatch (e.g. `PROJ-123` in a GitHub-configured repo) → log a soft warning and skip that child; continue with the remaining children. Do NOT crash.
- Cross-repo `owner/repo#N` child ref → extract the `owner/repo` prefix and dispatch `view_issue({ref: owner/repo#N})` through the configured backend; the backend module documents how it handles cross-repo refs.
- Traversal exceeds `MAX_DEPTH` (10) → render the deepest reached node, append `…(depth cap reached)`, and stop descending that branch. Do NOT recurse unboundedly.
- Cycle in the tree (a ref reappears in `visited`) → skip the repeated ref with a one-line warning (`cycle: <ref> already visited`) and continue. A `## Children` mirror plus native linkage can form a loop; the visited-set guard prevents infinite recursion.
- `Next up` names a sub-epic whose own `Next up` is `none` (sub-epic has open structure but no startable leaf on that path) → report it and fall back to offering the operator a specific leaf from the subtree, rather than starting the sub-epic itself.
- `list_child_issues` fails for a node during drift reconciliation → soft-warn (`drift check skipped for <ref>`) and skip that node's diff; the resume itself continues.
- `## Scope probe` command exits non-zero, or the section has no fenced code block → soft-warn and skip the ground-truth diff; never crash, never block the resume.
- Drift findings but the operator declines all follow-up offers → file nothing; the report was the deliverable. Resume never edits the `## Children` mirror (remediation is `initiative-tracking`'s adoption procedure).
