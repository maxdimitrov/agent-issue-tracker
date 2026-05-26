# agent-issue-tracker

Portable issue-tracking skills + slash commands for Claude Code, with **GitHub** and **Jira** backends.

Bundles five skills — `bug-tracking`, `feature-request`, `followup-tracking`, `initiative-tracking`, `skill-currency` — and three slash commands — `/tracker-init`, `/tracker-doctor`, `/resume-initiative` — that turn an idea, a defect, or a multi-week initiative into a tracker-issue with an agent-prompt-shaped body. The body shape lets a Claude Code agent (or any LLM agent) pick up the work cold weeks later without losing the context that produced it.

**Status:** v1 under development. The full v1 design lives at [`maxdimitrov/trading-bot:docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md`](https://github.com/maxdimitrov/trading-bot/blob/main/docs/superpowers/specs/2026-05-26-agent-issue-tracker-design.md). v1 ships with two backends (GitHub via `gh` CLI; Jira Cloud via the Atlassian Remote MCP), trading-bot as the GitHub dogfood consumer, and one work project as the Jira dogfood consumer.

## Why this exists

The four issue-tracking skills (bug-tracking / feature-request / followup-tracking / initiative-tracking) started life as project-local skills in [`maxdimitrov/trading-bot`](https://github.com/maxdimitrov/trading-bot). They encode a methodology — agent-prompt-shaped issue bodies, bail criteria (no fuzzy locus, no unbounded scope, no open design questions, no fuzzy acceptance), epic + sub-issue indexing — that turned out to be useful across personal AND work projects. This plugin extracts them once, with a backend abstraction so a project using Jira gets the same discipline as a project on GitHub.

## Dependency

This plugin **hard-depends on [`superpowers`](https://github.com/obra/superpowers)**. `claude plugin install agent-issue-tracker` auto-installs `superpowers` transitively. The skills' references to `superpowers:brainstorming`, `superpowers:writing-plans`, and `superpowers:verification-before-completion` are load-bearing — they assume the full agent-workflow pipeline is available.

## Roadmap

- v1.0.0 (under development) — five skills, three slash commands, GitHub + Jira backends, two consumers.
- v1.1 (planned) — port the `/audit-skills` detector + library (the enforcement helper for `skill-currency`).
- v2 (planned) — MCP server form factor so Cursor / Zed / other MCP-compatible clients can consume the tooling layer.

Day-one follow-on issues track each planned post-v1 enhancement.

## License

[MIT](LICENSE) — © 2026 Maksim Dimitrov.
