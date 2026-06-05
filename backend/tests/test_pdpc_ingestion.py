"""Unit tests for PDPC enforcement-decision ingestion (SGLB-01)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from data.ingestion import pdpc


def test_canonical_obligations_maps_aliases():
    assert pdpc.canonical_obligations("Protection") == ["protection"]
    assert pdpc.canonical_obligations("Accountability, Protection") == [
        "accountability",
        "protection",
    ]
    assert pdpc.canonical_obligations("Retention") == ["retention_limitation"]
    assert pdpc.canonical_obligations("DPO") == ["dpo"]


def test_canonical_obligations_rejects_unknown():
    assert pdpc.canonical_obligations("Not A Real Tag") == []


def test_canonical_obligations_deduplicates():
    assert pdpc.canonical_obligations("Protection, Protection") == ["protection"]


def test_parse_penalty_sgd_handles_dollar_format():
    assert pdpc.parse_penalty_sgd("$8,750") == 8750
    assert pdpc.parse_penalty_sgd("S$1,500.00") == 1500
    assert pdpc.parse_penalty_sgd("$0") == 0
    assert pdpc.parse_penalty_sgd("None") is None
    assert pdpc.parse_penalty_sgd("") is None


def test_derive_penalty_band_boundaries():
    assert pdpc.derive_penalty_band(None) == "none"
    assert pdpc.derive_penalty_band(0) == "none"
    assert pdpc.derive_penalty_band(1) == "low"
    assert pdpc.derive_penalty_band(4_999) == "low"
    assert pdpc.derive_penalty_band(5_000) == "mid"
    assert pdpc.derive_penalty_band(49_999) == "mid"
    assert pdpc.derive_penalty_band(50_000) == "high"
    assert pdpc.derive_penalty_band(315_000) == "high"


def test_redact_fact_summary_strips_penalty_lead():
    raw = (
        "A financial penalty of $58,000 was imposed and directions were issued to "
        "Goldheart Jewelry Pte Ltd for failing to put in place adequate patch "
        "management processes. Click here for more information."
    )
    out = pdpc.redact_fact_summary(raw)
    assert "$58,000" not in out
    assert "financial penalty" not in out.lower()
    assert "Click here" not in out
    assert "Goldheart Jewelry Pte Ltd" in out
    assert "failing to put in place adequate patch management processes" in out


def test_redact_fact_summary_masks_dollar_amounts_inline():
    raw = "The organisation was fined $10,000 and paid $5,500 in costs."
    out = pdpc.redact_fact_summary(raw)
    assert "$10,000" not in out
    assert "$5,500" not in out
    assert "[AMOUNT_REDACTED]" in out


def test_parse_pub_date_handles_pdpc_format():
    assert pdpc.parse_pub_date("26 Feb 2026") == dt.date(2026, 2, 26)
    assert pdpc.parse_pub_date("08 Jan 2020") == dt.date(2020, 1, 8)
    assert pdpc.parse_pub_date("") is None
    assert pdpc.parse_pub_date("not a date") is None


def test_assign_split_uses_documented_cutoffs():
    assert pdpc.assign_split(dt.date(2020, 5, 1)) == "train"
    assert pdpc.assign_split(dt.date(2023, 12, 31)) == "train"
    assert pdpc.assign_split(dt.date(2024, 1, 1)) == "dev"
    assert pdpc.assign_split(dt.date(2025, 12, 31)) == "dev"
    assert pdpc.assign_split(dt.date(2026, 1, 1)) == "test"
    assert pdpc.assign_split(dt.date(2026, 6, 4)) == "test"


def test_stable_id_is_deterministic_per_url():
    url = "https://www.pdpc.gov.sg/all-commissions-decisions/2026/01/example"
    assert pdpc.stable_id(url) == pdpc.stable_id(url)
    assert pdpc.stable_id(url).startswith("sglb_01_")
    assert len(pdpc.stable_id(url)) == len("sglb_01_") + 12


def test_stable_id_differs_per_url():
    a = pdpc.stable_id("https://a")
    b = pdpc.stable_id("https://b")
    assert a != b


def test_row_to_case_minimal_happy_path():
    row = {
        "Case Name": "Re Acme Pte Ltd",
        "Case Citation": "[2024] SGPDPC 1",
        "Date": "15 Mar 2024",
        "Obligations": "Protection",
        "Decision Type": "Financial Penalty",
        "Case Description": (
            "A financial penalty of $25,000 was imposed and directions were "
            "issued to Acme Pte Ltd for failing to put in place reasonable "
            "security arrangements to protect personal data."
        ),
        "Financial Penalty": "$25,000",
        "URL": "https://www.pdpc.gov.sg/example",
    }
    case, reason = pdpc._row_to_case(row)
    assert reason == ""
    assert case is not None
    assert case.obligations == ["protection"]
    assert case.penalty_band == "mid"
    assert case.penalty_sgd == 25_000
    assert case.split == "dev"
    assert "$25,000" not in case.fact_summary


def test_row_to_case_excludes_missing_url():
    case, reason = pdpc._row_to_case(
        {"Case Description": "x" * 100, "Date": "01 Jan 2024", "Obligations": "Protection"}
    )
    assert case is None
    assert "url" in reason


def test_row_to_case_excludes_unknown_obligation():
    row = {
        "URL": "https://example",
        "Date": "01 Jan 2024",
        "Obligations": "Made-Up Obligation",
        "Case Description": "x" * 200,
    }
    case, reason = pdpc._row_to_case(row)
    assert case is None
    assert "no obligations" in reason


def test_jsonl_row_shape_matches_harness_contract():
    row = {
        "Case Name": "Re Test Co",
        "Case Citation": "[2023] SGPDPC 99",
        "Date": "15 Jun 2023",
        "Obligations": "Protection, Accountability",
        "Decision Type": "Financial Penalty, Directions",
        "Case Description": (
            "A financial penalty of $10,000 was imposed and directions were "
            "issued to Test Co for failing to appoint a DPO."
        ),
        "Financial Penalty": "$10,000",
        "URL": "https://example.test/case",
    }
    case, _ = pdpc._row_to_case(row)
    assert case is not None
    payload = case.as_jsonl_row()
    assert payload["inputs"]["fact_summary"]
    assert payload["expected_output"]["obligations"] == ["protection", "accountability"]
    assert payload["expected_output"]["penalty_band"] == "mid"
    assert payload["extraction_rule_sha"]
    assert len(payload["extraction_rule_sha"]) == 7
    assert payload["metadata"]["task"] == "SGLB-01"
    assert payload["metadata"]["dataset_version"] == pdpc.DATASET_VERSION
    assert payload["metadata"]["label_provenance"].startswith("mechanical-extraction")


@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "data" / "raw" / "pdpc_decisions.xlsx").exists(),
    reason="raw PDPC xlsx not vendored in this environment",
)
def test_full_ingest_writes_splits_and_yaml(tmp_path: Path):
    xlsx = Path(__file__).parent.parent / "data" / "raw" / "pdpc_decisions.xlsx"
    out_dir = tmp_path / "sglb_01_pdpa"
    yaml_path = tmp_path / "sglb_01_pdpa.yaml"
    stats = pdpc.ingest(xlsx_path=xlsx, output_dir=out_dir, yaml_path=yaml_path)
    assert stats.written > 0
    assert (out_dir / "train.jsonl").exists()
    assert (out_dir / "dev.jsonl").exists()
    assert (out_dir / "test.jsonl").exists()
    assert yaml_path.exists()
    # Roundtrip a sample row.
    line = (out_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()[0]
    row = json.loads(line)
    assert row["id"].startswith("sglb_01_")
    assert "fact_summary" in row["inputs"]
    assert "obligations" in row["expected_output"]
    assert "penalty_band" in row["expected_output"]
    assert row["extraction_rule_sha"]
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert payload["extraction_rules"]["pdpc"] == row["extraction_rule_sha"]
    assert payload["cases"][0]["extraction_rule_sha"] == row["extraction_rule_sha"]
