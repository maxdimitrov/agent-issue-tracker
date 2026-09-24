"""The commands invoke these scripts directly, so git must record them as
executable (100755); otherwise every new command fails with exit 126 on
macOS/Linux checkouts."""
import subprocess

import pytest

from shell_helpers import REPO_ROOT

EXECUTABLE = (
    "hooks/session-title.sh",
    "scripts/loop-record.sh",
    "scripts/session-brief-collect.sh",
    "scripts/tracker-brief-collect.sh",
)


@pytest.mark.parametrize("path", EXECUTABLE)
def test_script_is_executable_in_git(path):
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s", "--", path],
        check=True, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    ).stdout.strip()
    assert out, f"{path} is not tracked"
    assert out.split()[0] == "100755", out
