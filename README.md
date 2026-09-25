# agent-issue-tracker

Portable issue-tracking skills + slash commands for Claude Code. Six skills, twelve slash commands, one session-title hook, two backends (GitHub via `gh`; Jira Cloud via the Atlassian Remote MCP). Install once; reuse across personal and work projects.

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
| [`initiative-tracking`](skills/initiative-tracking/SKILL.md) | Files an epic with an evergreen description; child status derives live from the tracker |
| [`skill-currency`](skills/skill-currency/SKILL.md) | Codifies the "skills update with the PR that changed the API" rule |
| [`tracker-contribute`](skills/tracker-contribute/SKILL.md) | Reports a problem with this plugin (or a fix) upstream to its own repo |

Twelve slash commands:

| Command | What it does |
| --- | --- |
| [`/tracker-init`](commands/tracker-init.md) | Interactive scaffolder — writes `.claude/issue-tracker.yaml` from prompts |
| [`/tracker-doctor`](commands/tracker-doctor.md) | Validates the config + backend reachability + vocabulary sanity |
| [`/resume-initiative`](commands/resume-initiative.md) | Loads an epic, prints status, optionally enters a worktree on the next-up child |
| [`/work-issue`](commands/work-issue.md) | Drives ONE named issue end-to-end — read, scope, worktree, brainstorm → plan → execute → verify → PR |
| [`/audit-skills`](commands/audit-skills.md) | PR-time doc-currency audit — lists docs whose references may be stale vs the branch's diff; informational, never blocks |
| [`/session-brief`](commands/session-brief.md) | Catch up on the current session — issue + PR links, CI, review threads awaiting you, a keep-going / compact / fresh verdict, and a resume note |
| [`/tracker-brief`](commands/tracker-brief.md) | Inbound digest since the last run — tracker activity, PRs, worktrees, resume notes and loop records joined into one ledger with a verdict per issue |
| [`/tracker-loop`](commands/tracker-loop.md) | One iteration of an unattended loop — babysit a PR, clear an epic, or poll a label — with budgets on disk; recurrence via `/loop` or `--loop` |
| [`/file-bug`](commands/file-bug.md) | Discoverable entry-point for the `bug-tracking` skill |
| [`/file-feature`](commands/file-feature.md) | Discoverable entry-point for the `feature-request` skill |
| [`/file-followup`](commands/file-followup.md) | Discoverable entry-point for the `followup-tracking` skill |
| [`/file-epic`](commands/file-epic.md) | Discoverable entry-point for the `initiative-tracking` skill |

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

## Session titles

In a configured project, a `SessionStart` hook titles each Claude Code
session (the VS Code tab name) at start/resume: issue/epic ref from the git
branch, the epic's next-up child when the GitHub backend can resolve it, and a
≤5-word Haiku summary of what the session was last doing. Example:
`#42 board-support · wiring webhook`. With no ref in the branch, the ref is
taken from the last one the operator *typed* (never from assistant prose or
tool output), in the configured backend's shape (`#N` on GitHub, `KEY-N` on
Jira).

Fail-open by design: no `.claude/issue-tracker.yaml` → no-op; manual renames
are never overwritten; any failure (no `jq`, no network, no `gh`) leaves the
title alone. Disable per-project with `session_titles: false`. Titles update
only at start/resume — mid-session focus shifts get a paste-ready `/rename`
suggestion from the `initiative-tracking` skill instead. Jira projects get
branch refs + AI summaries but no epic enrichment (hooks cannot reach MCP).

## Briefs and loops

Two briefs and one loop runtime, all backed by scripts that always exit 0 and print JSON, with state under `${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker/<project-key>/` and never inside a repo.

- **`/session-brief`** re-orients you in the session you are in: what you were doing, what needs you (review threads, red CI, conflicts), what is already resolved, and whether to keep going, `/compact`, or start fresh — with a resume note written for a cold start.
- **`/tracker-brief`** is the morning read: what moved in the tracker and on the git host since the last run, joined to your worktrees and resume notes, with one verdict per issue — Needs action, Status drift (a merged PR whose issue never closed), Waiting, Closeable, Stale, or No code artifact.
- **`/tracker-loop`** runs one iteration of an unattended loop. Three modes: `babysit` watches a PR to green and addresses code-level review comments; `clear` works an epic leaf by leaf through `/work-issue`; `poll` dispatches `/work-issue` on issues carrying a label. Recurrence is the harness's: `/loop /agent-issue-tracker:tracker-loop babysit #42` (self-paced) or `/loop 15m …` (fixed), or pass `--loop` to `/work-issue` / `/resume-initiative --start` to arm a session cron. Budgets (`loops:` in the config) are enforced from the record on disk, a judgement question from a reviewer always stops the loop, and nothing merges without `--merge`. A stopped loop stays stopped on later fires (a `checkpoint: fresh session` stop is the exception, it hands off through the resume note), and `/tracker-loop <mode> <ref> --restart` begins a new one.

