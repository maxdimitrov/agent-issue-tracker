#!/usr/bin/env bash
# tracker-brief-collect.sh -- deterministic local + git-host facts for /tracker-brief.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout. Missing
# data is null / [] / false, never an error and never a hang.
#
# Read-only EXCEPT `--commit-run`, which stamps the window file. Tracker
# activity (issues, comments) is NOT collected here -- the command reads it
# through the backend contract ops -- so `ledger[].tracker_status` is left
# null for the command to fill.
#
# Usage:
#   tracker-brief-collect.sh                 # emit facts (read-only)
#   tracker-brief-collect.sh --commit-run    # stamp last_run=now
#
# Env:
#   AIT_STATE_DIR    state root (default ${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker)
#   AIT_TIMEOUT      per-call cap, seconds (default 20)
#   AIT_SINCE        ISO-8601 override for the window start
#   AIT_STALE_DAYS   worktree staleness threshold (default 14; non-numeric -> default + errors[])
#   AIT_MAX_PR_DEEP  max PRs to fetch review threads + CI for (default 12; non-numeric -> default + errors[])

# shellcheck disable=SC2016
set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

CAP="${AIT_TIMEOUT:-20}"
ERRORS='[]'
note_err() { ERRORS="$(jq -c --arg e "$1" '. + [$e]' <<<"$ERRORS" 2>/dev/null || echo "$ERRORS")"; }
iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
is_array() { jq -e 'type == "array"' >/dev/null 2>&1 <<<"$1"; }
is_object() { jq -e 'type == "object"' >/dev/null 2>&1 <<<"$1"; }
# ensure_json <value> <fallback> [<label>] - value if it parses as JSON,
# else fallback; notes an errors[] entry when a non-empty label is given.
# Last line of defense before the final emit: every fragment gets one pass
# through this so a single malformed capture can never blank the whole
# script's stdout.
ensure_json() {
  local v="$1" fb="$2" label="${3:-}"
  if [ -n "$v" ] && jq -e . >/dev/null 2>&1 <<<"$v"; then
    printf '%s' "$v"
  else
    [ -n "$label" ] && note_err "invalid JSON for $label -- using fallback"
    printf '%s' "$fb"
  fi
}

if ! command -v jq >/dev/null 2>&1; then
  printf '{"fatal":"jq not installed","generated_at":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 0
fi

# A bad numeric override degrades to the default with an errors[] entry
# rather than breaking the jq slice / --argjson downstream. ${VAR:-} (not
# bare $VAR) is used throughout: `set -u` is on, and AIT_STALE_DAYS /
# AIT_MAX_PR_DEEP are ordinarily unset, not just empty. The case switches on
# a separate defaulted copy so an unset/empty override (which legitimately
# matches the default branch) does not then re-read the still-empty
# original variable when assigning.
AIT_STALE_DAYS="${AIT_STALE_DAYS:-}"
stale_in="${AIT_STALE_DAYS:-14}"
case "$stale_in" in
  ''|*[!0-9]*)
    STALE_DAYS=14
    [ -n "$AIT_STALE_DAYS" ] && note_err "AIT_STALE_DAYS '$AIT_STALE_DAYS' is not a number -- using default 14" ;;
  *) STALE_DAYS="$stale_in" ;;
esac
AIT_MAX_PR_DEEP="${AIT_MAX_PR_DEEP:-}"
max_deep_in="${AIT_MAX_PR_DEEP:-12}"
case "$max_deep_in" in
  ''|*[!0-9]*)
    MAX_PR_DEEP=12
    [ -n "$AIT_MAX_PR_DEEP" ] && note_err "AIT_MAX_PR_DEEP '$AIT_MAX_PR_DEEP' is not a number -- using default 12" ;;
  *) MAX_PR_DEEP="$max_deep_in" ;;
esac

STATE_DIR="$(ait_state_dir "$PWD")"
STATE="$STATE_DIR/tracker-brief.json"
CONFIG="$(ait_config_path "$PWD")" || CONFIG=""
BACKEND=""; GH_REPO=""; JIRA_SITE=""
if [ -n "$CONFIG" ]; then
  BACKEND="$(ait_config_get backend "$CONFIG")" || BACKEND=""
  GH_REPO="$(ait_config_get github.repo "$CONFIG")" || GH_REPO=""
  JIRA_SITE="$(ait_config_get jira.site "$CONFIG")" || JIRA_SITE=""
