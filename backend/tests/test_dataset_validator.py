from __future__ import annotations

import json
from pathlib import Path

import yaml

from benchmark.dataset_validator import validate_jsonl, validate_paths, validate_yaml
from benchmark.runner import load_dataset


def _case(name: str = "case_1", sha: str = "abcdef1") -> dict:
    return {
        "name": name,
        "extraction_rule_sha": sha,
        "inputs": {"query": "x"},
        "expected_output": {"labels": ["ok"]},
        "metadata": {"task": "SGLB-test"},
    }


def test_validate_yaml_accepts_header_and_case_shas(tmp_path: Path):
    path = tmp_path / "dataset.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "extraction_rules": {"pdpc": "abcdef1"},
                "cases": [_case()],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    assert validate_yaml(path) == []
    dataset = load_dataset(path)
    assert dataset.extraction_rules == {"pdpc": "abcdef1"}
    assert dataset.cases[0].extraction_rule_sha == "abcdef1"


def test_validate_yaml_fails_missing_case_sha(tmp_path: Path):
    path = tmp_path / "dataset.yaml"
    case = _case()
    case.pop("extraction_rule_sha")
    path.write_text(
        yaml.safe_dump(
            {
                "extraction_rules": {"pdpc": "abcdef1"},
                "cases": [case],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    issues = validate_yaml(path)
    assert len(issues) == 1
    assert "missing or invalid extraction_rule_sha" in issues[0].message


def test_validate_yaml_fails_case_sha_not_declared(tmp_path: Path):
    path = tmp_path / "dataset.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "extraction_rules": {"pdpc": "abcdef1"},
                "cases": [_case(sha="1234567")],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    issues = validate_yaml(path)
    assert len(issues) == 1
    assert "not declared" in issues[0].message


def test_validate_yaml_skips_legacy_without_header_when_not_required(tmp_path: Path):
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump({"cases": [_case()]}), encoding="utf-8")
    assert validate_yaml(path, require_declared=False) == []


def test_validate_yaml_fails_legacy_when_required(tmp_path: Path):
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump({"cases": [_case()]}), encoding="utf-8")
    issues = validate_yaml(path, require_declared=True)
    assert any("extraction_rules" in issue.message for issue in issues)


def test_validate_jsonl_fails_missing_row_sha(tmp_path: Path):
    path = tmp_path / "train.jsonl"
    path.write_text(json.dumps({"id": "row_1", "inputs": {}}) + "\n", encoding="utf-8")
    issues = validate_jsonl(path)
    assert len(issues) == 1
    assert "row_1" in issues[0].message


def test_validate_paths_checks_directory_jsonl(tmp_path: Path):
    root = tmp_path / "data"
    root.mkdir()
    (root / "train.jsonl").write_text(
        json.dumps({"id": "row_1", "extraction_rule_sha": "abcdef1"}) + "\n",
        encoding="utf-8",
    )
    assert validate_paths([root], require_declared=True) == []
