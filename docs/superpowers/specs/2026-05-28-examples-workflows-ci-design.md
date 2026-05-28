# examples + workflows + CI — design spec

**Date:** 2026-05-28
**Tracker:** [maxdimitrov/agent-issue-tracker#29](https://github.com/maxdimitrov/agent-issue-tracker/issues/29)
**Parent epic:** [maxdimitrov/trading-bot#153](https://github.com/maxdimitrov/trading-bot/issues/153)
**Phase:** 4 of 6 (first ~half — sibling sub-issue #30 ships README + smoke + v1.0.0)

## 1. Problem

The plugin's `examples/` and `.github/` directories are still Phase-0 skeletons. Three concrete gaps from design spec §5.1:

1. `examples/jira-config.yaml` does not exist. `examples/github-config.yaml` does — the asymmetry will show in the `examples/` listing and confuse Jira-backed adopters.
2. `examples/workflows/*.md` walkthroughs do not exist. The `examples/workflows/` directory is empty. Without them, an adopter reading the README has no way to see what the agent's filed-issue output actually looks like end-to-end against a concrete tracker.
3. `.github/workflows/ci.yml` does not exist. PRs against this repo run zero checks today. The contract-check failure mode (a `### <op>` heading drifting between `_interface.md` and the backend files) has no automated detection.

This sub-issue closes those three gaps. The sibling sub-issue (#30) then references these files in its README rewrite.

## 2. Goal

After this PR merges, `examples/` and `.github/workflows/` are populated end-to-end per design spec §5.1:

- `examples/jira-config.yaml` — minimal commented Jira config, sibling to `github-config.yaml`.
- `examples/workflows/file-a-bug.md` — operator walkthrough for bug filing.
- `examples/workflows/file-an-epic.md` — operator walkthrough for epic + sub-issue filing.
- `examples/workflows/resume-an-initiative.md` — operator walkthrough for `/resume-initiative`.
- `.github/workflows/ci.yml` — three jobs (markdown lint, YAML validate, backend-contract check).

CHANGELOG appended with a Phase 4 Added bullet, em-dash separator.

## 3. Non-goals (explicit)

- **`.github/ISSUE_TEMPLATE/*.md` content.** The plugin's whole methodology is that issues are filed via skills, not via GitHub's web UI templates. The Phase-0 empty directory stays empty. Decision recorded in CHANGELOG.
- **`file-a-feature.md` and `file-a-followup.md` walkthroughs.** Mechanical mirrors of `file-a-bug.md`; deferred to v1.1 follow-on if real demand surfaces.
- **A test suite.** The plugin ships markdown+YAML only. CI runs static checks; there is no runtime to test.
- **Secrets, PATs, or Jira-credential surface in CI.** Backend-contract check is pure-static. No `GITHUB_TOKEN` beyond default; no Atlassian creds; no API calls.
- **Scripts directory.** Backend-contract check inlines its shell into the CI step. No `scripts/ci/` to maintain.

## 4. Architecture

### 4.1 `examples/jira-config.yaml`

Minimal commented YAML matching `examples/github-config.yaml`'s shape (terse — adopters go to `issue-tracker.yaml.example` for full schema docs). Required fields per `examples/issue-tracker.yaml.example` lines 66-108: `site`, `cloud_id`, `project`, `issue_types` (the four-type mapping). Two-line header comment naming this as the minimal Jira sibling.

### 4.2 Walkthrough shape

All three walkthroughs share a section structure, operator-facing voice (second-person), and link discipline:

```
# Walkthrough: <verb>

[One-paragraph intro naming the configured backend + project context]

## 1. Trigger
[The operator's natural-language input that activates the skill]

## 2. Skill activation
[Which skill activates; what config it reads; which backend module it dispatches to]

## 3. Body draft
[The agent-prompt body the skill produces, following the relevant templates/*-body.md]

## 4. Dispatch
[The literal backend invocation — the actual gh / MCP call]

## 5. Result
[What the tracker shows; how the skill confirms to the operator]

## Variations
[Bullet list of common alternative paths: other backend, bail criteria, missing vocabulary]
```

Cross-link policy: walkthroughs link INWARD to skills (`skills/<name>/SKILL.md`), templates (`templates/<name>.md`), backends (`backends/<name>.md`), and each other. They do NOT link to README (which is being rewritten in #30 and would create circular drafting).

### 4.3 `.github/workflows/ci.yml`

Three jobs, all on `ubuntu-latest`, runs on `pull_request` + `push` to `main`. Action versions pinned (`@v4` / `@v16` style, not `@main`).

```yaml
jobs:
  markdown-lint:
    [DavidAnson/markdownlint-cli2-action@v16, globs: '**/*.md']

  yaml-validate:
    [pip install yamllint; yamllint -d relaxed .]

  backend-contract:
    [inline shell: extract ### `<op>` headings from _interface.md, assert
     every operation appears in every backends/<backend>.md]
```

The backend-contract check is a ~12-line shell block. It catches the failure mode where a contract operation gets renamed or added without updating the backend implementations in lockstep. Pure-static; no network; no auth.

### 4.4 CHANGELOG entry

```
- Phase 4 (#29): examples + workflows + CI — minimal `examples/jira-config.yaml`
  sibling to `examples/github-config.yaml`; three operator-facing walkthroughs
  (`examples/workflows/file-a-bug.md`, `file-an-epic.md`, `resume-an-initiative.md`)
  showing the trigger → skill → backend → tracker dispatch shape end-to-end;
  `.github/workflows/ci.yml` with three jobs (markdown-lint via markdownlint-cli2,
  yaml-validate via yamllint, backend-contract checker as inline shell asserting
  every `### <op>` heading in `backends/_interface.md` appears in every backend
  implementation). First ~half of Phase 4; sibling (#30) ships README + smoke
  + v1.0.0 tag.
```

Em-dash separator (— U+2014), NOT ASCII `--`.

## 5. Cross-backend invariants — does this sub-issue's output respect them?

Not directly — invariants are a property of the seven-operation contract, which lives in `backends/_interface.md` and is enforced by the new CI `backend-contract` job. This sub-issue's only invariant-adjacent deliverable is that CI check.

## 6. Verification

The CI workflow itself is YAML; validate it locally:

```
yamllint -d relaxed .github/workflows/ci.yml
```

The backend-contract check is a shell snippet; run it directly to confirm the patterns match the live files:

```
contract_ops=$(grep -oP '^### \`\K[a-z_]+(?=\`)' backends/_interface.md | sort -u)
for backend in backends/github.md backends/jira.md; do
  backend_ops=$(grep -oP '^### \`\K[a-z_]+(?=\`)' "$backend" | sort -u)
  comm -23 <(echo "$contract_ops") <(echo "$backend_ops")
done
```

Should print nothing. If it prints, either the patterns are wrong (tune the `grep -oP`) or the live files have drifted (real contract bug — file a fix).

Em-dash discipline:

```
grep -P 'Phase 4.*--' CHANGELOG.md   # should print nothing
grep -P 'Phase 4.*—' CHANGELOG.md    # should match
```

## 7. Notes

- This sub-issue ships FIRST so #30's README has working examples + walkthroughs to link to.
- The five `examples/workflows/*.md` filenames in design spec §5.1 list three concrete ones (file-a-bug, file-an-epic, resume-an-initiative). The other two are mechanical mirrors deferred to v1.1.
- Pin CI action versions strictly. `@main` is a CI failure mode — drift kills builds.
- Pure-addition PR; squash-merge; auto-close issue via `Closes #29` in PR body.
- Em-dash regression hazard hit in PR #19/#22/#28 — bake the grep into the verify block.
