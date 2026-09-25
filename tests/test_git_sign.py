"""Subprocess tests for scripts/git-sign.sh (gpg.ssh.program wrapper, #119).

Every external binary the wrapper touches (op-ssh-sign, op, ssh-add,
ssh-keygen, ssh-agent) is a stub on PATH that logs its argv under tmp_path,
so the suite never reaches the real 1Password app, the real service account
or a real ssh-agent. After every case the temp tree is walked to prove no
private-key block ever reached disk.
"""
import os
from pathlib import Path

import pytest

from shell_helpers import SCRIPTS, env_with_path, isolated_env, make_stub, run_script

SCRIPT = SCRIPTS / "git-sign.sh"

TOKEN = "ops_TESTTOKEN_never_print_me_8f3a"
PRIV_MARKER = "BEGIN OPENSSH PRIVATE KEY"
FAKE_PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFAKEFAKEFAKEFAKEFAKE"
KEY_REF = "op://Automation/agent-signing-key"

# Each stub appends one line per call: its argv joined by tabs.
LOG_ARGV = ('(IFS="$(printf \'\\t\')"; printf \'%s\\n\' "$*") '
            '>>"$AIT_TEST_LOGS/$(basename "$0").log"')

OP_SSH_SIGN_STUB = f"""{LOG_ARGV}
printf 'DESKTOP-SIG\\n'
exit "${{STUB_OPSSH_RC:-0}}"
"""

# Never logs the token itself: only whether it matched what the test set up.
OP_STUB = f"""{LOG_ARGV}
if [ "${{OP_SERVICE_ACCOUNT_TOKEN:-}}" = "${{STUB_EXPECT_TOKEN:-}}" ]; then
    echo match >>"$AIT_TEST_LOGS/op-token-seen.log"
else
    echo mismatch >>"$AIT_TEST_LOGS/op-token-seen.log"
fi
[ "$1" = read ] || exit 1
case "$2" in
    *"/public key") printf '{FAKE_PUB}\\r\\n' ;;
    *"/private key?ssh-format=openssh")
        printf -- '-----BEGIN OPENSSH PRIVATE KEY-----\\r\\n'
        printf 'b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABfake\\r\\n'
        printf -- '-----END OPENSSH PRIVATE KEY-----\\r\\n' ;;
    *) echo "[ERROR] no such field" >&2; exit 1 ;;
esac
"""

# -l: exit 2 when no reachable agent (no sock file), list the key once a
# load was recorded (or STUB_PRELOADED=1), else "no identities" (rc 1).
# Load: records only the stdin length and marker flags, never the content;
# fails the first STUB_ADD_FAILS loads.
SSH_ADD_STUB = f"""{LOG_ARGV}
if [ "$1" = "-l" ]; then
    if [ -z "${{SSH_AUTH_SOCK:-}}" ] || [ ! -e "$SSH_AUTH_SOCK" ]; then
        echo "Could not open a connection to your authentication agent." >&2
        exit 2
    fi
    if [ -e "$AIT_TEST_STATE/loaded" ] || [ "${{STUB_PRELOADED:-0}}" = 1 ]; then
        echo "256 SHA256:stubfp agent-signing-key (ED25519)"
        exit 0
    fi
    echo "The agent has no identities."
    exit 1
fi
data="$(cat)"
begin=no; cr=no
case "$data" in "-----BEGIN OPENSSH PRIVATE KEY-----"*) begin=yes ;; esac
case "$data" in *"$(printf '\\r')"*) cr=yes ;; esac
echo "len=${{#data}} begin=$begin cr=$cr" >>"$AIT_TEST_LOGS/ssh-add-stdin.log"
n=0
[ -e "$AIT_TEST_STATE/add-count" ] && n="$(cat "$AIT_TEST_STATE/add-count")"
n=$((n + 1)); echo "$n" >"$AIT_TEST_STATE/add-count"
if [ "$n" -le "${{STUB_ADD_FAILS:-0}}" ]; then
    echo "agent refused operation" >&2
    exit 1
fi
touch "$AIT_TEST_STATE/loaded"
echo "Identity added: (stdin) (agent-signing-key)" >&2
"""

