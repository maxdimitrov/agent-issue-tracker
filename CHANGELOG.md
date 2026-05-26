# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 0 bootstrap: plugin manifest, LICENSE, README/CONTRIBUTING/CHANGELOG placeholders, directory skeleton from spec §5.1.
- Phase 1 (#9): backend operation contract (`backends/_interface.md`) — seven operations + five cross-backend invariants; GitHub backend module (`backends/github.md`) via `gh` CLI; config schema reference (`examples/issue-tracker.yaml.example`) and minimal GitHub example (`examples/github-config.yaml`).
- Phase 2 (#11): bug-tracking skill — tracker-agnostic port from trading-bot; dispatches via the seven-operation backend contract. New `templates/bug-body.md` skeleton consumed by the skill's body-template section. First Phase 2 skill — establishes the de-trading-bot-ification pattern for #12/#13/#14/#15.

## Pre-history

This plugin extracts methodology that originated as project-local skills in [`maxdimitrov/trading-bot`](https://github.com/maxdimitrov/trading-bot). The v1 design spec is at [`maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md). v1.0.0 is the first release; earlier work lived in the trading-bot repo as `.claude/skills/{bug-tracking,feature-request,followup-tracking,initiative-tracking}/SKILL.md`.
