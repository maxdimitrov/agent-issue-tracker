---
description: Open a new Claude Code tab in VS Code with a prompt typed into its input box, ready for Enter — the handoff /file-followup and /session-brief offer, as a command you invoke directly with any prompt, or with none to take the next step this session named.
---

# /new-tab [<prompt>]

Open a fresh Claude Code tab in VS Code with `<prompt>` already typed into its input box. This is the same handoff that `/file-followup` and `/session-brief` **offer** at the end of their flows, available on demand with any prompt. It has nothing to do with the tracker: no config is read, no backend is called.

Everything after the command is the prompt, verbatim. With nothing after it, the prompt is the next step this session already named (step 1):

```
/new-tab /agent-issue-tracker:work-issue #42
/new-tab Read the resume note at <path> and continue from it.
/new-tab Review the open PR on this branch and address the review threads.
/new-tab
```

## What you should do

1. **Find the prompt.**
   - **Text after `/new-tab`** — that text is the prompt, exactly as typed. Do not rephrase, expand, trim, or add context to it.
   - **No text** — take the prompt from the conversation: the next step this session itself told the operator to start in another session, most recent first. A candidate is something the session named concretely: a command with its arguments (`/agent-issue-tracker:work-issue #50`, from "#50 and #51 can be worked with `/agent-issue-tracker:work-issue`"), or a resume note it wrote ("Read the resume note at `<path>` and continue from it."). Use the command or path as the session named it; never summarise the conversation into a prompt, and never invent a step the session did not name.
     - The tab opens in this VS Code window's workspace. Drop a candidate the session said must run from another repository or directory, and say in one line that it needs a session opened there.
     - **One candidate** → it is the prompt; go to step 2 without asking.
     - **Several** → ask once which one (AskUserQuestion, the candidates as options, the first one the session named marked recommended), then go to step 2 with the answer. Still one tab.
     - **None** → ask in one line what should go in the tab, and stop.

2. **Run the script once**, with the whole prompt as a single argument:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/open-session-tab.sh" '<prompt>'
   ```

   Quote it so the shell passes it through as one word; single quotes are safest when the prompt contains `"`, `$` or `#`. Invoking the command **is** the operator's consent — the offer step the flows use does not apply here. Do not ask "shall I open it?" first.

3. **Report from the JSON.** The script always exits 0 and always prints one JSON object.
   - `"opened":true` — say in one line that the tab is open with the prompt typed in (quote it when step 1 inferred it), **not submitted**: the operator presses Enter. VS Code first asks whether to allow the extension to open the URI, and that dialog is easy to miss, so mention it.
   - `"opened":false` — name the `reason` in one clause and print the prompt in a fenced block for copy-paste. That is the whole fallback. `not-vscode` is the CLI / JetBrains case (`CLAUDE_CODE_ENTRYPOINT` is not `claude-vscode`). `no-code-cli` means `code` is not on PATH (`AIT_CODE_CLI` names another binary). `prompt-too-long` means over 2000 characters: suggest writing the body to a file and pointing the prompt at its path, which is how `/session-brief` keeps its resume-note prompt short.

## What it does not do

- **Submit the prompt.** The URI handler types it in; the operator sends it. There is no submit parameter.
- **Title the tab.** The URI has no title parameter and `/rename` cannot share a message with the real prompt. The new tab is named by whatever the prompt turns into.
- **Open more than one tab, or retry.** One invocation, one `code --open-url`, even when the session named several next steps. A `launch-failed` is reported, not retried.
- **Change the flows.** `/file-followup` and `/session-brief` (on **fresh session**) keep offering the tab and never open one unasked. This command exists so you can get the same tab without going through them.

## How it works

[`scripts/open-session-tab.sh`](../scripts/open-session-tab.sh) URL-encodes the prompt with `jq` and fires `code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"`, the Claude Code extension's URI handler. Contract: always exit 0, always one JSON object on stdout — `{"opened":true,"uri":…,"prompt":…}` or `{"opened":false,"reason":…,"prompt":…}`, with `reason` one of `not-vscode | no-code-cli | no-jq | empty-prompt | prompt-too-long | launch-failed`. Env: `CLAUDE_CODE_ENTRYPOINT` (set by Claude Code; only `claude-vscode` opens a tab) and `AIT_CODE_CLI` (the VS Code CLI to call, default `code`).
