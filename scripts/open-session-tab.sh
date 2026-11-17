#!/usr/bin/env bash
# open-session-tab.sh -- open a new Claude Code tab in VS Code with a prompt
# typed into its input box (NOT submitted; the operator presses Enter).
#
# Usage: open-session-tab.sh "<prompt>"
#        open-session-tab.sh --repo <dir> "<prompt>"
#
# Fires the Claude Code extension's URI handler:
#   code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"
# VS Code asks the operator to allow the extension to open the URI first.
#
# The URI has no folder parameter: VS Code hands it to the focused window.
# So with --repo the script first runs `code <dir>` (focuses that folder's
# window, or opens a new one), polls `code --status` until a window titled
# with the folder's name is listed, lets the extension load, and only then
# fires the URI. A window that never shows up gets no URI (window-not-ready):
# firing anyway would type the prompt into whichever window has focus.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout:
#   {"opened":true,"uri":"...","prompt":"..."[,"repo":"<dir>"]}
#   {"opened":false,"reason":"<why>","prompt":"..."[,"repo":"<dir>"]}
# reason is one of not-vscode | no-code-cli | no-jq | empty-prompt |
# prompt-too-long | launch-failed | no-such-repo | window-not-ready. On
# opened:false the caller prints the prompt for copy-paste instead -- that is
# the CLI / JetBrains behaviour.
#
# Callers must only run this after the operator accepted the offer: it is an
# outward action on their editor.
#
# Env:
#   CLAUDE_CODE_ENTRYPOINT  set by Claude Code; only "claude-vscode" opens a tab
#   AIT_CODE_CLI            the VS Code CLI to call (default: code)
#   AIT_WINDOW_WAIT         --repo: seconds to wait for the window (default 30)
#   AIT_WINDOW_SETTLE       --repo: seconds for a NEW window's extension host
#                           to load before the URI fires (default 5)
#   AIT_WINDOW_FOCUS_SETTLE --repo: the same for an already open window
#                           (default 1)

set -uo pipefail

MAX_PROMPT=2000
repo=""
has_repo=0
if [ "${1-}" = "--repo" ]; then
  has_repo=1
  repo="${2-}"
  shift 2 2>/dev/null || shift $#
fi
prompt="${1-}"
cli="${AIT_CODE_CLI:-code}"

# Hand-rolled so the no-jq path can still answer in JSON.
json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }

emit() {  # emit <opened> <reason-or-empty> [uri]
  if command -v jq >/dev/null 2>&1; then
    jq -cn --argjson o "$1" --arg r "$2" --arg u "${3-}" --arg p "$prompt" \
      --arg d "$repo" --argjson hd "$has_repo" '
      (if $o then {opened:true, uri:$u, prompt:$p} else {opened:false, reason:$r, prompt:$p} end)
      + (if $hd == 1 then {repo:$d} else {} end)'
  else
    local extra=""
    [ "$has_repo" = 1 ] && extra=",\"repo\":\"$(json_escape "$repo")\""
    printf '{"opened":false,"reason":"%s","prompt":"%s"%s}\n' "$2" "$(json_escape "$prompt")" "$extra"
  fi
  exit 0
}
fail() { emit false "$1"; }

# The folder's window is listed by `code --status` as
#   window [N] (<editor title> - <folder> - Visual Studio Code)
# or, with no editor open, (<folder> - Visual Studio Code). Fixed strings,
# so a folder name with regex characters still matches, and `Trading-old`
# or `MyTrading` never pass for `Trading`.
window_open() {
  local status
  status="$("$cli" --status 2>/dev/null </dev/null)" || return 1
  printf '%s\n' "$status" | grep -qF -e " - $name - Visual Studio Code" -e "($name - Visual Studio Code"
}

[ "${CLAUDE_CODE_ENTRYPOINT:-}" = "claude-vscode" ] || fail not-vscode
if [ "$has_repo" = 1 ]; then
  [ -n "$repo" ] && [ -d "$repo" ] || fail no-such-repo
fi
[ -n "$prompt" ] || fail empty-prompt
[ "${#prompt}" -le "$MAX_PROMPT" ] || fail prompt-too-long
command -v jq >/dev/null 2>&1 || fail no-jq
command -v "$cli" >/dev/null 2>&1 || fail no-code-cli

encoded="$(jq -rn --arg p "$prompt" '$p | @uri')" || fail no-jq
uri="vscode://anthropic.claude-code/open?prompt=${encoded}"

if [ "$has_repo" = 1 ]; then
  trimmed="$repo"
  while [ "${#trimmed}" -gt 1 ] && [ "${trimmed%/}" != "$trimmed" ]; do trimmed="${trimmed%/}"; done
  name="$(basename "$trimmed")"
  settle="${AIT_WINDOW_SETTLE:-5}"
  window_open && settle="${AIT_WINDOW_FOCUS_SETTLE:-1}"
  "$cli" "$repo" >/dev/null 2>&1 </dev/null || fail launch-failed
  deadline=$((SECONDS + ${AIT_WINDOW_WAIT:-30}))
  until window_open; do
    [ "$SECONDS" -lt "$deadline" ] || fail window-not-ready
    sleep 1
  done
  sleep "$settle"
fi

"$cli" --open-url "$uri" >/dev/null 2>&1 </dev/null || fail launch-failed

emit true "" "$uri"
