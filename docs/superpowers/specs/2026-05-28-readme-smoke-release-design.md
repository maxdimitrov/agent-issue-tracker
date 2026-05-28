# README rewrite + smoke gate + v1.0.0 release — design spec

**Date:** 2026-05-28
**Tracker:** [maxdimitrov/agent-issue-tracker#30](https://github.com/maxdimitrov/agent-issue-tracker/issues/30)
**Parent epic:** [maxdimitrov/trading-bot#153](https://github.com/maxdimitrov/trading-bot/issues/153)
**Phase:** 4 of 6 (capstone)

## 1. Problem

Three gaps remain before v1.0.0 can ship:

1. **README is a Phase-0 placeholder.** Five paragraphs of "what this plugin will be" + a v1-under-development disclaimer. No install, no backend setup, no skill tour, no command tour. An adopter landing on the GitHub repo page has nothing actionable. This is the single biggest gate to public adoption.
2. **CONTRIBUTING doesn't document the release gate.** The Phase-0 placeholder explicitly says "the v1.0.0 release smoke-test gate — lands in Phase 4." Without that section, future contributors (or future-self) can tag a release without running the §8.3 smokes.
3. **`v1.0.0` is not tagged.** The Unreleased CHANGELOG lists every Phase 0/1/2/3/4 deliverable; nothing's been moved to a versioned release. `claude plugin install agent-issue-tracker@v1.0.0` doesn't resolve.

This sub-issue closes all three plus runs the actual smoke tests that gate the release.

## 2. Goal

After this PR merges AND the v1.0.0 tag is pushed:

- `README.md` is the canonical adopter-facing front page: methodology framing, install, backend setup (GitHub + Jira), configuration, walkthrough links, skill + command tours, dependency rationale, roadmap.
- `CONTRIBUTING.md` has a "Release process" section documenting the §8.3 five-scenario smoke-test gate.
- `CHANGELOG.md` has a `## [1.0.0] - 2026-05-28` section with every Phase 0/1/2/3/4 deliverable + a "Release-gate smokes" record.
- `v1.0.0` annotated tag exists on `origin`, with an annotation message naming the smoke gate.
- The five smoke scenarios from design spec §8.3 have all run (Jira smoke may be deferred — see §4 below).

## 3. Non-goals (explicit)

- **Marketing copy.** No "powerful", "seamless", "robust" adjectives. Adopters evaluate plugins from the install instructions and the skills/commands tables.
- **Trading-bot dogfood cutover.** That's Phase 5 (filed as a separate sub-issue against trading-bot). This sub-issue ends at the v1.0.0 tag.
- **Jira live smoke against the operator's work project.** If the Atlassian connector is unavailable in the release session, smoke #2 defers to Phase 6. The deferral is documented in the release CHANGELOG and the tag annotation message.
- **README localization, screenshots, or animated GIFs.** Plain markdown prose only.
- **Per-skill or per-command sub-pages.** The README has compact tours; deep reference lives in the skill / command / backend files themselves.

## 4. Smoke gate — what we run before tagging

Per design spec §8.3. Each smoke MUST pass (or be documented as deferred with reason) before the tag is pushed.

| # | Scenario | Pass criteria |
|---|---|---|
| 1 | GitHub backend smoke against `maxdimitrov/agent-issue-tracker` itself | File one bug + one feature + one followup + one epic-with-sub-issue. Labels, body shape, sub-issue linkage all correct. Close after verification. |
| 2 | Jira backend smoke against a real Jira project | Same five-issue flow against the operator's work project or a dedicated `agent-issue-tracker-smoketest` subproject. Verify field mappings, parent link, ADF rendering. **Likely DEFERRED to Phase 6** if Atlassian connector not in session. |
| 3 | `/tracker-init` from blank state | Both backends if possible. Verify scaffolder produces valid YAML matching `examples/<backend>-config.yaml`. |
| 4 | `/tracker-doctor` | Against valid config (PASS), missing-labels config (WARN), malformed YAML (FAIL). Verify routing. |
| 5 | `/resume-initiative` against `trading-bot#153` | The parent epic. Verify parser handles its Status block, `## Children` task-list mirror, and Decision log. |

Smoke #2 is the only one likely to defer. The other four MUST PASS before tagging.

Smoke execution discipline:

- Each smoke records its outcome in CHANGELOG.md under the `[1.0.0]` block's `### Release-gate smokes` sub-section.
- Each smoke that PASSED records the test issue refs (so the operator can trace what was filed).
- Each smoke that PASSED-WITH-NOTE records the note.
- Each smoke that DEFERRED records the reason + the Phase that picks it up.
- A FAILED smoke blocks the tag — no exception.

## 5. README architecture

Section order is fixed:

1. **Title** (h1: `# agent-issue-tracker`) + 1-paragraph elevator pitch.
2. **What this is** — 2-3 paragraph methodology framing (the agent-prompt body shape, the bail criteria, the epic + sub-issue indexing).
3. **What ships** — two compact tables (5 skills + 3 slash commands).
4. **Install** — 3 commands (marketplace add, install, `/tracker-init`).
5. **Backend setup** — two sub-sections (GitHub + Jira); ~2 paragraphs each.
6. **Configuration** — 1 paragraph + link to `examples/issue-tracker.yaml.example`.
7. **Walkthroughs** — 3 links to `examples/workflows/*.md`.
8. **Methodology (deep dive)** — 4-6 paragraphs on the body shape, bail criteria, taxonomy, epic indexing, Status block, `## Children` mirror, skill-currency rule.
9. **Dependency** — 1-2 paragraphs on superpowers (rationale, transitive install).
10. **Adding a backend** — brief paragraph + link to `backends/_interface.md` and CONTRIBUTING.
11. **Roadmap** — brief list (v1.0.0 → v1.1 → v2 → day-one follow-ons).
12. **License** — MIT.

Prose discipline:

- The "should I install this?" answer must land in the first 90 seconds of reading.
- No marketing adjectives.
- Cross-links to in-tree files (skills, commands, backends, examples) — all verified at PR-open time.

## 6. CONTRIBUTING update

Two new sections appended to the existing file (don't rewrite — extend):

- **Release process** — the §8.3 smoke gate as a numbered five-step checklist, plus the rule that tag annotation messages must name the smoke outcomes.
- **Adding a backend** — pointer to `backends/_interface.md` (the seven-operation contract) + the CI `backend-contract` job as the static check.

Existing sections (Where things are decided, Where work is tracked, Issue body shape, License) stay byte-identical.

## 7. CHANGELOG release block

The current `## [Unreleased]` block contains every Phase 0/1/2/3/4 bullet. Convert it to:

```markdown
## [1.0.0] - 2026-05-28

### Added

[every Phase 0/1/2/3/4 bullet, chronological — copied from Unreleased]

### Release-gate smokes

- Smoke 1 (GitHub against this repo) — <outcome>
- Smoke 2 (Jira) — <outcome>
- Smoke 3 (/tracker-init) — <outcome>
- Smoke 4 (/tracker-doctor) — <outcome>
- Smoke 5 (/resume-initiative against trading-bot#153) — <outcome>

## [Unreleased]

(empty — heading retained for forward work)
```

Em-dash discipline preserved (— U+2014).

## 8. Tag

```
git tag -a v1.0.0 -m "v1.0.0 — first public release. Five skills, three slash commands, GitHub + Jira backends. Smoke gate per CONTRIBUTING.md Release process passed. <Note Jira deferral here if applicable>."
git push origin v1.0.0
```

- Annotated tag (`-a`), not lightweight.
- Tag the squash-merge commit of THIS PR — NOT the feature branch.
- Verify with `git tag -l v1.0.0` locally and `git ls-remote --tags origin v1.0.0` after push.
- Do NOT force-push the tag if a re-tag is needed; that's a separate decision with the operator.

## 9. Risk register

- **Jira smoke deferral.** Likely (Atlassian connector not in session). Document as DEFERRED to Phase 6; do not block release.
- **README cross-link rot.** Mitigated by local-resolution check before commit.
- **CHANGELOG byte-regression.** Em-dash hazard hit in PRs #19/#22/#28. Grep before commit.
- **Tag annotation mistake.** Once pushed, force-push is the only fix and that's destructive. Verify the message + the commit ref locally before push.
- **Smoke runtime cost.** Smoke 1 files 5 issues and closes them; smoke 5 reads an epic; smokes 3-4 are read-only. Total cost: ~10 minutes if the session has the necessary tools.

## 10. Verification

```bash
# README structural
wc -l README.md                                # >= 250
grep -E '^## ' README.md | wc -l               # >= 10 headings

# Cross-link integrity
grep -oP '\]\((?!https?:)\K[^)#]+(?=[#)])' README.md | while read p; do
  [ -e "$p" ] || echo "BROKEN: $p"
done                                            # silent = pass

# CONTRIBUTING release section
grep -E '^## Release process' CONTRIBUTING.md

# CHANGELOG release
grep -E '^## \[1\.0\.0\]' CHANGELOG.md
grep -E '^### Release-gate smokes' CHANGELOG.md

# Em-dash
grep -P 'Phase [0-9].*--' CHANGELOG.md          # should print nothing
grep -P 'Phase [0-9].*—' CHANGELOG.md           # should match each row

# Tag (post-merge)
git tag -l v1.0.0                              # present
git tag -v v1.0.0 2>&1 | head -10              # annotation visible
git ls-remote --tags origin v1.0.0             # on origin

# Lint local before push
npx markdownlint-cli2 'README.md' 'CONTRIBUTING.md' 'CHANGELOG.md' 'examples/**/*.md'
```

## 11. Notes

- This is the capstone PR. README + CONTRIBUTING are the only files an adopter reads BEFORE deciding to install. Treat them as the most prose-quality-sensitive files in the plugin.
- The tag goes up AFTER the squash-merge, AGAINST the squash commit. Do NOT tag the feature branch.
- Smoke deferrals are honest. A deferred Jira smoke is fine — pretending we ran it isn't.
