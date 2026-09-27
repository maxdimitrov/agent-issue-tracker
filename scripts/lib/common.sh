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

# ait_uri_encode <s> - percent-encodes <s> for a URL query value (jq @uri:
# everything but A-Z a-z 0-9 -_.~ is escaped, so `/`, `+`, `#`, `&` and
# spaces in a branch name cannot break the query). -j prints no trailing
# newline, so a native Windows jq cannot leave a stray CR in the capture.
ait_uri_encode() { jq -jn --arg s "${1-}" '$s | @uri'; }

# ait_json_type <json> - prints the JSON type of <json> (array, object,
# string, number, boolean, null); prints nothing and returns 1 when <json>
# is empty or does not parse as exactly one JSON value.
ait_json_type() {
  local t
  [ -n "${1-}" ] || return 1
  t="$(jq -jse 'if length == 1 then .[0] | type else error("not one value") end' <<<"$1" 2>/dev/null)" || return 1
  [ -n "$t" ] || return 1
  printf '%s' "$t"
}

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

# ait_spill_json <dir> <name> <json> - writes <json> to <dir>/<name>.json,
# for a caller to load back with `jq --slurpfile name <path>` (binding
# $name to a one-element array wrapping the parsed content, i.e. the
# caller reads it back as $name[0]). Keeps a large fragment (many PRs,
# review threads, deep-dive detail) off argv, where the OS process
# argument limit -- about 32 KB on Windows -- can make the jq invocation
# itself silently never start and print nothing, breaking a collector's
# one-JSON-object-on-stdout contract. Prints the file path on success;
# prints nothing and returns 1 if <dir> is empty or the write fails, so a
# caller can fall back to a small default written to its own temp file.
ait_spill_json() {
  local dir="$1" name="$2" content="$3" f
  [ -n "$dir" ] || return 1
  f="$dir/$name.json"
  printf '%s' "$content" >"$f" 2>/dev/null || return 1
  printf '%s' "$f"
}

