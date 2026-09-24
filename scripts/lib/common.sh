#!/usr/bin/env bash
# common.sh - shared helpers for agent-issue-tracker scripts and hooks.
#
# Source it (never execute it):
#   . "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"              # from scripts/
#   . "$(cd "$(dirname "$0")" && pwd)/../scripts/lib/common.sh"   # from hooks/
#
# Contract: bash 3.2 + BSD userland safe. Every function prints its result
# on stdout; a function that finds nothing prints nothing and returns 1.
# Nothing here calls exit and nothing here sets -e, so callers keep control.

ait_hash() { if command -v shasum >/dev/null 2>&1; then shasum -a 256; else sha256sum; fi; }

ait_json_str() { jq -Rn --arg v "${1-}" '$v'; }

# ait_run_capped <secs> <cmd...> - timeout(1) / gtimeout, else a watchdog.
# The watchdog's stdout goes to /dev/null on purpose: holding the caller's
# command-substitution pipe open would block every call for the full cap.
ait_run_capped() {
  local cap="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then timeout "$cap" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$cap" "$@"; return $?; fi
  "$@" &
  local pid=$! watcher status
  ( sleep "$cap"; kill -TERM "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  watcher=$!
  wait "$pid" 2>/dev/null
  status=$?
  kill -TERM "$watcher" 2>/dev/null
  wait "$watcher" 2>/dev/null
  return $status
}

# GNU first: on Linux, BSD-style `stat -f %m` succeeds with filesystem info
# (garbage here) instead of failing, so it cannot be the probe.
ait_file_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null; }

