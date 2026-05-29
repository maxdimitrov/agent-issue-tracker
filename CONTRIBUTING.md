# Contributing to agent-issue-tracker

## Where work is tracked

- **Sub-issues for plugin development:** filed against THIS repo with phase- or scope-prefixed titles, following the agent-prompt body shape below.
- **Post-v1 enhancements:** filed against THIS repo with the `enhancement` label.

## Issue body shape

All issues filed against this repo follow the same agent-prompt body shape the plugin itself ships:

- Goal
- Locus (file paths, function/route, subsystem)
- Skills to load (which plugin skills + which superpowers skills)
- What's missing (for enhancements) or Symptom + Repro + Impact (for bugs)
- Why
- Sketch (for enhancements) or Root cause hypothesis (optional, for bugs)
- Constraints (out of scope, invariants, style)
- Acceptance (writable as a regression test)
- Verify (exact commands to prove the change)
- Notes

A vague body wastes an agent run. A structured body gets a draft PR back.

## Release process

Before any release tag is pushed, the seven smoke scenarios must run against a real GitHub-backed repo and a real Jira project, then against the published plugin install on a clean machine:

1. **GitHub backend smoke** — file one bug, one feature, one followup, and one epic-with-sub-issue against `maxdimitrov/agent-issue-tracker` itself. Verify labels, body shape, and sub-issue linkage. Close all five after verification.
2. **Jira backend smoke** — same five-issue flow against a real Jira project (the operator's work project or a dedicated `agent-issue-tracker-smoketest` subproject). Verify field mappings, parent link, and ADF rendering.
3. **`/tracker-init` from blank state** — both backends. Verify the scaffolder produces valid YAML matching `examples/<backend>-config.yaml` shape and the next-step panel is correct.
4. **`/tracker-doctor`** — run against a valid config (PASS path), a config with missing-on-tracker areas labels (WARN path), and a malformed YAML (FAIL path). Verify the routing.
5. **`/resume-initiative` against a real existing epic** — verify the parser handles its Status block, `## Children` task-list mirror, and Decision log.
6. **Install path against the published repo (added v1.0.1, #35)** — on a clean machine, `claude plugin marketplace add maxdimitrov/agent-issue-tracker` and `claude plugin install agent-issue-tracker` both exit 0; `~/.claude/plugins/installed_plugins.json` records the just-tagged version. Catches `marketplace.json` regressions.
7. **Plugin loads enabled post-install (added v1.0.2, #37)** — same clean-machine session, `claude plugin list` shows the plugin as `Status: ✔ enabled` (not `✘ failed to load`); `claude plugin details agent-issue-tracker` reports all 8 components (5 skills + 3 commands); in a fresh CC session opened against the install, `/tracker-doctor`, `/tracker-init`, and `/resume-initiative` are resolvable as slash commands. Catches `plugin.json.dependencies` cross-marketplace-resolution regressions.

Record each smoke's outcome under the new release's `### Release-gate smokes` sub-section in `CHANGELOG.md`. The release tag's annotation message must name the smoke gate and any deferrals.

If smoke 2 (Jira) cannot run in the release session (Atlassian connector not configured), document the deferral with reason. The other six MUST pass before tagging — a failed smoke blocks the tag with no exception. Smokes 6 and 7 specifically require a tag candidate to exist (so the marketplace-add + install pull the candidate); the practical sequence is: smokes 1-5 pass → push candidate tag to a feature branch → run smokes 6-7 → if green, tag `main` at the merge commit.

Then tag:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <one-line summary>. Smoke gate per CONTRIBUTING.md Release process passed. <Note any deferrals>."
git push origin vX.Y.Z
```

Annotated tags only (`-a`). Tag the squash-merge commit of the release PR, not the feature branch. Never force-push a release tag without an explicit operator decision.

## Adding a backend

The contract every backend implements lives in [`backends/_interface.md`](backends/_interface.md) — seven operations (`create_issue`, `add_label`, `link_sub_issue`, `list_open_issues`, `view_issue`, `edit_body`, `close_issue`) with identical tracker-agnostic inputs, plus five cross-backend invariants every backend must satisfy.

A new backend ships as a single `backends/<backend>.md` file documenting how each contract operation maps to that backend's native API. The reference implementations are [`backends/github.md`](backends/github.md) (via the `gh` CLI) and [`backends/jira.md`](backends/jira.md) (via the Atlassian Remote MCP). Both follow the same section structure — Auth, Reference table, per-operation block, Cross-backend invariants, PR close-on-merge convention, Setup verification — and a new backend should mirror it.

The CI `backend-contract` job is the static check: it asserts every operation heading in `backends/_interface.md` appears in every `backends/<backend>.md`. Adding a backend with a missing operation will fail the job.

GitLab (`glab` CLI), Linear, Asana, plaintext-file, and Jira Server / Data Center are filed as day-one follow-on issues. See [the issues list](https://github.com/maxdimitrov/agent-issue-tracker/issues?q=is%3Aissue+label%3Aenhancement) under the `enhancement` label.

## License

This project is MIT-licensed. By contributing you agree your changes ship under the same license.