fi

# ------------------------------------------------------------ --commit-run
if [ "${1:-}" = "--commit-run" ]; then
  NOW="$(iso_now)"
  PREV="$(jq -r '.last_run // empty' "$STATE" 2>/dev/null)"
  jq -n --arg now "$NOW" --arg prev "${PREV:-}" \
    '{last_run: $now, previous_run: (if $prev == "" then null else $prev end)}' \
    >"$STATE.tmp" 2>/dev/null && mv "$STATE.tmp" "$STATE" 2>/dev/null
  jq -n --arg now "$NOW" --arg p "$STATE" '{committed: $now, state_file: $p}'
  exit 0
fi

# ------------------------------------------------------------------ window
NOW_EPOCH="$(date -u +%s)"
LAST_RUN="$(jq -r '.last_run // empty' "$STATE" 2>/dev/null)"
FIRST_RUN=true
if [ -n "${AIT_SINCE:-}" ]; then
  SINCE="$AIT_SINCE"; FIRST_RUN=false
elif [ -n "$LAST_RUN" ]; then
  SINCE="$LAST_RUN"; FIRST_RUN=false
else
  SINCE="$(ait_iso_from_epoch $((NOW_EPOCH - 86400)))"
fi
SINCE_EPOCH="$(ait_epoch_from_iso "$SINCE")" || SINCE_EPOCH=0
if [ "$SINCE_EPOCH" -gt 0 ]; then
  WIN_DAYS=$(( (NOW_EPOCH - SINCE_EPOCH) / 86400 ))
else
  WIN_DAYS=1; note_err "could not parse window start '$SINCE'"
fi
SUMMARIZE=false; [ "$WIN_DAYS" -gt 5 ] && SUMMARIZE=true
SINCE_DATE="${SINCE%%T*}"

# ------------------------------------------------------------ repo / viewer
IS_GIT=false; NWO=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  IS_GIT=true
  origin="$(git remote get-url origin 2>/dev/null || echo "")"
  case "$origin" in
    *github.com*)
      NWO="$(printf '%s' "$origin" \
        | sed -E 's#^(git@github\.com:|ssh://git@github\.com/|https://github\.com/)##; s#\.git$##; s#/$##')" ;;
  esac
fi
GH_OK=false; GH_LOGIN=""
if [ -z "$NWO" ]; then
  note_err "no GitHub origin remote -- PR data skipped"
elif ! command -v gh >/dev/null 2>&1; then
  note_err "gh unavailable -- PR data skipped"
else
  GH_LOGIN="$(ait_gh_out "$CAP" gh api user --jq .login)"
  if [ -n "$GH_LOGIN" ]; then GH_OK=true; else note_err "gh api user failed (auth?) -- PR data skipped"; fi
fi

