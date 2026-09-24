#!/usr/bin/env bash
# session-brief-collect.sh -- deterministic facts for /session-brief.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout. Missing
# data is null / [] / false, never an error and never a hang. Read-only with
# respect to git, the git host and the repo; the only write is mkdir -p on
# the state directory so the resume note has somewhere to land.
#
# Env:
#   AIT_STATE_DIR      state root (default ${XDG_CACHE_HOME:-~/.cache}/agent-issue-tracker)
#   AIT_TIMEOUT        per-network-call cap in seconds (default 15)
#   AIT_TRANSCRIPT     explicit transcript path (skips discovery)
#   CLAUDE_CONFIG_DIR  where the Claude config tree lives (default $HOME/.claude)

set -uo pipefail
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

CAP="${AIT_TIMEOUT:-15}"

if ! command -v jq >/dev/null 2>&1; then
  printf '{"error":"jq not found on PATH","session":null,"repo":null,"git":null,"ticket":null,"pr":null,"ci":null,"review":null,"handoff":null,"loop":null,"config":null}\n'
  exit 0
fi
have_gh=false
command -v gh >/dev/null 2>&1 && have_gh=true

CWD="$(ait_norm_path "$PWD")"
CONFIG="$(ait_config_path "$PWD")" || CONFIG=""
BACKEND=""
[ -n "$CONFIG" ] && { BACKEND="$(ait_config_get backend "$CONFIG")" || BACKEND=""; }
STATE_DIR="$(ait_state_dir "$PWD")"

# ------------------------------------------------------------- repo / git
IS_GIT=false; ROOT=null; ROOT_RAW=""; IS_WORKTREE=false; MAIN_REPO=null; MAIN_RAW=""
if git rev-parse --git-dir >/dev/null 2>&1; then
  IS_GIT=true
  ROOT_RAW="$(ait_norm_path "$(git rev-parse --show-toplevel 2>/dev/null)")"
  ROOT="$(ait_json_str "$ROOT_RAW")"
  MAIN_RAW="$(ait_main_repo "$PWD")" || MAIN_RAW="$ROOT_RAW"
  MAIN_REPO="$(ait_json_str "$MAIN_RAW")"
  [ "$MAIN_RAW" != "$ROOT_RAW" ] && IS_WORKTREE=true
fi

