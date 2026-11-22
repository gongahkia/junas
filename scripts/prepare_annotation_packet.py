#!/usr/bin/env python3
"""Assemble blank offline review packets using the T3B.1 annotation contract."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import prepare_evaluation_dataset as prep  # noqa: E402

RESERVATIONS = "junas.holdout_reservations.v1"
GROUPS = ("source_id", "template_family_id", "scenario_family_id")


def reservation_check(manifest, reservations):
    """Compare planning identities only; reserved sources do not exist yet."""
    docs = prep.validate_manifest(manifest, development_only=True)
    prep.keys(reservations, {"schema_version", "protocol_id", "dataset_id", "status", "documents"})
    prep.require(reservations["schema_version"] == RESERVATIONS, "invalid reservations schema")
    prep.require(reservations["protocol_id"] == prep.PROTOCOL, "invalid reservations protocol")
    prep.require(reservations["dataset_id"] == manifest["dataset_id"], "dataset identity mismatch")
    prep.require(reservations["status"] == "NOT READY", "reservations cannot establish a protected holdout")
    slots = reservations["documents"]
    prep.require(isinstance(slots, list) and 0 < len(slots) <= prep.MAX_DOCUMENTS, "invalid reservation count")
    seen, conflicts = {d["document_id"] for d in docs}, []
    for slot in slots:
        prep.keys(slot, {
            "document_id", "split", "source_id", "template_family_id", "scenario_family_id", "jurisdiction",
            "document_type", "content_status", "source_eligibility", "prior_use",
        })
        for key in ("document_id", *GROUPS):
            prep.require(prep.identifier(slot[key]), f"invalid reserved {key}")
        prep.require(slot["document_id"] not in seen, "duplicate reserved document ID")
        seen.add(slot["document_id"])
        prep.require(slot["split"] == "protected_holdout", "invalid reserved partition")
        prep.require(slot["jurisdiction"] == "SG" and slot["document_type"] == "unassigned", "invalid reservation scope")
        prep.require(slot["content_status"] == "not_collected", "reserved content must remain uncollected")
        prep.require(slot["source_eligibility"] == "pending" and slot["prior_use"] == "unknown", "unverified reserved eligibility")
        for doc in docs:
            reasons = [key for key in GROUPS if slot[key] == doc[key]]
            if reasons:
                conflicts.append({"documents": [doc["document_id"], slot["document_id"]], "reasons": reasons})
    return {
        "reserved_slots": len(slots), "conflicts": conflicts, "protected_holdout_readiness": "NOT READY",
        "content_comparison": "unavailable: reserved sources/text/hashes have not been collected",
        "qualification": "Disjoint planning IDs do not establish semantic separation or access protection.",
    }


def blank_submission(document):
    return {
        "schema_version": prep.REVIEW, "protocol_id": prep.PROTOCOL, "record_id": None,
        "document_id": document["document_id"], "split": "development",
        "canonical_text_sha256": document["canonical_text_sha256"], "reviewer_id": None,
        "stage": "draft", "timestamp": None,
        "provenance": {"label_origin": "unknown", "blinded_to_junas": None, "blinded_to_models": None,
                       "blinded_to_other_annotations": None, "source_author": None, "synthetic": document["synthetic"]},
        "coverage": {"PII": "unknown", "MNPI": "unknown"}, "pii": [], "mnpi": [], "exclusions": [],
        "notes": "", "supersedes": None, "based_on": [], "approval": None,
    }


def declared_independent(record, by_id):
    while True:
        p = record["provenance"]
        if not (
            p["label_origin"] == "human" and p["blinded_to_junas"] is True and p["blinded_to_models"] is True
            and p["blinded_to_other_annotations"] is True and p["source_author"] is False
        ):
            return False
        if record["supersedes"] is None:
            return True
        record = by_id[record["supersedes"]]


def workflow_status(manifest, texts, records, *, simulation=False):
    by_id, latest, accepted = prep.validate_reviews(manifest, texts, records)
    states = {}
    for document in manifest["documents"]:
        doc_id = document["document_id"]
        active = [by_id[i] for (d, _), i in latest.items() if d == doc_id]
        submitted = [r for r in active if r["stage"] == "submitted"]
        disagreements = [
            [a["record_id"], b["record_id"]] for a, b in combinations(submitted, 2)
            if prep.snapshot_content(a) != prep.snapshot_content(b)
        ]
        adjudications = [
            r for r in active if r["stage"] == "adjudicated"
            and set(r["based_on"]) == {x["record_id"] for x in submitted}
        ]
        state = "unreviewed"
        if doc_id in accepted:
            state = "accepted"
        elif adjudications:
            state = "adjudicated"
        elif disagreements:
            state = "disagreement_pending"
        elif len(submitted) >= 2:
            state = "independently_double_annotated" if all(
                declared_independent(r, by_id) for r in submitted
            ) else "double_annotated_unqualified"
        elif submitted:
            state = "annotated_by_one_reviewer"
        states[doc_id] = {
            "state": state, "active_submissions": len(submitted), "disagreements": disagreements,
            "independence": "declared_not_verified" if len(submitted) >= 2 and all(
                declared_independent(r, by_id) for r in submitted
            ) else "not_established",
        }
    return {
        "schema_version": "junas.annotation_packet_status.v1", "simulation": simulation, "documents": states,
        "recorded_events": len(records), "verified_human_events": 0,
        "qualification": "States describe supplied records only; reviewers, attestations and approvals are not authenticated.",
        "independent_ground_truth_readiness": "NOT READY", "protected_holdout_readiness": "NOT READY",
    }


def write_json(path, value):
    prep.write_new(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def build_packet(manifest_path, reservations_path, guidelines_path, output):
    manifest = prep.read_json(manifest_path)
    # refuse protected content before reading guidelines, sources or any labels.
    prep.validate_manifest(manifest, development_only=True)
    reservations = prep.read_json(reservations_path)
    check = reservation_check(manifest, reservations)
    prep.require(not check["conflicts"], "reserved source/template/scenario family contamination")
    manifest, texts = prep.load_development(manifest, manifest_path.parent)
    guidelines = guidelines_path.read_text(encoding="utf-8")
    prep.require(prep.nonempty(guidelines), "reviewer guidelines required")
    for document in manifest["documents"]:
        prep.require(document["source_path"] == document["text_path"], "packet pilot requires canonical-text sources")
    output.mkdir()  # existing packets are never overwritten.
    kit = output / "reviewer-kit"
    (kit / "documents").mkdir(parents=True)
    (kit / "submission-templates").mkdir()
    prep.write_new(kit / "INSTRUCTIONS.md", guidelines)
    metadata = []
    generated = copy.deepcopy(manifest)
    for document in generated["documents"]:
        doc_id = document["document_id"]
        relative = f"reviewer-kit/documents/{doc_id}.txt"
        # write bytes: no platform newline translation may alter the hash.
        with (output / relative).open("xb") as stream:
            stream.write(texts[doc_id].encode("utf-8"))
        document.update(source_path=relative, text_path=relative)
        metadata.append({k: document[k] for k in (
            "document_id", "source_id", "template_family_id", "scenario_family_id", "jurisdiction", "document_type",
            "canonical_text_sha256", "synthetic", "generation_origin",
        )})
        write_json(kit / "submission-templates" / f"{doc_id}.json", blank_submission(document))
    write_json(kit / "document-metadata.json", metadata)
    write_json(output / "manifest.json", generated)
    write_json(output / "holdout-reservations.json", reservations)
    write_json(output / "reservation-check.json", check)
    prep.write_new(output / "reviews.jsonl", "")
    write_json(output / "status.json", workflow_status(generated, texts, []))
    inventory = {
        str(p.relative_to(output)): prep.file_sha256(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    write_json(output / "packet-hashes.json", inventory)
    return {"development_documents": len(texts), "reserved_metadata_slots": check["reserved_slots"], "human_annotations": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("manifest", type=Path)
    p.add_argument("--reservations", type=Path, required=True)
    p.add_argument("--guidelines", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("status")
    p.add_argument("manifest", type=Path)
    p.add_argument("--reviews", type=Path, required=True)
    p.add_argument("--simulation", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_packet(args.manifest, args.reservations, args.guidelines, args.output)
        else:
            manifest, texts = prep.load_development(prep.read_json(args.manifest), args.manifest.parent)
            result = workflow_status(manifest, texts, prep.read_reviews(args.reviews), simulation=args.simulation)
            write_json(args.output, result)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"packet preparation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
