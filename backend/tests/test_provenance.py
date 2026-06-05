from __future__ import annotations

import subprocess
from pathlib import Path

from data.ingestion._provenance import extraction_rule_sha, extraction_rules_for
from data.ingestion import pdpc, sso


def _git_short_sha(path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    rel = path.resolve().relative_to(root)
    output = subprocess.check_output(
        ["git", "log", "-n", "1", "--pretty=%H", "--", str(rel)],
        cwd=root,
        text=True,
    ).strip()
    return output[:7]


def test_extraction_rule_sha_matches_git_log_for_pdpc_module():
    path = Path(pdpc.__file__)
    assert extraction_rule_sha(path) == _git_short_sha(path)


def test_extraction_rules_for_returns_named_short_shas():
    rules = extraction_rules_for({
        "pdpc": Path(pdpc.__file__),
        "sso": Path(sso.__file__),
    })
    assert rules == {
        "pdpc": _git_short_sha(Path(pdpc.__file__)),
        "sso": _git_short_sha(Path(sso.__file__)),
    }
    assert all(len(value) == 7 for value in rules.values())
