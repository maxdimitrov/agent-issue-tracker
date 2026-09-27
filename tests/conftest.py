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
