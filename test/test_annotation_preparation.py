"""Synthetic infrastructure checks, never a classifier-performance benchmark."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import prepare_evaluation_dataset as prep
from scripts.span_metrics import occurrence_scores


def plan():
    return {
        "schema_version": prep.MANIFEST,
        "protocol_id": prep.PROTOCOL,
        "dataset_id": "toy-only",
        "purpose": "tooling_toy",
        "documents": [
            {
                "document_id": "toy-1",
                "split": "development",
                "source_id": "toy-source",
                "template_family_id": "toy-template",
                "scenario_family_id": "toy-scenario",
                "source_path": "source.txt",
                "text_path": "canonical.txt",
                "jurisdiction": "SG",
                "document_type": "memo",
                "synthetic": True,
                "generation_origin": "human",
                "authorization": {
                    "basis": "synthetic_owned",
                    "reference": "unit-test-only",
                    "licence": "repository test",
                },
                "prior_use": "none",
            }
        ],
    }


@pytest.fixture
def dataset(tmp_path):
    (tmp_path / "source.txt").write_bytes(b"Alex Alex\r\ntransaction pending")
    (tmp_path / "canonical.txt").write_bytes(b"Alex Alex\r\ntransaction pending")
    return prep.load_development(plan(), tmp_path, verify=False)


def entry(manifest, *, reviewer="annotator-a", stage="submitted", record_id="r1"):
    return {
        "schema_version": prep.REVIEW,
        "protocol_id": prep.PROTOCOL,
        "record_id": record_id,
        "document_id": "toy-1",
        "split": "development",
        "canonical_text_sha256": manifest["documents"][0]["canonical_text_sha256"],
        "reviewer_id": reviewer,
        "stage": stage,
        "timestamp": "2026-01-01T12:00:00Z",
        "provenance": {
            "label_origin": "human",
            "blinded_to_junas": True,
            "blinded_to_models": True,
            "blinded_to_other_annotations": True,
            "source_author": False,
            "synthetic": True,
        },
        "coverage": {"PII": "exhaustive", "MNPI": "unknown"},
        "pii": [
            {
                "category": "PII",
                "label": "PERSON_NAME",
                "start_char": 0,
                "end_char": 4,
                "matched_text": "Alex",
                "certainty": "certain",
                "reason": "fictional individual",
            }
        ],
        "mnpi": [],
        "exclusions": [],
        "notes": "toy declaration, no actual human review",
        "supersedes": None,
        "based_on": [],
        "approval": None,
    }


def seal(record, records=()):
    record = copy.deepcopy(record)
    record["previous_record_sha256"] = records[-1]["record_sha256"] if records else None
    record["record_sha256"] = prep.record_hash(record)
    return record


def accept(manifest, base, records):
    r = entry(manifest, reviewer="acceptance-owner", stage="accepted", record_id="accept1")
    for k in ("pii", "mnpi", "coverage", "exclusions"):
        r[k] = copy.deepcopy(base[k])
    r["based_on"] = [base["record_id"]]
    r["approval"] = {"reviewer_id": r["reviewer_id"], "timestamp": r["timestamp"], "reason": "toy explicit approval"}
    return seal(r, records)


def test_exact_annotations_and_crlf_preservation(dataset):
    manifest, texts = dataset
    assert texts["toy-1"] == "Alex Alex\r\ntransaction pending"
    r = seal(entry(manifest))
    result = prep.review_report(manifest, texts, [r])
    assert result["validation"] == "PASS" and result["accepted_documents"] == 0
    assert result["independent_ground_truth_readiness"] == "NOT READY"


def test_repeated_occurrences_remain_distinct_and_t3a_compatible(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    second = dict(r["pii"][0], start_char=5, end_char=9)
    r["pii"].append(second)
    submitted = seal(r)
    approved = accept(manifest, submitted, [submitted])
    spans, units, coverage = prep.occurrence_inputs(manifest, texts, [submitted, approved])
    assert [(s.start, s.end) for s in spans] == [(0, 4), (5, 9)]
    # both sides are toy annotations, never Junas or model predictions.
    assert occurrence_scores(spans, spans, texts=units, coverage=coverage)["exact"]["matched"] == 2
    q = prep.review_report(manifest, texts, [submitted, approved])["accepted_qualifications"]["toy-1"]
    assert q["synthetic"] and not q["adjudicated"] and q["annotators"] == ["annotator-a"]
    assert q["independence"] == "declared_not_verified"


@pytest.mark.parametrize(
    "change",
    [
        {"start_char": -1},
        {"start_char": 1},
        {"start_char": True},
        {"end_char": 99},
        {"end_char": 0},
        {"matched_text": "other"},
        {"label": "CORPORATION"},
    ],
)
def test_bad_offsets_and_taxonomy_refused(dataset, change):
    manifest, texts = dataset
    r = entry(manifest)
    r["pii"][0].update(change)
    with pytest.raises(ValueError):
        prep.validate_reviews(manifest, texts, [seal(r)])


def test_missing_coverage_is_not_exhaustive(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    del r["coverage"]["PII"]
    with pytest.raises(ValueError, match="fields"):
        prep.validate_reviews(manifest, texts, [seal(r)])


def test_partial_and_uncertain_annotations_stay_qualified(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    r["pii"][0]["certainty"] = "abstain"
    with pytest.raises(ValueError, match="uncertain PII"):
        prep.validate_reviews(manifest, texts, [seal(r)])
    r["coverage"]["PII"] = "partial"
    submitted = seal(r)
    approved = accept(manifest, submitted, [submitted])
    spans, units, coverage = prep.occurrence_inputs(manifest, texts, [submitted, approved])
    assert spans == []
    assert occurrence_scores(spans, [], texts=units, coverage=coverage)["exact"]["precision_if_exhaustive"] is None


def test_unknown_provenance_and_model_proposals_cannot_be_laundered(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    r["provenance"].update(label_origin="human_reviewed_model", blinded_to_models=False)
    r = seal(r)
    approved = accept(manifest, r, [r])
    result = prep.review_report(manifest, texts, [r, approved])
    q = result["accepted_qualifications"]["toy-1"]
    assert q["label_origins"] == ["human", "human_reviewed_model"] and q["independence"] == "not_established"
    r = entry(manifest)
    r["provenance"].update(label_origin="unknown", blinded_to_junas=None)
    assert prep.review_report(manifest, texts, [seal(r)])["declared_blind_non_author_submissions"] == 0


def test_unreviewed_drafts_never_become_occurrence_gold(dataset):
    manifest, texts = dataset
    draft = seal(entry(manifest, stage="draft"))
    assert prep.occurrence_inputs(manifest, texts, [draft]) == ([], {}, {})
    with pytest.raises(ValueError, match="unsubmitted draft"):
        prep.validate_reviews(manifest, texts, [draft, accept(manifest, draft, [draft])])


def test_disagreements_require_separate_adjudication(dataset):
    manifest, texts = dataset
    a = seal(entry(manifest))
    b = entry(manifest, reviewer="annotator-b", record_id="r2")
    b["pii"] = []
    b = seal(b, [a])
    assert prep.review_report(manifest, texts, [a, b])["disagreements"] == [["r1", "r2"]]
    with pytest.raises(ValueError, match="adjudication"):
        prep.validate_reviews(manifest, texts, [a, b, accept(manifest, a, [a, b])])
    adjudication = entry(manifest, reviewer="adjudicator", stage="adjudicated", record_id="adj")
    adjudication["based_on"] = ["r1", "r2"]
    adjudication = seal(adjudication, [a, b])
    records = [a, b, adjudication]
    records.append(accept(manifest, adjudication, records))
    report = prep.review_report(manifest, texts, records)
    assert report["accepted_documents"] == 1 and report["accepted_qualifications"]["toy-1"]["adjudicated"]
    assert report["disagreements"] == [["r1", "r2"]]  # history retained.


def test_corrections_are_linked_and_revoke_old_acceptance(dataset):
    manifest, texts = dataset
    a = seal(entry(manifest))
    approved = accept(manifest, a, [a])
    correction = entry(manifest, record_id="r2")
    correction["supersedes"] = "r1"
    records = [a, approved]
    records.append(seal(correction, records))
    assert prep.review_report(manifest, texts, records)["accepted_documents"] == 0
    correction["supersedes"] = None
    with pytest.raises(ValueError, match="previous snapshot"):
        prep.validate_reviews(manifest, texts, [a, approved, seal(correction, [a, approved])])


def test_log_tampering_and_duplicate_ids_are_refused(dataset):
    manifest, texts = dataset
    a = seal(entry(manifest))
    a["notes"] += " changed"
    with pytest.raises(ValueError, match="hash mismatch"):
        prep.validate_reviews(manifest, texts, [a])
    a = seal(entry(manifest))
    with pytest.raises(ValueError):
        prep.validate_reviews(manifest, texts, [a, seal(entry(manifest), [a])])


def test_no_silent_changes_at_acceptance(dataset):
    manifest, texts = dataset
    a = seal(entry(manifest))
    approved = accept(manifest, a, [a])
    approved["pii"] = []
    with pytest.raises(ValueError, match="silently change"):
        prep.validate_reviews(manifest, texts, [a, seal(approved, [a])])


def test_uncertain_mnpi_is_neither_safe_nor_high_risk(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    r["mnpi"] = [
        {
            "start_char": 11,
            "end_char": 30,
            "matched_text": "transaction pending",
            "entity": None,
            "potential_materiality": "unknown",
            "public_status": "unknown",
            "as_of": None,
            "evidence": [],
            "ambiguity": "no issuer or publication context",
            "human_review_required": True,
        }
    ]
    assert prep.review_report(manifest, texts, [seal(r)])["validation"] == "PASS"
    r["mnpi"][0]["human_review_required"] = False
    with pytest.raises(ValueError, match="human review"):
        prep.validate_reviews(manifest, texts, [seal(r)])


def heldout_metadata(manifest):
    m = copy.deepcopy(manifest)
    d = m["documents"][0]
    d.update(
        document_id="held-toy",
        split="protected_holdout",
        source_id="other-source",
        template_family_id="other-template",
        scenario_family_id="other-scenario",
    )
    return m


@pytest.mark.parametrize(
    "key", ["source_id", "template_family_id", "scenario_family_id", "source_sha256", "canonical_text_sha256"]
)
def test_cross_partition_contamination(dataset, key):
    manifest, _ = dataset
    held = heldout_metadata(manifest)
    held["documents"][0][key] = manifest["documents"][0][key]
    result = prep.partition_check([manifest, held])
    assert key in result["conflicts"][0]["reasons"]
    assert result["protected_holdout_readiness"] == "NOT READY"


def test_near_duplicate_variants_and_regression_registry(dataset):
    manifest, _ = dataset
    held = heldout_metadata(manifest)
    result = prep.partition_check([manifest, held], [held["documents"][0]["source_sha256"]])
    assert any("previously_used_source" in c["reasons"] for c in result["conflicts"])
    assert any("near_duplicate" in c["reasons"] for c in result["conflicts"])
    assert prep.fingerprints("Case 123\nAgreement") == prep.fingerprints("CASE 999 agreement")


def test_protected_admission_happens_before_any_content_read(dataset):
    manifest, _ = dataset
    held = heldout_metadata(manifest)
    with patch.object(Path, "read_bytes", side_effect=AssertionError("must not open protected source")):
        with pytest.raises(ValueError, match="protected content access refused"):
            prep.load_development(held, Path("/does-not-exist"))
        assert prep.partition_check([held])["protected_holdout_readiness"] == "NOT READY"


def test_prior_exposed_holdout_and_malformed_manifest(dataset):
    manifest, _ = dataset
    held = heldout_metadata(manifest)
    held["documents"][0]["prior_use"] = "regression"
    with pytest.raises(ValueError, match="previously exposed"):
        prep.partition_check([held])
    manifest["documents"] = []
    with pytest.raises(ValueError):
        prep.validate_manifest(manifest)


def test_text_edits_and_path_escape_are_refused(dataset, tmp_path):
    manifest, _ = dataset
    (tmp_path / "canonical.txt").write_text("changed")
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        prep.load_development(manifest, tmp_path)
    manifest["documents"][0]["text_path"] = "../secret.txt"
    with pytest.raises(ValueError, match="unsafe source path"):
        prep.load_development(manifest, tmp_path)


def test_cli_creates_new_hashes_and_append_only_snapshots_without_overwrite(tmp_path):
    (tmp_path / "source.txt").write_text("Alex Alex")
    (tmp_path / "canonical.txt").write_text("Alex Alex")
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan()))
    manifest_path = tmp_path / "manifest.json"
    assert prep.main(["fingerprint", str(path), "--output", str(manifest_path)]) == 0
    assert prep.main(["fingerprint", str(path), "--output", str(manifest_path)]) == 2
    manifest = json.loads(manifest_path.read_text())
    e = tmp_path / "entry.json"
    e.write_text(json.dumps(entry(manifest, stage="draft")))
    log = tmp_path / "reviews.jsonl"
    assert prep.main(["append", str(manifest_path), "--entry", str(e), "--output", str(log)]) == 0
    old = log.read_bytes()
    correction = entry(manifest, stage="submitted", record_id="r2")
    correction["supersedes"] = "r1"
    e.write_text(json.dumps(correction))
    new_log = tmp_path / "reviews-v2.jsonl"
    assert (
        prep.main(["append", str(manifest_path), "--reviews", str(log), "--entry", str(e), "--output", str(new_log)])
        == 0
    )
    assert log.read_bytes() == old
    report = tmp_path / "report.json"
    assert prep.main(["validate", str(manifest_path), "--reviews", str(new_log), "--output", str(report)]) == 0
    assert json.loads(report.read_text())["accepted_documents"] == 0


def test_cli_refuses_protected_before_reading_review_file(dataset, tmp_path):
    manifest, _ = dataset
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(heldout_metadata(manifest)))
    assert (
        prep.main(
            [
                "validate",
                str(path),
                "--reviews",
                str(tmp_path / "MUST-NOT-OPEN"),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        == 2
    )
    assert not (tmp_path / "out.json").exists()


def test_correction_does_not_erase_detector_exposure(dataset):
    manifest, texts = dataset
    first = entry(manifest)
    first["provenance"]["label_origin"] = "detector_derived"
    first = seal(first)
    corrected = entry(manifest, record_id="r2")
    corrected["supersedes"] = "r1"
    corrected = seal(corrected, [first])
    approved = accept(manifest, corrected, [first, corrected])
    q = prep.review_report(manifest, texts, [first, corrected, approved])["accepted_qualifications"]["toy-1"]
    assert "detector_derived" in q["label_origins"] and q["independence"] == "not_established"


def test_distinct_labels_may_overlap_but_identical_gold_may_not(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    r["pii"].append(dict(r["pii"][0], label="PERSONAL_RECORD_ID"))
    assert prep.review_report(manifest, texts, [seal(r)])["validation"] == "PASS"
    r["pii"].append(r["pii"][0])
    with pytest.raises(ValueError, match="duplicate PII"):
        prep.validate_reviews(manifest, texts, [seal(r)])


def test_negative_annotations_and_missing_reviewers_stay_qualified(dataset):
    manifest, texts = dataset
    r = entry(manifest)
    r["pii"] = []
    r["provenance"]["source_author"] = True
    r = seal(r)
    report = prep.review_report(manifest, texts, [r, accept(manifest, r, [r])])
    q = report["accepted_qualifications"]["toy-1"]
    assert q["qualification"] == "single annotator" and q["independence"] == "not_established"
    assert q["coverage"]["PII"] == "exhaustive"


@pytest.mark.parametrize("field", ["blinded_to_junas", "blinded_to_models", "blinded_to_other_annotations"])
def test_missing_blindness_does_not_establish_independence(dataset, field):
    manifest, texts = dataset
    r = entry(manifest)
    r["provenance"][field] = None
    r = seal(r)
    approved = accept(manifest, r, [r])
    q = prep.review_report(manifest, texts, [r, approved])["accepted_qualifications"]["toy-1"]
    assert q["independence"] == "not_established"


def test_symlink_escape_is_refused(dataset, tmp_path):
    manifest, _ = dataset
    (tmp_path / "canonical.txt").unlink()
    (tmp_path / "canonical.txt").symlink_to(tmp_path.parent / "outside.txt")
    with pytest.raises(ValueError, match="escapes"):
        prep.load_development(manifest, tmp_path)


def test_independent_groups_do_not_imply_holdout_readiness(dataset):
    manifest, _ = dataset
    held = heldout_metadata(manifest)
    d = held["documents"][0]
    d.update(source_sha256="a" * 64, canonical_text_sha256="b" * 64, similarity_sha256=["c" * 64])
    result = prep.partition_check([manifest, held])
    assert result["status"] == "no_recorded_conflict" and result["protected_holdout_readiness"] == "NOT READY"


def test_cli_malformed_input_creates_no_report(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("[]")
    out = tmp_path / "out.json"
    assert prep.main(["fingerprint", str(path), "--output", str(out)]) == 2
    assert not out.exists()


def test_preparation_does_not_import_classifier():
    import subprocess
    import sys

    code = (
        "import sys; from scripts import prepare_evaluation_dataset; "
        "assert not any(x.startswith('junas') for x in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-B", "-c", code], cwd=prep.ROOT, capture_output=True).returncode == 0
