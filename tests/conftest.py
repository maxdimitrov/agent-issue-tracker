"""Put scripts/ on sys.path so tests import audit_skills directly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pytest

_OVERRIDES = ("TRACKER_BACKEND_OVERRIDE", "TRACKER_GITHUB_REPO_OVERRIDE",
              "TRACKER_JIRA_SITE_OVERRIDE", "TRACKER_JIRA_PROJECT_OVERRIDE")


@pytest.fixture(autouse=True)
def _no_tracker_overrides(monkeypatch):
    """A developer's TRACKER_*_OVERRIDE must never reach a test subprocess."""
    for k in _OVERRIDES:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _no_real_keel(monkeypatch, tmp_path):
    """A developer's keel CLI must never receive a test's writes: keel
    reporting is off (AIT_KEEL=0) unless a test turns it back on against a
    stub, and KEEL_HOME points at the test's own directory either way, so
    even a real keel would spool there. AIT_PROJECT_KEY is never inherited."""
    monkeypatch.setenv("AIT_KEEL", "0")
    monkeypatch.setenv("KEEL_HOME", (tmp_path / "keel-home").as_posix())
    monkeypatch.delenv("AIT_PROJECT_KEY", raising=False)
    monkeypatch.delenv("AIT_KEEL_ACTOR", raising=False)
