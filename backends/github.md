# GitHub Backend

Backend module for [`gh` CLI](https://cli.github.com/) — the dispatch surface for the `github` backend. Implements the seven operations from [`_interface.md`](_interface.md).

## Auth

Consumer runs `gh auth login` once per machine. The `gh` CLI manages the credential. No per-project token storage in the plugin.

For GitHub Enterprise, `gh auth login --hostname <enterprise-host>`. The `github.repo` field in `.claude/issue-tracker.yaml` is qualified by host implicitly because `gh` resolves `owner/repo` against whichever host the CLI is currently authed to.

## Reference: `gh issue` and `gh api` commands

| Operation | Command shape |
|---|---|
| Create | `gh issue create --repo OWNER/REPO --title TITLE --body-file PATH --label "L1,L2"` |
| Add label | `gh issue edit N --repo OWNER/REPO --add-label LABEL` |
| Sub-issue link (resolve child id) | `gh api repos/OWNER/REPO/issues/N --jq .id` |
| Sub-issue link (attach) | `gh api -X POST repos/OWNER/REPO/issues/PARENT/sub_issues -F sub_issue_id=CHILD_ID` |
| List open | `gh issue list --repo OWNER/REPO --label LABEL --state open --json number,title,state` |
| View | `gh issue view N --repo OWNER/REPO --json body,labels,state` |
| Edit body (destructive) | `gh issue edit N --repo OWNER/REPO --body-file PATH` |
| Close | `gh issue close N --repo OWNER/REPO --comment "REASON"` |

---

## Operations

### `create_issue`

```bash
# Write body to a temp file (gh --body has shell-escaping pitfalls; --body-file is safer)
echo "$BODY" > .tmp_issue_body.md
gh issue create \
  --repo "$GITHUB_REPO" \
  --title "$TITLE" \
  --body-file .tmp_issue_body.md \
  --label "$(IFS=,; echo "${LABELS[*]}")"
rm .tmp_issue_body.md
```

Returns the URL of the created issue; the skill captures the trailing `/N` as the ref.

**Field mapping:**
- `type` → maps to a label from `types.<type>.labels` in config (`bug → bug`, `feature → enhancement`, `epic → epic`, etc.)
- `area` → applied as a label (`github` backend uses labels for areas; no `components` concept)
- `subsystem` → not a label; goes inline in the issue body's Locus block
- `parent` → not used at create-time; sub-issue linkage is a separate `link_sub_issue` call after the child exists

---

### `add_label`

```bash
gh issue edit "$N" --repo "$GITHUB_REPO" --add-label "$LABEL"
```

If `$LABEL` doesn't exist on the repo, `gh` errors. `/tracker-doctor` warns if the consumer's configured `areas:` enum references missing labels and prints the `gh label create` commands to fix.

---

### `link_sub_issue`

Two-step on GitHub. The native `sub_issues` API takes the child's *database id* (integer), not its number.

```bash
# Resolve child database id (NOT the issue number)
CHILD_ID=$(gh api repos/"$GITHUB_REPO"/issues/"$CHILD_N" --jq .id)

# Attach via the sub-issue API
gh api -X POST repos/"$GITHUB_REPO"/issues/"$PARENT_N"/sub_issues \
  -F sub_issue_id="$CHILD_ID"
```

**Critical gotcha:** the `sub_issue_id` field MUST be passed with `-F` (typed integer), not `-f` (string). Wrong flag returns:

```
HTTP 422: Invalid property /sub_issue_id: is not of type integer
```

This bites every operator who reads the GitHub API docs casually. Always `-F`.

---

### `list_open_issues`

```bash
gh issue list \
  --repo "$GITHUB_REPO" \
  --label "$FILTER" \
  --state open \
  --json number,title,state \
  --jq '.[] | "\(.number)\t\(.title)\t\(.state)"'
```

For multi-label AND-filter, repeat `--label`. For type-filter, pass the type-driven label (`bug`, `enhancement`, `epic`).

---

### `view_issue`

```bash
gh issue view "$N" --repo "$GITHUB_REPO" --json body,labels,state,title
```

Returns JSON with the issue's body, labels array, state (`OPEN | CLOSED`), and title. For parent lookup on sub-issues, query `gh api repos/$GITHUB_REPO/issues/$N --jq '.sub_issue_id // empty'` (no native parent field via `gh issue view`).

---

### `edit_body`

```bash
# Read current body first if doing read-modify-write
gh issue view "$N" --repo "$GITHUB_REPO" --json body --jq .body > .tmp_current_body.md
# ... modify .tmp_current_body.md in memory ...
gh issue edit "$N" --repo "$GITHUB_REPO" --body-file .tmp_current_body.md
rm .tmp_current_body.md
```

Destructive replace. There is no append-only API on `gh`. The Status-block-update path in `initiative-tracking` uses exactly this read-modify-write shape.

---

### `close_issue`

```bash
gh issue close "$N" --repo "$GITHUB_REPO" --comment "$COMMENT"
```

For `reason: not_planned`, pass `--reason "not planned"`. For `reason: duplicate`, no native equivalent — close with a `--comment` that references the duplicate's ref instead.

---

## Cross-backend invariants — how GitHub satisfies them

1. **Body format is markdown** — GitHub renders markdown natively. Plugin emits markdown directly.
2. **Whole-body edits are destructive** — `gh issue edit --body-file` replaces the whole description. Plugin pattern: `gh issue view --json body --jq .body` → modify in memory → `gh issue edit --body-file`.
3. **Sub-issue linkage** — GitHub's native sub-issue API (the `sub_issues` endpoint). Implemented per `link_sub_issue` above.
4. **Issue refs are opaque** — GitHub refs are `#N`, where `N` is the per-repo issue number. The skill treats this as opaque; only this backend module knows the syntax.
5. **`/tracker-doctor` reachability** — runs `gh auth status` + `gh repo view "$GITHUB_REPO"`. Both must succeed.

## PR close-on-merge convention

GitHub auto-closes referenced issues when the merging PR's body or title contains `Fixes #N`, `Closes #N`, or `Resolves #N` and the PR merges to the repo's default branch. The plugin's `feature-request` and `bug-tracking` skills tell the agent to include `Closes #<N>` in PR bodies for this backend. `Fixes #N` and `Closes #N` work identically; a project can pick whichever phrasing it prefers via `github.default_pr_close_syntax` below.

The consumer's `.claude/issue-tracker.yaml`'s `github.default_pr_close_syntax` field is rendered into PR description templates as the recommended phrasing.

## Setup verification

`/tracker-doctor` runs (in order):

1. `gh auth status` — must succeed (consumer is authed).
2. `gh repo view "$GITHUB_REPO"` — must succeed (repo exists, consumer has access).
3. For each label in `areas:`, `gh label list --repo "$GITHUB_REPO" --search "$LABEL"` — warning if missing, prints `gh label create` next-step.
