# Write `/tracker-doctor` Command — Design

**Date:** 2026-05-27
**Tracker:** [`maxdimitrov/agent-issue-tracker#23`](https://github.com/maxdimitrov/agent-issue-tracker/issues/23)
**Parent epic:** [`maxdimitrov/trading-bot#153`](https://github.com/maxdimitrov/trading-bot/issues/153)
**Parent design spec:** [`docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md) on `maxdimitrov/trading-bot` main — sections §5.6 (slash commands list), §7.2 (the four-step validator flow), §8.3 (`/tracker-doctor` smoke is a Phase 4 release gate). The seven-operation contract and the cross-backend invariant #5 that names `/tracker-doctor` as the smoke test are in [`backends/_interface.md`](../../backends/_interface.md) on this repo.

## 1. Problem

`/tracker-init` writes a `.claude/issue-tracker.yaml`. The next failure mode is not "the YAML is malformed" — `/tracker-init` writes well-formed YAML by construction. It is "the YAML is well-formed but the actual tracker doesn't have the labels / issue types / project the YAML names." Without a validator, the operator discovers a mis-configured tracker only when their first `create_issue` returns 404 / 401 / 422 from `gh` or the Atlassian MCP — at which point they have to guess whether the failure is auth (wrong), the repo (wrong), a missing label (vocabulary), a missing project key (Jira), an `issue_types` mapping (Jira), or the connector itself (not enabled). That post-mortem debugging is the friction the plugin is supposed to remove.

The seven-operation backend contract pins `/tracker-doctor` as the smoke test (cross-backend invariant #5 in [`backends/_interface.md`](../../backends/_interface.md)). Every backend MUST work end-to-end against `/tracker-doctor` — so this command is the contract enforcer, not a nice-to-have diagnostic. Phase 4 release gating (parent spec §8.3) names it explicitly.

## 2. Goal

Ship `commands/tracker-doctor.md` — a markdown-only read-only slash command that runs three check phases against `.claude/issue-tracker.yaml` and the configured backend:

1. **Schema validation** — file present, parses, required fields per backend, enum constraints.
2. **Backend reachability** — auth + repo/project + a `view_issue` round-trip (the canonical reachability probe per cross-backend invariant #5).
3. **Vocabulary sanity** — labels / issue types / components named in the YAML exist on the actual tracker.

Each check reports `PASS` / `WARN` / `FAIL` with a literal next-step command the operator can paste. The command always exits 0 (informational discipline; mirrors `/audit-skills` + `/audit-pii`). It does NOT modify the YAML or the tracker — read-only.

When `/tracker-doctor` is green, `create_issue` / `view_issue` / `/resume-initiative` will work; that is the post-condition the operator can rely on. When it is not green, every reported finding carries the literal command to fix it.

## 3. Non-goals (explicit)

- **Auto-creating missing labels / issue types / components.** The validator prints `gh label create` / `getJiraProjectMetadata` next-steps; the operator runs them. Single-responsibility — the validator validates.
- **Editing `.claude/issue-tracker.yaml` to fix detected problems.** If a field is wrong, the operator hand-edits or re-runs `/tracker-init --force`. The validator is read-only.
- **End-to-end create-issue test.** Creating a real issue in the tracker as part of a smoke test is wrong shape — it leaves a real artifact every time the operator runs the validator. The reachability probe is read-only (`view_issue`).
- **Cross-backend smoke.** The validator runs the backend the YAML says, not both. A GitHub config is not validated against the Atlassian MCP, and vice versa.
- **Validating that issues already filed via the plugin are well-shaped.** That is the skills' job (the body templates already enforce shape). The validator checks the tracker config, not historical artifacts.
- **Network retries / exponential backoff.** The probes are one-shot. A network failure is a `FAIL` with the literal retry command — operator's problem, not the validator's.
- **A `--fix` flag.** Out of scope. Possibly a future enhancement; tracked as a follow-up if it ever surfaces real demand. Today the validator is purely diagnostic.

## 4. Architecture decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| File shape | Markdown + YAML frontmatter | Mirrors `commands/resume-initiative.md` and `commands/tracker-init.md`. Slash commands are markdown only; the agent EXECUTES the prose. |
| Exit code discipline | Always 0 | Informational, never gating. Same discipline as `/audit-skills` / `/audit-pii`. The operator decides whether `WARN` matters; the tooling never blocks. |
| Phase ordering | Schema → Reachability → Vocabulary | Each phase depends on the prior. A schema `FAIL` short-circuits the rest (reachability probes against a broken config compound noise; vocabulary probes against an unreachable backend duplicate the reachability `FAIL`). |
| Reachability probe | `view_issue` per cross-backend invariant #5 | The contract pins this. `list_open_issues` would only prove auth; `view_issue` proves auth + ref-resolution + read-path in one call. |
| Probe-ref default | `#1` (GitHub) / `<jira.project>-1` (Jira) | Conventional first-issue ref. The `--smoke-issue <ref>` flag overrides for projects whose `-1` issue doesn't exist or is restricted. |
| 404 on probe ref | `PASS-WITH-NOTE`, not `FAIL` | A fresh repo / project trips this — the dispatch path is proven (auth + ref-resolution worked); the issue just doesn't exist yet. Calling that `FAIL` would mean every greenfield consumer fails their first run; wrong UX. |
| Vocabulary checks | `WARN`-only | The plugin works without these — but `create_issue` will fail noisily if a referenced label / issue type is missing. WARN is the right pressure level. |
| Output style | Mirror `/audit-skills` | Phase header → indented `[PASS] / [WARN] / [FAIL] <check>` lines → fenced next-step block for non-PASS findings → summary line. |
| `--smoke-issue` flag | Documented for both backends | Overrides the default probe ref. Jira's `<PROJECT>-1` may genuinely not exist (project started from a higher seed); the operator supplies a known-good ref. |
| Markdown-only invariant | No embedded shell scripts beyond what `backends/<backend>.md` already documents as probe commands | The probes (`gh auth status`, `gh repo view`, `getAccessibleAtlassianResources`, etc.) are named in prose; the agent executes them at runtime. |
| Read-only invariant | No `create_issue`, no `edit_body`, no `add_label`, no `close_issue` | Cross-cuts the whole command. Documented in the Failure modes section as a behavioural guarantee. |

## 5. Flow

Three phases plus a final summary. Each phase's checks are tagged `[PASS] / [WARN] / [FAIL]`. Phase 1 `FAIL` short-circuits the rest (the YAML is broken; reachability probes would just compound noise).

### Phase 1 — Schema validation

Read `.claude/issue-tracker.yaml` from the consumer's CWD. Apply these checks in order; each is its own line in the output:

| Check | PASS condition | FAIL output |
|---|---|---|
| File exists | the file is present at `.claude/issue-tracker.yaml` | "no config found; run `/tracker-init`" |
| YAML parses | the file loads as a valid YAML document (the agent uses its own parser; the prose names YAML parsing as the gate) | "YAML parse error: `<line>:<col>: <message>`" |
| `schema_version: 1` | top-level key present with value `1` | "missing or wrong schema_version (only `1` is supported in v1)" |
| `backend:` present | top-level key present with value `github` or `jira` | "missing or unrecognized backend (must be `github` or `jira`)" |
| Backend-conditional required block | if `backend: github`, the `github:` block exists with `github.repo` set; if `backend: jira`, the `jira:` block exists with `jira.site`, `jira.cloud_id`, `jira.project`, `jira.issue_types` all set | "missing required `<backend>.<field>` for backend `<backend>`" |
| `types.*` only contains known keys | each key under `types:` (if present) is one of `bug`, `feature`, `followup`, `epic`, `sub` | "unknown type key under `types:`: `<list>`" |
| Jira-only: `jira.issue_types` covers all five plugin types | mapping has keys `bug`, `feature`, `epic`, `sub`, `followup` | "missing issue_types mapping for: `<list>`" |

WARN-only (not FAIL):
- `areas:` is empty or missing (optional — but warn so the operator knows skill prose falls back to free-form).
- `subsystems:` is empty or missing (same — optional but worth surfacing).
- Jira-only: `parent_link_style: epic_link` but `epic_link_field` not set (defaults to `customfield_10014` if absent — warn but use the default).

If any check `FAIL`s in Phase 1, **stop here**. Do NOT run Phase 2 or Phase 3. The config is structurally broken; reachability probes against it would just compound the noise. The summary line still prints with the Phase 1 counts.

### Phase 2 — Backend reachability

Branch on `backend:` value from the schema. Phase 2 always finishes with `view_issue` (per cross-backend invariant #5) as the final reachability proof — different backends have different setup-prerequisite checks before that.

**2a. GitHub branch.** Three sequential probes per [`backends/github.md`](../../backends/github.md) "Setup verification" section:

1. `gh auth status` — `PASS` if exits 0; `FAIL` with "run `gh auth login` and retry" otherwise.
2. `gh repo view <github.repo>` — `PASS` if exits 0; `FAIL` with the literal `gh` error (typically "Could not resolve to a Repository") + suggestion to fix `github.repo` in the YAML.
3. **Canonical reachability:** invoke `view_issue({ref: "#<smoke-ref-or-1>"})` against the configured backend (which dispatches to `gh issue view <N> --repo <github.repo> --json body,labels,state,title`).
   - `PASS` if the call returns a structured response (issue exists).
   - `PASS-WITH-NOTE` if the call returns 404 — the repo is reachable, but the issue doesn't exist (greenfield repo). The dispatch path is proven.
   - `FAIL` only on 401 / 403 (auth wrong despite Step 1 passing — token scope mismatch) or connection error.

**2b. Jira branch.** Three sequential probes per [`backends/jira.md`](../../backends/jira.md) setup section (the sibling Phase 3 sub-issue — this command's prose can be written in parallel since §5.5 of the parent design spec pins the conceptual probe shape):

1. **Atlassian MCP availability** — confirm the agent's tool surface includes the Atlassian Remote MCP family (`createJiraIssue`, `getJiraIssue`, `searchJiraIssuesUsingJql`, `getAccessibleAtlassianResources`). `FAIL` with "enable the Atlassian connector at claude.ai → Settings → Connectors → Atlassian" otherwise. The agent uses `ToolSearch` against keywords like `jira atlassian` if uncertain.
2. **`cloud_id` round-trip** — invoke `getAccessibleAtlassianResources`; confirm the configured `jira.cloud_id` appears in the returned site list and matches the configured `jira.site`. `FAIL` with the list of accessible cloud_ids otherwise.
3. **Canonical reachability:** invoke `view_issue({ref: "<smoke-ref-or-PROJECT-1>"})` where `<smoke-ref>` is the value of `--smoke-issue` if passed, otherwise the default `<jira.project>-1` (e.g. `TRADE-1`). The configured backend dispatches to `getJiraIssue(cloudId, issueKey)`.
   - `PASS` if the call returns a structured response.
   - `PASS-WITH-NOTE` if the call returns 404 — the project is reachable, but the probe issue doesn't exist (project may have started from a higher seed, or `<PROJECT>-1` is restricted). The dispatch path is proven.
   - `FAIL` only on 401 / 403 (auth wrong, or `cloud_id` doesn't match `site`) or connection error.

If any check `FAIL`s in Phase 2, **continue to Phase 3** — vocabulary sanity is independent of reachability (the labels-list probe in 3a hits `gh label list` which has its own auth path). But document this so the operator knows: Phase 3 results may be empty or 401 if reachability is broken. Phase 2 `FAIL` is the actionable finding; Phase 3 is informational.

### Phase 3 — Vocabulary sanity

Branch on `backend:` value. Each check is `WARN`-level (the plugin works without these — but the operator's first `create_issue` will fail noisily if they're missing).

**3a. GitHub branch.** For each value in the consumer's `areas:` list (skip if `areas:` is empty or missing — already `WARN`ed in Phase 1), check whether the label exists on the configured repo:

```bash
gh label list --repo "<github.repo>" --search "<area>" --json name --jq '.[].name'
```

If the label is missing, `WARN` with the literal next-step command in a fenced block the operator can paste:

```bash
gh label create "<area>" --repo "<github.repo>" --description "Area: <area>" --color BFD4F2
```

Print one such command per missing area.

**3b. Jira branch.** Two checks:

1. For each value in `jira.issue_types.*` (the five mapped issue type names — `Bug`, `Story`, etc.), check whether the issue type exists in the configured Jira project. Conventional MCP call: `getJiraProjectMetadata({cloudId, projectKey})` (or the equivalent `issueTypes` endpoint exposed by the MCP; the agent uses `ToolSearch` against `jira project metadata` if the name has shifted in the current MCP version). `WARN` with "missing issue type `<name>` in project `<projectKey>`; check your Jira project settings or remap in `.claude/issue-tracker.yaml`" for any missing type.
2. If `jira.area_field: components`, list the project's configured Components (via the same metadata call) and surface them as a `WARN-info` line so the operator knows what areas they can use. No `FAIL` — `area_field` defaults to free-form when components don't match.

### Phase 4 — Summary

Always exit 0. The final line aggregates counts:

```
Summary: <F> FAIL · <W> WARN · <P> PASS
```

`<F>`, `<W>`, `<P>` are the integer counts of `FAIL` / `WARN` / `PASS` lines across Phases 1-3. `PASS-WITH-NOTE` counts as `PASS` for the summary but renders inline as `[PASS] ... (note: <reason>)`.

## 6. Output format (full example)

The command's prose includes one verbatim example block so reviewers can diff against the intended UX. The agent renders this shape at runtime:

```
=== /tracker-doctor — agent-issue-tracker schema v1 ===

Phase 1 — schema validation
  [PASS] file exists
  [PASS] YAML parses
  [PASS] schema_version: 1
  [PASS] backend: github
  [PASS] github.repo: maxdimitrov/example-project
  [WARN] areas: unset (skills will use free-form area)

Phase 2 — backend reachability
  [PASS] gh auth status
  [PASS] gh repo view maxdimitrov/example-project
  [PASS] view_issue(#1) — issue exists

Phase 3 — vocabulary sanity
  (no areas configured; skipping)

Summary: 0 FAIL · 1 WARN · 8 PASS
```

For `FAIL` / `WARN` lines, render the literal next-step command in a fenced block under the line. Example for a missing-label `WARN` in Phase 3a:

```
Phase 3 — vocabulary sanity
  [WARN] area label `dashboard` missing on maxdimitrov/example-project
```
```bash
gh label create "dashboard" --repo "maxdimitrov/example-project" --description "Area: dashboard" --color BFD4F2
```

## 7. Failure modes (consolidated)

Explicit in the command's "Failure modes" section at the bottom of the file:

1. **Config missing.** Report "no config found; run `/tracker-init`" as a Phase 1 `FAIL`. Exit 0.
2. **Phase 1 FAIL (any).** Do not run Phase 2 or 3 — the YAML is structurally broken; further probes would compound noise. Summary line still prints with Phase 1 counts.
3. **Backend probe timeout / network error.** Render as `FAIL` with the literal command the operator should retry by hand. Exit 0 (informational).
4. **Atlassian MCP not in tool surface (Jira).** Phase 2 step 1 = `FAIL` with the connector setup link. Phases 2 step 2/3 + Phase 3 skip with a note ("Atlassian MCP unavailable; skipping").
5. **Operator interrupts mid-validation.** No side effects — the command is read-only. The harness's interrupt handling closes the session; no partial state on disk or in the tracker.

## 8. Invariants

- **Always exit 0.** Informational discipline. Mirrors `/audit-skills` / `/audit-pii`. The operator decides whether `WARN` matters; the validator never gates.
- **Read-only.** No `create_issue`, no `edit_body`, no `add_label`, no `close_issue`. No modifications to `.claude/issue-tracker.yaml`. Cross-cuts every check.
- **Canonical reachability probe is `view_issue`.** Cross-backend invariant #5 from [`backends/_interface.md`](../../backends/_interface.md). Every backend's Phase 2 final step dispatches through that contract operation, not the backend's raw CLI / MCP.
- **PASS / WARN / FAIL is fixed.** `FAIL` = dispatch path is broken; `WARN` = dispatch works but vocabulary is incomplete; `PASS` = green; `PASS-WITH-NOTE` = dispatch works but the probe artifact is absent (404).
- **Markdown-only file.** Slash commands are markdown. No embedded shell scripts beyond what `backends/<backend>.md` already documents as probe commands.
- **Phase 1 short-circuits Phases 2-3.** A broken schema makes downstream probes meaningless.

## 9. Cross-references

- [`commands/resume-initiative.md`](../../commands/resume-initiative.md) — the markdown shape precedent (frontmatter, "What you should do", Failure modes block, Conventions assumed).
- [`commands/tracker-init.md`](../../commands/tracker-init.md) — the sibling Phase 3 command whose written YAML is the file `/tracker-doctor` validates. Schema invariants must agree across both commands.
- [`backends/_interface.md`](../../backends/_interface.md) — the seven-operation contract. Cross-backend invariant #5 names `/tracker-doctor` as THE smoke test.
- [`backends/github.md`](../../backends/github.md) — "Setup verification" section documents the GitHub probes verbatim.
- `backends/jira.md` — sibling Phase 3 sub-issue (`#24`). When it lands, the Jira branch's probe wording aligns to its setup section. Until then, the parent design spec §5.5 pins the conceptual probes (Atlassian MCP availability, `getAccessibleAtlassianResources`, `getJiraIssue`) clearly enough for this command to be written in parallel.
- [`examples/issue-tracker.yaml.example`](../../examples/issue-tracker.yaml.example) — the schema v1 the validator checks against.

## 10. Acceptance

The PR closes when **all** are true:

- [ ] `commands/tracker-doctor.md` exists; renders cleanly; carries YAML frontmatter `description:`.
- [ ] No literal string `maxdimitrov/trading-bot` anywhere in the new file.
- [ ] Three phases documented in order (schema validation → backend reachability → vocabulary sanity), plus a Summary section.
- [ ] Cross-backend invariant #5 cited explicitly: the canonical reachability probe is `view_issue` from the contract, dispatched through the configured backend.
- [ ] Both backend branches' reachability probes documented (GitHub: `gh auth status` → `gh repo view` → `view_issue(#<N>)`; Jira: MCP availability → `cloud_id` round-trip → `view_issue(<PROJECT>-<N>)`).
- [ ] `--smoke-issue <ref>` flag documented (for both backends — the default probe ref can be overridden).
- [ ] `PASS-WITH-NOTE` semantics documented for the 404 case (repo / project reachable but the probe ref doesn't exist).
- [ ] Output format example block included (PASS / WARN / FAIL lines under each phase + summary line at the end).
- [ ] Always-exit-0 invariant stated explicitly.
- [ ] Read-only invariant stated explicitly.
- [ ] Failure-modes section covers the five scenarios from §7.
- [ ] CHANGELOG.md `[Unreleased] → Added` carries the Phase 3 entry in the same `Phase X (#Y): <name> — ...` format as the Phase 2 and earlier Phase 3 entries.

## 11. Verification

The verification grep block from issue #23 binds the acceptance. Re-stated here for the spec record:

```bash
test -f commands/tracker-doctor.md

# No trading-bot string leakage
grep -F "maxdimitrov/trading-bot" commands/tracker-doctor.md \
  && echo "LEAK" || echo "clean"

# Three phases named in prose
for phase in "schema validation" "backend reachability" "vocabulary sanity"; do
  grep -qiE "$phase" commands/tracker-doctor.md \
    || { echo "MISSING phase: $phase"; exit 1; }
done

# Cross-backend invariant #5 cited (view_issue as the canonical reachability probe)
grep -qE "view_issue" commands/tracker-doctor.md \
  || { echo "MISSING view_issue as canonical reachability probe"; exit 1; }
grep -qiE "invariant.*5|smoke test" commands/tracker-doctor.md \
  || { echo "MISSING cross-backend invariant #5 citation"; exit 1; }

# Both backend branches present
grep -qE "gh auth status" commands/tracker-doctor.md \
  || { echo "MISSING GitHub auth probe"; exit 1; }
grep -qE "gh repo view" commands/tracker-doctor.md \
  || { echo "MISSING GitHub repo probe"; exit 1; }
grep -qiE "atlassian.*(remote.*)?mcp|atlassian.*connector" commands/tracker-doctor.md \
  || { echo "MISSING Atlassian MCP availability probe"; exit 1; }
grep -qE "getJiraIssue|getAccessibleAtlassianResources" commands/tracker-doctor.md \
  || { echo "MISSING Jira MCP probe tool names"; exit 1; }

# --smoke-issue flag documented
grep -qE "\-\-smoke-issue" commands/tracker-doctor.md \
  || { echo "MISSING --smoke-issue flag"; exit 1; }

# PASS / WARN / FAIL classification used
for cls in "PASS" "WARN" "FAIL"; do
  grep -q "$cls" commands/tracker-doctor.md \
    || { echo "MISSING classification: $cls"; exit 1; }
done

# Always-exit-0 invariant stated
grep -qiE "exit 0|always exit 0|exits 0" commands/tracker-doctor.md \
  || { echo "MISSING always-exit-0 invariant"; exit 1; }

# Read-only invariant stated
grep -qiE "read-only" commands/tracker-doctor.md \
  || { echo "MISSING read-only invariant"; exit 1; }
```

## 12. Notes

- This is a WRITE-FROM-SCRATCH command, not a port — there is no trading-bot equivalent. Spec compliance + cold-read review are the gates, not byte-level audit (lesson from PR #19's en-dash regression doesn't apply here, but the cold-read discipline established in PRs #21 / #25 does).
- The three Phase 3 siblings (`/tracker-init` — done via PR #25, this one, `backends/jira.md` — open as `#24`) are unblocked-in-parallel; pick any order. This spec is written without dependency on `backends/jira.md`'s yet-unlanded prose — §5.5 of the parent design spec is enough.
- The canonical reachability probe is `view_issue` per cross-backend invariant #5. Resist the temptation to use `list_open_issues` instead: `view_issue` proves the read-path AND ref-resolution AND auth in one call; `list_open_issues` only proves the auth path. The contract pins this for a reason.
- The Jira branch's `cloud_id` round-trip catches the most-likely mis-config (operator pasted the wrong cloud_id into `/tracker-init` from outside MCP discovery). It is not optional.
- The "PASS-WITH-NOTE for 404 on the probe ref" is the subtle bit reviewers should focus on. A fresh repo / project will trip the 404 branch — calling that `FAIL` would mean every greenfield consumer fails their first `/tracker-doctor` run, which is the wrong UX. The 404 case proves auth + ref-resolution (the hard parts); the issue not existing is the easy part.
- Phase 1 `FAIL` deliberately short-circuits Phases 2-3. Phase 2 `FAIL` deliberately does NOT short-circuit Phase 3 — `gh label list` has an independent auth path, and vocabulary findings remain actionable even when reachability is broken (the operator can fix the labels before fixing reachability). The asymmetry is intentional; document it.
- Vocabulary checks are `WARN`-only, never `FAIL`. The plugin works without configured labels / issue types; the failure surfaces at first `create_issue`. `WARN` is the right pressure level — surfaces the problem before it bites without blocking.
- This is the third plugin command. After it lands, Phase 3 is `/resume-initiative` (#20, shipped) + `/tracker-init` (#22, shipped) + this one + `backends/jira.md` (#24, open). Phase 3 closes when #24 closes — completing the Jira backend module.
