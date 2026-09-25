#!/bin/sh
# git-sign.sh -- gpg.ssh.program wrapper for headless-capable SSH commit
# signing through the 1Password Automation service account (#119).
#
# Git calls this as:  git-sign.sh -Y sign -n git -f <pubkey-file> <buffer-file>
#
# Two steps:
# 1. Try the operator's default signer, op-ssh-sign (1Password desktop app,
#    biometric prompt, personal key). If it succeeds, nothing changes: same
#    key, same prompt, same <buffer-file>.sig that git reads back.
# 2. If it fails (app locked or absent, prompt unanswered) fall back to a
#    dedicated agent signing key held in the 1Password Automation vault,
#    resolved with the service-account token into a private in-memory
#    ssh-agent, and sign with `ssh-keygen -Y sign`. The private key is never
#    written to disk: it moves op -> tr -> ssh-add through a pipe only.
#    Only the public half is cached.
#
# Deliberately standalone (does not source scripts/lib/common.sh) so it works
# as gpg.ssh.program from any repo, outside the plugin directory.
#
# ## Environment (all optional)
#
#   AIT_SIGN_FORCE_SA=1       skip step 1 (tests; unattended runs)
#   AIT_OP_SSH_SIGN=<path>    desktop signer binary. Default: the Windows
#                             alias $HOME/AppData/Local/Microsoft/WindowsApps/
#                             op-ssh-sign.exe if present, else the macOS app
#                             binary if present, else op-ssh-sign on PATH,
#                             else step 1 is skipped
#   AIT_RUNNER_DIR=<dir>      state dir (default: ~/.claude-runner)
#   AIT_SIGN_KEY_REF=<op uri> key item (default: op://Automation/agent-signing-key)
#   AIT_SIGN_KEY_TTL=<ttl>    ssh-add lifetime for the agent key (default: 12h)
#   OP_SERVICE_ACCOUNT_TOKEN  used as-is when set; else read from
#   OP_TOKEN_FILE=<file>      this file (default: $AIT_RUNNER_DIR/op-token)
#
# State under $AIT_RUNNER_DIR: agent-signing-key.pub (public key cache) and
# ssh-agent.env (the private agent's socket, reused across commits).
#
# ## Setup (operator, once)
#
#   1. Generate the key inside 1Password, so it never touches this disk:
#        op item create --vault Automation --category "SSH Key" \
#          --title agent-signing-key --ssh-generate-key ed25519
#   2. Register the public key on GitHub as an additional signing key:
#        gh auth refresh -h github.com -s admin:ssh_signing_key
#        gh ssh-key add <pub> --type signing --title agent-signing-key
#      (<pub> is ~/.claude-runner/agent-signing-key.pub after a first
#      fallback run, or `op read "op://Automation/agent-signing-key/public key"`
#      saved to a file). The operator's personal key stays registered.
#   3. Let `git log --show-signature` verify locally by appending to
#      ~/.ssh/allowed_signers:
#        <committer-email> namespaces="git" <public key line>
#   4. Wire it (user.signingkey stays the operator's key):
#        git config --global gpg.ssh.program <abs path to scripts/git-sign.sh>
#      or, scoped to one repo:
#        git -C <repo> config gpg.ssh.program <abs path to scripts/git-sign.sh>
#
# Pure ASCII, POSIX sh, bash 3.2 / BSD userland safe. Never prints token or
# key material; stderr carries at most one `git-sign: ...` line.

set -u
umask 077

RUNNER_DIR="${AIT_RUNNER_DIR:-$HOME/.claude-runner}"
KEY_REF="${AIT_SIGN_KEY_REF:-op://Automation/agent-signing-key}"
KEY_TTL="${AIT_SIGN_KEY_TTL:-12h}"
PUB="$RUNNER_DIR/agent-signing-key.pub"
AGENT_ENV="$RUNNER_DIR/ssh-agent.env"
WHY=""

log() { printf 'git-sign: %s%s\n' "$WHY" "$*" >&2; }

# --- 1. desktop signer first -------------------------------------------------
if [ -n "${AIT_OP_SSH_SIGN:-}" ]; then
    OP_SSH_SIGN="$AIT_OP_SSH_SIGN"
elif [ -x "$HOME/AppData/Local/Microsoft/WindowsApps/op-ssh-sign.exe" ]; then
    OP_SSH_SIGN="$HOME/AppData/Local/Microsoft/WindowsApps/op-ssh-sign.exe"
elif [ -x "/Applications/1Password.app/Contents/MacOS/op-ssh-sign" ]; then
    OP_SSH_SIGN="/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
