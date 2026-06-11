"""Put scripts/ on sys.path so tests import audit_skills directly."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
