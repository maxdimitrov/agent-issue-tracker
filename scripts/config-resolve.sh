#!/usr/bin/env bash
# config-resolve.sh -- print the effective .claude/issue-tracker.yaml (#7).
#
# Usage: config-resolve.sh [--provenance] [<dir>]
#
# The project file (nearest walking up from <dir>, default $PWD) merged over
# $HOME/.claude/issue-tracker.yaml by top-level key, then the
# TRACKER_*_OVERRIDE leaves. README "Where the config is found" has the rule.
#
# Exit 0: stdout is the YAML. With --provenance: a first `#global<TAB><path>`
#   line when a global file is merged (even if every key in it is shadowed),
#   then `key<TAB>source` lines (project:<path>, global:<path>, env:<VAR>).
# Exit 1: not configured (no project file); stdout is empty.
# Exit 2: bad usage.
# Warnings about a skipped global file go to stderr.

set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

mode=resolve
dir=""
for a in "$@"; do
  case "$a" in
    --provenance) mode=provenance ;;
    -*) printf 'usage: config-resolve.sh [--provenance] [<dir>]\n' >&2; exit 2 ;;
    *) [ -z "$dir" ] || { printf 'usage: config-resolve.sh [--provenance] [<dir>]\n' >&2; exit 2; }
       dir="$a" ;;
  esac
done
dir="${dir:-$PWD}"

if [ "$mode" = provenance ]; then
  ait_config_provenance "$dir" || exit 1
else
  ait_config_resolve "$dir" || exit 1
fi