ait_iso_from_epoch() {
  local out
  out="$(date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    || out="$(date -u -r "$1" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" \
    || return 1
  [ -n "$out" ] || return 1
  printf '%s' "$out"
}

ait_epoch_from_iso() {
  local out
  out="$(date -u -d "$1" +%s 2>/dev/null)" \
    || out="$(date -u -j -f %Y-%m-%dT%H:%M:%SZ "$1" +%s 2>/dev/null)" \
    || return 1
  [ -n "$out" ] || return 1
  printf '%s' "$out"
}

# ait_ref_from_branch <branch> - issue ref parsed from the branch leaf:
# a Jira key, else a leading number, else an `issue-N` segment. Same rules
# the session-title hook has always used.
#
# The leading-number rule only fires when the number is immediately followed
# by `-` or end-of-string, so a version segment like `1.8.0` (leading digit
# run followed by `.`) is never mistaken for an issue number.
ait_ref_from_branch() {
  local leaf="${1##*/}" ref="" num=""
  ref="$(printf '%s' "$leaf" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)" || true
  if [ -z "$ref" ]; then
    num="$(printf '%s' "$leaf" | grep -oE '^[0-9]+(-|$)' | head -1)" || true
    num="${num%-}"
    if [ -z "$num" ]; then
      num="$(printf '%s' "$leaf" | grep -oE '(^|-)issue-?[0-9]+' | grep -oE '[0-9]+' | head -1)" || true
    fi
    [ -n "$num" ] && ref="#$num"
  fi
  [ -n "$ref" ] || return 1
  printf '%s' "$ref"
}

# Mirrors ait_ref_from_branch's tightened leading-number rule: the strip only
# fires when the number is immediately followed by `-` or end-of-string, so
# `release/1.8.0` keeps its leading `1` untouched (it slugs as `1.8.0`,
# hook-identical - dots are never converted here).
ait_slug_from_branch() {
  local leaf="${1##*/}" out
  out="$(printf '%s' "$leaf" \
    | sed -E 's/[A-Z][A-Z0-9]+-[0-9]+//; s/^[0-9]+(-|$)//; s/(^|-)issue-?[0-9]+//' \
    | sed -E 's/^[-_]+//; s/[-_]+$//' | cut -c1-24)"
  printf '%s' "$out"
}

# ait_norm_path <path> - absolute, forward slashes, Windows drive form under
# MSYS (pwd -W), so one directory hashes the same from Git Bash and from a
# Windows-launched process. Non-directories are returned unchanged.
ait_norm_path() {
  local p="$1"
  [ -d "$p" ] || { printf '%s' "$p"; return 0; }
  ( cd "$p" 2>/dev/null && { pwd -W 2>/dev/null || pwd; } ) | tr '\\' '/' | tr -d '\n'
}

# ait_main_repo [<dir>] - root of the main checkout shared by all worktrees.
ait_main_repo() {
  local d="${1:-.}" gcd
  gcd="$(git -C "$d" rev-parse --git-common-dir 2>/dev/null)" || return 1
  [ -n "$gcd" ] || return 1
  case "$gcd" in /* | [A-Za-z]:*) ;; *) gcd="$d/$gcd" ;; esac
  gcd="$(ait_norm_path "$gcd")"
  printf '%s' "${gcd%/*}"
}

# ait_project_key [<dir>] - <basename>-<sha256(main repo path)[0:8]>.
ait_project_key() {
  local d="${1:-.}" root name h
  root="$(ait_main_repo "$d")" || root="$(ait_norm_path "$d")"
  name="$(basename "$root" | tr -cd 'A-Za-z0-9._-' | cut -c1-40)"
  h="$(printf '%s' "$root" | ait_hash | cut -c1-8)"
  printf '%s-%s' "${name:-project}" "$h"
}

ait_state_dir() {
  local root="${AIT_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/agent-issue-tracker}"
  local dir="$root/$(ait_project_key "${1:-.}")"
  mkdir -p "$dir" 2>/dev/null
  printf '%s' "$dir"
}

ait_config_path() {
  local d="${1:-.}" top
  if [ -f "$d/.claude/issue-tracker.yaml" ]; then
    printf '%s' "$d/.claude/issue-tracker.yaml"
    return 0
  fi
  top="$(git -C "$d" rev-parse --show-toplevel 2>/dev/null)" || top=""
  if [ -n "$top" ] && [ -f "$top/.claude/issue-tracker.yaml" ]; then
    printf '%s' "$top/.claude/issue-tracker.yaml"
    return 0
  fi
  return 1
}

# ait_config_get <key> [<config>] - `backend`, `github.repo`, `loops.interval`.
# A flat reader for the plugin's own schema: a top-level `key: value`, or a
# two-space-indented `sub: value` under `section:`. Quoted values keep
# everything inside the quotes; unquoted values lose a trailing ` # comment`.
# Not a YAML parser, and not meant to be one.
ait_config_get() {
  local key="$1" cfg="${2:-}" section="" sub="" val=""
  [ -n "$cfg" ] || cfg="$(ait_config_path)" || return 1
  case "$key" in
    *.*)
      section="${key%%.*}"
      sub="${key#*.}"
      val="$(awk -v s="$section" -v k="$sub" '
        /^[A-Za-z_]+:/ { insec = ($0 ~ "^" s ":"); next }
        insec && $0 ~ "^  " k ":" { sub("^  " k ":[ \t]*", ""); print; exit }' "$cfg")"
      ;;
    *)
      val="$(awk -v k="$key" '$0 ~ "^" k ":" { sub("^" k ":[ \t]*", ""); print; exit }' "$cfg")"
      ;;
  esac
  val="$(printf '%s' "$val" | sed -E 's/^"([^"]*)".*$/\1/; t; s/^'"'"'([^'"'"']*)'"'"'.*$/\1/; t; s/[[:space:]]+#.*$//; s/[[:space:]]+$//')"
  [ -n "$val" ] || return 1
  printf '%s' "$val"
}

# ait_issue_url <ref> [<config>] - tracker URL for a ref, or nothing.
ait_issue_url() {
  local ref="$1" cfg="${2:-}" backend repo site
  [ -n "$cfg" ] || cfg="$(ait_config_path)" || return 1
  backend="$(ait_config_get backend "$cfg")" || return 1
  case "$backend" in
    github)
      repo="$(ait_config_get github.repo "$cfg")" || return 1
      case "$ref" in
        \#[0-9]*) printf 'https://github.com/%s/issues/%s' "$repo" "${ref#\#}" ;;
        */*\#[0-9]*) printf 'https://github.com/%s/issues/%s' "${ref%%#*}" "${ref##*#}" ;;
        *) return 1 ;;
      esac
      ;;
    jira)
      site="$(ait_config_get jira.site "$cfg")" || return 1
      case "$ref" in
        [A-Z]*-[0-9]*) printf 'https://%s/browse/%s' "$site" "$ref" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}

true