SSH_KEYGEN_STUB = f"""{LOG_ARGV}
case "$1" in
    -lf) echo "256 SHA256:stubfp comment (ED25519)" ;;
    -Y) echo "STUB-SIGNATURE" ;;
    *) exit 1 ;;
esac
"""

SSH_AGENT_STUB = f"""{LOG_ARGV}
touch "$AIT_TEST_STATE/sock"
printf 'SSH_AUTH_SOCK=%s/sock; export SSH_AUTH_SOCK;\\n' "$AIT_TEST_STATE"
printf 'SSH_AGENT_PID=1; export SSH_AGENT_PID;\\necho Agent pid 1;\\n'
"""

# Git for Windows' bash launcher puts /usr/bin (which ships the real ssh-*)
# ahead of the inherited PATH, so the stub dir is prepended again from
# inside the shell. The wrapper then runs under `sh`, as git runs it.
LAUNCHER = """bin="$AIT_TEST_BIN"
if command -v cygpath >/dev/null 2>&1; then bin="$(cygpath -u "$bin")"; fi
PATH="$bin:$PATH"; export PATH
exec sh "$@"
"""

STUBS = {
    "op-ssh-sign": OP_SSH_SIGN_STUB,
    "op": OP_STUB,
    "ssh-add": SSH_ADD_STUB,
    "ssh-keygen": SSH_KEYGEN_STUB,
    "ssh-agent": SSH_AGENT_STUB,
}


def _path_without(names):
    """The ambient PATH minus any dir holding a binary named in `names`."""
    keep = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        if any(os.path.exists(os.path.join(d, n + ext))
               for n in names for ext in ("", ".exe", ".cmd", ".bat")):
            continue
        keep.append(d)
    return os.pathsep.join(keep)


class Rig:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.bin = tmp_path / "bin"
        self.logs = tmp_path / "logs"
        self.state = tmp_path / "state"
        self.runner = tmp_path / "runner"
        self.home = tmp_path / "home"
        for d in (self.logs, self.state, self.home):
            d.mkdir(parents=True, exist_ok=True)
        for name, body in STUBS.items():
            make_stub(self.bin, name, body)
        env = isolated_env(
            tmp_path,
            HOME=self.home.as_posix(),
            AIT_RUNNER_DIR=self.runner.as_posix(),
            AIT_OP_SSH_SIGN=(self.bin / "op-ssh-sign").as_posix(),
            AIT_TEST_LOGS=self.logs.as_posix(),
            AIT_TEST_STATE=self.state.as_posix(),
            AIT_TEST_BIN=self.bin.as_posix(),
            STUB_EXPECT_TOKEN=TOKEN,
        )
        for k in ("SSH_AUTH_SOCK", "SSH_AGENT_PID", "OP_SERVICE_ACCOUNT_TOKEN",
                  "OP_TOKEN_FILE", "AIT_SIGN_FORCE_SA", "AIT_SIGN_KEY_REF",
                  "AIT_SIGN_KEY_TTL", "OP_CONNECT_HOST", "OP_CONNECT_TOKEN"):
            env.pop(k, None)
        # Hide the real 1Password binaries so a deleted stub never falls
        # through to them. (The ssh-* stubs shadow the real ones by coming
        # first; their dirs also hold tr/awk/grep, so they stay on PATH.)
        env["PATH"] = _path_without(["op", "op-ssh-sign"])
        self.env = env_with_path(env, self.bin)
        self.launcher = tmp_path / "launch.sh"
        self.launcher.write_text(LAUNCHER)
        self.pubfile = tmp_path / "git-tmp-pub"
        self.pubfile.write_text("ssh-ed25519 AAAAoperatorkey\n")
        self.buffer = tmp_path / "buffer"
        self.buffer.write_text("tree 0000\n\ncommit message\n")

    def git_argv(self):
        return ["-Y", "sign", "-n", "git", "-f",
                self.pubfile.as_posix(), self.buffer.as_posix()]

    def write_token_file(self):
        self.runner.mkdir(parents=True, exist_ok=True)
        (self.runner / "op-token").write_text(f"  {TOKEN}\r\n")

    def run(self, **extra_env):
        env = dict(self.env)
        env.update(extra_env)
        return run_script(self.launcher, args=[SCRIPT.as_posix(), *self.git_argv()],
                          env=env)

    def calls(self, name):
        p = self.logs / f"{name}.log"
        if not p.exists():
            return []
        return [line.split("\t") for line in p.read_text().splitlines()]

    def loads(self):
        return [c for c in self.calls("ssh-add") if c[0] != "-l"]

    def op_reads(self):
        return [c[1] for c in self.calls("op") if c[0] == "read"]

    def runner_files(self):
        if not self.runner.exists():
            return []
        return sorted(p.name for p in self.runner.rglob("*"))


