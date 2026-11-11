#!/usr/bin/env bash
# tracker-init-render.sh -- render the .claude/issue-tracker.yaml that
# /tracker-init writes, from an answers file. Both /tracker-init modes use it:
# the interactive flow writes the operator's answers to a temp answers file
# first, `--answers <file>` passes the caller's file, so the same answers
# always give the same config.
#
# Usage:
#   tracker-init-render.sh <answers.yaml>
#
# Answers file (the plugin's flat YAML: top-level keys, two-space sections,
# `  - item` lists; comments allowed):
#   backend: github                  # github | jira (required)
#   github:
#     repo: owner/repo               # required for github
#     project: <board URL>           # optional (Projects v2 board)
#   jira:
#     site: acme.atlassian.net       # required for jira (https:// and a trailing / are stripped)
#     cloud_id: <id>                 # required for jira
#     project: TRADE                 # required for jira
#     feature_type: Story            # Story (default) | Task
#     area_field: components         # components (default) | labels
#     parent_link_style: native      # native (default) | epic_link
#   areas:                           # optional list
#     - backend
#   subsystems:                      # optional list
#     - ingest
#   date: 2026-10-22                 # optional, the header's date (default today, UTC)
#
# Prints the config on stdout and exits 0; on a bad answers file prints
# `error: <why>` on stderr, nothing on stdout, and exits 2.

set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

die() { printf 'error: %s\n' "$1" >&2; exit 2; }

file="${1:-}"
[ -n "$file" ] || die "usage: tracker-init-render.sh <answers.yaml>"
[ -r "$file" ] || die "cannot read $file"
TEXT="$(tr -d '\r' <"$file")"
_ait_config_wellformed <(printf '%s\n' "$TEXT") || die "$file is not the flat YAML this reader takes"

get() { printf '%s\n' "$TEXT" | _ait_config_pick "$1"; }
# list <key> - the `  - item` lines under top-level <key>:, one per line.
list() {
  printf '%s\n' "$TEXT" | awk -v k="$1" '
    /^[A-Za-z_][A-Za-z0-9_]*:/ { insec = ($0 ~ "^" k ":[[:space:]]*(#.*)?$"); next }
    insec && /^[[:space:]]+-[[:space:]]/ {
      v = $0; sub(/^[[:space:]]+-[[:space:]]+/, "", v); sub(/[[:space:]]+#.*$/, "", v)
      sub(/[[:space:]]+$/, "", v)
      if (v ~ /^".*"$/ || v ~ /^'"'"'.*'"'"'$/) v = substr(v, 2, length(v) - 2)
      if (v != "") print v
    }'
}
# val <s> - a YAML scalar: double-quoted when it holds `#` or `: `, the two
# things the plugin's flat reader would otherwise cut.
val() {
  case "$1" in
    *'#'* | *': '*) printf '"%s"' "$1" ;;
    *) printf '%s' "$1" ;;
  esac
}
one_of() {
  local v="$1" name="$2"
  shift 2
  for ok in "$@"; do [ "$v" = "$ok" ] && return 0; done
  die "$name must be one of: $*; got '$v'"
}

backend="$(get backend)" || die "backend is required (github | jira)"
one_of "$backend" backend github jira

day="$(get date)" || day="$(date -u +%Y-%m-%d)"
case "$day" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *) die "date must be YYYY-MM-DD; got '$day'" ;;
esac

if [ "$backend" = github ]; then
  repo="$(get github.repo)" || die "github.repo is required for the github backend"
  case "$repo" in
    */*/* | /* | */ | *' '*) die "github.repo must be owner/repo; got '$repo'" ;;
    ?*/?*) ;;
    *) die "github.repo must be owner/repo; got '$repo'" ;;
  esac
  board="$(get github.project)" || board=""
else
  site="$(get jira.site)" || die "jira.site is required for the jira backend"
  site="${site#https://}"; site="${site#http://}"; site="${site%/}"
  [ -n "$site" ] || die "jira.site is empty"
  cloud="$(get jira.cloud_id)" || die "jira.cloud_id is required for the jira backend"
  jproject="$(get jira.project)" || die "jira.project is required for the jira backend"
  feature="$(get jira.feature_type)" || feature=Story
  one_of "$feature" jira.feature_type Story Task
  area_field="$(get jira.area_field)" || area_field=components
  one_of "$area_field" jira.area_field components labels
  link="$(get jira.parent_link_style)" || link=native
  one_of "$link" jira.parent_link_style native epic_link
fi

areas="$(list areas)"
subsystems="$(list subsystems)"

# \342\200\224 is an em dash (UTF-8), kept out of this file's bytes.
printf '# .claude/issue-tracker.yaml \342\200\224 agent-issue-tracker schema v1\n'
printf '#\n'
printf '# Written by /tracker-init on %s. Schema reference:\n' "$day"
printf '# https://github.com/maxdimitrov/agent-issue-tracker/blob/main/examples/issue-tracker.yaml.example\n'
printf '#\n'
printf '# Run /tracker-doctor to validate this config.\n'
printf '\n'
printf 'schema_version: 1\n'
printf 'backend: %s\n' "$backend"
if [ -n "$areas" ]; then
  printf 'areas:\n'
  while IFS= read -r a; do printf '  - %s\n' "$(val "$a")"; done <<<"$areas"
fi
if [ -n "$subsystems" ]; then
  printf 'subsystems:\n'
  while IFS= read -r s; do printf '  - %s\n' "$(val "$s")"; done <<<"$subsystems"
fi
if [ "$backend" = github ]; then
  printf 'github:\n'
  printf '  repo: %s\n' "$(val "$repo")"
  printf '  default_pr_close_syntax: "Fixes #N"\n'
  [ -n "$board" ] && printf '  project: %s\n' "$(val "$board")"
else
  printf 'jira:\n'
  printf '  site: %s\n' "$(val "$site")"
  printf '  cloud_id: %s\n' "$(val "$cloud")"
  printf '  project: %s\n' "$(val "$jproject")"
  printf '  issue_types:\n'
  printf '    feature: %s\n' "$feature"
  printf '    bug: Bug\n'
  printf '    epic: Epic\n'
  printf '    sub: Sub-task\n'
  printf '    followup: Task\n'
  printf '  area_field: %s\n' "$area_field"
  printf '  parent_link_style: %s\n' "$link"
  [ "$link" = epic_link ] && printf '  epic_link_field: customfield_10014\n'
  printf '  done_transition: Done\n'
  printf '  close_on_merge_hint: ""\n'
fi
exit 0