# ait_gh_out <secs> <cmd...> - stdout only when the capped call exits 0;
# empty otherwise, and always returns 0 itself. `gh` writes error bodies
# (GraphQL errors, 403s, truncated output from a killed timeout) to stdout
# even on a non-zero exit, so a bare `cmd || echo ""` still lets that body
# through via command substitution -- this keeps only real data and lets a
# caller tell "no data" from "malformed data" by checking emptiness alone.
ait_gh_out() {
  local cap="$1"
  shift
  local out rc
  out="$(ait_run_capped "$cap" "$@" 2>/dev/null)"
  rc=$?
  [ "$rc" -eq 0 ] && printf '%s' "$out"
  return 0
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
#
# Pure bash (`[[ =~ ]]`, POSIX ERE, leftmost-longest like the grep -oE it
# replaced): no subprocess per call, which matters when a collector maps
# a hundred PR branches. The patterns live in variables so bash 3.2 and 4+
# parse them the same way; LC_ALL=C keeps [A-Z] ASCII-only.
ait_ref_from_branch() {
  local leaf="${1##*/}" re LC_ALL=C
  re='[A-Z][A-Z0-9]+-[0-9]+'
  if [[ $leaf =~ $re ]]; then printf '%s' "${BASH_REMATCH[0]}"; return 0; fi
  re='^([0-9]+)(-|$)'
  if [[ $leaf =~ $re ]]; then printf '#%s' "${BASH_REMATCH[1]}"; return 0; fi
  re='(^|-)issue-?([0-9]+)'
  if [[ $leaf =~ $re ]]; then printf '#%s' "${BASH_REMATCH[2]}"; return 0; fi
  return 1
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
  ( cd "$p" 2>/dev/null && { pwd -W 2>/dev/null || pwd; } ) | tr "\\\\" "/" | tr -d '\n'
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
  local dir
  dir="$root/$(ait_project_key "${1:-.}")"
  mkdir -p "$dir" 2>/dev/null
  printf '%s' "$dir"
}

# ait_config_path [<dir>] - the nearest .claude/issue-tracker.yaml: <dir>, then
# each ancestor up to its git toplevel, then (from a linked worktree) the main
# checkout root, then the ancestors above the toplevel. The walk above the
# toplevel stops below $HOME: a $HOME/.claude/issue-tracker.yaml is never picked
# up by it (a global fallback is #7's call, not this lookup's).
ait_config_path() {
  local d="${1:-.}" f=".claude/issue-tracker.yaml" p top main home inrepo next
  if [ -f "$d/$f" ]; then
    printf '%s' "$d/$f"
    return 0
  fi
  p="$(ait_norm_path "$d")"
  top="$(git -C "$d" rev-parse --show-toplevel 2>/dev/null)" || top=""
  main=""
  if [ -n "$top" ]; then
    top="$(ait_norm_path "$top")"
    main="$(ait_main_repo "$d")" || main=""
    [ "$main" = "$top" ] && main=""
  fi
  home=""
  [ -n "${HOME:-}" ] && home="$(ait_norm_path "$HOME")"
  inrepo="${top:+1}"
  while :; do
    [ -z "$inrepo" ] && [ -n "$home" ] && [ "$p" = "$home" ] && return 1
    if [ -f "$p/$f" ]; then
      printf '%s' "$p/$f"
      return 0
    fi
    if [ -n "$inrepo" ] && [ "$p" = "$top" ]; then
      inrepo=""
      if [ -n "$main" ] && [ -f "$main/$f" ]; then
        printf '%s' "$main/$f"
        return 0
      fi
    fi
    next="${p%/*}"
    [ "$next" = "$p" ] && return 1
    p="$next"
  done
}

# --- config resolution (#7): global base layer + env overrides ---------------
# The effective config is the project file (ait_config_path) merged over
# $HOME/.claude/issue-tracker.yaml by top-level key, then the four
# TRACKER_*_OVERRIDE leaves. The global file never activates on its own: no
# project file means not configured. README "Where the config is found".

# _ait_config_wellformed <file> - every line is blank, a comment, a top-level
# `key:` line, an indented line or a top-level list item.
_ait_config_wellformed() {
  awk '/^[[:space:]]*$/ || /^[[:space:]]*#/ || /^[A-Za-z_][A-Za-z0-9_]*:/ || /^[[:space:]]/ || /^- / { next }
       { bad = 1; exit }
       END { exit bad }' "$1"
}

# _ait_config_keys <file> - its top-level keys, in file order, each once.
_ait_config_keys() {
  awk '/^[A-Za-z_][A-Za-z0-9_]*:/ { k = $0; sub(/:.*/, "", k); if (!seen[k]++) print k }' "$1"
}

# _ait_config_merge <project> [<global>] - the project's blocks in project
# order, then the global's blocks for keys the project lacks, in global order.
# A block is a top-level `key:` line plus everything up to the next one;
# comments and blank lines between blocks travel with the block after them.
# schema_version never comes from the global file.
_ait_config_merge() {
  awk '
    function close_block() {
      # A key repeated within one file keeps its first block (the old reader
      # returned the first value).
      if (key != "" && !has[f, key]) { body[f, key] = buf; order[f, ++n[f]] = key; has[f, key] = 1 }
      key = ""; buf = ""
    }
    FNR == 1 { if (NR > 1) close_block(); f++; pend = "" }
    /^[A-Za-z_][A-Za-z0-9_]*:/ {
      close_block()
      key = $0; sub(/:.*/, "", key)
      buf = pend $0 "\n"; pend = ""
      next
    }
    /^[[:space:]]*$/ || /^#/ { pend = pend $0 "\n"; next }
    { if (key == "") pend = pend $0 "\n"; else { buf = buf pend $0 "\n"; pend = "" } }
    END {
      close_block()
      for (i = 1; i <= n[1]; i++) printf "%s", body[1, order[1, i]]
      for (i = 1; i <= n[2]; i++) {
        k = order[2, i]
        if (k == "schema_version" || has[1, k]) continue
        printf "%s", body[2, k]
      }
    }' "$@"
}

# _ait_config_set_leaf <key> <value> - stdin YAML with one leaf set: a
# top-level `key: value`, or `  sub: value` under `section:`. Replaces the
# line when present, appends it to the section (or the file) when not. A value
# holding `#` or `: ` is double-quoted so ait_config_get reads it back whole.
_ait_config_set_leaf() {
  local key="$1" val="$2" section="" sub=""
  case "$val" in *'#'* | *': '*) val="\"$val\"" ;; esac
  case "$key" in *.*) section="${key%%.*}"; sub="${key#*.}" ;; *) sub="$key" ;; esac
  awk -v s="$section" -v k="$sub" -v v="$val" '
    function emit_missing() {
      if (done) return
      if (s == "") print k ": " v
      else if (insec) print "  " k ": " v
      else { print s ":"; print "  " k ": " v }
      done = 1
    }
    s == "" && $0 ~ "^" k ":" { print k ": " v; done = 1; next }
    s != "" && /^[A-Za-z_][A-Za-z0-9_]*:/ {
      if (insec) emit_missing()
      insec = ($0 ~ "^" s ":")
      print; next
    }
    s != "" && insec && $0 ~ "^  " k ":" { print "  " k ": " v; done = 1; next }
    { print }
    END { emit_missing() }'
}

