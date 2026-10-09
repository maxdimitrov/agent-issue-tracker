#!/usr/bin/env bash
# nudge.sh -- SessionStart (resume) + Stop hook: one-line tracker nudges.
#
# Prints nothing, or exactly one {"systemMessage":"[tracker] ..."} object, and
# always exits 0. systemMessage reaches the user only: this hook never blocks
# a turn, never adds model context and never emits sessionTitle
# (session-title.sh owns the title).
#
# Each nudge shows at most once per (session, kind). The marker is created
# before the message is printed, so a state dir that cannot be written means
# silence, never a repeat.
#
# Switches: AIT_NUDGES=0 (all off), AIT_NUDGES_OFF=resume,deferral (named
# off), config key `nudges: false` (all off for the project).
#
# Spec: docs/superpowers/specs/2026-10-09-tracker-nudges-design.md

set -u

_ait_lib="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/../scripts/lib/common.sh"
[ -f "$_ait_lib" ] || exit 0
# shellcheck source=scripts/lib/common.sh
. "$_ait_lib"

[ "${AIT_NUDGES:-}" = "0" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null)" || exit 0
[ -n "$payload" ] || exit 0
field() { printf '%s' "$payload" | jq -r "$1 // empty" 2>/dev/null || true; }

# kind_off <kind> -- 0 when <kind> is listed in AIT_NUDGES_OFF.
kind_off() {
  case ",$(printf '%s' "${AIT_NUDGES_OFF:-}" | tr -d ' ')," in
    *",$1,"*) return 0 ;;
  esac
  return 1
}

backend=""
# config_gate <cwd> -- 0 when <cwd> is in a configured project whose config
# does not say `nudges: false`; sets $backend.
config_gate() {
  local eff
  [ -n "$1" ] && [ -d "$1" ] || return 1
  eff="$( cd "$1" 2>/dev/null && ait_config_resolve 2>/dev/null )" || return 1
  [ "$(printf '%s\n' "$eff" | _ait_config_pick nudges 2>/dev/null)" = "false" ] && return 1
  backend="$(printf '%s\n' "$eff" | _ait_config_pick backend 2>/dev/null)" || backend=""
  return 0
}

marker_dir="${CLAUDE_PLUGIN_DATA:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker}/nudges"
session_id=""

# claim <kind> -- create this session's marker for <kind> exclusively; 1 when
# it already exists or cannot be written.
claim() {
  mkdir -p "$marker_dir" 2>/dev/null || return 1
  ( set -C; : >"$marker_dir/$session_id.$1" ) 2>/dev/null
}

emit() { jq -cn --arg m "[tracker] $1" '{systemMessage: $m}'; }

# Deferral phrasing (followup-tracking's lexicon, multi-word only: a bare
# "follow-up" or "TODO" is too common to mean anything).
LEXICON="out of scope for this (pr|change|issue)"
LEXICON="$LEXICON|(in|for) a (separate|follow-?up|later) (pr|change|issue)"
LEXICON="$LEXICON|follow-?up (issue|ticket|pr)|later phase"
LEXICON="$LEXICON|leaving .{1,40} for (later|a follow-?up|the next pass|another pr)"
LEXICON="$LEXICON|defer(red|ring)? .{1,40} to (a|the) (follow-?up|later|separate|next)"
LEXICON="$LEXICON|we'?ll handle .{1,40} (later|separately|in a separate)"

# Whole-session facts from a bounded transcript tail: prints "nudge" when the
# session committed or opened a PR and filed nothing. Sub-agent records are
# skipped; a truncated first line is dropped by fromjson?.
# shellcheck disable=SC2016
TRANSCRIPT_JQ='
  [inputs | fromjson? | select(type == "object" and (.isSidechain // false) != true)] as $r
  | [$r[] | select(.type == "assistant") | .message.content | arrays | .[]
     | select(type == "object" and .type == "tool_use")] as $tu
  | [$tu[] | select(.name == "Bash" or .name == "PowerShell")
     | .input.command | strings] as $cmds
  | [$r[] | select(.type == "user") | .message.content
     | if type == "string" then .
       elif type == "array" then (.[] | select(type == "object" and .type == "text") | .text | strings)
       else empty end] as $said
  | (any($cmds[]; test("\\bgit\\b[^\\n|;&]*\\bcommit\\b") or test("\\bgh\\b[^\\n|;&]*\\bpr create\\b"))) as $work
  | (any($cmds[]; test("\\bgh\\b[^\\n|;&]*\\bissue create\\b"))
     or any($tu[]; .name == "Skill"
            and ((.input.skill // "") | test("(file-followup|file-bug|file-feature|followup-tracking|bug-tracking|feature-request)$")))
     or any($said[]; test("(^|<command-name>)/(agent-issue-tracker:)?file-(followup|bug|feature)"))) as $filed
  | if $work and ($filed | not) then "nudge" else empty end'

deferral_flow() {
  local cwd transcript verdict
  kind_off deferral && exit 0
  [ "$(field '.stop_hook_active')" = "true" ] && exit 0
  field '.last_assistant_message' | grep -qiE "$LEXICON" || exit 0
  cwd="$(field '.cwd')"
  config_gate "$cwd" || exit 0
  [ -e "$marker_dir/$session_id.deferral" ] && exit 0
  transcript="$(field '.transcript_path')"
  [ -n "$transcript" ] && [ -r "$transcript" ] || exit 0
  verdict="$(tail -c 4000000 "$transcript" 2>/dev/null | jq -R -r -n "$TRANSCRIPT_JQ" 2>/dev/null)" || verdict=""
  [ "$verdict" = "nudge" ] || exit 0
  claim deferral || exit 0
  emit "Scope was deferred this turn and nothing was filed -- /file-followup?"
}

event="$(field '.hook_event_name')"
session_id="$(field '.session_id')"
[ -n "$session_id" ] || exit 0
case "$session_id" in */* | *..* | *\\*) exit 0 ;; esac

case "$event" in
  Stop) deferral_flow ;;
  SessionStart) exit 0 ;;
  *) exit 0 ;;
esac
exit 0