def assert_no_private_key_on_disk(root):
    """No file under root, other than the stub scripts, holds a key block."""
    root = Path(root)
    stub_dir = root / "bin"
    for p in root.rglob("*"):
        if not p.is_file() or stub_dir in p.parents:
            continue
        assert PRIV_MARKER.encode() not in p.read_bytes(), \
            f"private key block on disk: {p}"


@pytest.fixture
def rig(tmp_path):
    r = Rig(tmp_path)
    yield r
    assert_no_private_key_on_disk(tmp_path)


def stderr_lines(r):
    return [line for line in r.stderr.splitlines() if line.strip()]


def assert_fallback_signed(rig, r):
    assert r.returncode == 0, (r.stdout, r.stderr)
    # git reads the signature from <buffer>.sig, not stdout; stdout only
    # shows the stub signer ran last.
    assert r.stdout.endswith("STUB-SIGNATURE\n")
    pub = rig.runner / "agent-signing-key.pub"
    assert pub.read_bytes() == (FAKE_PUB + " agent-signing-key\n").encode()
    reads = rig.op_reads()
    assert f"{KEY_REF}/public key" in reads
    assert f"{KEY_REF}/private key?ssh-format=openssh" in reads
    loads = rig.loads()
    assert loads, "ssh-add never loaded a key"
    for c in loads:
        # stdin only: exactly `-t <ttl> -`, never a file argument
        assert c == ["-t", "12h", "-"], c
    last = (rig.logs / "ssh-add-stdin.log").read_text().splitlines()[-1]
    assert "begin=yes" in last and "cr=no" in last, last
    signs = [c for c in rig.calls("ssh-keygen") if c[0] == "-Y"]
    assert signs == [["-Y", "sign", "-n", "git", "-f", pub.as_posix(),
                      rig.buffer.as_posix()]]
    seen = rig.calls("op-token-seen")
    assert seen and all(c == ["match"] for c in seen), seen


# 1. Acceptance: desktop signer OK -> its argv unchanged, op never called.
def test_desktop_signer_success_passes_through(rig):
    r = rig.run()
    assert r.returncode == 0, r.stderr
    assert r.stdout == "DESKTOP-SIG\n"
    assert rig.calls("op-ssh-sign") == [rig.git_argv()]
    assert rig.calls("op") == []
    assert rig.calls("ssh-keygen") == []
    assert rig.runner_files() == []


# 2. Acceptance: desktop fails + token file -> op read, stdin load, re-sign.
def test_fallback_with_token_file(rig):
    rig.write_token_file()
    r = rig.run(STUB_OPSSH_RC="1")
    assert rig.calls("op-ssh-sign") == [rig.git_argv()]
    assert_fallback_signed(rig, r)
    assert stderr_lines(r) == []


# 3. Token from the environment; the token never leaks anywhere.
def test_fallback_with_env_token_never_leaks(rig, tmp_path):
    r = rig.run(STUB_OPSSH_RC="1", OP_SERVICE_ACCOUNT_TOKEN=TOKEN)
    assert_fallback_signed(rig, r)
    assert not (rig.runner / "op-token").exists()
    assert TOKEN not in r.stdout and TOKEN not in r.stderr
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert TOKEN.encode() not in p.read_bytes(), f"token in {p}"


