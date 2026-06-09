# agent-issue-tracker

Portable issue-tracking skills + slash commands for Claude Code. Six skills, four slash commands, two backends (GitHub via `gh`; Jira Cloud via the Atlassian Remote MCP). Install once; reuse across personal and work projects.

## What this is

An issue tracker designed for agent handoff. A future Claude Code session can't pick up your "fix the auth thing" ticket cold weeks later — it lacks the locus, the repro, the constraints, the acceptance bar that made the ticket fileable in the first place. The skills here file issues in a shape an agent can read: Goal, Locus, Skills to load, Constraints, Acceptance, Verify — every field load-bearing, every body capable of carrying the context that produced it. The six skills also encode bail criteria (no fuzzy locus, no unbounded scope, no open design questions, no fuzzy acceptance) that prevent vague issues from reaching the agent in the first place.

The methodology started as project-local skills hard-coded to a single GitHub repo. It turned out to generalize across personal and work projects, so the skills moved here — tracker-agnostic, with a thin backend abstraction so a project using Jira gets the same discipline as a project on GitHub.

## What ships

Six skills:

| Skill | What it does |
| --- | --- |
| [`bug-tracking`](skills/bug-tracking/SKILL.md) | Files a bug with agent-prompt-shaped repro / impact / acceptance |
| [`feature-request`](skills/feature-request/SKILL.md) | Files an enhancement with sketch / acceptance / bail criteria |
| [`followup-tracking`](skills/followup-tracking/SKILL.md) | Files work deferred from in-flight effort, with parent reference |
| [`initiative-tracking`](skills/initiative-tracking/SKILL.md) | Files an epic plus its sub-issue index, with a parseable Status block |
| [`skill-currency`](skills/skill-currency/SKILL.md) | Codifies the "skills update with the PR that changed the API" rule |
| [`tracker-contribute`](skills/tracker-contribute/SKILL.md) | Reports a problem with this plugin (or a fix) upstream to its own repo |

Four slash commands:

| Command | What it does |
| --- | --- |
| [`/tracker-init`](commands/tracker-init.md) | Interactive scaffolder — writes `.claude/issue-tracker.yaml` from prompts |
| [`/tracker-doctor`](commands/tracker-doctor.md) | Validates the config + backend reachability + vocabulary sanity |
| [`/resume-initiative`](commands/resume-initiative.md) | Loads an epic, prints status, optionally enters a worktree on the next-up child |
| [`/work-issue`](commands/work-issue.md) | Drives ONE named issue end-to-end — read, scope, worktree, brainstorm → plan → execute → verify → PR |

## Install

```bash
claude plugin marketplace add maxdimitrov/agent-issue-tracker
claude plugin install agent-issue-tracker
```