# --------------------------------------------------------------- worktrees
WORKTREES='[]'
if [ "$IS_GIT" = true ]; then
  idx=0
  # Fields are unit-separator- not tab-delimited: `read` with IFS set to a
  # whitespace character (tab included) still collapses runs of it and
  # strips them at field edges, so a detached worktree's empty branch field
  # between two separators silently vanishes and shifts every field after
  # it. Octal \037 is used (not \x1f): a gawk extension is needed for awk
  # itself to interpret a \x escape, and POSIX/macOS awk don't guarantee
  # it -- so the byte is expanded by bash's $'...' quoting before either
  # awk or read ever sees a backslash, sidestepping the portability gap.
  while IFS=$'\037' read -r wpath wbranch wdet; do
    [ -n "$wpath" ] || continue
    wpath="$(ait_norm_path "$wpath")"
    primary=false; [ "$idx" -eq 0 ] && primary=true
    idx=$((idx + 1))
    ref=""; [ -n "$wbranch" ] && { ref="$(ait_ref_from_branch "$wbranch")" || ref=""; }
    dirty="$(git -C "$wpath" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    le="$(git -C "$wpath" log -1 --format=%ct 2>/dev/null)"; [ -n "$le" ] || le=0
    lastsub="$(git -C "$wpath" log -1 --format=%s 2>/dev/null)"
    lastc=""; [ "$le" -gt 0 ] && lastc="$(ait_iso_from_epoch "$le")"
    age=0; [ "$le" -gt 0 ] && age=$(( (NOW_EPOCH - le) / 86400 ))
    stale=false
    if [ "$primary" = false ] && [ "$age" -ge "$STALE_DAYS" ] && [ "${dirty:-0}" -eq 0 ]; then stale=true; fi
    touched=false; [ "$le" -ge "$SINCE_EPOCH" ] && touched=true
    # Ask the git host whether this branch landed. `git merge-base --is-ancestor`
    # is NOT usable: squash/rebase merges rewrite the SHA, so a branch whose PR
    # merged still reports "not an ancestor". The branch->PR lookup has no such
    # blind spot.
    landed=null
    if [ "$GH_OK" = true ] && [ -n "$wbranch" ] && [ "$primary" = false ]; then
      landed_raw="$(ait_gh_out "$CAP" gh pr list --repo "$NWO" --head "$wbranch" --state all \
        --limit 5 --json number,state,mergedAt,title,url)"
      if is_array "$landed_raw"; then
        landed="$(jq -c '([.[] | select(.state == "MERGED")][0]) // .[0] // null' <<<"$landed_raw" 2>/dev/null)"
        [ -n "$landed" ] || landed=null
      else
        note_err "gh pr list --head unusable for $wbranch"
      fi
    fi
    WORKTREES="$(jq -c --arg path "$wpath" --arg branch "$wbranch" --arg ref "$ref" \
      --arg lastsub "$lastsub" --arg lastc "$lastc" \
      --argjson dirty "${dirty:-0}" --argjson age "$age" --argjson detached "$wdet" \
      --argjson stale "$stale" --argjson primary "$primary" --argjson touched "$touched" \
      --argjson landed "$landed" \
      '. + [{path: $path, branch: (if $branch == "" then null else $branch end),
             ref: (if $ref == "" then null else $ref end), detached: $detached,
             primary: $primary, dirty_count: $dirty,
             last_commit: (if $lastc == "" then null else $lastc end),
             last_subject: (if $lastsub == "" then null else $lastsub end),
             idle_days: $age, stale: $stale, touched_in_window: $touched,
             landed_pr: $landed}]' <<<"$WORKTREES")"
  done < <(git worktree list --porcelain 2>/dev/null | awk -v OFS=$'\037' '
    /^worktree /{ if (p != "") print p, b, d; p = substr($0, 10); b = ""; d = "false" }
    /^branch /  { b = substr($0, 8); sub("^refs/heads/", "", b) }
    /^detached/ { d = "true" }
    END         { if (p != "") print p, b, d }')
fi

# --------------------------------------------------------------------- PRs
# Every list is scoped to THIS repo's origin. `gh pr list` is used rather than
# `gh search prs`: the search index lags and `--state=all` is invalid there.
PR_FIELDS='number,title,url,state,isDraft,updatedAt,createdAt,author,headRefName'
gh_prs() { ait_gh_out "$CAP" gh pr list --repo "$NWO" --limit 40 --json "$PR_FIELDS" "$@"; }
AUTHORED='[]'; REVREQ='[]'; MENTIONS='[]'; MERGED='[]'; ALLTIME='[]'
if [ "$GH_OK" = true ]; then
  AUTHORED="$(gh_prs --author @me --state open)"
  is_array "$AUTHORED" || { note_err "gh pr list (authored) unusable"; AUTHORED='[]'; }
  REVREQ="$(gh_prs --search 'review-requested:@me' --state open)"
  is_array "$REVREQ" || { note_err "gh pr list (review-requested) unusable"; REVREQ='[]'; }
  MENTIONS="$(gh_prs --search 'mentions:@me' --state open)"
  is_array "$MENTIONS" || { note_err "gh pr list (mentions) unusable"; MENTIONS='[]'; }
  MERGED="$(gh_prs --author @me --state merged --search "merged:>=$SINCE_DATE")"
  is_array "$MERGED" || { note_err "gh pr list (merged) unusable"; MERGED='[]'; }
  # Unwindowed on purpose: a PR merged weeks ago whose issue never closed is
  # drift, and a windowed list cannot see it.
  ALLTIME="$(ait_gh_out "$CAP" gh pr list --repo "$NWO" --author @me --state all --limit 100 --json "$PR_FIELDS")"
  is_array "$ALLTIME" || { note_err "gh pr list (all-time) unusable"; ALLTIME='[]'; }

  # Branch -> ref map, built with the SAME rule a worktree's ref uses
  # (ait_ref_from_branch), so a PR and a worktree on the same branch never
  # disagree -- e.g. "release/1.8.0" is a version segment to both, never
  # "#1" to one and null to the other. Only a title-based fallback (a `[#N]`
  # or Jira key literally in the PR title) is left for jq to compute, since
  # that has no bash-side equivalent to reuse.
  BRANCH_REFS='{}'
  # tr strips a trailing \r: a native Windows jq build opens its stdout in
  # text mode, so this multi-line stream arrives \r\n-terminated. `$(...)`
  # only strips trailing newlines off the WHOLE capture, not the \r glued
  # to the end of every line but the last, so every branch but the last in
  # sorted order would otherwise carry a stray \r into its map key below
  # and never match a PR's (\r-free) headRefName lookup. Same fix already
  # applied to the TARGETS stream further down.
  branches="$(jq -r -n --argjson a "$AUTHORED" --argjson b "$REVREQ" --argjson c "$MENTIONS" \
    --argjson d "$MERGED" --argjson e "$ALLTIME" \
    '[$a[], $b[], $c[], $d[], $e[]] | map(.headRefName // empty) | map(select(. != "")) | unique | .[]' 2>/dev/null \
    | tr -d '\r')"
  while IFS= read -r br; do
    [ -n "$br" ] || continue
    r="$(ait_ref_from_branch "$br")" || continue
    [ -n "$r" ] || continue
    BRANCH_REFS="$(jq -c --arg b "$br" --arg r "$r" '. + {($b): $r}' <<<"$BRANCH_REFS" 2>/dev/null)"
    [ -n "$BRANCH_REFS" ] || BRANCH_REFS='{}'
  done <<<"$branches"

  REF_JQ='
    def title_ref:
      ([(.title // "") | scan("[A-Z][A-Z0-9]+-[0-9]+")] | first)
      // ([(.title // "") | scan("#[0-9]+")] | first)
      // null;
    def refof: ($branch_refs[(.headRefName // "")] // title_ref);
    def with_refs: map(. + {ref: refof});
  '
  AUTHORED="$(jq -c --argjson branch_refs "$BRANCH_REFS" "$REF_JQ with_refs" <<<"$AUTHORED")"
  REVREQ="$(jq -c --argjson branch_refs "$BRANCH_REFS" "$REF_JQ with_refs" <<<"$REVREQ")"
  MENTIONS="$(jq -c --argjson branch_refs "$BRANCH_REFS" "$REF_JQ with_refs" <<<"$MENTIONS")"
  MERGED="$(jq -c --argjson branch_refs "$BRANCH_REFS" "$REF_JQ with_refs" <<<"$MERGED")"
  ALLTIME="$(jq -c --argjson branch_refs "$BRANCH_REFS" "$REF_JQ with_refs" <<<"$ALLTIME")"
fi

# Deep detail for PRs that are mine or awaiting me. `gh pr checks` and
# statusCheckRollup 403 on a fine-grained PAT (checks is Apps-only), so CI
# comes from the Actions API, which actions:read covers.
DEEP='[]'
if [ "$GH_OK" = true ]; then
  # Process substitution is avoided here: under a non-interactive MSYS bash
  # (as pytest launches it on Windows) /dev/fd is not wired up, so `<(...)`
  # silently fails and every target would be lost. Pass both arrays in as
  # jq variables instead. MAX_PR_DEEP is bound as a number, not spliced into
  # the filter text, since it may come straight from an env var.
  TARGETS="$(jq -n -c --argjson au "$AUTHORED" --argjson rr "$REVREQ" --argjson n "$MAX_PR_DEEP" \
    '($au + $rr) | unique_by(.url) | .[0:$n]' 2>/dev/null)"
  [ -n "$TARGETS" ] || TARGETS='[]'
  while IFS=$'\037' read -r num url title pref; do
    [ -n "$num" ] || continue
    meta="$(ait_gh_out "$CAP" gh pr view "$num" --repo "$NWO" \
      --json reviewDecision,headRefName,isDraft,mergeable,updatedAt,comments,reviews)"
    # is_object rejects both an empty capture (the gh call failed -- ait_gh_out
    # already discarded its stdout) and a non-empty-but-truncated/malformed
    # one (a capped call killed mid-write), so `--argjson meta` below can
    # never be handed anything that would make it -- and the whole script's
    # stdout -- come up empty.
    if ! is_object "$meta"; then
      note_err "gh pr view failed for $NWO#$num"
      continue
    fi
    owner="${NWO%%/*}"; name="${NWO##*/}"
    threads="$(ait_gh_out "$CAP" gh api graphql -f query='
      query($owner:String!,$name:String!,$num:Int!){
        repository(owner:$owner,name:$name){
          pullRequest(number:$num){
            reviewThreads(first:100){nodes{
              isResolved isOutdated
              comments(first:1){nodes{author{login} body url createdAt}}}}}}}' \
      -F owner="$owner" -F name="$name" -F num="$num")"
    unresolved=0; threadlist='[]'
    if is_object "$threads"; then
      unresolved="$(jq '[.data.repository.pullRequest.reviewThreads.nodes[]? | select(.isResolved == false)] | length' <<<"$threads" 2>/dev/null || echo 0)"
      threadlist="$(jq -c '[.data.repository.pullRequest.reviewThreads.nodes[]?
        | select(.isResolved == false)
        | {author: (.comments.nodes[0].author.login // null), url: (.comments.nodes[0].url // null),
           created: (.comments.nodes[0].createdAt // null), outdated: .isOutdated,
           excerpt: ((.comments.nodes[0].body // "")[0:280])}]' <<<"$threads" 2>/dev/null || echo '[]')"
    else
      note_err "graphql threads failed for $NWO#$num"
    fi
    head="$(jq -r '.headRefName // empty' <<<"$meta")"
    ci_status=null
    if [ -n "$head" ]; then
      runs="$(ait_gh_out "$CAP" gh api "repos/$NWO/actions/runs?branch=$head&per_page=1")"
      if is_object "$runs"; then
        ci_status="$(jq -c '(.workflow_runs[0] // {})
          | {status: (.status // null), conclusion: (.conclusion // null), name: (.name // null),
             run_url: (.html_url // null), started: (.run_started_at // null)}' <<<"$runs" 2>/dev/null || echo null)"
      else
        note_err "actions API failed for $NWO ($head)"
      fi
    fi
    new_comments="$(jq -c --arg since "$SINCE" --arg me "$GH_LOGIN" \
      '[((.comments // []) + (.reviews // []))[]
        | select((.createdAt // .submittedAt // "") > $since)
        | select((.author.login // "") != $me)
        | {author: (.author.login // null), created: (.createdAt // .submittedAt),
           url: (.url // null), state: (.state // null), excerpt: ((.body // "")[0:280])}]' <<<"$meta" 2>/dev/null || echo '[]')"
    deep_next="$(jq -c --arg nwo "$NWO" --argjson num "$num" --arg url "$url" --arg title "$title" \
      --arg head "$head" --arg pref "$pref" --argjson unresolved "${unresolved:-0}" \
      --argjson threads "$threadlist" --argjson ci "${ci_status:-null}" \
      --argjson newc "${new_comments:-[]}" --argjson meta "$meta" \
      '. + [{repo: $nwo, number: $num, url: $url, title: $title, headRefName: $head,
             ref: (if $pref == "" then null else $pref end),
             review_decision: ($meta.reviewDecision // null), is_draft: ($meta.isDraft // false),
             mergeable: ($meta.mergeable // null), updated: ($meta.updatedAt // null),
             unresolved_threads: $unresolved, threads: $threads, ci: $ci, new_comments: $newc}]' \
      <<<"$DEEP" 2>/dev/null)"
    if [ -n "$deep_next" ]; then
      DEEP="$deep_next"
    else
      note_err "failed to record pr_detail for $NWO#$num"
    fi
  # tr strips a trailing \r: a native Windows jq build opens its stdout in
  # text mode, so each line of this multi-line stream arrives \r\n-
  # terminated and the \r would otherwise stick to the last (pref) field.
  # The join separator is \037 (not a real tab): the same IFS-whitespace
  # collapse hazard fixed for the worktree parser above applies here too --
  # an empty pref (no ref on the PR) sits in the middle of the record.
  done < <(jq -r '.[] | [(.number | tostring), .url, .title, (.ref // "")] | join("\u001f")' <<<"$TARGETS" 2>/dev/null | tr -d '\r')
fi

# ------------------------------------------------------------ resume notes
RESUME='[]'
if [ -d "$STATE_DIR/resume" ]; then
  while IFS= read -r f; do
    [ -f "$f" ] || continue
    first="$(head -1 "$f" 2>/dev/null)"
    ref="$(printf '%s' "$first" | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | head -1)" || ref=""
    mt="$(ait_file_mtime "$f")"; [ -n "$mt" ] || mt=0
    age=$(( (NOW_EPOCH - mt) / 86400 ))
    RESUME="$(jq -c --arg p "$f" --arg s "$(basename "$f" .md)" --arg r "$ref" \
      --arg w "$(ait_iso_from_epoch "$mt")" --argjson age "$age" \
      '. + [{path: $p, slug: $s, ref: (if $r == "" then null else $r end), written: $w, age_days: $age}]' <<<"$RESUME")"
  done < <(find "$STATE_DIR/resume" -maxdepth 1 -name '*.md' 2>/dev/null | sort)
fi

# ------------------------------------------------------------------- loops
LOOPS='[]'
if [ -d "$STATE_DIR/loops" ]; then
  LOOPS="$(cat "$STATE_DIR"/loops/*.json 2>/dev/null | jq -s -c --arg since "$SINCE" '
    [.[] | {id, mode, ref, branch, state, stop_reason, started,
            iterations_count: ((.iterations // []) | length),
            last_action: ((.iterations // []) | last | .action // null),
            actions_in_window: [(.iterations // [])[] | select(.at >= $since and .noop != true)],
            prs_opened: (.prs_opened // [])}]' 2>/dev/null || echo '[]')"
  [ -n "$LOOPS" ] || LOOPS='[]'
fi

# ------------------------------------------------------------------ ledger
# Join every surface on an EXTRACTED ref compared for equality -- never a
# substring test: "#604" is inside "[#6041] ..." and would steal that PR.
LEDGER="$(jq -n --argjson wt "$WORKTREES" --argjson rn "$RESUME" --argjson lp "$LOOPS" \
  --argjson at "$ALLTIME" --argjson dp "$DEEP" \
  --arg backend "$BACKEND" --arg gh_repo "$GH_REPO" --arg jira "$JIRA_SITE" '
  def url($k):
    if $backend == "github" and $gh_repo != "" and ($k | startswith("#"))
      then "https://github.com/" + $gh_repo + "/issues/" + ($k | ltrimstr("#"))
    elif $backend == "jira" and $jira != "" and ($k | test("^[A-Z][A-Z0-9]+-[0-9]+$"))
      then "https://" + $jira + "/browse/" + $k
    else null end;
  ([ ($wt[] | .ref), ($rn[] | .ref), ($lp[] | .ref), ($at[] | .ref) ] | map(select(. != null)) | unique) as $keys
  | [ $keys[] as $k
      | ([$at[] | select(.ref == $k)]) as $prs
      | ([$lp[] | select(.ref == $k)]) as $loops
      | { ref: $k, ticket_url: url($k),
          worktree:    ([$wt[] | select(.ref == $k)] | first // null),
          resume_note: ([$rn[] | select(.ref == $k)] | first // null),
          loops: $loops,
          open_pr:   ([$prs[] | select(.state == "OPEN")] | first // null),
          merged_pr: ([$prs[] | select(.state == "MERGED")] | first // null),
          closed_pr: ([$prs[] | select(.state == "CLOSED")] | first // null),
          detail:    ([$dp[] | select(.ref == $k)] | first // null),
          tracker_status: null }
      # All-time PR history pulls in every issue ever shipped. A row is only
      # worth a verdict when something is still lying around.
      | .actionable = (.worktree != null or .resume_note != null or .open_pr != null
                       or any(.loops[]; .state == "live")) ]' 2>/dev/null)"
LEDGER="${LEDGER:-[]}"

ORPHANS="$(jq -c '[.[] | select(.primary == false and (.detached == true or .ref == null))]' <<<"$WORKTREES" 2>/dev/null || echo '[]')"

# Last-line-of-defense validation: every fragment must parse as JSON before
# it can reach the final emit, so one malformed capture that slipped past
# its own guard above degrades to [] with an errors[] entry instead of
# making the whole `jq -n --argjson` call below fail and print nothing.
WORKTREES="$(ensure_json "$WORKTREES" '[]' worktrees)"
RESUME="$(ensure_json "$RESUME" '[]' resume_notes)"
LOOPS="$(ensure_json "$LOOPS" '[]' loops)"
AUTHORED="$(ensure_json "$AUTHORED" '[]' prs.authored_open)"
REVREQ="$(ensure_json "$REVREQ" '[]' prs.review_requested)"
MENTIONS="$(ensure_json "$MENTIONS" '[]' prs.mentions)"
MERGED="$(ensure_json "$MERGED" '[]' prs.merged_in_window)"
ALLTIME="$(ensure_json "$ALLTIME" '[]' prs.all_time_authored)"
DEEP="$(ensure_json "$DEEP" '[]' pr_detail)"
LEDGER="$(ensure_json "$LEDGER" '[]' ledger)"
ORPHANS="$(ensure_json "$ORPHANS" '[]' orphan_worktrees)"
ERRORS="$(ensure_json "$ERRORS" '[]' "")"

jq -n \
  --arg generated "$(iso_now)" --arg since "$SINCE" --arg last "${LAST_RUN:-}" \
  --arg state "$STATE" --arg state_dir "$STATE_DIR" --arg config "$CONFIG" \
  --arg backend "$BACKEND" --arg nwo "$NWO" --arg login "$GH_LOGIN" \
  --argjson first "$FIRST_RUN" --argjson days "$WIN_DAYS" --argjson summ "$SUMMARIZE" \
  --argjson ghok "$GH_OK" --argjson stale_days "$STALE_DAYS" \
  --argjson wt "$WORKTREES" --argjson rn "$RESUME" --argjson lp "$LOOPS" \
  --argjson au "$AUTHORED" --argjson rr "$REVREQ" --argjson mn "$MENTIONS" \
  --argjson mg "$MERGED" --argjson at "$ALLTIME" --argjson dp "$DEEP" \
  --argjson ledger "$LEDGER" --argjson orphans "$ORPHANS" --argjson errors "$ERRORS" \
  '{
    generated_at: $generated,
    window: {since: $since, last_run: (if $last == "" then null else $last end),
             first_run: $first, days: $days, summarize_mode: $summ, state_file: $state},
    viewer: {gh_login: (if $login == "" then null else $login end), gh_available: $ghok},
    config: {path: (if $config == "" then null else $config end),
             backend: (if $backend == "" then null else $backend end),
             repo: (if $nwo == "" then null else $nwo end),
             state_dir: $state_dir, stale_days: $stale_days},
    worktrees: $wt,
    resume_notes: $rn,
    loops: $lp,
    prs: {authored_open: $au, review_requested: $rr, mentions: $mn,
          merged_in_window: $mg, all_time_authored: $at},
    pr_detail: $dp,
    ledger: $ledger,
    orphan_worktrees: $orphans,
    errors: $errors
  }'

exit 0