# _ait_config_env - stdin YAML with the non-empty TRACKER_*_OVERRIDE leaves set.
_ait_config_env() {
  local out
  out="$(cat)"
  [ -n "${TRACKER_BACKEND_OVERRIDE:-}" ] &&
    out="$(printf '%s\n' "$out" | _ait_config_set_leaf backend "$TRACKER_BACKEND_OVERRIDE")"
  [ -n "${TRACKER_GITHUB_REPO_OVERRIDE:-}" ] &&
    out="$(printf '%s\n' "$out" | _ait_config_set_leaf github.repo "$TRACKER_GITHUB_REPO_OVERRIDE")"
  [ -n "${TRACKER_JIRA_SITE_OVERRIDE:-}" ] &&
    out="$(printf '%s\n' "$out" | _ait_config_set_leaf jira.site "$TRACKER_JIRA_SITE_OVERRIDE")"
  [ -n "${TRACKER_JIRA_PROJECT_OVERRIDE:-}" ] &&
    out="$(printf '%s\n' "$out" | _ait_config_set_leaf jira.project "$TRACKER_JIRA_PROJECT_OVERRIDE")"
  printf '%s\n' "$out"
}

# _ait_config_global <project> - the global file to merge under <project>, or
# nothing. It must exist, not be <project> itself, be well-formed, and carry
# the project's schema_version (or none). A skipped file gets one WARN on stderr.
_ait_config_global() {
  local proj="$1" g pv gv
  [ -n "${HOME:-}" ] || return 0
  g="$HOME/.claude/issue-tracker.yaml"
  { [ -f "$g" ] && [ -r "$g" ]; } || return 0
  [ "$(ait_norm_path "${g%/*}")" = "$(ait_norm_path "${proj%/*}")" ] && return 0
  if ! _ait_config_wellformed "$g"; then
    printf 'WARN: %s is malformed; ignoring it\n' "$g" >&2
    return 0
  fi
  pv="$(ait_config_get schema_version "$proj")" || pv=""
  gv="$(ait_config_get schema_version "$g")" || gv=""
  if [ -n "$gv" ] && [ "$gv" != "$pv" ]; then
    printf 'WARN: %s has schema_version %s but the project has %s; ignoring it\n' \
      "$g" "$gv" "${pv:-none}" >&2
    return 0
  fi
  printf '%s' "$g"
}

# ait_config_resolve [<dir>] - the effective config as YAML on stdout; 1 with
# no output when no project file is found.
ait_config_resolve() {
  local proj glob
  proj="$(ait_config_path "${1:-$PWD}")" || return 1
  [ -r "$proj" ] || return 1
  glob="$(_ait_config_global "$proj")"
  _ait_config_merge "$proj" ${glob:+"$glob"} | _ait_config_env
}

# ait_config_provenance [<dir>] - `key<TAB>source` per effective top-level key
# (project:<path> | global:<path>), then one `section.key<TAB>env:<VAR>` line
# per applied override; 1 when not configured.
ait_config_provenance() {
  local proj glob k var key
  proj="$(ait_config_path "${1:-$PWD}")" || return 1
  [ -r "$proj" ] || return 1
  glob="$(_ait_config_global "$proj" 2>/dev/null)"
  _ait_config_keys "$proj" | while IFS= read -r k; do printf '%s\tproject:%s\n' "$k" "$proj"; done
  if [ -n "$glob" ]; then
    _ait_config_keys "$glob" | while IFS= read -r k; do
      [ "$k" = schema_version ] && continue
      _ait_config_keys "$proj" | grep -qx "$k" && continue
      printf '%s\tglobal:%s\n' "$k" "$glob"
    done
  fi
  for var in TRACKER_BACKEND_OVERRIDE:backend TRACKER_GITHUB_REPO_OVERRIDE:github.repo \
             TRACKER_JIRA_SITE_OVERRIDE:jira.site TRACKER_JIRA_PROJECT_OVERRIDE:jira.project; do
    key="${var#*:}"; var="${var%%:*}"
    [ -n "${!var:-}" ] && printf '%s\tenv:%s\n' "$key" "$var"
  done
  return 0
}

# ait_config_get <key> [<config>] - `backend`, `github.repo`, `loops.interval`.
# A flat reader for the plugin's own schema: a top-level `key: value`, or a
# two-space-indented `sub: value` under `section:`. Quoted values keep
# everything inside the quotes; unquoted values lose a trailing ` # comment`.
# Not a YAML parser, and not meant to be one. Without <config> it reads the
# effective config for $PWD (ait_config_resolve); with one, that file only.
# A caller reading several keys resolves once and pipes the text to
# _ait_config_pick instead: each resolve costs ~0.7s on Git Bash.
ait_config_get() {
  local key="$1" cfg="${2:-}" text
  if [ -n "$cfg" ]; then
    text="$(cat "$cfg" 2>/dev/null)" || return 1
  else
    text="$(ait_config_resolve "$PWD")" || return 1
  fi
  printf '%s\n' "$text" | _ait_config_pick "$key"
}

# _ait_config_pick <key> - the value of <key> in the YAML on stdin (the
# ait_config_get rules); 1 when it is absent or empty.
_ait_config_pick() {
  local key="$1" section="" sub="" val=""
  case "$key" in
    *.*)
      section="${key%%.*}"
      sub="${key#*.}"
      val="$(awk -v s="$section" -v k="$sub" '
        /^[A-Za-z_]+:/ { insec = ($0 ~ "^" s ":"); next }
        insec && $0 ~ "^  " k ":" { sub("^  " k ":[ \t]*", ""); print; exit }')"
      ;;
    *)
      val="$(awk -v k="$key" '$0 ~ "^" k ":" { sub("^" k ":[ \t]*", ""); print; exit }')"
      ;;
  esac
  val="$(printf '%s' "$val" | sed -E 's/^"([^"]*)".*$/\1/; t; s/^'"'"'([^'"'"']*)'"'"'.*$/\1/; t; s/[[:space:]]+#.*$//; s/[[:space:]]+$//')"
  [ -n "$val" ] || return 1
  printf '%s' "$val"
}

# ait_issue_url <ref> [<config>] - tracker URL for a ref, or nothing. Without
# <config>, the effective config for $PWD.
ait_issue_url() {
  local ref="$1" cfg="${2:-}" text
  if [ -n "$cfg" ]; then
    text="$(cat "$cfg" 2>/dev/null)" || return 1
  else
    text="$(ait_config_resolve "$PWD")" || return 1
  fi
  _ait_issue_url_from "$ref" "$text"
}

# _ait_issue_url_from <ref> <yaml> - ait_issue_url over already-read config
# text, for callers that resolved once.
_ait_issue_url_from() {
  local ref="$1" text="$2" backend repo site
  backend="$(printf '%s\n' "$text" | _ait_config_pick backend)" || return 1
  case "$backend" in
    github)
      repo="$(printf '%s\n' "$text" | _ait_config_pick github.repo)" || return 1
      case "$ref" in
        \#[0-9]*) printf 'https://github.com/%s/issues/%s' "$repo" "${ref#\#}" ;;
        */*\#[0-9]*) printf 'https://github.com/%s/issues/%s' "${ref%%#*}" "${ref##*#}" ;;
        *) return 1 ;;
      esac
      ;;
    jira)
      site="$(printf '%s\n' "$text" | _ait_config_pick jira.site)" || return 1
      case "$ref" in
        [A-Z]*-[0-9]*) printf 'https://%s/browse/%s' "$site" "$ref" ;;
        *) return 1 ;;
      esac
      ;;
    *) return 1 ;;
  esac
}

true