**New tab handoff (VS Code only).** After `/file-followup` files an issue, or when `/session-brief` says **fresh session**, the agent offers to open a new Claude Code tab with the next prompt typed in: `/agent-issue-tracker:work-issue <ref>`, or a pointer to the resume note. It uses the extension's URI handler (`code --open-url "vscode://anthropic.claude-code/open?prompt=…"`, via `scripts/open-session-tab.sh`). The prompt is not submitted, so you press Enter, and VS Code asks once to allow the URI. It is always an offer, never automatic. In the CLI or JetBrains, the prompt is printed for copy-paste as before.

## Walkthroughs

End-to-end operator views of what filing and resuming look like against a real tracker:

- [Filing a bug](examples/workflows/file-a-bug.md) — trigger → skill → backend dispatch → tracker result, with variations for Jira and bail criteria
- [Filing an epic + sub-issues](examples/workflows/file-an-epic.md) — the evergreen description, the marker-tagged machine-block comment, and native sub-issue linkage
- [Resuming an initiative](examples/workflows/resume-an-initiative.md) — the modes of `/resume-initiative`

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

An epic's description is **evergreen** — `## Goal`, `## Scope`, `## Success criteria`, `## Design spec` — edited only when the initiative's own goal or scope changes, never per child. Child membership, per-child status, and next-up are never written anywhere; [`/resume-initiative`](commands/resume-initiative.md) derives them live on every read from the tracker's native parent-child linkage (`list_child_issues` + `view_issue`), so closing a child requires no edit to the epic at all. This aligns with the common convention of keeping epic descriptions evergreen — status lives in the tracker's own linkage, not hand-written lists.

Structure that isn't natively derivable — phase names and ordering, a sub-epic's parent pointer, the current-branch signal, an optional scope probe, and a decision log — lives in one marker-tagged **machine-block comment** (`<!-- agent-issue-tracker:machine-block -->`), written via the `read_comments` / `upsert_comment` contract operations. A flat epic with none of that carries no comment at all. To guard against a spoofed comment on a public repo, readers select the **earliest** marker-carrying comment from a **trusted** author (GitHub: `authorAssociation` ∈ OWNER/MEMBER/COLLABORATOR; Jira: trusted by default on org-internal instances).

Epics filed before this shape existed keep working indefinitely via `/resume-initiative`'s legacy reader (a body `## Status block` heading selects that path) — no forced migration. Convert one in place with `/resume-initiative <ref> --adopt`.

### Skill currency

When a PR changes API surface — a new module, a new public function, a new CLI subcommand, a new env var, a new DB table, a new HTTP route, a changed function signature, a removed function/file — the affected `.claude/skills/*.md` files MUST update in the same PR. A stale skill misleads every future agent that touches the area. The [`skill-currency`](skills/skill-currency/SKILL.md) skill codifies this; the [`/audit-skills`](commands/audit-skills.md) command is its shipped enforcement helper — run it before opening a PR.

## Dependency

The plugin hard-depends on [`superpowers`](https://github.com/obra/superpowers). `claude plugin install agent-issue-tracker` resolves and auto-installs `superpowers` at the same scope. Missing dep → install fails with a clear error; no silent partial install.

The dependency is load-bearing. The skills cite `superpowers:brainstorming`, `superpowers:writing-plans`, and `superpowers:verification-before-completion` directly — operators wanting structured issue-tracking almost certainly want the full agent-workflow pipeline. Bundling the dep guarantees one install gives you both.

## Adding a backend

The eleven-operation contract every backend implements lives in [`backends/_interface.md`](backends/_interface.md). Reference implementations: [`backends/github.md`](backends/github.md) (via `gh` CLI), [`backends/jira.md`](backends/jira.md) (via the Atlassian Remote MCP). The CI `backend-contract` job asserts every contract operation heading appears in every backend file — catches drift on PR.

A GitLab backend is filed as [#4](https://github.com/maxdimitrov/agent-issue-tracker/issues/4) and waits for a consumer; other trackers are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the backend-addition checklist.

## Roadmap

The current release is the top entry in [CHANGELOG.md](CHANGELOG.md); every shipped capability is recorded there with its issue and PR numbers. Open work, in priority order, lives in [the issues list](https://github.com/maxdimitrov/agent-issue-tracker/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement):

- **Post-merge finish phase** for `/work-issue` — merged-vs-released transitions, index refresh, merge method, worktree cleanup (#115).
- **Session-boundary nudges** via hook `systemMessage` (#114, needs a design pass).
- **Config resolution** — env-var overrides and a global `~/.claude/issue-tracker.yaml` fallback (#7, needs a design pass).

## License

[MIT](LICENSE) — © 2026 Maksim Dimitrov.
