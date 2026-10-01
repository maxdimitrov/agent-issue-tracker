---
description: Open a new Claude Code tab in VS Code with a prompt typed into its input box, ready for Enter — the handoff /file-followup and /session-brief offer, as a command you invoke directly with any prompt.
---

# /new-tab <prompt>

Open a fresh Claude Code tab in VS Code with `<prompt>` already typed into its input box. This is the same handoff that `/file-followup` and `/session-brief` **offer** at the end of their flows, available on demand with any prompt. It has nothing to do with the tracker: no config is read, no backend is called.

Everything after the command is the prompt, verbatim:

```
/new-tab /agent-issue-tracker:work-issue #42
/new-tab Read the resume note at <path> and continue from it.
/new-tab Review the open PR on this branch and address the review threads.
```

## What you should do

1. **Take the prompt as given.** The text after `/new-tab` is the prompt, exactly as typed — do not rephrase, expand, trim, or add context to it. With no text after the command, ask in one line what should go in the tab and stop; do not compose a prompt from the conversation.

2. **Run the script once**, with the whole prompt as a single argument:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/open-session-tab.sh" '<prompt>'
   ```

   Quote it so the shell passes it through as one word; single quotes are safest when the prompt contains `"`, `$` or `#`. Invoking the command **is** the operator's consent — the offer step the flows use does not apply here. Do not ask "shall I open it?" first.

3. **Report from the JSON.** The script always exits 0 and always prints one JSON object.
   - `"opened":true` — say in one line that the tab is open with the prompt typed in, **not submitted**: the operator presses Enter. VS Code first asks whether to allow the extension to open the URI, and that dialog is easy to miss, so mention it.
   - `"opened":false` — name the `reason` in one clause and print the prompt in a fenced block for copy-paste. That is the whole fallback. `not-vscode` is the CLI / JetBrains case (`CLAUDE_CODE_ENTRYPOINT` is not `claude-vscode`). `no-code-cli` means `code` is not on PATH (`AIT_CODE_CLI` names another binary). `prompt-too-long` means over 2000 characters: suggest writing the body to a file and pointing the prompt at its path, which is how `/session-brief` keeps its resume-note prompt short.

## What it does not do

- **Submit the prompt.** The URI handler types it in; the operator sends it. There is no submit parameter.
- **Title the tab.** The URI has no title parameter and `/rename` cannot share a message with the real prompt. The new tab is named by whatever the prompt turns into.
- **Open more than one tab, or retry.** One invocation, one `code --open-url`. A `launch-failed` is reported, not retried.
- **Change the flows.** `/file-followup` and `/session-brief` (on **fresh session**) keep offering the tab and never open one unasked. This command exists so you can get the same tab without going through them.

## How it works

[`scripts/open-session-tab.sh`](../scripts/open-session-tab.sh) URL-encodes the prompt with `jq` and fires `code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"`, the Claude Code extension's URI handler. Contract: always exit 0, always one JSON object on stdout — `{"opened":true,"uri":…,"prompt":…}` or `{"opened":false,"reason":…,"prompt":…}`, with `reason` one of `not-vscode | no-code-cli | no-jq | empty-prompt | prompt-too-long | launch-failed`. Env: `CLAUDE_CODE_ENTRYPOINT` (set by Claude Code; only `claude-vscode` opens a tab) and `AIT_CODE_CLI` (the VS Code CLI to call, default `code`).
