#!/usr/bin/env bash
# loop-record.sh -- bookkeeping for /tracker-loop. One JSON record per loop
# under <state-dir>/loops/<id>.json; every subcommand prints JSON on stdout.
# Budgets are enforced from the record on disk, so a loop survives a context
# compaction with its counters intact.
#
# Usage:
#   loop-record.sh create <mode> <ref> <branch> [--merge] [--draft] [--cron-id <id>]
#                  [--max-iterations N] [--max-hours N] [--idle-stop-after N] [--interval <s>]
#   loop-record.sh find [--any] <mode> <ref>      # live record with that mode+ref, or null;
#                                                  # --any: newest record regardless of state
#                                                  # (by started, ties broken by id)
#   loop-record.sh check <id>                     # {"ok":true,...} or {"ok":false,"reason":...}
#                                                 # max_iterations counts entries whose
#                                                 # action is not "skip"
#   loop-record.sh append <id> <action> <detail> [--noop]
#   loop-record.sh add-pr <id> <pr-ref>
#   loop-record.sh set-cron <id> <job-id>
#   loop-record.sh stop <id> <reason> [--transcript <path>]
#                                                 # --transcript: stored as stop_transcript
#   loop-record.sh reopen <id>                    # stopped -> live, counters kept,
#                                                 # cron_job_id cleared
#   loop-record.sh get <id>
#   loop-record.sh list                           # live records, summarised
#   loop-record.sh window <id>                    # recurring loops: this fire's
#                                                 # `loop <id> window ok|skipped` line
#   loop-record.sh claim <mode> <ref> <branch> --cron-id schtasks:<TaskName> [--restart]
#                  [create flags]                 # a scheduled fire's load-or-create:
#                                                 # {"action":"use|create|reopen|refuse",...}
#
# Exit 0 on success, 1 when the record does not exist, 2 on a usage error.
#
# Recurring mode: a record whose cron_job_id starts with `schtasks:` is fired
# by an external scheduler (Windows Task Scheduler) that outlives every
# session. Its budgets count per window, not per lifetime: windows are
# budget.max_hours long, back to back from `started`. max_iterations counts
# the acting entries (an action other than wait, wait-ci or skip, not a noop)
# in the current window; when they are spent, `check` says so with
# recurring:true and the record stays live until the next window. max_hours
# and idle_stop_after never stop it: an idle scheduled loop is the normal
# state. `check` stamps `last_fire` and numbers the fire (`fire`), `append`
# tags its entry with that number, and `window` reports whether anything
# acted in this fire. `append` keeps only the current and previous window's
# entries.
# Every other record behaves as before.
#
# keel: with the keel CLI on PATH (and AIT_KEEL not 0), create, append, stop,
# reopen and check also spool keel events (loop.created, loop.iteration for
# entries that are not noops, loop.stopped) and a `loop:<id>` heartbeat whose
# payload carries cron_id. Without keel nothing is emitted and nothing changes.
#
# Ids are claimed with a noclobber (set -C) write, which is atomic on one
# machine's filesystem; two machines sharing one state dir are not supported.

set -uo pipefail
# shellcheck source=scripts/lib/common.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/common.sh"

DIR="$(ait_state_dir "$PWD")/loops"
mkdir -p "$DIR" 2>/dev/null
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# --- keel reporting (a no-op without keel) -----------------------------------
# keel_actor <id> - the actor kind for this loop's events: runner for a
# scheduled (schtasks:) loop, claude_session otherwise.
keel_actor() {
  case "$(jq -r '.cron_job_id // ""' "$(path_of "$1")" 2>/dev/null)" in
    schtasks:*) printf 'runner' ;;
    *) printf 'claude_session' ;;
  esac
}
# keel_minutes <interval> - minutes in `15m` / `1h` / `90s` / `2d` / `20`,
# at least 30 (the self-paced idle hint), so a heartbeat is not called
# silent between two ordinary fires.
keel_minutes() {
  local v="${1:-15m}" n m
  n="${v%[smhd]}"
  case "$n" in '' | *[!0-9]*) n=15; v=15m ;; esac
  case "$v" in
    *s) m=$(( (n + 59) / 60 )) ;;
    *h) m=$(( n * 60 )) ;;
    *d) m=$(( n * 1440 )) ;;
    *) m="$n" ;;
  esac
  [ "$m" -lt 30 ] && m=30
  printf '%s' "$m"
}
# keel_beat <id> - a loop:<id> heartbeat, payload {cron_id, mode, ref}.
keel_beat() {
  local p payload interval
  ait_keel_on || return 0
  p="$(path_of "$1")"
  payload="$(jq -c '{cron_id: .cron_job_id, mode, ref}' "$p" 2>/dev/null)" || return 0
  interval="$(jq -r '.options.interval // "15m"' "$p" 2>/dev/null)"
  ait_keel_beat "loop:$1" "$(keel_minutes "$interval")m" "$payload" "$(ait_keel_project "$PWD")"
}
# keel_event <id> <type> <jq filter over the record> [<idem-key>]
keel_event() {
  local payload
  ait_keel_on || return 0
  payload="$(jq -c "$3" "$(path_of "$1")" 2>/dev/null)" || return 0
  AIT_KEEL_ACTOR="$(keel_actor "$1")" ait_keel_event "$2" "$payload" "${4:-}" "$PWD"
}

