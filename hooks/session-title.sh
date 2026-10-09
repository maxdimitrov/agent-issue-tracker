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
# Resolve once (a resolve costs ~0.7s on Git Bash); it fails exactly when
# there is no project file, which is the "not configured" gate.
eff="$( cd "$cwd" 2>/dev/null && ait_config_resolve 2>/dev/null )" || exit 0
cfg_get() { printf '%s\n' "$eff" | _ait_config_pick "$1" 2>/dev/null || true; }
[ "$(cfg_get session_titles)" = "false" ] && exit 0

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
backend="$(cfg_get backend)"
jira_key=""
if [ "$backend" = "jira" ]; then
  jira_key="$(cfg_get jira.project)"
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

# --- stage 6: epic enrichment (GitHub backend only; 24h cache; read-only) -------
# The lookup itself lives in scripts/lib/common.sh (ait_branch_epic), shared
# with hooks/nudge.sh.
epic_next=""
if [ "$backend" = "github" ] && [ -n "$branch" ]; then
  e_line="$(ait_branch_epic "$cwd" "$branch" "$toplevel")" || e_line=""
  if [ -n "$e_line" ]; then
    e_ref="$(printf '%s\n' "$e_line" | cut -f1)"
    e_title="$(printf '%s\n' "$e_line" | cut -f2)"
    e_next_line="$(printf '%s\n' "$e_line" | cut -f3)"
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
