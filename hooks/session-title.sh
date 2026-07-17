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

# --- portability helpers (macOS bash 3.2 + BSD userland, and Linux) ----------
tmo() { # tmo <seconds> <cmd...> — timeout(1) if available, else run unbounded
  local s="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$s" "$@"; else "$@"; fi
}
file_mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }
hash_key() { if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi; }

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
  leaf="${branch##*/}"
  ref="$(printf '%s' "$leaf" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)" || true
  if [ -z "$ref" ]; then
    num="$(printf '%s' "$leaf" | grep -oE '^[0-9]+' | head -1)" || true
    [ -z "$num" ] && num="$(printf '%s' "$leaf" | grep -oE '(^|-)issue-?[0-9]+' | grep -oE '[0-9]+' | head -1)" || true
    [ -n "$num" ] && ref="#$num"
  fi
  slug="$(printf '%s' "$leaf" \
    | sed -E 's/[A-Z][A-Z0-9]+-[0-9]+//; s/^[0-9]+//; s/(^|-)issue-?[0-9]+//' \
    | sed -E 's/^[-_]+//; s/[-_]+$//' | cut -c1-24)"
fi
if [ -z "$ref" ] && [ -f "$transcript_path" ]; then
  ref="$(tail -c 200000 "$transcript_path" 2>/dev/null \
    | grep -oE '(#[0-9]+|[A-Z][A-Z0-9]+-[0-9]+)' | tail -1)" || true
  slug=""
fi

# --- stage 6: epic enrichment (populated in a later task) ----------------------
epic_next=""

# --- stage 7: AI tail (populated in a later task) -------------------------------
ai_tail=""

# --- stage 8: idle marker --------------------------------------------------------
idle=""
if [ -f "$transcript_path" ]; then
  m="$(file_mtime "$transcript_path")" || m=""
  if [ -n "$m" ]; then
    days=$((($(date +%s) - m) / 86400))
    [ "$days" -ge 1 ] && idle="idle ${days}d"
  fi
fi

# --- stage 9: compose + emit ------------------------------------------------------
[ -n "$ref$ai_tail" ] || exit 0
anchor="$ref"
if [ -n "$ref" ] && [ -n "$slug" ]; then anchor="$ref $slug"; fi

title=""
for part in "$anchor" "$ai_tail" "${epic_next:+next $epic_next}" "$idle"; do
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