# 4. Acceptance: no token anywhere -> non-zero, one stderr line, no files.
def test_no_token_fails_with_one_line_and_no_files(rig):
    r = rig.run(STUB_OPSSH_RC="1")
    assert r.returncode != 0
    lines = stderr_lines(r)
    assert len(lines) == 1, r.stderr
    assert lines[0].startswith("git-sign: ")
    assert "op-ssh-sign" in lines[0] and "token" in lines[0]
    assert not rig.runner.exists()
    assert rig.calls("op") == []
    assert rig.calls("ssh-agent") == []


def test_op_token_file_override(rig, tmp_path):
    tf = tmp_path / "elsewhere-token"
    tf.write_text(TOKEN + "\n")
    r = rig.run(AIT_SIGN_FORCE_SA="1", OP_TOKEN_FILE=tf.as_posix())
    assert_fallback_signed(rig, r)


# 5. AIT_SIGN_FORCE_SA=1 skips the desktop signer entirely.
def test_force_sa_skips_desktop_signer(rig):
    rig.write_token_file()
    r = rig.run(AIT_SIGN_FORCE_SA="1")
    assert rig.calls("op-ssh-sign") == []
    assert_fallback_signed(rig, r)


# 6. A flaky first ssh-add load is retried once.
def test_first_ssh_add_failure_is_retried(rig):
    rig.write_token_file()
    r = rig.run(AIT_SIGN_FORCE_SA="1", STUB_ADD_FAILS="1")
    assert_fallback_signed(rig, r)
    assert len(rig.loads()) == 2


def test_two_ssh_add_failures_report_its_stderr_on_one_line(rig):
    rig.write_token_file()
    r = rig.run(AIT_SIGN_FORCE_SA="1", STUB_ADD_FAILS="2")
    assert r.returncode != 0
    assert len(rig.loads()) == 2
    lines = stderr_lines(r)
    assert len(lines) == 1, r.stderr
    assert "agent refused operation" in lines[0]
    assert [c for c in rig.calls("ssh-keygen") if c[0] == "-Y"] == []


# 7. Key already held by the agent -> the private key is never read.
def test_key_already_loaded_skips_private_read(rig):
    rig.write_token_file()
    r = rig.run(AIT_SIGN_FORCE_SA="1", STUB_PRELOADED="1")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "STUB-SIGNATURE\n"
    assert not any("private key" in x for x in rig.op_reads())
    assert rig.loads() == []


def test_cached_public_key_and_agent_are_reused(rig):
    rig.write_token_file()
    assert rig.run(AIT_SIGN_FORCE_SA="1").returncode == 0
    r = rig.run(AIT_SIGN_FORCE_SA="1")
    assert r.returncode == 0, r.stderr
    assert rig.op_reads().count(f"{KEY_REF}/public key") == 1
    assert len(rig.calls("ssh-agent")) == 1
    assert len(rig.loads()) == 1


def test_stale_agent_env_starts_a_fresh_agent(rig):
    rig.write_token_file()
    (rig.runner / "ssh-agent.env").write_text(
        f"SSH_AUTH_SOCK={rig.tmp.as_posix()}/gone; export SSH_AUTH_SOCK;\n")
    r = rig.run(AIT_SIGN_FORCE_SA="1")
    assert len(rig.calls("ssh-agent")) == 1
    assert_fallback_signed(rig, r)


def test_unreachable_ambient_agent_is_not_used(rig):
    rig.write_token_file()
    r = rig.run(AIT_SIGN_FORCE_SA="1",
                SSH_AUTH_SOCK=(rig.tmp / "ambient-dead").as_posix())
    assert len(rig.calls("ssh-agent")) == 1
    assert_fallback_signed(rig, r)


# 9. op missing from PATH with a token present -> one line, non-zero.
def test_missing_op_cli_fails_with_one_line(rig):
    rig.write_token_file()
    (rig.bin / "op").unlink()
    r = rig.run(AIT_SIGN_FORCE_SA="1")
    assert r.returncode != 0
    lines = stderr_lines(r)
    assert len(lines) == 1, r.stderr
    assert "op CLI" in lines[0]
    assert rig.calls("ssh-keygen") == []