elif command -v op-ssh-sign >/dev/null 2>&1; then
    OP_SSH_SIGN="op-ssh-sign"
else
    OP_SSH_SIGN=""
fi

if [ "${AIT_SIGN_FORCE_SA:-0}" != "1" ] && [ -n "$OP_SSH_SIGN" ] &&
    { [ -x "$OP_SSH_SIGN" ] || command -v "$OP_SSH_SIGN" >/dev/null 2>&1; }; then
    "$OP_SSH_SIGN" "$@"
    rc=$?
    [ "$rc" -eq 0 ] && exit 0
    # Stay quiet on a successful fallback; prefix any later failure instead,
    # so stderr never carries more than one line.
    WHY="op-ssh-sign failed (rc $rc); "
fi

# --- 2. service-account token -------------------------------------------------
if [ -z "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]; then
    tf="${OP_TOKEN_FILE:-$RUNNER_DIR/op-token}"
    if [ ! -r "$tf" ]; then
        log "no OP_SERVICE_ACCOUNT_TOKEN and no service-account token at $tf"
        exit 1
    fi
    OP_SERVICE_ACCOUNT_TOKEN="$(tr -d '[:space:]' < "$tf")"
    if [ -z "$OP_SERVICE_ACCOUNT_TOKEN" ]; then
        log "service-account token file $tf is empty"
        exit 1
    fi
    export OP_SERVICE_ACCOUNT_TOKEN
fi

command -v op >/dev/null 2>&1 || { log "op CLI not on PATH"; exit 1; }

# --- 3. public key (cached; public material only) ----------------------------
if [ ! -s "$PUB" ]; then
    mkdir -p "$RUNNER_DIR"
    if ! op read "$KEY_REF/public key" > "$PUB.tmp" 2>/dev/null; then
        rm -f "$PUB.tmp"
        log "could not read $KEY_REF/public key with the service account"
        exit 1
    fi
    printf '%s agent-signing-key\n' "$(tr -d '\r\n' < "$PUB.tmp")" > "$PUB.tmp2"
    rm -f "$PUB.tmp"
    mv -f "$PUB.tmp2" "$PUB"
fi
fp="$(ssh-keygen -lf "$PUB" 2>/dev/null | awk '{print $2}')"
[ -n "$fp" ] || { log "cannot fingerprint $PUB"; exit 1; }

# --- 4. private ssh-agent (never an unreachable ambient agent) ---------------
# On Windows the ambient pipe is 1Password's own agent (refuses ssh-add when
# locked) and the OpenSSH service is disabled, so run our own agent and keep
# its socket in $AGENT_ENV for the next commit.
agent_ok() { ssh-add -l >/dev/null 2>&1; [ "$?" -ne 2 ]; }
if [ -r "$AGENT_ENV" ]; then
    # shellcheck disable=SC1090
    . "$AGENT_ENV" >/dev/null 2>&1
fi
if [ -z "${SSH_AUTH_SOCK:-}" ] || ! agent_ok; then
    mkdir -p "$RUNNER_DIR"
    ssh-agent -s > "$AGENT_ENV" 2>/dev/null || { log "cannot start ssh-agent"; exit 1; }
    # shellcheck disable=SC1090
    . "$AGENT_ENV" >/dev/null 2>&1
    agent_ok || { log "started ssh-agent but cannot reach it"; exit 1; }
fi

key_loaded() { ssh-add -l 2>/dev/null | grep -F -q "$fp"; }

# Key bytes stay in the pipe: never a file, never a variable, never echoed.
# op on Windows may emit CRLF and ssh-add rejects CR in the key. `err`
# captures ssh-add's stderr only (its stdout goes to /dev/null).
load_key() {
    op read "$KEY_REF/private key?ssh-format=openssh" 2>/dev/null \
        | tr -d '\r' | ssh-add -t "$KEY_TTL" - 2>&1 >/dev/null | tr '\r\n' '  '
}

if ! key_loaded; then
    err="$(load_key)"
    if ! key_loaded; then
        # One retry: the first load has been seen to flake on Windows.
        err="$(load_key)"
        if ! key_loaded; then
            log "could not load the agent signing key into ssh-agent: ${err:-no message}"
            exit 1
        fi
    fi
fi

# --- 5. sign with the agent key: swap git's -f <file> for our public key ----
i=0; n=$#; sub=0
while [ "$i" -lt "$n" ]; do
    a="$1"; shift
    if [ "$sub" = 1 ]; then
        a="$PUB"; sub=0
    elif [ "$a" = "-f" ]; then
        sub=1
    fi
    set -- "$@" "$a"
    i=$((i + 1))
done
exec ssh-keygen "$@"
