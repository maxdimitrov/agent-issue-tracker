# Design — unattended commit signing via the 1Password service account

Issue: #119. Date: 2026-09-25. Status: implemented as `scripts/git-sign.sh`; the design itself is imported, not re-decided here.

## Imported decision

The design pass lives in the Trading repo at `docs/superpowers/specs/2026-07-06-unattended-signing-design.md` (candidates A to D, scorecard, child issues CI-1 to CI-5). The operator ratified its recommendation on 2026-09-24: **(B)** sign with `ssh-keygen -Y sign` using a key fetched through `op` into an in-memory ssh-agent, plus **(D)** a dedicated, low-value agent signing key, converging on 1Password Connect later. This repo builds CI-1 + CI-2 first. Nothing from that spec is copied here; read it there.

## Mechanism

`scripts/git-sign.sh` is set as `gpg.ssh.program`. Git calls it as `git-sign.sh -Y sign -n git -f <pubkey-file> <buffer-file>`.

1. **Desktop signer first.** Unless `AIT_SIGN_FORCE_SA=1`, run `op-ssh-sign` with git's arguments unchanged (`AIT_OP_SSH_SIGN`, else the Windows alias, else the macOS app binary, else `op-ssh-sign` on PATH). Exit 0 means done: same personal key, same biometric prompt as before.
2. **Service-account fallback.** Token from `OP_SERVICE_ACCOUNT_TOKEN`, else `${OP_TOKEN_FILE:-~/.claude-runner/op-token}`. Public key read once with `op read "op://Automation/agent-signing-key/public key"` and cached as `~/.claude-runner/agent-signing-key.pub`. A private ssh-agent (socket kept in `~/.claude-runner/ssh-agent.env`, never the 1Password or Windows service agent) gets the key by pipe only: `op read ".../private key?ssh-format=openssh" | tr -d '\r' | ssh-add -t 12h -`, retried once. Then `exec ssh-keygen` with git's `-f` value swapped for the cached public key.

Every failure is one `git-sign: ...` line on stderr and a non-zero exit, so git reports a failed signature as it does today. There is never a silent unsigned commit.

## Custody note

The fallback holds the private key in agent memory for the `-t` lifetime (default 12h, `AIT_SIGN_KEY_TTL`). That is a step down from `op-ssh-sign`, which never exposes the key. It is bounded by the key itself (dedicated to the agent, able to sign commits but not push or trade, revocable on GitHub without touching the operator's key) and by the TTL. The private half is generated inside 1Password and never touches disk: no file, no shell variable, no temp file.

## Operator prerequisites

- `op item create --vault Automation --category "SSH Key" --title agent-signing-key --ssh-generate-key ed25519`
- `gh auth refresh -h github.com -s admin:ssh_signing_key`, then `gh ssh-key add <pub> --type signing --title agent-signing-key` (until then fallback commits verify locally but show Unverified on GitHub).
- `~/.ssh/allowed_signers`: `<committer-email> namespaces="git" <public key line>`.
- `git config --global gpg.ssh.program <abs path>/git-sign.sh`, or `git config gpg.ssh.program ...` in one repo. `user.signingkey` stays the operator's key. The plugin cache path is versioned, so copy the script somewhere stable (the doctor suggests `~/.claude-runner/git-sign.sh`).

`/tracker-doctor` Phase 4 warns when SSH commit signing goes through a bare `op-ssh-sign`, or when the wrapper is wired with no token available.

## Out of scope

1Password Connect (the wrapper needs no change for it; nothing is built), re-signing history, push auth (`GH_TOKEN`), the Trading repo's own wiring (CI-3 there), YubiKey.

## Verification

```bash
python -m pytest -q tests/test_git_sign.py
shellcheck -x scripts/git-sign.sh
# live (operator machine, 1Password app locked, token present):
git -c gpg.ssh.program="$PWD/scripts/git-sign.sh" commit --allow-empty -m probe && git log -1 --format=%G?
gh api repos/<nwo>/commits/<sha> --jq .commit.verification.verified
# live, app unlocked: git log --show-signature shows the personal key's fingerprint, unchanged
```
