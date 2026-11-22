"""Blind packet integrity and simulated review mechanics, never classifier performance."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import prepare_annotation_packet as packet
from scripts import prepare_evaluation_dataset as prep
from test.test_annotation_preparation import accept, entry, plan, seal

PILOT = prep.ROOT / "docs/annotation-pilot"


def reservations(manifest):
    return {
        "schema_version": packet.RESERVATIONS,
        "protocol_id": prep.PROTOCOL,
        "dataset_id": manifest["dataset_id"],
        "status": "NOT READY",
        "documents": [
            {
                "document_id": "reserved-toy",
                "split": "protected_holdout",
                "source_id": "unused-source",
                "template_family_id": "unused-template",
                "scenario_family_id": "unused-scenario",
                "jurisdiction": "SG",
                "document_type": "unassigned",
                "content_status": "not_collected",
                "source_eligibility": "pending",
                "prior_use": "unknown",
            }
        ],
    }


@pytest.fixture
def toy(tmp_path):
    (tmp_path / "source.txt").write_bytes(b"Alex Alex\r\ntransaction pending")
    (tmp_path / "canonical.txt").write_bytes(b"Alex Alex\r\ntransaction pending")
    return prep.load_development(plan(), tmp_path, verify=False)


def stage(manifest, texts, records):
    report = packet.workflow_status(manifest, texts, records, simulation=True)
    assert report["simulation"] is True and report["verified_human_events"] == 0
    return report["documents"]["toy-1"]


def test_real_packet_has_twenty_unreviewed_sources_and_ten_content_free_reservations():
    manifest, texts = prep.load_development(prep.read_json(PILOT / "manifest.json"), PILOT)
    assert len(texts) == 20 and {d["jurisdiction"] for d in manifest["documents"]} == {"SG"}
    assert len({d["scenario_family_id"] for d in manifest["documents"]}) == 10
    assert all(d["synthetic"] and d["generation_origin"] == "model" for d in manifest["documents"])
    assert all(d["prior_use"] == "development" for d in manifest["documents"])
    reserved = prep.read_json(PILOT / "holdout-reservations.json")
    check = packet.reservation_check(manifest, reserved)
    assert check["reserved_slots"] == 10 and check["conflicts"] == []
    assert check["protected_holdout_readiness"] == "NOT READY"
    assert all(
        set(r).isdisjoint({"text", "text_path", "source_path", "source_sha256", "canonical_text_sha256"})
        for r in reserved["documents"]
    )
    assert prep.read_reviews(PILOT / "reviews.jsonl") == []
    status = packet.workflow_status(manifest, texts, [])
    assert all(d["state"] == "unreviewed" for d in status["documents"].values())
    assert status["verified_human_events"] == status["recorded_events"] == 0


def test_packet_inventory_and_blank_identity_times_and_labels():
    for name, digest in prep.read_json(PILOT / "packet-hashes.json").items():
        assert prep.file_sha256(PILOT / name) == digest
    manifest = prep.read_json(PILOT / "manifest.json")
    for document in manifest["documents"]:
        r = prep.read_json(PILOT / "reviewer-kit/submission-templates" / (document["document_id"] + ".json"))
        assert r == packet.blank_submission(document)
        assert r["reviewer_id"] is r["timestamp"] is r["record_id"] is r["approval"] is None
        assert r["pii"] == r["mnpi"] == r["exclusions"] == []
        assert r["coverage"] == {"PII": "unknown", "MNPI": "unknown"}
    guide = (PILOT / "reviewer-kit/INSTRUCTIONS.md").read_text()
    assert all(rule not in guide for rules in prep.PII_RULE_MAP.values() for rule in rules)
    assert "must_detect" not in guide and "actual case labels" not in guide
    assert set(prep.PII_RULE_MAP) <= set(guide.replace("`", " ").split())


def test_templates_cannot_be_submitted_as_gold():
    manifest, texts = prep.load_development(prep.read_json(PILOT / "manifest.json"), PILOT)
    r = packet.blank_submission(manifest["documents"][0])
    r["stage"] = "accepted"
    r = seal(r)
    with pytest.raises(ValueError):
        prep.validate_reviews(manifest, texts, [r])


def test_single_and_independent_double_annotations_are_qualified(toy):
    manifest, texts = toy
    assert stage(manifest, texts, [])["state"] == "unreviewed"
    a = seal(entry(manifest, reviewer="sim-a"))
    assert stage(manifest, texts, [a])["state"] == "annotated_by_one_reviewer"
    b = seal(entry(manifest, reviewer="sim-b", record_id="r2"), [a])
    result = stage(manifest, texts, [a, b])
    assert result["state"] == "independently_double_annotated"
    assert result["independence"] == "declared_not_verified"


def test_unqualified_double_annotation_never_claims_independence(toy):
    manifest, texts = toy
    a = seal(entry(manifest, reviewer="sim-a"))
    b = entry(manifest, reviewer="sim-b", record_id="r2")
    b["provenance"]["blinded_to_other_annotations"] = False
    b = seal(b, [a])
    assert stage(manifest, texts, [a, b])["state"] == "double_annotated_unqualified"


def test_disagreement_adjudication_and_explicit_acceptance_remain_separate(toy):
    manifest, texts = toy
    a = seal(entry(manifest, reviewer="sim-a"))
    b = entry(manifest, reviewer="sim-b", record_id="r2")
    b["pii"] = []
    b = seal(b, [a])
    records = [a, b]
    assert stage(manifest, texts, records)["state"] == "disagreement_pending"
    adj = entry(manifest, reviewer="sim-adjudicator", stage="adjudicated", record_id="adj")
    adj["based_on"] = ["r1", "r2"]
    records.append(seal(adj, records))
    result = stage(manifest, texts, records)
    assert result["state"] == "adjudicated" and result["disagreements"] == [["r1", "r2"]]
    records.append(accept(manifest, records[-1], records))
    assert stage(manifest, texts, records)["state"] == "accepted"


def test_correction_revokes_completion_and_retains_provenance(toy):
    manifest, texts = toy
    a = entry(manifest, reviewer="sim-a")
    a["provenance"]["label_origin"] = "detector_derived"
    a = seal(a)
    corrected = entry(manifest, reviewer="sim-a", record_id="r2")
    corrected["supersedes"] = "r1"
    corrected = seal(corrected, [a])
    b = seal(entry(manifest, reviewer="sim-b", record_id="r3"), [a, corrected])
    result = stage(manifest, texts, [a, corrected, b])
    assert result["state"] == "double_annotated_unqualified"


@pytest.mark.parametrize("key", packet.GROUPS)
def test_reserved_family_overlap_is_reported_without_reading_sources(toy, key):
    manifest, _ = toy
    reserved = reservations(manifest)
    reserved["documents"][0][key] = manifest["documents"][0][key]
    with patch.object(Path, "read_bytes", side_effect=AssertionError("metadata only")):
        assert packet.reservation_check(manifest, reserved)["conflicts"][0]["reasons"] == [key]


@pytest.mark.parametrize(
    "field,value", [("text", "must not collect"), ("source_sha256", "a" * 64), ("reviewer_id", "invented")]
)
def test_reserved_contents_hashes_and_reviewers_are_refused(toy, field, value):
    manifest, _ = toy
    reserved = reservations(manifest)
    reserved["documents"][0][field] = value
    with pytest.raises(ValueError, match="fields"):
        packet.reservation_check(manifest, reserved)


def test_builder_copies_exact_text_and_never_overwrites(toy, tmp_path):
    manifest, _ = toy
    prep.write_new(tmp_path / "manifest.json", json.dumps(manifest))
    prep.write_new(tmp_path / "reserved.json", json.dumps(reservations(manifest)))
    prep.write_new(tmp_path / "guide.md", "Toy guidelines only\n")
    out = tmp_path / "packet"
    args = [
        "build",
        str(tmp_path / "manifest.json"),
        "--reservations",
        str(tmp_path / "reserved.json"),
        "--guidelines",
        str(tmp_path / "guide.md"),
        "--output",
        str(out),
    ]
    assert packet.main(args) == 0
    assert (out / "reviewer-kit/documents/toy-1.txt").read_bytes() == b"Alex Alex\r\ntransaction pending"
    assert packet.main(args) == 2
    manifest, texts = prep.load_development(prep.read_json(out / "manifest.json"), out)
    assert packet.workflow_status(manifest, texts, [])["recorded_events"] == 0


def test_builder_refuses_protected_before_other_content_reads(toy, tmp_path):
    manifest, _ = toy
    manifest = copy.deepcopy(manifest)
    manifest["documents"][0]["split"] = "protected_holdout"
    with patch.object(prep, "read_json", side_effect=[manifest]):
        with patch.object(Path, "read_text", side_effect=AssertionError("do not read guidelines or text")):
            with pytest.raises(ValueError, match="protected content access refused"):
                packet.build_packet(
                    tmp_path / "manifest.json", tmp_path / "reserved.json", tmp_path / "guide", tmp_path / "out"
                )
    assert not (tmp_path / "out").exists()


def test_repeated_offsets_and_incomplete_targets_use_existing_validator(toy):
    manifest, texts = toy
    a = entry(manifest, reviewer="sim-a")
    a["pii"].append(dict(a["pii"][0], start_char=5, end_char=9))
    assert stage(manifest, texts, [seal(a)])["active_submissions"] == 1
    a["pii"][1]["start_char"] = 6
    with pytest.raises(ValueError, match="span/text mismatch"):
        stage(manifest, texts, [seal(a)])
    a["pii"].pop()
    a["coverage"]["MNPI"] = "complete"
    with pytest.raises(ValueError, match="coverage declaration"):
        stage(manifest, texts, [seal(a)])


def test_packet_module_has_no_classifier_import():
    code = (
        "import sys; from scripts import prepare_annotation_packet; "
        "assert not any(x.startswith('junas') for x in sys.modules)"
    )
    assert subprocess.run([sys.executable, "-B", "-c", code], cwd=prep.ROOT, capture_output=True).returncode == 0
