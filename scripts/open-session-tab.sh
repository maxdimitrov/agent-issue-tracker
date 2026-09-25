#!/usr/bin/env bash
# open-session-tab.sh -- open a new Claude Code tab in VS Code with a prompt
# typed into its input box (NOT submitted; the operator presses Enter).
#
# Usage: open-session-tab.sh "<prompt>"
#
# Fires the Claude Code extension's URI handler:
#   code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"
# VS Code asks the operator to allow the extension to open the URI first.
#
# Contract: ALWAYS exits 0, ALWAYS prints one JSON object on stdout:
#   {"opened":true,"uri":"...","prompt":"..."}
#   {"opened":false,"reason":"<why>","prompt":"..."}
# reason is one of not-vscode | no-code-cli | no-jq | empty-prompt |
# prompt-too-long | launch-failed. On opened:false the caller prints the
# prompt for copy-paste instead -- that is the CLI / JetBrains behaviour.
#
# Callers must only run this after the operator accepted the offer: it is an
# outward action on their editor.
#
# Env:
#   CLAUDE_CODE_ENTRYPOINT  set by Claude Code; only "claude-vscode" opens a tab
#   AIT_CODE_CLI            the VS Code CLI to call (default: code)

set -uo pipefail

MAX_PROMPT=2000
prompt="${1-}"
cli="${AIT_CODE_CLI:-code}"

# Hand-rolled so the no-jq path can still answer in JSON.
json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr -d '\n\r'; }

fail() {
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg r "$1" --arg p "$prompt" '{opened:false, reason:$r, prompt:$p}'
  else
    printf '{"opened":false,"reason":"%s","prompt":"%s"}\n' "$1" "$(json_escape "$prompt")"
  fi
  exit 0
}

[ "${CLAUDE_CODE_ENTRYPOINT:-}" = "claude-vscode" ] || fail not-vscode
[ -n "$prompt" ] || fail empty-prompt
[ "${#prompt}" -le "$MAX_PROMPT" ] || fail prompt-too-long
command -v jq >/dev/null 2>&1 || fail no-jq
command -v "$cli" >/dev/null 2>&1 || fail no-code-cli

encoded="$(jq -rn --arg p "$prompt" '$p | @uri')" || fail no-jq
uri="vscode://anthropic.claude-code/open?prompt=${encoded}"

"$cli" --open-url "$uri" >/dev/null 2>&1 </dev/null || fail launch-failed

jq -cn --arg u "$uri" --arg p "$prompt" '{opened:true, uri:$u, prompt:$p}'
exit 0