BRANCH=null; BRANCH_RAW=""; DETACHED=false; BASE=null; BASE_RAW=""; ON_BASE=false
AHEAD=0; BEHIND=0; DIRTY_COUNT=0; DIRTY_FILES='[]'; LAST_COMMIT=null; COMMITS='[]'
if [ "$IS_GIT" = true ]; then
  if BRANCH_RAW="$(git symbolic-ref --short -q HEAD 2>/dev/null)"; then
    BRANCH="$(ait_json_str "$BRANCH_RAW")"
  else
    DETACHED=true
    BRANCH_RAW="$(git rev-parse --short HEAD 2>/dev/null || echo "")"
    BRANCH="$(ait_json_str "$BRANCH_RAW")"
  fi
  # origin/HEAD names the default branch when the clone recorded it; else
  # probe the usual names and take the one this branch diverged from last.
  BASE_RAW="$(git symbolic-ref --short -q refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')" || BASE_RAW=""
  if [ -z "$BASE_RAW" ]; then
    best=-1
    for c in develop staging master main production; do
      git show-ref --verify --quiet "refs/remotes/origin/$c" || continue
      n="$(git rev-list --count "origin/$c..HEAD" 2>/dev/null || echo "")"
      [ -z "$n" ] && continue
      if [ "$best" -lt 0 ] || [ "$n" -lt "$best" ]; then best="$n"; BASE_RAW="$c"; fi
    done
  fi
  if [ -n "$BASE_RAW" ]; then
    BASE="$(ait_json_str "$BASE_RAW")"
    [ "$BRANCH_RAW" = "$BASE_RAW" ] && ON_BASE=true
    counts="$(git rev-list --left-right --count "origin/$BASE_RAW...HEAD" 2>/dev/null || echo "")"
    if [ -n "$counts" ]; then
      BEHIND="$(printf '%s' "$counts" | awk '{print $1}')"
      AHEAD="$(printf '%s' "$counts" | awk '{print $2}')"
    fi
    COMMITS="$(git log --format='%h%x1f%s' "origin/$BASE_RAW..HEAD" 2>/dev/null | head -20 \
      | jq -Rn '[inputs | split("\u001f") | {sha: .[0], subject: .[1]}]')"
  fi
  DIRTY_FILES="$(git status --porcelain 2>/dev/null | head -25 \
    | jq -Rn '[inputs | {status: .[0:2], path: .[3:]}]')"
  DIRTY_COUNT="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  LAST_COMMIT="$(git log -1 --format='%h%x1f%s%x1f%cr%x1f%an' 2>/dev/null \
    | jq -Rn 'input? // "" | if . == "" then null else split("\u001f")
        | {sha: .[0], subject: .[1], when: .[2], author: .[3]} end')"
fi

# ------------------------------------------------------------------ ticket
TICKET=null; TICKET_URL=null; TICKET_KEY=""
if [ -n "$BRANCH_RAW" ] && [ "$DETACHED" = false ]; then
  TICKET_KEY="$(ait_ref_from_branch "$BRANCH_RAW")" || TICKET_KEY=""
fi
if [ -n "$TICKET_KEY" ]; then
  TICKET="$(ait_json_str "$TICKET_KEY")"
  if [ -n "$CONFIG" ]; then
    url="$(ait_issue_url "$TICKET_KEY" "$CONFIG")" || url=""
    [ -n "$url" ] && TICKET_URL="$(ait_json_str "$url")"
  fi
fi

# --------------------------------------------------------- PR / CI / review
PR=null; PR_NUMBER=""; CI=null; REVIEW=null; ME=""; NWO=""; NWO_JSON=null
if [ "$IS_GIT" = true ] && [ "$have_gh" = true ] && [ "$DETACHED" = false ]; then
  NWO="$(ait_run_capped "$CAP" gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")"
  [ -n "$NWO" ] && NWO_JSON="$(ait_json_str "$NWO")"

  # statusCheckRollup is deliberately absent: the checks scope is Apps-only,
  # so a fine-grained PAT 403s the whole query. CI comes from the Actions API.
  PR_JSON="$(ait_run_capped "$CAP" gh pr view --json number,url,state,isDraft,mergeable,baseRefName,updatedAt,title,reviewDecision 2>/dev/null || echo "")"
  if [ -n "$PR_JSON" ] && jq -e 'type == "object"' >/dev/null 2>&1 <<<"$PR_JSON"; then
    PR="$PR_JSON"
    PR_NUMBER="$(jq -r '.number // empty' <<<"$PR_JSON")"
  fi

  if [ -n "$NWO" ] && [ -n "$BRANCH_RAW" ]; then
    RUNS="$(ait_run_capped "$CAP" gh api "repos/$NWO/actions/runs?branch=$BRANCH_RAW&per_page=30" 2>/dev/null || echo "")"
    if [ -n "$RUNS" ]; then
      # Newest run per workflow, then a primary. The single newest run is
      # often a skipped bot workflow, not the test suite anyone cares about.
      CI="$(jq '
        [ (.workflow_runs // [])[] | {
            id, workflow: .name, status, conclusion,
            run_url: .html_url, sha: (.head_sha[0:7]), when: .created_at
          } ]
        | group_by(.workflow) | map(sort_by(.when) | last) | sort_by(.when) | reverse
        as $runs
        | ($runs | map(select(.conclusion != "skipped" and .conclusion != "cancelled"))) as $real
        | (($real | map(select(.workflow == "CI")) | first)
           // ($real | map(select(.workflow | test("test|build|ci"; "i"))) | first)
           // ($real | first) // ($runs | first)) as $primary
        | if $primary == null then null else $primary + {all_workflows: $runs} end' <<<"$RUNS" 2>/dev/null || echo null)"
      [ -n "$CI" ] || CI=null
      RUN_ID="$(jq -r '.id // empty' <<<"$CI" 2>/dev/null)"
      CONCL="$(jq -r '.conclusion // empty' <<<"$CI" 2>/dev/null)"
      if [ -n "$RUN_ID" ] && [ "$CONCL" = "failure" ]; then
        FAILED="$(ait_run_capped "$CAP" gh api "repos/$NWO/actions/runs/$RUN_ID/jobs" 2>/dev/null \
          | jq '[(.jobs // [])[] | select(.conclusion == "failure") | {name, url: .html_url}]' 2>/dev/null || echo "[]")"
        CI="$(jq --argjson f "${FAILED:-[]}" '. + {failed_jobs: $f}' <<<"$CI")"
      fi
    fi
  fi

  # Resolved state lives only in GraphQL -- the REST comments API can't see it.
  if [ -n "$NWO" ] && [ -n "$PR_NUMBER" ]; then
    ME="$(ait_run_capped "$CAP" gh api user -q .login 2>/dev/null || echo "")"
    OWNER="${NWO%%/*}"
    REPO="${NWO##*/}"
    THREADS="$(ait_run_capped "$CAP" gh api graphql \
      -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
        reviewThreads(first:60){nodes{isResolved isOutdated path line
          comments(first:25){totalCount nodes{author{login} body createdAt}}}}}}}' \
      -F o="$OWNER" -F r="$REPO" -F n="$PR_NUMBER" 2>/dev/null || echo "")"
    if [ -n "$THREADS" ]; then
      REVIEW="$(jq --arg me "$ME" '
        [ (.data.repository.pullRequest.reviewThreads.nodes // [])[] | {
            resolved: .isResolved,
            outdated: .isOutdated,
            path: .path,
            line: .line,
            author: (.comments.nodes[0].author.login // null),
            excerpt: ((.comments.nodes[0].body // "") | gsub("\\s+"; " ") | .[0:180]),
            replies: ((.comments.totalCount // 1) - 1),
            last_author: (.comments.nodes[-1].author.login // null),
            created: (.comments.nodes[0].createdAt // null)
          } ]
        | map(. + {awaiting_you: ((.resolved | not) and (.last_author != $me))})
        | {threads: ., open_count: (map(select(.resolved | not)) | length),
           resolved_count: (map(select(.resolved)) | length),
           awaiting_you_count: (map(select(.awaiting_you)) | length)}' <<<"$THREADS" 2>/dev/null || echo null)"
      [ -n "$REVIEW" ] || REVIEW=null
    fi
  fi
fi

# -------------------------------------------------------------- transcript
# The harness exposes no session id to Bash. Resolve best-effort, in order:
# explicit env, the undocumented session-id env, then the newest transcript
# whose recent entries record THIS cwd (so sibling-worktree sessions of the
# same repo never read each other's transcript).
TRANSCRIPT=""; SOURCE=""
matches_cwd() { # <file> <normalised-lowercase-path>
  tail -c 300000 "$1" 2>/dev/null \
    | jq -R -r 'fromjson? | .cwd // empty' 2>/dev/null | tail -50 \
    | tr '\\' '/' | tr '[:upper:]' '[:lower:]' | grep -Fxq "$2"
}
if [ -n "${AIT_TRANSCRIPT:-}" ] && [ -f "$AIT_TRANSCRIPT" ]; then
  TRANSCRIPT="$AIT_TRANSCRIPT"; SOURCE="env"
elif [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
  for f in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/projects/*/"$CLAUDE_CODE_SESSION_ID".jsonl; do
    [ -f "$f" ] && { TRANSCRIPT="$f"; SOURCE="session-id"; break; }
  done
fi
if [ -z "$TRANSCRIPT" ]; then
  projects="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects"
  want="$(printf '%s' "$CWD" | tr '[:upper:]' '[:lower:]')"
  main_l="$(printf '%s' "$MAIN_RAW" | tr '[:upper:]' '[:lower:]')"
  if [ -d "$projects" ]; then
    cands="$(find "$projects" -mindepth 2 -maxdepth 2 -name '*.jsonl' -mmin -30 2>/dev/null \
      | while IFS= read -r f; do printf '%s\t%s\n' "$(ait_file_mtime "$f")" "$f"; done \
      | sort -rn | cut -f2-)"
    for target in "$want" "$main_l"; do
      [ -n "$target" ] || continue
      while IFS= read -r f; do
        [ -n "$f" ] || continue
        if matches_cwd "$f" "$target"; then TRANSCRIPT="$f"; SOURCE="discovered"; break; fi
      done <<EOF
$cands
EOF
      [ -n "$TRANSCRIPT" ] && break
    done
  fi
fi

SESSION=null
if [ -n "$TRANSCRIPT" ]; then
  BYTES="$(wc -c < "$TRANSCRIPT" | tr -d ' ')"
  SESSION="$(jq -Rn '[inputs | fromjson?]' "$TRANSCRIPT" 2>/dev/null \
    | jq --arg src "$SOURCE" --arg path "$TRANSCRIPT" --argjson bytes "${BYTES:-0}" '
    def ts: (.timestamp // empty) | sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch empty);
    def txt: if (.message.content | type) == "string" then .message.content
             else ([(.message.content // [])[] | select(type == "object" and .type == "text") | .text] | join(" ")) end;
    def is_prompt: .type == "user" and (.toolUseResult | not) and (.isMeta != true) and (.isSidechain != true);
    def refof: ((capture("(?<k>[A-Z][A-Z0-9]+-[0-9]+)") | .k)
                // ((split("/") | last) | capture("^(?<n>[0-9]+)") | "#" + .n));
    ([.[] | select(is_prompt) | txt | gsub("\\s+"; " ")] | map(select(length > 0))) as $p
    | {
        transcript: $path, transcript_source: $src, transcript_bytes: $bytes,
        title: ([.[] | select(.type == "ai-title") | .aiTitle] | last),
        turns_user: ($p | length),
        turns_assistant: ([.[] | select(.type == "assistant" and (.isSidechain != true))] | length),
        first_prompt: ($p | first | if . == null then null else .[0:400] end),
        last_prompt: ($p | last | if . == null then null else .[0:400] end),
        started: ([.[] | ts] | min),
        last_activity: ([.[] | ts] | max),
        branches_seen: ([.[] | .gitBranch // empty | select(. != "" and . != "HEAD")] | unique),
        cwds_seen: ([.[] | .cwd // empty | select(. != "")] | unique),
        compaction_markers: ([.[] | select((.isCompactSummary == true) or (.type == "summary") or (.subtype == "compact_boundary"))] | length)
      }
    | . + {span_hours: (if .started and .last_activity
             then (((.last_activity - .started) / 360 | floor) / 10) else null end)}
    | . + {tickets_seen: ([.branches_seen[] | refof] | unique)}
  ' 2>/dev/null || echo null)"
  [ -n "$SESSION" ] || SESSION=null
fi

# ----------------------------------------------------------------- handoff
if [ -n "$TICKET_KEY" ]; then
  SLUG="$(printf '%s' "$TICKET_KEY" | tr '/#' '--' | sed 's/^-*//' | tr -cd 'A-Za-z0-9._-')"
elif [ "$IS_GIT" = true ]; then
  SLUG="$(printf '%s-%s' "$(basename "$ROOT_RAW")" "$BRANCH_RAW" | tr '/ ' '--' | tr -cd 'A-Za-z0-9._-')"
else
  SLUG="$(basename "$CWD" | tr -cd 'A-Za-z0-9._-')"
fi
[ -z "$SLUG" ] && SLUG="session"
mkdir -p "$STATE_DIR/resume" 2>/dev/null
RESUME_PATH="$STATE_DIR/resume/$SLUG.md"
RESUME_EXISTS=false; RESUME_AGE=null
if [ -f "$RESUME_PATH" ]; then
  RESUME_EXISTS=true
  RESUME_AGE="$(ait_json_str "$(ait_iso_from_epoch "$(ait_file_mtime "$RESUME_PATH")")")"
fi

# -------------------------------------------------------------------- loop
LOOP=null
if [ -d "$STATE_DIR/loops" ] && [ -n "$BRANCH_RAW" ]; then
  LOOP="$(cat "$STATE_DIR"/loops/*.json 2>/dev/null | jq -s --arg b "$BRANCH_RAW" '
    [.[] | select(.state == "live" and .branch == $b)] | first // null
    | if . == null then null else {
        id, mode, ref, started, cron_job_id, stop_reason,
        iterations: ((.iterations // []) | length),
        last_action: ((.iterations // []) | last | .action // null)
      } end' 2>/dev/null || echo null)"
  [ -n "$LOOP" ] || LOOP=null
fi

# -------------------------------------------------------------------- emit
jq -n \
  --argjson session "${SESSION:-null}" \
  --argjson pr "${PR:-null}" \
  --argjson ci "${CI:-null}" \
  --argjson review "${REVIEW:-null}" \
  --argjson loop "${LOOP:-null}" \
  --argjson dirty_files "${DIRTY_FILES:-[]}" \
  --argjson commits "${COMMITS:-[]}" \
  --argjson last_commit "${LAST_COMMIT:-null}" \
  --argjson root "${ROOT:-null}" \
  --argjson main_repo "${MAIN_REPO:-null}" \
  --argjson nwo "${NWO_JSON:-null}" \
  --argjson branch "${BRANCH:-null}" \
  --argjson base "${BASE:-null}" \
  --argjson ticket "${TICKET:-null}" \
  --argjson ticket_url "${TICKET_URL:-null}" \
  --argjson resume_age "${RESUME_AGE:-null}" \
  --arg cwd "$CWD" \
  --arg resume_path "$RESUME_PATH" \
  --arg me "$ME" \
  --arg config_path "$CONFIG" \
  --arg backend "$BACKEND" \
  --arg state_dir "$STATE_DIR" \
  --argjson is_git "$IS_GIT" \
  --argjson is_worktree "$IS_WORKTREE" \
  --argjson detached "$DETACHED" \
  --argjson on_base "$ON_BASE" \
  --argjson ahead "${AHEAD:-0}" \
  --argjson behind "${BEHIND:-0}" \
  --argjson dirty_count "${DIRTY_COUNT:-0}" \
  --argjson gh "$have_gh" \
  --argjson resume_exists "$RESUME_EXISTS" \
  '{
    session: $session,
    repo: {cwd: $cwd, root: $root, is_git: $is_git, is_worktree: $is_worktree,
           main_repo: $main_repo, name_with_owner: $nwo, gh_available: $gh,
           viewer: (if $me == "" then null else $me end)},
    git: {branch: $branch, base: $base, on_base: $on_base, detached: $detached,
          ahead: $ahead, behind: $behind, dirty_count: $dirty_count,
          dirty_files: $dirty_files, last_commit: $last_commit, commits: $commits},
    ticket: {key: $ticket, url: $ticket_url},
    pr: $pr,
    ci: $ci,
    review: $review,
    handoff: {resume_path: $resume_path, exists: $resume_exists, written: $resume_age},
    loop: $loop,
    config: {path: (if $config_path == "" then null else $config_path end),
             backend: (if $backend == "" then null else $backend end),
             state_dir: $state_dir}
  }'

exit 0
