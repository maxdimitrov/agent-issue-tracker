#!/usr/bin/env bash
# session-title.sh — SessionStart hook: initiative-aware session titles.
#
# Reads the SessionStart payload on stdin. When the session lives in a project
# with .claude/issue-tracker.yaml, emits
#   {"hookSpecificOutput":{"hookEventName":"SessionStart","sessionTitle":"…"}}
# on stdout. Always exits 0 — every failure path means "leave the title alone".
# Stdout discipline: ONLY the JSON payload may reach stdout; plain stdout from
# a SessionStart hook is injected into the session as context.
#
# Spec: docs/superpowers/specs/2026-07-16-session-titles-design.md

set -u

tmo() { # tmo <seconds> <cmd...> — timeout(1) if available, else run unbounded
  local s="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; else "$@"; fi
}

# --- stage 0: shared helpers (fail-open when the plugin tree is incomplete) --
_ait_lib="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../scripts/lib/common.sh"
[ -f "$_ait_lib" ] || exit 0
# shellcheck source=scripts/lib/common.sh
. "$_ait_lib"

# --- stage 1: recursion + dependency guards -----------------------------------
[ -n "${AIT_TITLE_GUARD:-}" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

# --- stage 2: parse stdin ------------------------------------------------------
payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0
field() { printf '%s' "$payload" | jq -r "$1 // empty" 2>/dev/null || true; }

session_id="$(field '.session_id')"
transcript_path="$(field '.transcript_path')"
cwd="$(field '.cwd')"
src="$(field '.source')"
current_title="$(field '.session_title')"

[ -n "$session_id" ] || exit 0
case "$session_id" in */* | *..*) exit 0 ;; esac
[ -d "$cwd" ] || exit 0
case "$src" in startup | resume) : ;; *) exit 0 ;; esac

# --- stage 3: config gate ------------------------------------------------------
toplevel="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)" || toplevel=""
config=""
if [ -f "$cwd/.claude/issue-tracker.yaml" ]; then
  config="$cwd/.claude/issue-tracker.yaml"
elif [ -n "$toplevel" ] && [ -f "$toplevel/.claude/issue-tracker.yaml" ]; then
  config="$toplevel/.claude/issue-tracker.yaml"
fi
[ -n "$config" ] || exit 0
grep -Eq '^session_titles:[[:space:]]*false[[:space:]]*$' "$config" && exit 0

# --- stage 4: manual-rename gate ------------------------------------------------
state_dir="${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker/session-titles"
mkdir -p "$state_dir" 2>/dev/null || exit 0
state_file="$state_dir/$session_id"
pin_file="$state_dir/$session_id.pinned"

[ -f "$pin_file" ] && exit 0
if [ -f "$state_file" ]; then
  last_set="$(cat "$state_file" 2>/dev/null)"
  if [ -n "$current_title" ] && [ "$current_title" != "$last_set" ]; then
    : >"$pin_file"
    exit 0
  fi
elif [ -n "$current_title" ]; then
  # A title we did not set. The platform default is "<dir>-xx"; anything else
  # is a manual name — pin the session and never touch it.
  case "$current_title" in
    "$(basename "$cwd")"-[a-z0-9][a-z0-9]) : ;;
    *)
      : >"$pin_file"
      exit 0
      ;;
  esac
fi

# --- stage 5: base ref + slug from branch, transcript fallback -----------------
branch="$(git -C "$cwd" branch --show-current 2>/dev/null)" || branch=""
ref=""
slug=""
if [ -n "$branch" ]; then
  ref="$(ait_ref_from_branch "$branch")" || ref=""
  slug="$(ait_slug_from_branch "$branch")"
fi
# The configured backend decides what a ref looks like from here on:
# `#N` on GitHub; `KEY-N` on Jira, narrowed to `jira.project` when it is set.
backend="$(grep -E '^backend:' "$config" 2>/dev/null | head -1 | awk '{print $2}')" || backend=""
jira_key=""
if [ "$backend" = "jira" ]; then
  jira_key="$(awk '/^jira:/{f=1; next} /^[^[:space:]#]/{f=0} f && /^[[:space:]]+project:/{print $2; exit}' \
    "$config" 2>/dev/null | tr -d '"'"'")" || jira_key=""
  case "$jira_key" in *[!A-Z0-9]*) jira_key="" ;; esac
fi
case "$backend" in
  github) ref_shape='#[0-9]+' ;;
  jira) ref_shape="${jira_key:-[A-Z][A-Z0-9]+}-[0-9]+" ;;
  *) ref_shape="" ;;
esac
if [ -z "$ref" ] && [ -n "$ref_shape" ] && [ -f "$transcript_path" ]; then
  # Only text the operator typed counts: user records, string content or text
  # blocks. Assistant prose and tool results (order numbers, statement lines,
  # other repos' issue links) are exactly the noise that produced wrong titles.
  # Tokens split on anything outside [A-Za-z0-9#_-] and must match whole, so
  # "#302-1234567" is not "#302".
  ref="$(tail -c 200000 "$transcript_path" 2>/dev/null | jq -R -r '
      fromjson? | select(.type == "user") | .message.content
      | if type == "string" then .
        elif type == "array" then (.[] | select(type == "object" and .type == "text") | .text)
        else empty end' 2>/dev/null \
    | tr -c 'A-Za-z0-9#_\n-' '\n' | grep -xE "$ref_shape" | tail -1)" || true
  slug=""
fi

# --- machine-block second pass (stage 6 helper) ---------------------------------
# New-shape epics carry no "- **Current branch:**" line in the body (that
# signal now lives in the marker-tagged machine-block comment). Legacy epics
# (body has a "## Status block" line) are filtered out before the cap below --
# they can never match the machine-block path, so skipping them here spends
# the 10-epic budget only on epics that could plausibly match, cutting the
# worst-case SessionStart latency. Bounded to the first 10 (post-filter)
# epics; every gh call is tmo-bounded; any failure yields no match and never
# breaks the title. Trust: authorAssociation must be one of
# OWNER/MEMBER/COLLABORATOR; the earliest qualifying marker comment wins.
machine_block_epic_line() {
  local mb_epics_json="$1" mb_branch="$2" mb_cwd="$3"
  local mb_num="" mb_title="" mb_comments="" mb_body="" mb_phases=""
  local mb_next="" mb_checked=0 mb_ref="" mb_refnum="" mb_state="" mb_line=""
  while IFS=$'\t' read -r mb_num mb_title; do
    [ -n "$mb_num" ] || continue
    mb_comments="$(cd "$mb_cwd" && tmo 5 gh issue view "$mb_num" --json comments 2>/dev/null)" \
      || mb_comments=""
    [ -n "$mb_comments" ] || continue
    mb_body="$(printf '%s' "$mb_comments" | jq -r --arg b "$mb_branch" '
      [.comments[]
       | select(.body | contains("<!-- agent-issue-tracker:machine-block -->"))
       | select(.authorAssociation == "OWNER" or .authorAssociation == "MEMBER"
                or .authorAssociation == "COLLABORATOR")][0] // empty
      | select(.body | split("\n") | map(rtrimstr("\r")) | index("- " + $b))
      | .body' 2>/dev/null)" || mb_body=""
    [ -n "$mb_body" ] || continue
    mb_phases="$(printf '%s' "$mb_body" | awk '/^## Phases/{f=1; next} /^## /{if (f) exit} f')"
    mb_next=""
    mb_checked=0
    for mb_ref in $(printf '%s' "$mb_phases" | grep -oE '#[0-9]+'); do
      mb_checked=$((mb_checked + 1))
      [ "$mb_checked" -le 5 ] || break
      mb_refnum="${mb_ref#\#}"
      mb_state="$(cd "$mb_cwd" && tmo 5 gh issue view "$mb_refnum" --json state --jq .state \
        2>/dev/null)" || mb_state=""
      if [ "$mb_state" = "OPEN" ]; then
        mb_next="$mb_ref"
        break
      fi
    done
    mb_line="$(printf '#%s\t%s\t%s' "$mb_num" "$mb_title" "$mb_next")"
    break
  done < <(printf '%s' "$mb_epics_json" | jq -r '
      [.[] | select((.body // "") | contains("## Status block") | not)][:10][]
      | [(.number|tostring), .title] | @tsv')
  printf '%s' "$mb_line"
}

# --- stage 6: epic enrichment (GitHub backend only; 24h cache; read-only) -------
epic_next=""
if [ "$backend" = "github" ] && [ -n "$branch" ] && command -v gh >/dev/null 2>&1; then
  cache_dir="$state_dir/epic-cache"
  mkdir -p "$cache_dir" 2>/dev/null || true
  key="$(printf '%s|%s' "${toplevel:-$cwd}" "$branch" | ait_hash | cut -c1-16)"
  cache_file="$cache_dir/$key"
  fresh=""
  if [ -f "$cache_file" ]; then
    cm="$(ait_file_mtime "$cache_file")" || cm=0
    case "$cm" in '' | *[!0-9]*) cm=0 ;; esac
    [ $(($(date +%s) - cm)) -lt 86400 ] && fresh=1
  fi
  if [ -z "$fresh" ]; then
    epics_json="$(cd "$cwd" && tmo 5 gh issue list --label epic --state open \
      --json number,title,body --limit 50 2>/dev/null)" || epics_json=""
    if [ -n "$epics_json" ]; then
      printf '%s' "$epics_json" | jq -r --arg b "$branch" '
        [.[] | select(any(.body | split("\n")[]; rtrimstr("\r") == ("- **Current branch:** " + $b)))][0] // empty
        | [("#" + (.number | tostring)), .title,
           ((.body | capture("- \\*\\*Next up:\\*\\* (?<n>[^\n]+)").n) // "")]
        | @tsv' >"$cache_file" 2>/dev/null || : >"$cache_file"
    else
      : >"$cache_file"
    fi
    # New-shape epics have no body "- **Current branch:**" line (it now lives
    # in the machine-block comment). When the legacy body-match above found
    # nothing, run a bounded second pass over the same epic list.
    if [ ! -s "$cache_file" ] && [ -n "$epics_json" ]; then
      mb_line="$(machine_block_epic_line "$epics_json" "$branch" "$cwd")" || mb_line=""
      [ -n "$mb_line" ] && printf '%s' "$mb_line" >"$cache_file" 2>/dev/null
    fi
  fi
  if [ -s "$cache_file" ]; then
    e_ref="$(cut -f1 "$cache_file" 2>/dev/null)"
    e_title="$(cut -f2 "$cache_file" 2>/dev/null)"
    e_next_line="$(cut -f3 "$cache_file" 2>/dev/null)"
    if [ -n "$e_ref" ]; then
      ref="$e_ref"
      slug="$(printf '%s' "$e_title" | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/^epic: *//; s/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-24)"
      epic_next="$(printf '%s' "$e_next_line" \
        | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | head -1)" || true
    fi
  fi
