# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 0 bootstrap: plugin manifest, LICENSE, README/CONTRIBUTING/CHANGELOG placeholders, directory skeleton from spec §5.1.
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from trading-bot; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-trading-bot-ification pattern for #12/#13/#14/#15.
- Phase 2 (#12): feature-request skill — tracker-agnostic port from trading-bot, mechanical re-application of the #11 transforms. Houses the canonical bug-vs-feature disambig table referenced by `bug-tracking`. New `templates/feature-body.md` skeleton consumed by the skill's body-template section.
- Phase 2 (#13): followup-tracking skill — tracker-agnostic port from trading-bot. Type-orthogonal sibling to bug-tracking + feature-request; covers origination (work deferred from in-flight effort), not type. New `templates/followup-body.md` skeleton — first non-standard body template in the plugin, with five followup-specific blocks (Parent / What's already done / What's been tried-ruled out / Related issues / Why deferred) preceding the standard tail. Validates the templates/*-body.md pattern for `templates/epic-body.md` (#14).
- Phase 2 (#14): initiative-tracking skill — tracker-agnostic port from trading-bot, the most-surgery port of the four (parent spec §6.2). Four surgical transforms: native sub-issue API block → `link_sub_issue` indirection; Status-block parser extension (Next-up accepts both `#N` and `PROJ-123`); read-modify-write warning generalized via the destructive-edit cross-backend invariant from `backends/_interface.md`; per-backend fallback section reframed as a cross-backend invariant (the `## Children` task-list mirror is the canonical index; native linkage is per-backend native plumbing). New `templates/epic-body.md` carries the four canonical Status-block field prefixes (`- **Phase:**`, `- **Next up:**`, `- **Current branch:**`, `- **Last updated:**`) literally — Phase 3 `/resume-initiative` parses them character-for-character. New `templates/sub-issue-body.md` is a thin compose-by-reference wrapper around feature-body.md / bug-body.md plus a `## Parent epic` block (deliberate divergence from followup-body.md's self-contained pattern).
- `commands/resume-initiative.md` — tracker-agnostic port of the slash command. Dispatches through `list_open_issues` / `view_issue` from `backends/_interface.md`, parses both `#N` and `PROJ-123` Status-block refs, handles cross-repo `## Children` task-list mirrors with three ref shapes (`#N`, `owner/repo#N`, `PROJ-123`), Mode 3 worktree creation lands in the consumer's CWD. Phase 3 (#20).

## Pre-history

This plugin extracts methodology that originated as project-local skills in [`maxdimitrov/trading-bot`](https://github.com/maxdimitrov/trading-bot). The v1 design spec is at [`maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md). v1.0.0 is the first release; earlier work lived in the trading-bot repo as `.claude/skills/{bug-tracking,feature-request,followup-tracking,initiative-tracking}/SKILL.md`.
