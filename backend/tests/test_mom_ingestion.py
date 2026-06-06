"""SGLB-05 end-to-end integration smoke (Batch A A3).

Feeds an A1 fixture HTML through the A2 parser into the sglb_05 builder
and then through the benchmark harness with the multi_label_f1 evaluator.
Asserts the oracle scores 1.0 — the case round-trips through every stage
of the v0.1 pipeline.

This is the missing piece from Batch A: A1 (network) + A2 (parser) +
A4 (adapter) all landed, but the end-to-end integration test that proves
the four parts compose was authored separately.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from benchmark.dataset_builders.sglb_05 import build, write_outputs  # noqa: E402
from benchmark.runner import run  # noqa: E402
from data.parsers.mom_parser import parse_press_release_html  # noqa: E402

FIXTURE_DIR = BACKEND_ROOT / "tests" / "fixtures" / "mom"
PRESS_RELEASE_FIXTURE = FIXTURE_DIR / "press_release_2026_0528_efma_offences.html"
PRESS_RELEASE_URL = (
    "https://www.mom.gov.sg/newsroom/press-releases/2026/0528-efma-offences"
)


def _write_mom_jsonl(record, path: Path) -> None:
    payload = {
        "doc_id": record.doc_id,
        "source_url": record.source_url,
        "subsource": record.subsource,
        "title": record.title,
        "body_plain": record.body_plain,
        "stated_breaches": list(record.stated_breaches),
        "act_references": list(record.act_references),
        "subject_organisation": record.subject_organisation,
        "pub_date": record.pub_date,
        # Provenance field added by NEW-EXTRACT-VERSION (PR #98); the
        # production ingester (backend/data/ingestion/mom.py) computes
        # this from the git SHA of the extraction module. For the
        # integration test we synthesise a deterministic placeholder.
        "extraction_rule_sha": "test_fixture_sha_a3_integration",
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_mom_end_to_end_smoke(tmp_path):
    # 1. Load the A1 fixture HTML committed under tests/fixtures/mom/.
    assert PRESS_RELEASE_FIXTURE.exists(), (
        f"missing fixture {PRESS_RELEASE_FIXTURE}; A1 should have committed it"
    )
    html = PRESS_RELEASE_FIXTURE.read_text(encoding="utf-8")

    # 2. Run it through A2's parser; fixture must yield non-empty
    #    stated_breaches or the builder will filter the case out.
    record = parse_press_release_html(html, PRESS_RELEASE_URL)
    assert record.doc_id, "parser produced empty doc_id"
    assert record.body_plain, "parser produced empty body_plain"
    assert record.stated_breaches, (
        "fixture must yield stated_breaches — A2 parser's mechanical "
        "extraction depends on MOM's DOM markers being present"
    )

    # 3. Write MomRecord to a tmp_path JSONL matching the builder's
    #    expected input schema.
    jsonl_path = tmp_path / "enforcement.jsonl"
    _write_mom_jsonl(record, jsonl_path)

    # 4. Run the SGLB-05 builder against the fixture JSONL.
    cases = build(jsonl_path)
    assert len(cases) >= 1, (
        "builder emitted 0 cases against a fixture with non-empty "
        "stated_breaches — investigate redactor or filter logic"
    )

    # 5. Materialise the harness-shaped YAML + JSONL splits.
    yaml_path = tmp_path / "sglb_05_employment_issue.yaml"
    splits_dir = tmp_path / "benchmarks" / "sglb_05_employment_issue"
    write_outputs(cases, yaml_path, splits_dir)
    assert yaml_path.exists()

    # 6. Run the benchmark harness end-to-end with the oracle runner
    #    and the multi_label_f1 evaluator. The oracle returns the gold
    #    labels verbatim so the score must be 1.0.
    summary = asyncio.run(
        run(
            workflow="sglb_05",
            dataset_path=yaml_path,
            evaluators=["multi_label_f1"],
        )
    )
    assert summary.total_cases == len(cases)
    means = summary.per_evaluator_mean()
    assert means.get("multi_label_f1") == pytest.approx(1.0)


def test_mom_jsonl_schema_matches_builder_expectations(tmp_path):
    """The JSONL emitted by parser+writer round-trips through builder
    without schema drift. Guards against silent field rename between A2
    output and sglb_05.build() input."""
    html = PRESS_RELEASE_FIXTURE.read_text(encoding="utf-8")
    record = parse_press_release_html(html, PRESS_RELEASE_URL)
    jsonl_path = tmp_path / "enforcement.jsonl"
    _write_mom_jsonl(record, jsonl_path)

    # Reload and ensure every field the builder reads is present.
    rows = [
        json.loads(line)
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    required = {
        "doc_id",
        "source_url",
        "subsource",
        "title",
        "body_plain",
        "stated_breaches",
        "act_references",
        "pub_date",
    }
    assert required.issubset(row.keys()), (
        f"JSONL row missing fields the builder needs: {required - row.keys()}"
    )


def test_built_yaml_passes_dataset_schema(tmp_path):
    """The YAML produced by the builder is loadable and has the case
    shape the harness expects (id, inputs.scenario, expected_output.labels)."""
    html = PRESS_RELEASE_FIXTURE.read_text(encoding="utf-8")
    record = parse_press_release_html(html, PRESS_RELEASE_URL)
    jsonl_path = tmp_path / "enforcement.jsonl"
    _write_mom_jsonl(record, jsonl_path)

    cases = build(jsonl_path)
    yaml_path = tmp_path / "sglb_05_employment_issue.yaml"
    splits_dir = tmp_path / "benchmarks" / "sglb_05_employment_issue"
    write_outputs(cases, yaml_path, splits_dir)

    loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert "cases" in loaded, "dataset YAML must have top-level 'cases' key"
    first = loaded["cases"][0]
    assert "inputs" in first and "scenario" in first["inputs"]
    assert "expected_output" in first and "labels" in first["expected_output"]
    assert first["expected_output"]["labels"], "labels must be non-empty"
