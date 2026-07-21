# GitHub Backend

Backend module for [`gh` CLI](https://cli.github.com/) — the dispatch surface for the `github` backend. Implements the eight operations from [`_interface.md`](_interface.md).

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
| List children | `gh api --paginate repos/OWNER/REPO/issues/PARENT_N/sub_issues` |
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

### `list_child_issues`

The read-inverse of `link_sub_issue` — GET the same `sub_issues` endpoint that `link_sub_issue` POSTs to. Returns the parent's direct children, open and closed.

```bash
gh api --paginate repos/"$GITHUB_REPO"/issues/"$PARENT_N"/sub_issues \
  --jq '.[] | "\(.number)\t\(.title)\t\(.state)"'
```

`--paginate` is required: the endpoint pages at 30, and a silently truncated list would drop children from the adopted `## Children` mirror. Each item carries `state` (`open` / `closed`) — adoption needs the closed ones to render `[x] … — closed` lines. The skill translates each row to `{ref: #number, title, status}`.

**Cross-repo children** (`owner/repo#N`): a child in another repo lives under *its* repo's endpoint — call `gh api repos/<that-owner>/<that-repo>/issues/<N>/sub_issues` for that child's repo, not the configured `github.repo`.

**Nesting (invariant 6):** GitHub sub-issues nest arbitrarily deep, so this call returns the true direct children at every level — there is no native ceiling below the body mirror's reach (contrast Jira). The skill recurses one node at a time via the `## Children` mirror.

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
6. **Initiative nesting** — GitHub's native sub-issue API nests **arbitrarily deep**: a sub-issue can itself own sub-issues via the same `POST repos/.../issues/<parent>/sub_issues` call (`link_sub_issue`), so native linkage never hits a ceiling that `initiative-tracking`'s body mirror exceeds. Root-vs-nested detection still uses the cross-backend signal (a `## Parent epic` block in the body) rather than the native relation, because `gh issue view` does not return a parent field — see `view_issue` above, which resolves a parent only via the extra `gh api .../issues/<N> --jq '.sub_issue_id // empty'` call.

## PR close-on-merge convention

GitHub auto-closes referenced issues when the merging PR's body or title contains `Fixes #N`, `Closes #N`, or `Resolves #N` and the PR merges to the repo's default branch. The plugin's `feature-request` and `bug-tracking` skills tell the agent to include `Closes #<N>` in PR bodies for this backend. `Fixes #N` and `Closes #N` work identically; a project can pick whichever phrasing it prefers via `github.default_pr_close_syntax` below.

The consumer's `.claude/issue-tracker.yaml`'s `github.default_pr_close_syntax` field is rendered into PR description templates as the recommended phrasing.

## Setup verification

`/tracker-doctor` runs (in order):

1. `gh auth status` — must succeed (consumer is authed).
2. `gh repo view "$GITHUB_REPO"` — must succeed (repo exists, consumer has access).
3. For each label in `areas:`, `gh label list --repo "$GITHUB_REPO" --search "$LABEL"` — warning if missing, prints `gh label create` next-step.

## GitHub Projects v2 board (optional)

**Optional, GitHub-only. Not a contract operation** — see
[`_interface.md`](_interface.md) "Optional backend-specific capabilities". When the
consumer's `.claude/issue-tracker.yaml` sets `github.project`, `initiative-tracking`
mirrors the initiative tree onto that GitHub Projects (v2) board: it adds the root
epic, every sub-epic, and every leaf child as items and reflects each child's
lifecycle in the board's built-in **Status** field. The board is a human-facing
view; the epic body's `## Children` task-list mirror stays canonical. With
`github.project` unset, none of this runs.

GitHub Projects v2 is GraphQL-only; the `gh project` subcommands wrap it and need
the `project` token scope:

    gh auth refresh -s project,read:project

### Project config

`github.project` is a **user- or org-level** Projects board URL:

- user board: `https://github.com/users/<owner>/projects/<N>`
- org board:  `https://github.com/orgs/<org>/projects/<N>`

Parse `<owner>` (the path segment after `users/` or `orgs/`) and `<N>` (the
trailing number). Repo-level project URLs (`.../<owner>/<repo>/projects/<N>`) are
NOT supported — repo projects can't span repos, which defeats the cross-repo use
case.

### Resolve board identifiers (once per session, then cache)

    # project node id
    PROJECT_ID=$(gh project view <N> --owner <owner> --format json --jq .id)

    # Status field id + the Todo / In Progress / Done option ids
    gh project field-list <N> --owner <owner> --format json \
      --jq '.fields[] | select(.name=="Status")'
    # -> {"id":"<STATUS_FIELD_ID>", "options":[{"id":"..","name":"Todo"}, ...]}

Match option names case-insensitively, tolerating `Todo` / `To do`. If the board
has no `Status` field or an expected option is missing, skip the status write
(still add the item) and WARN once.

### Add an item + set its Status

    # add (idempotent: an issue already on the board returns its existing item)
    ITEM_ID=$(gh project item-add <N> --owner <owner> \
      --url <issue-url> --format json --jq .id)

    # set Status (non-draft items require --id AND --project-id; one field per call)
    gh project item-edit --id "$ITEM_ID" --project-id "$PROJECT_ID" \
      --field-id "$STATUS_FIELD_ID" --single-select-option-id "$OPTION_ID"

`<issue-url>` is the child's full GitHub issue URL. Because the board is
user/org-level, a cross-repo `owner/repo#N` child is added by its own repo's issue
URL — the same call works regardless of which repo the issue lives in.

### Set Status on an item already on the board

When the issue was added earlier (close -> `Done`; work-start -> `In Progress` —
set by `/resume-initiative --start` or `/work-issue`), resolve its item id by
content URL first:

    ITEM_ID=$(gh project item-list <N> --owner <owner> --format json -L 200 \
      --jq '.items[] | select(.content.url=="<issue-url>") | .id')

then `item-edit` as above. (`item-list` defaults to 30 items; pass `-L` generously.
Best-effort: if the item isn't in the fetched page, WARN and skip.)

### Failure semantics

Every `gh project` call here is **best-effort**. Any failure — missing `project`
scope, unreachable board, GraphQL error, absent `Status` field — is a WARN, never a
block: the underlying `create_issue` / `link_sub_issue` / `close_issue` /
`/resume-initiative --start` / `/work-issue` operation still succeeds. The
`## Children` mirror is the source of truth; a degraded board never blocks an
initiative operation.