# The current window of a recurring record, as jq definitions: $now is the
# epoch, a record's window is budget.max_hours long and windows run back to
# back from `started`.
# shellcheck disable=SC2016
WINDOW_JQ='
  def epoch: sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch 0);
  def recurring: ((.cron_job_id // "") | startswith("schtasks:"));
  def win_secs: ((.budget.max_hours // 24) * 3600);
  def win_start: (.started | epoch) as $s | ($now - $s) as $age
    | if $age <= 0 then $s else $s + (($age / win_secs | floor) * win_secs) end;
  def acting: (.action != "skip" and .action != "wait" and .action != "wait-ci" and .noop != true);
'
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
# all_records - every record, any state, as a JSON array; find and list
# filter to live. Parses each file on its own so one corrupt record cannot
# hide every other loop from find/list.
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
    if [ -z "$mode" ] || [ -z "$ref" ]; then usage "create <mode> <ref> <branch> [flags]"; fi
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
    # 0[0-9]*: a leading zero (007) is not a JSON number; reject it here
    # rather than let jq --argjson fail after the id is claimed.
    case "$maxi" in ""|*[!0-9]*|0|0[0-9]*) usage "--max-iterations must be a positive integer" ;; esac
    case "$maxh" in ""|*[!0-9]*|0|0[0-9]*) usage "--max-hours must be a positive integer" ;; esac
    case "$idle" in ""|*[!0-9]*|0|0[0-9]*) usage "--idle-stop-after must be a positive integer" ;; esac
    slug="$(printf '%s' "$ref" | tr '/#' '--' | sed 's/^-*//' | tr -cd 'A-Za-z0-9._-')"
    base="$(printf '%s-%s-%s' "$mode" "${slug:-x}" "$(date -u +%Y%m%d%H%M%S)")"
    # Claim the id atomically: a noclobber write fails when the file exists,
    # so two creates in the same second can never both take one id.
    id="$base"; n=2
    while ! (set -C; : >"$(path_of "$id")") 2>/dev/null; do
      if [ ! -f "$(path_of "$id")" ] || [ "$n" -gt 1000 ]; then
        printf '{"error":"cannot write state dir","path":"%s"}\n' "$DIR"
        exit 1
      fi
      id="$base-$n"; n=$((n + 1))
    done
    p="$(path_of "$id")"
    if jq -n --arg id "$id" --arg mode "$mode" --arg ref "$ref" --arg branch "$branch" \
      --arg now "$(now)" --arg cron "$cron" --arg interval "$interval" \
      --argjson merge "$merge" --argjson draft "$draft" \
      --argjson maxi "$maxi" --argjson maxh "$maxh" --argjson idle "$idle" \
      '{id: $id, mode: $mode, ref: $ref, branch: (if $branch == "" then null else $branch end),
        started: $now, state: "live", stop_reason: null, stop_transcript: null, stopped: null,
        cron_job_id: (if $cron == "" then null else $cron end),
        options: {merge: $merge, draft: $draft, interval: $interval},
        budget: {max_iterations: $maxi, max_hours: $maxh, idle_stop_after: $idle},
        iterations: [], prs_opened: []}' >"$p.tmp"; then
      mv "$p.tmp" "$p"
    else
      rm -f "$p.tmp" "$p"
      printf '{"error":"create failed","id":"%s"}\n' "$id"
      exit 1
    fi
    jq -c --arg p "$p" '{id, path: $p}' "$p"
    keel_event "$id" loop.created '{id, mode, ref, branch, cron_id: .cron_job_id, interval: .options.interval}' \
      "loop.created:$id"
    keel_beat "$id"
    ;;
  find)
    any=false
    [ "${1:-}" = "--any" ] && { any=true; shift; }
    [ $# -ge 2 ] || usage "find [--any] <mode> <ref>"
    if [ "$any" = true ]; then
      all_records | jq -c --arg m "$1" --arg r "$2" \
        '[.[] | select(.mode == $m and .ref == $r)] | sort_by(.started, (.id | length), .id) | last // null'
    else
      all_records | jq -c --arg m "$1" --arg r "$2" \
        '[.[] | select(.state == "live" and .mode == $m and .ref == $r)] | first // null'
    fi
    ;;
  check)
    [ $# -ge 1 ] || usage "check <id>"
    require "$1"
    p="$(path_of "$1")"
    nowe="$(date -u +%s)"
    if jq -e "$WINDOW_JQ"' recurring and .state == "live"' --argjson now "$nowe" "$p" >/dev/null 2>&1; then
      # shellcheck disable=SC2016
      modify "$1" --arg at "$(now)" '.last_fire = $at | .fire = ((.fire // 0) + 1)'
      if ! jq -c --argjson now "$nowe" "$WINDOW_JQ"'
        win_start as $ws
        | [.iterations[] | select((.at | epoch) >= $ws)] as $win
        | ([$win[] | select(acting)] | length) as $n
        | ([$win | reverse[] | (.noop == true)] | index(false) // ($win | length)) as $trailing
        | {ws: ($ws | todate), we: (($ws + win_secs) | todate)} as $w
        | if $n >= .budget.max_iterations
          then {ok: false, recurring: true, reason: "window: max_iterations",
                window_started: $w.ws, window_ends: $w.we}
          else {ok: true, recurring: true, iterations: $n, trailing_noops: $trailing,
                window_started: $w.ws, window_ends: $w.we} end' "$p"; then
        printf '{"error":"corrupt record","id":"%s"}\n' "$1"
        exit 1
      fi
      keel_beat "$1"
      exit 0
    fi
    if ! jq -c --argjson now "$nowe" '
      def epoch: sub("\\.[0-9]+Z$"; "Z") | (try fromdateiso8601 catch 0);
      ([.iterations[] | select(.action != "skip")] | length) as $n
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
    ait_keel_on && jq -e '.state == "live"' "$p" >/dev/null 2>&1 && keel_beat "$1"
    ;;
  append)
    [ $# -ge 2 ] || usage "append <id> <action> <detail> [--noop]"
    id="$1"; action="$2"; detail="${3:-}"; noop=false
    [ "${4:-}" = "--noop" ] && noop=true
    [ "$detail" = "--noop" ] && { detail=""; noop=true; }
    require "$id"
    # A recurring record keeps the current and the previous window only: it
    # never ends, and every fire appends.
    # shellcheck disable=SC2016
    modify "$id" --arg at "$(now)" --arg a "$action" --arg d "$detail" --argjson n "$noop" \
      --argjson now "$(date -u +%s)" "$WINDOW_JQ"'
      .iterations += [{at: $at, action: $a, detail: $d, noop: $n} + (if .fire then {fire: .fire} else {} end)]
      | if recurring then (win_start - win_secs) as $cut
          | .iterations |= map(select((.at | epoch) >= $cut)) else . end'
    jq -c '{id, iterations: (.iterations | length), last_action: (.iterations | last | .action)}' "$(path_of "$id")"
    if [ "$noop" = false ]; then
      # shellcheck disable=SC2016
      keel_event "$id" loop.iteration '{id, mode, ref, action: (.iterations | last | .action),
        detail: (.iterations | last | .detail), at: (.iterations | last | .at)}'
    fi
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
    [ $# -ge 2 ] || usage "stop <id> <reason> [--transcript <path>]"
    id="$1"; reason="$2"; shift 2
    transcript=""
    if [ $# -gt 0 ]; then
      if [ "$1" != "--transcript" ] || [ $# -lt 2 ]; then
        usage "stop <id> <reason> [--transcript <path>]"
      fi
      transcript="$2"
    fi
    require "$id"
    # shellcheck disable=SC2016
    modify "$id" --arg r "$reason" --arg at "$(now)" --arg t "$transcript"       '.state = "stopped" | .stop_reason = $r | .stopped = $at
       | .stop_transcript = (if $t == "" then null else $t end)'
    jq -c '{id, state, stop_reason, cron_job_id}' "$(path_of "$id")"
    keel_event "$id" loop.stopped '{id, mode, ref, reason: .stop_reason, cron_id: .cron_job_id, stopped}' \
      "loop.stopped:$id:$(jq -r '.stopped' "$(path_of "$id")" 2>/dev/null)"
    ;;
  reopen)
    # Continue a checkpointed loop in a new session: back to live with the
    # started time, iterations, prs_opened, budget and options untouched.
    # The old session's cron died with it, so cron_job_id is cleared.
    [ $# -ge 1 ] || usage "reopen <id>"
    require "$1"
    modify "$1" '.state = "live" | .stop_reason = null | .stop_transcript = null | .stopped = null
      | .cron_job_id = null'
    jq -c '{id, state, iterations: (.iterations | length)}' "$(path_of "$1")"
    keel_beat "$1"
    ;;
  window)
    # The line a recurring fire ends with: ok when an acting entry was
    # appended since this fire's `check`, skipped otherwise. check numbers
    # the fires (.fire) and append tags each entry with the current one, so
    # two fires within one second never see each other's entries. A record
    # that is not live is always skipped: a fire that only refused (a paused
    # loop) never ran `check`, so its .fire still names an older fire.
    # A fire that acts and then stops runs `window` before `stop`.
    [ $# -ge 1 ] || usage "window <id>"
    require "$1"
    # shellcheck disable=SC2016
    if ! jq -c --argjson now "$(date -u +%s)" "$WINDOW_JQ"'
      .fire as $f
      | (if .state == "live" and $f != null and any(.iterations[]; .fire == $f and acting)
         then "ok" else "skipped" end) as $w
      | {id, window: $w, line: ("loop " + .id + " window " + $w)}' "$(path_of "$1")"; then
      printf '{"error":"corrupt record","id":"%s"}\n' "$1"
      exit 1
    fi
    ;;
  claim)
    # Recurring mode's load-or-create, for a fire of the scheduled task named
    # by --cron-id. Only a record that task owns is ever used, reopened or
    # paused-on: a live loop of the same mode and ref driven by anything else
    # (an interactive /loop, a session cron) is left alone and the fire is
    # refused, so that loop keeps its 1.12.0 budgets.
    [ $# -ge 3 ] || usage "claim <mode> <ref> <branch> --cron-id schtasks:<TaskName> [--restart] [create flags]"
    mode="$1"; ref="$2"; branch="$3"; shift 3
    cron=""; restart=false; pass=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --cron-id) cron="${2:-}"; shift ;;
        --restart) restart=true ;;
        --merge | --draft) pass+=("$1") ;;
        --max-iterations | --max-hours | --idle-stop-after | --interval) pass+=("$1" "${2:-}"); shift ;;
        *) usage "unknown flag $1" ;;
      esac
      shift
    done
    case "$cron" in schtasks:?*) ;; *) usage "claim needs --cron-id schtasks:<TaskName>" ;; esac
    if [ -z "$mode" ] || [ -z "$ref" ]; then usage "claim <mode> <ref> <branch> --cron-id schtasks:<TaskName>"; fi
    refuse() {
      jq -nc --arg id "$1" --arg m "$2" --arg why "$3" \
        '{action: "refuse", id: $id, reason: $why, message: $m, line: ("loop " + $id + " window skipped")}'
      exit 0
    }
    live="$(all_records | jq -c --arg m "$mode" --arg r "$ref" \
      '[.[] | select(.state == "live" and .mode == $m and .ref == $r)] | first // null')"
    if [ "$live" != null ] && [ -n "$live" ]; then
      lid="$(jq -r '.id' <<<"$live")"
      lcron="$(jq -r '.cron_job_id // ""' <<<"$live")"
      if [ "$lcron" = "$cron" ]; then
        jq -nc --arg id "$lid" '{action: "use", id: $id}'
        exit 0
      fi
      owner="${lcron:-another session (no cron id)}"
      refuse "$lid" "loop $lid is owned by $owner; not acting" "owned by $owner"
    fi
    if [ "$restart" = false ]; then
      newest="$(all_records | jq -c --arg m "$mode" --arg r "$ref" --arg c "$cron" \
        '[.[] | select(.mode == $m and .ref == $r and .cron_job_id == $c)]
         | sort_by(.started, (.id | length), .id) | last // null')"
      if [ "$newest" != null ] && [ -n "$newest" ]; then
        nid="$(jq -r '.id' <<<"$newest")"
        nreason="$(jq -r '.stop_reason // ""' <<<"$newest")"
        case "$nreason" in
          "operator stop")
            refuse "$nid" "loop $nid is stopped (operator stop); pass --restart to begin a new loop" "operator stop" ;;
          checkpoint:*)
            "$BASH" "$0" reopen "$nid" >/dev/null || exit 1
            "$BASH" "$0" set-cron "$nid" "$cron" >/dev/null || exit 1
            jq -nc --arg id "$nid" '{action: "reopen", id: $id}'
            exit 0 ;;
        esac
      fi
    fi
    made="$("$BASH" "$0" create "$mode" "$ref" "$branch" --cron-id "$cron" ${pass[@]+"${pass[@]}"})" || {
      printf '%s\n' "$made"; exit 1; }
    jq -c '{action: "create", id, path}' <<<"$made"
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
  *) usage "create|find|check|append|add-pr|set-cron|stop|reopen|get|list|window|claim" ;;
esac
exit 0