The install auto-resolves [`superpowers`](https://github.com/obra/superpowers) as a transitive dependency (see [Dependency](#dependency) below).

Then scaffold your project's config:

```bash
/tracker-init
```

And validate:

```bash
/tracker-doctor
```

You're ready to file issues. Trigger any skill by intent — "file a bug", "open an epic", "spin out a followup" — and the skill handles the rest.

## Backend setup

### GitHub

Authenticate once per machine via the GitHub CLI:

```bash
gh auth login
```

`/tracker-init` detects the auth state and defaults `github.repo` to your current repository (via `gh repo view --json nameWithOwner`). The minimal config that results is in [`examples/github-config.yaml`](examples/github-config.yaml). For the literal `gh` invocations the skills dispatch through, see [`backends/github.md`](backends/github.md).

### Jira Cloud

Enable the Atlassian connector in [claude.ai](https://claude.ai) → Settings → Connectors → Atlassian. The connector handles OAuth, scopes, refresh, and rate limiting; no API tokens live in the plugin or in your config file.

`/tracker-init` detects the connector via the MCP tool surface and queries `getAccessibleAtlassianResources` for your reachable sites — if exactly one site is accessible, both `jira.site` and `jira.cloud_id` are written without prompting; multiple sites surface a picker. The minimal config is in [`examples/jira-config.yaml`](examples/jira-config.yaml). For the literal Atlassian Remote MCP tools the skills dispatch through, see [`backends/jira.md`](backends/jira.md).

## Configuration

Every consuming project commits one `.claude/issue-tracker.yaml`. It declares the backend, the project's vocabulary (areas, subsystems), and any backend-specific overrides (Jira issue-type mapping, parent-link style, custom workflow transitions). The fully-commented schema lives at [`examples/issue-tracker.yaml.example`](examples/issue-tracker.yaml.example) — read it once; you'll override maybe three keys.

`.claude/issue-tracker.yaml` is the only configuration surface. No env-var overrides in v1; no global `~/.claude/issue-tracker.yaml`. Both are filed as v2 follow-on issues.

## Walkthroughs

End-to-end operator views of what filing and resuming look like against a real tracker:

- [Filing a bug](examples/workflows/file-a-bug.md) — trigger → skill → backend dispatch → tracker result, with variations for Jira and bail criteria
- [Filing an epic + sub-issues](examples/workflows/file-an-epic.md) — including the canonical four-line Status block and the cross-backend `## Children` task-list mirror
- [Resuming an initiative](examples/workflows/resume-an-initiative.md) — the three modes of `/resume-initiative`

## Methodology

### The agent-prompt body shape

Every issue this plugin files follows a shape an agent can pick up cold:

- **Goal** — one sentence; the observable outcome.
- **Locus** — file paths, function/route, subsystem. No "TBD".
- **Skills to load** — which plugin skills + which `superpowers:*` skills.
- **Symptom + Repro + Impact** (bugs) or **What's missing + Sketch** (features).
- **Constraints** — out of scope, invariants, style.
- **Acceptance** — writable as a regression test.
- **Verify** — exact commands to prove the change.
- **Notes** — related issues, prior PRs.

The shape is in [`templates/`](templates/). Skills fill these templates; backends dispatch the result. A vague body wastes an agent run; a structured body gets a draft PR back.

### Bail criteria

A skill refuses to file when:

- The locus is "things are slow" instead of a specific component.
- Acceptance is "works correctly" instead of an observable predicate.
- The repro is missing.
- The design has unresolved open questions (those get a `needs-design` issue first, and a separate brainstorm).

The bail is intentional. The cost of an unfileable issue is one round of clarification; the cost of an agent run against a vague brief is hours.

### Issue type taxonomy

Five types, kept distinct on purpose:

| Type | When |
| --- | --- |
| `bug` | Something works wrong now. There's a repro. Fix restores correct behaviour. |
| `feature` | Something doesn't exist yet. The agent builds it. Sketch is concrete. |
| `followup` | Work spun out of in-flight effort. Parent reference is required. |
| `epic` | Multi-week initiative. Multiple sub-issues, design spec, phases. |
| `sub` | A child issue under an epic, typed as bug or feature underneath. |

The disambig table between bug and feature lives in [`feature-request`](skills/feature-request/SKILL.md) — that's the canonical reference both skills cite.

### Epic + sub-issue indexing

Epics carry a four-line **Status block** with canonical field labels — `**Phase:**`, `**Next up:**`, `**Current branch:**`, `**Last updated:**`. [`/resume-initiative`](commands/resume-initiative.md) matches each line on its bold field label, tolerant of the leading list-bullet character (Jira's ADF round-trip rewrites a leading `-` to `*`). Update them as sub-issues close.

The epic body also carries a `## Children` task-list mirror — the **cross-backend source of truth** for the sub-issue index. It handles all three ref shapes: `#N` (same-repo GitHub), `owner/repo#N` (cross-repo GitHub), `PROJ-123` (Jira). Native sub-issue linkage via the tracker's own API is additional UI metadata; the mirror is what every consumer of the epic reads.

### Skill currency

When a PR changes API surface — a new module, a new public function, a new CLI subcommand, a new env var, a new DB table, a new HTTP route, a changed function signature, a removed function/file — the affected `.claude/skills/*.md` files MUST update in the same PR. A stale skill misleads every future agent that touches the area. The [`skill-currency`](skills/skill-currency/SKILL.md) skill codifies this; the `/audit-skills` enforcement helper is a v1.1 follow-on.

## Dependency

The plugin hard-depends on [`superpowers`](https://github.com/obra/superpowers). `claude plugin install agent-issue-tracker` resolves and auto-installs `superpowers` at the same scope. Missing dep → install fails with a clear error; no silent partial install.

The dependency is load-bearing. The skills cite `superpowers:brainstorming`, `superpowers:writing-plans`, and `superpowers:verification-before-completion` directly — operators wanting structured issue-tracking almost certainly want the full agent-workflow pipeline. Bundling the dep guarantees one install gives you both.

## Adding a backend

The eight-operation contract every backend implements lives in [`backends/_interface.md`](backends/_interface.md). Reference implementations: [`backends/github.md`](backends/github.md) (via `gh` CLI), [`backends/jira.md`](backends/jira.md) (via the Atlassian Remote MCP). The CI `backend-contract` job asserts every contract operation heading appears in every backend file — catches drift on PR.

GitLab, Linear, Asana, plaintext-file, and Jira Server / Data Center are filed as day-one follow-on issues. See [CONTRIBUTING.md](CONTRIBUTING.md) for the backend-addition checklist.

## Roadmap

- **v1.0.0** (this release) — five skills, three slash commands, GitHub + Jira backends, full CI.
- **v1.1** (planned) — port the `/audit-skills` detector + library as the enforcement helper for `skill-currency`.
- **v2** (planned) — MCP server form factor so Cursor / Zed / other MCP-compatible clients can consume the tooling layer.

Day-one follow-on issues filed against this repo cover each post-v1 enhancement; see [the issues list](https://github.com/maxdimitrov/agent-issue-tracker/issues?q=is%3Aissue+label%3Aenhancement) under the `enhancement` label.

## License

[MIT](LICENSE) — © 2026 Maksim Dimitrov.
