"""Local mirror of the CI backend-contract job: every `### `op`` heading in
backends/_interface.md must appear in every backend module."""
import re
from pathlib import Path

BACKENDS = Path(__file__).resolve().parents[1] / "backends"
OP = re.compile(r"^### `([a-z_]+)`$", re.M)


def ops(path):
    return set(OP.findall(path.read_text(encoding="utf-8")))


def test_every_backend_implements_every_contract_op():
    contract = ops(BACKENDS / "_interface.md")
    assert contract, "no operation headings in _interface.md"
    for backend in ("github.md", "jira.md"):
        missing = contract - ops(BACKENDS / backend)
        assert not missing, f"{backend} missing {sorted(missing)}"


def test_contract_has_list_updated_issues():
    assert "list_updated_issues" in ops(BACKENDS / "_interface.md")