fi

# --- stage 7: AI tail (resume only; hard-bounded; recursion-guarded) -------------
ai_tail=""
if [ "$src" = "resume" ] && [ -z "${AIT_TITLE_NO_AI:-}" ] && [ -s "$transcript_path" ] \
  && command -v claude >/dev/null 2>&1; then
  excerpt="$(tail -c 200000 "$transcript_path" 2>/dev/null | jq -R -r '
      fromjson? | select(.type == "user" or .type == "assistant") | .message.content
      | if type == "string" then .
        elif type == "array" then (.[] | select(type == "object" and .type == "text") | .text)
        else empty end' 2>/dev/null | tail -n 40 | tail -c 4000)" || excerpt=""
  if [ -n "$excerpt" ]; then
    prompt="Output ONLY a lowercase phrase of at most 5 words describing what this coding session is working on right now. No punctuation, no quotes."
    # Exit status is deliberately ignored: on Windows `claude -p` prints the
    # phrase and then overruns the budget on process exit (status 124). The
    # output is validated on shape below; an empty or rambling answer drops.
    ai_tail="$(printf '%s\n\n<session-excerpt>\n%s\n</session-excerpt>\n' "$prompt" "$excerpt" \
      | AIT_TITLE_GUARD=1 tmo 8 claude -p --model haiku 2>/dev/null)" || :
    ai_tail="$(printf '%s' "$ai_tail" | head -1 \
      | sed -E "s/^[\"' ]+//; s/[\"' .]+\$//")"
    words="$(printf '%s' "$ai_tail" | wc -w | tr -d ' ')"
    if [ "${words:-0}" -gt 5 ]; then
      ai_tail=""
    else
      ai_tail="$(printf '%s' "$ai_tail" | cut -c1-40)"
    fi
  fi
fi

# No idle marker: the hook fires at start/resume, the one moment a session
# stops being idle, and cannot retitle afterwards, so an `idle Nd` part would
# be wrong for the whole live session.

# --- stage 8: compose + emit ------------------------------------------------------
[ -n "$ref$ai_tail" ] || exit 0
anchor="$ref"
if [ -n "$ref" ] && [ -n "$slug" ]; then anchor="$ref $slug"; fi

title=""
for part in "$anchor" "$ai_tail" "${epic_next:+next $epic_next}"; do
  [ -n "$part" ] || continue
  # ai_tail beats "next <ref>": once ai_tail is in, drop epic_next.
  case "$part" in "next "*) [ -n "$ai_tail" ] && continue ;; esac
  if [ -n "$title" ]; then candidate="$title · $part"; else candidate="$part"; fi
  [ "${#candidate}" -le 64 ] || break
  title="$candidate"
done
[ -n "$title" ] || exit 0

printf '%s' "$title" >"$state_file"
jq -cn --arg t "$title" '{hookSpecificOutput:{hookEventName:"SessionStart",sessionTitle:$t}}'
exit 0
