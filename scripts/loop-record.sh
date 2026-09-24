#!/usr/bin/env bash
# loop-record.sh -- bookkeeping for /tracker-loop. One JSON record per loop
# under <state-dir>/loops/<id>.json; every subcommand prints JSON on stdout.
# Budgets are enforced from the record on disk, so a loop survives a context
# compaction with its counters intact.
#
# Usage:
#   loop-record.sh create <mode> <ref> <branch> [--merge] [--draft] [--cron-id <id>]
#                  [--max-iterations N] [--max-hours N] [--idle-stop-after N] [--interval <s>]
#   loop-record.sh find <mode> <ref>              # live record with that mode+ref, or null
#   loop-record.sh check <id>                     # {"ok":true,...} or {"ok":false,"reason":...}
#   loop-record.sh append <id> <action> <detail> [--noop]
#   loop-record.sh add-pr <id> <pr-ref>
#   loop-record.sh set-cron <id> <job-id>
#   loop-record.sh stop <id> <reason>
#   loop-record.sh get <id>
#   loop-record.sh list                           # live records, summarised
#
# Exit 0 on success, 1 when the record does not exist, 2 on a usage error.

set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

DIR="$(ait_state_dir "$PWD")/loops"
mkdir -p "$DIR" 2>/dev/null
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
usage() { printf '{"error":"usage: %s"}\n' "$1" >&2; exit 2; }
path_of() { printf '%s/%s.json' "$DIR" "$1"; }
require() { [ -f "$(path_of "$1")" ] || { printf '{"error":"no such loop","id":"%s"}\n' "$1"; exit 1; }; }
# modify <id> <jq options and filter...> -- read-modify-write, atomic.
# On a corrupt record jq fails: the half-written tmp file is removed, an
# error JSON is printed and the script exits 1 (never falls through to the
# unconditional exit 0 at the bottom).
modify() {
  local id="$1" p
  shift
  p="$(path_of "$id")"
  if jq "$@" "$p" >"$p.tmp"; then
    mv "$p.tmp" "$p"
  else
    rm -f "$p.tmp"
    printf '{"error":"corrupt record","id":"%s"}\n' "$id"
    exit 1
  fi
}
# all_records - live records as a JSON array. Parses each file on its own
# so one corrupt record cannot hide every other live loop from find/list.
all_records() {
  local f line out
  out=""
  for f in "$DIR"/*.json; do
    [ -f "$f" ] || continue
    line="$(jq -c . "$f" 2>/dev/null)" || continue
    out="$out$line
"
  done
  if [ -n "$out" ]; then
    printf '%s' "$out" | jq -s '.'
  else
    printf '[]'
  fi
}

cmd="${1:-}"
[ $# -gt 0 ] && shift
case "$cmd" in
  create)
    [ $# -ge 3 ] || usage "create <mode> <ref> <branch> [flags]"
    mode="$1"; ref="$2"; branch="$3"; shift 3
    [ -n "$mode" ] && [ -n "$ref" ] || usage "create <mode> <ref> <branch> [flags]"
    merge=false; draft=false; cron=""; maxi=50; maxh=24; idle=12; interval="15m"
    while [ $# -gt 0 ]; do
      case "$1" in
        --merge) merge=true ;;
        --draft) draft=true ;;
        --cron-id) cron="${2:-}"; shift ;;
        --max-iterations) maxi="${2:-50}"; shift ;;
        --max-hours) maxh="${2:-24}"; shift ;;
        --idle-stop-after) idle="${2:-12}"; shift ;;
        --interval) interval="${2:-15m}"; shift ;;
        *) usage "unknown flag $1" ;;
      esac
      shift
    done
    case "$maxi" in ""|*[!0-9]*|0) usage "--max-iterations must be a positive integer" ;; esac
    case "$maxh" in ""|*[!0-9]*|0) usage "--max-hours must be a positive integer" ;; esac
    case "$idle" in ""|*[!0-9]*|0) usage "--idle-stop-after must be a positive integer" ;; esac
    slug="$(printf '%s' "$ref" | tr '/#' '--' | sed 's/^-*//' | tr -cd 'A-Za-z0-9._-')"
    base="$(printf '%s-%s-%s' "$mode" "${slug:-x}" "$(date -u +%Y%m%d%H%M%S)")"
    id="$base"; n=2
    while [ -f "$(path_of "$id")" ]; do id="$base-$n"; n=$((n + 1)); done
    p="$(path_of "$id")"
    if jq -n --arg id "$id" --arg mode "$mode" --arg ref "$ref" --arg branch "$branch" \
      --arg now "$(now)" --arg cron "$cron" --arg interval "$interval" \
      --argjson merge "$merge" --argjson draft "$draft" \
      --argjson maxi "$maxi" --argjson maxh "$maxh" --argjson idle "$idle" \
      '{id: $id, mode: $mode, ref: $ref, branch: (if $branch == "" then null else $branch end),
        started: $now, state: "live", stop_reason: null, stopped: null,
        cron_job_id: (if $cron == "" then null else $cron end),
        options: {merge: $merge, draft: $draft, interval: $interval},
        budget: {max_iterations: $maxi, max_hours: $maxh, idle_stop_after: $idle},
        iterations: [], prs_opened: []}' >"$p.tmp"; then
      mv "$p.tmp" "$p"
    else
      rm -f "$p.tmp"
      printf '{"error":"create failed","id":"%s"}\n' "$id"
      exit 1
    fi
    jq -c --arg p "$p" '{id, path: $p}' "$p"
    ;;
  find)
    [ $# -ge 2 ] || usage "find <mode> <ref>"
    all_records | jq -c --arg m "$1" --arg r "$2" \
      '[.[] | select(.state == "live" and .mode == $m and .ref == $r)] | first // null'
    ;;
  check)
    [ $# -ge 1 ] || usage "check <id>"
    require "$1"
    if ! jq -c --argjson now "$(date -u +%s)" '
      def epoch: sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch 0);
      (.iterations | length) as $n
      | (($now - (.started | epoch)) / 3600) as $hours
      | ([.iterations | reverse[] | (.noop == true)] | index(false) // $n) as $trailing
      | if .state != "live" then {ok: false, reason: ("stopped: " + (.stop_reason // "unknown"))}
        elif $n >= .budget.max_iterations then {ok: false, reason: "budget: max_iterations"}
        elif $hours >= .budget.max_hours then {ok: false, reason: "budget: max_hours"}
        elif $trailing >= .budget.idle_stop_after then {ok: false, reason: "budget: idle_stop_after"}
        else {ok: true, iterations: $n, hours: (($hours * 10 | floor) / 10), trailing_noops: $trailing} end' \
      "$(path_of "$1")"; then
      printf '{"error":"corrupt record","id":"%s"}\n' "$1"
      exit 1
    fi
    ;;
  append)
    [ $# -ge 2 ] || usage "append <id> <action> <detail> [--noop]"
    id="$1"; action="$2"; detail="${3:-}"; noop=false
    [ "${4:-}" = "--noop" ] && noop=true
    [ "$detail" = "--noop" ] && { detail=""; noop=true; }
    require "$id"
    # shellcheck disable=SC2016
    modify "$id" --arg at "$(now)" --arg a "$action" --arg d "$detail" --argjson n "$noop" \
      '.iterations += [{at: $at, action: $a, detail: $d, noop: $n}]'
    jq -c '{id, iterations: (.iterations | length), last_action: (.iterations | last | .action)}' "$(path_of "$id")"
    ;;
  add-pr)
    [ $# -ge 2 ] || usage "add-pr <id> <pr-ref>"
    require "$1"
    # shellcheck disable=SC2016
    modify "$1" --arg pr "$2" '.prs_opened = ((.prs_opened // []) + [$pr] | unique)'
    jq -c '{id, prs_opened}' "$(path_of "$1")"
    ;;
  set-cron)
    [ $# -ge 2 ] || usage "set-cron <id> <job-id>"
    require "$1"
    # shellcheck disable=SC2016
    modify "$1" --arg j "$2" '.cron_job_id = $j'
    jq -c '{id, cron_job_id}' "$(path_of "$1")"
    ;;
  stop)
    [ $# -ge 2 ] || usage "stop <id> <reason>"
    require "$1"
    # shellcheck disable=SC2016
    modify "$1" --arg r "$2" --arg at "$(now)" '.state = "stopped" | .stop_reason = $r | .stopped = $at'
    jq -c '{id, state, stop_reason, cron_job_id}' "$(path_of "$1")"
    ;;
  get)
    [ $# -ge 1 ] || usage "get <id>"
    require "$1"
    jq -c '. + {path: $p}' --arg p "$(path_of "$1")" "$(path_of "$1")"
    ;;
  list)
    all_records | jq -c '[.[] | select(.state == "live")
      | {id, mode, ref, branch, started, cron_job_id, prs_opened,
         iterations: (.iterations | length), last_action: (.iterations | last | .action // null)}]'
    ;;
  *) usage "create|find|check|append|add-pr|set-cron|stop|get|list" ;;
esac
exit 0
