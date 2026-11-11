#!/usr/bin/env bash
# keel-emit.sh -- report one event to keel, when keel is installed.
#
# Usage:
#   keel-emit.sh <event-type> [<key>=<value> ...]
#   keel-emit.sh work.started ref=#42 branch=feat/42-widget
#
# Spools `keel event <event-type> --project <slug> --payload <json> --spool`
# with the key=value pairs as a JSON object of strings. The project is the
# slug in `.keel/project.yaml` at the repo's top (or its main checkout's);
# without one the event goes without --project. The commands call it at
# their milestones (/work-issue: work.started, work.pr_opened, work.done).
#
# Contract: ALWAYS exits 0 and prints nothing. Without the keel CLI on PATH,
# or with AIT_KEEL=0, it does nothing at all: no keel, no behaviour change.

set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

type="${1:-}"
[ -n "$type" ] || exit 0
shift
ait_keel_on || exit 0
command -v jq >/dev/null 2>&1 || exit 0

payload='{}'
for kv in "$@"; do
  case "$kv" in
    ?*=*) ;;
    *) continue ;;
  esac
  payload="$(jq -c --arg k "${kv%%=*}" --arg v "${kv#*=}" '. + {($k): $v}' <<<"$payload" 2>/dev/null)" \
    || payload='{}'
done

ait_keel_event "$type" "$payload" "" "$PWD"
exit 0
