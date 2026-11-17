---
description: Open a new Claude Code tab in VS Code with a prompt typed into its input box, ready for Enter — in this window, or with --repo in another repository's window (focused, or opened first). The handoff /file-followup and /session-brief offer, as a command you invoke directly with any prompt, or with none to take the next step this session named. Also use it when the operator asks in plain words to open a window or tab in another repo with a prompt to do something there ("open a window in Trading with a prompt to fix the dashboard-api").
---

# /new-tab [--repo <repo>] [<prompt>]

Open a fresh Claude Code tab in VS Code with `<prompt>` already typed into its input box. This is the same handoff that `/file-followup` and `/session-brief` **offer** at the end of their flows, available on demand with any prompt. It has nothing to do with the tracker: no config is read, no backend is called.

Without `--repo` the tab opens in this window's workspace. With `--repo <repo>` it opens in that repository's VS Code window: the window is focused if it is already open, opened first if not.

Everything after the command (and after `--repo <repo>`) is the prompt, verbatim. With nothing after it, the prompt is the next step this session already named (step 1):

```
/new-tab /agent-issue-tracker:work-issue #42
/new-tab Read the resume note at <path> and continue from it.
/new-tab --repo Trading /agent-issue-tracker:work-issue #660
/new-tab
```

## What you should do

1. **Find the prompt.**
   - **Text after `/new-tab`** — that text is the prompt, exactly as typed. Do not rephrase, expand, trim, or add context to it.
   - **No text** — take the prompt from the conversation: the next step this session itself told the operator to start in another session, most recent first. A candidate is something the session named concretely: a command with its arguments (`/agent-issue-tracker:work-issue #50`, from "#50 and #51 can be worked with `/agent-issue-tracker:work-issue`"), or a resume note it wrote ("Read the resume note at `<path>` and continue from it."). Use the command or path as the session named it; never summarise the conversation into a prompt, and never invent a step the session did not name.
     - A candidate the session said must run from another repository or directory opens there: use `--repo` with that directory.
     - **One candidate** → it is the prompt; go to step 2 without asking.
     - **Several** → ask once which one (AskUserQuestion, the candidates as options, the first one the session named marked recommended), then go to step 2 with the answer. Still one tab.
     - **None** → ask in one line what should go in the tab, and stop.
   - **The operator describes the prompt instead of typing it** ("open a window in Trading with a prompt to fix the dashboard-api") — write it. The new session starts with none of this conversation, so the prompt must stand on its own: the goal in one sentence, what this session found (file paths, functions, numbers, PR or issue numbers), what is already done, the constraints that apply (the repo's worktree and DECISIONS rules, what must not change), and how to tell it worked. State findings as findings and ideas as ideas to weigh, not as a spec. Keep it under the 2000-character limit; for more, write the body to a file and point the prompt at its path.

2. **Resolve `--repo`** (skip without it). Accept an absolute path, or a repository name resolved to its absolute path: a sibling of this repository, or a directory the session or memory already associates with that name (the operator's projects directory). Take the repository root unless a worktree was named. A name that matches nothing, or matches several, is asked about in one line, never guessed.

3. **Run the script once**, with the whole prompt as a single argument:

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/scripts/open-session-tab.sh" '<prompt>'
   "${CLAUDE_PLUGIN_ROOT}/scripts/open-session-tab.sh" --repo '<absolute dir>' '<prompt>'
   ```

   Quote it so the shell passes it through as one word; single quotes are safest when the prompt contains `"`, `$` or `#`. Invoking the command, or asking for the window in words, **is** the operator's consent — the offer step the flows use does not apply here. Do not ask "shall I open it?" first. With `--repo` the script takes 5–40 s (it waits for the window); run it in the foreground with a 60 s timeout.

4. **Report from the JSON.** The script always exits 0 and always prints one JSON object.
   - `"opened":true` — say in one line that the tab is open with the prompt typed in (quote it when step 1 inferred or wrote it), **not submitted**: the operator presses Enter. With `--repo`, name the repository whose window it is in. VS Code first asks whether to allow the extension to open the URI, and that dialog is easy to miss, so mention it.
   - `"opened":false` — name the `reason` in one clause and print the prompt in a fenced block for copy-paste. That is the whole fallback. `not-vscode` is the CLI / JetBrains case (`CLAUDE_CODE_ENTRYPOINT` is not `claude-vscode`). `no-code-cli` means `code` is not on PATH (`AIT_CODE_CLI` names another binary). `prompt-too-long` means over 2000 characters: suggest writing the body to a file and pointing the prompt at its path, which is how `/session-brief` keeps its resume-note prompt short. `no-such-repo` means the `--repo` directory does not exist. `window-not-ready` means the repository's window was asked for but never showed up in `code --status` within 30 s, so no URI was fired (it would have landed in whichever window had focus): the window may still be opening; paste the prompt into a new Claude Code tab there.

## What it does not do

- **Submit the prompt.** The URI handler types it in; the operator sends it. There is no submit parameter.
- **Title the tab.** The URI has no title parameter and `/rename` cannot share a message with the real prompt. The new tab is named by whatever the prompt turns into.
- **Open more than one tab, or retry.** One invocation, one `code --open-url`, even when the session named several next steps. A `launch-failed` or `window-not-ready` is reported, not retried.
- **Create the repository's worktree.** The prompt tells the new session to; the window opens on the directory given.
- **Change the flows.** `/file-followup` and `/session-brief` (on **fresh session**) keep offering the tab and never open one unasked. This command exists so you can get the same tab without going through them.

## How it works

[`scripts/open-session-tab.sh`](../scripts/open-session-tab.sh) URL-encodes the prompt with `jq` and fires `code --open-url "vscode://anthropic.claude-code/open?prompt=<urlencoded>"`, the Claude Code extension's URI handler. The URI has no folder parameter, and VS Code hands it to the focused window, so with `--repo` the script first runs `code <dir>`, polls `code --status` until a window titled `… - <folder> - Visual Studio Code` is listed, waits for the extension to load (5 s for a new window, 1 s for one already open), and only then fires the URI. Contract: always exit 0, always one JSON object on stdout — `{"opened":true,"uri":…,"prompt":…}` or `{"opened":false,"reason":…,"prompt":…}`, plus `"repo"` with `--repo`, with `reason` one of `not-vscode | no-code-cli | no-jq | empty-prompt | prompt-too-long | launch-failed | no-such-repo | window-not-ready`. Env: `CLAUDE_CODE_ENTRYPOINT` (set by Claude Code; only `claude-vscode` opens a tab), `AIT_CODE_CLI` (the VS Code CLI to call, default `code`), and for `--repo` `AIT_WINDOW_WAIT` (default 30), `AIT_WINDOW_SETTLE` (default 5) and `AIT_WINDOW_FOCUS_SETTLE` (default 1), in seconds.
