#!/usr/bin/env python3
"""Offline annotation preparation; never invokes a detector or evaluates a holdout."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.span_metrics import COVERAGE, Span, file_sha256, input_identity  # noqa: E402

PROTOCOL = "junas.legal-pilot.v1"
MANIFEST = "junas.annotation_manifest.v1"
REVIEW = "junas.annotation_review.v1"
PII_RULE_MAP = {
    "GOVERNMENT_ID": ("sg_nric_fin", "us_ssn", "uk_nin", "au_tfn", "passport_number"),
    "PERSON_NAME": ("named_person",),
    "EMAIL": ("email_address",),
    "PHONE": ("phone_number",),
    "POSTAL_ADDRESS": ("sg_postal_address", "au_postal_address"),
    "BANK_ACCOUNT": ("bank_account",),
    "PERSONAL_RECORD_ID": (
        "employee_id",
        "customer_account_number",
        "bank_customer_reference",
        "medical_record_number",
        "insurance_member_id",
    ),
    "DATE_OF_BIRTH": ("date_of_birth",),
    "QUASI_IDENTIFIER_COMBINATION": ("quasi_identifier_combination",),
}
MAX_DOCUMENTS = 100
MAX_TEXT_CHARACTERS = 20_000
NEAR_DUPLICATE_THRESHOLD = 0.75


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, required, optional=()):
    require(isinstance(value, dict), "expected an object")
    require(
        set(required) <= value.keys() <= set(required) | set(optional), f"invalid fields; expected {sorted(required)}"
    )


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value) is not None


def timestamp(value):
    require(nonempty(value), "timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    require(parsed.tzinfo is not None, "timestamp must include timezone")
    return parsed


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def record_hash(record):
    payload = {k: v for k, v in record.items() if k != "record_sha256"}
    return input_identity(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def fingerprints(text):
    """Contamination heuristic only; exact annotation text is never normalized."""
    tokens = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    tokens = ["<number>" if any(c.isdigit() for c in token) else token for token in tokens]
    width = min(3, len(tokens))
    return sorted({input_identity(" ".join(tokens[i : i + width])) for i in range(len(tokens) - width + 1)})


def validate_manifest(manifest, *, hashed=True, development_only=False):
    keys(manifest, {"schema_version", "protocol_id", "dataset_id", "purpose", "documents"})
    require(manifest["schema_version"] == MANIFEST and manifest["protocol_id"] == PROTOCOL, "unknown manifest/protocol")
    require(identifier(manifest["dataset_id"]), "invalid dataset ID")
    require(manifest["purpose"] in {"tooling_toy", "pilot"}, "invalid dataset purpose")
    docs = manifest["documents"]
    require(isinstance(docs, list) and 0 < len(docs) <= MAX_DOCUMENTS, "expected 1–100 documents")
    # admission precedes all source, text and review file reads.
    require(all(isinstance(d, dict) for d in docs), "invalid document record")
    if development_only:
        require(all(d.get("split") == "development" for d in docs), "protected content access refused")
    ids = set()
    for d in docs:
        required = {
            "document_id",
            "split",
            "source_id",
            "template_family_id",
            "scenario_family_id",
            "source_path",
            "text_path",
            "jurisdiction",
            "document_type",
            "synthetic",
            "generation_origin",
            "authorization",
            "prior_use",
        }
        hashes = {"source_sha256", "canonical_text_sha256", "similarity_sha256"}
        keys(d, required | (hashes if hashed else set()))
        for k in ("document_id", "source_id", "template_family_id", "scenario_family_id"):
            require(identifier(d[k]), f"invalid {k}")
        require(d["document_id"] not in ids, "duplicate document ID")
        ids.add(d["document_id"])
        require(d["split"] in {"development", "protected_holdout"}, "invalid split")
        require(d["jurisdiction"] in {"SG", "US", "UK", "AU"}, "outside pilot jurisdictions")
        require(nonempty(d["document_type"]), "document type required")
        require(type(d["synthetic"]) is bool, "synthetic declaration required")
        require(d["generation_origin"] in {"human", "model", "none", "unknown"}, "invalid generation origin")
        require(
            d["synthetic"] or d["generation_origin"] == "none", "non-synthetic source cannot have generation origin"
        )
        require(d["prior_use"] in {"none", "development", "regression", "unknown"}, "invalid prior-use declaration")
        if d["split"] == "protected_holdout":
            require(d["prior_use"] == "none", "previously exposed source cannot be protected holdout")
        keys(d["authorization"], {"basis", "reference", "licence"})
        require(d["authorization"]["basis"] in {"synthetic_owned", "public_licensed"}, "authorization required")
        require(all(nonempty(v) for v in d["authorization"].values()), "authorization evidence required")
        require(
            (d["authorization"]["basis"] == "synthetic_owned") == d["synthetic"],
            "source authorization/synthetic mismatch",
        )
        for k in ("source_path", "text_path"):
            require(
                nonempty(d[k]) and not Path(d[k]).is_absolute() and ".." not in Path(d[k]).parts, "unsafe source path"
            )
        if hashed:
            require(digest(d["source_sha256"]) and digest(d["canonical_text_sha256"]), "source/text hashes required")
            s = d["similarity_sha256"]
            require(isinstance(s, list) and bool(s) and all(digest(v) for v in s), "similarity fingerprint required")
            require(s == sorted(set(s)), "similarity fingerprints must be sorted and unique")
    return docs


def local_path(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), "source path escapes manifest directory")
    return path


def load_development(manifest, root, *, verify=True):
    docs = validate_manifest(manifest, hashed=verify, development_only=True)
    texts = {}
    generated = copy.deepcopy(manifest)
    for original, d in zip(docs, generated["documents"]):
        source = local_path(root, d["source_path"])
        raw = local_path(root, d["text_path"]).read_bytes()
        text = raw.decode("utf-8")  # preserve CRLF, Unicode and every character offset.
        require(bool(text.strip()) and len(text) <= MAX_TEXT_CHARACTERS, "canonical text must be 1–20,000 characters")
        actual = {
            "source_sha256": file_sha256(source),
            "canonical_text_sha256": input_identity(text),
            "similarity_sha256": fingerprints(text),
        }
        if verify:
            require(all(original[k] == v for k, v in actual.items()), "source/text fingerprint mismatch")
        d.update(actual)
        texts[d["document_id"]] = text
    return generated, texts


def partition_check(manifests, excluded_hashes=()):
    """Metadata-only comparison; never resolves paths or opens source/label files."""
    docs = [d for m in manifests for d in validate_manifest(m)]
    require(all(digest(h) for h in excluded_hashes), "invalid excluded-source registry")
    require(len(docs) <= MAX_DOCUMENTS, "pilot exceeds 100 documents")
    require(len({d["document_id"] for d in docs}) == len(docs), "duplicate document IDs across manifests")
    conflicts = []
    for d in docs:
        if d["split"] == "protected_holdout" and {d["source_sha256"], d["canonical_text_sha256"]} & set(
            excluded_hashes
        ):
            conflicts.append({"documents": [d["document_id"]], "reasons": ["previously_used_source"]})
    for a, b in combinations(docs, 2):
        if a["split"] == b["split"]:
            continue
        reasons = [
            k
            for k in ("source_id", "template_family_id", "scenario_family_id", "source_sha256", "canonical_text_sha256")
            if a[k] == b[k]
        ]
        left, right = set(a["similarity_sha256"]), set(b["similarity_sha256"])
        similarity = len(left & right) / len(left | right)
        if similarity >= NEAR_DUPLICATE_THRESHOLD:
            reasons.append("near_duplicate")
        if reasons:
            conflicts.append({"documents": [a["document_id"], b["document_id"]], "reasons": reasons})
    return {
        "schema_version": "junas.partition_check.v1",
        "conflicts": conflicts,
        "status": "contamination_detected" if conflicts else "no_recorded_conflict",
        "protected_holdout_readiness": "NOT READY",
        "qualification": "Metadata and similarity checks do not prove access isolation or independence.",
    }


def span_check(span, text):
    require(type(span.get("start_char")) is int and type(span.get("end_char")) is int, "integer offsets required")
    start, end = span["start_char"], span["end_char"]
    require(0 <= start < end <= len(text), "span outside canonical text")
    require(text[start:end] == span.get("matched_text"), "span/text mismatch")


def validate_snapshot(record, document, text):
    keys(
        record,
        {
            "schema_version",
            "protocol_id",
            "record_id",
            "document_id",
            "split",
            "canonical_text_sha256",
            "reviewer_id",
            "stage",
            "timestamp",
            "provenance",
            "coverage",
            "pii",
            "mnpi",
            "exclusions",
            "notes",
            "supersedes",
            "based_on",
            "approval",
            "previous_record_sha256",
            "record_sha256",
        },
    )
    require(record["schema_version"] == REVIEW, "unknown review schema")
    require(
        record["protocol_id"] == PROTOCOL and record["split"] == document["split"], "review protocol/split mismatch"
    )
    require(identifier(record["record_id"]) and identifier(record["reviewer_id"]), "reviewer and record IDs required")
    require(record["document_id"] == document["document_id"], "unknown review document")
    require(record["canonical_text_sha256"] == document["canonical_text_sha256"], "review source hash mismatch")
    require(record["stage"] in {"draft", "submitted", "adjudicated", "accepted"}, "invalid annotation stage")
    timestamp(record["timestamp"])
    require(isinstance(record["notes"], str), "notes must be text")
    keys(
        record["provenance"],
        {
            "label_origin",
            "blinded_to_junas",
            "blinded_to_models",
            "blinded_to_other_annotations",
            "source_author",
            "synthetic",
        },
    )
    p = record["provenance"]
    require(
        p["label_origin"] in {"human", "human_reviewed_model", "detector_derived", "unknown"}, "invalid label origin"
    )
    for k in ("blinded_to_junas", "blinded_to_models", "blinded_to_other_annotations", "source_author"):
        require(p[k] is None or type(p[k]) is bool, "blindness/authorship must be boolean or unknown")
    require(type(p["synthetic"]) is bool and p["synthetic"] == document["synthetic"], "synthetic provenance mismatch")
    keys(record["coverage"], {"PII", "MNPI"})
    require(
        all(isinstance(c, str) and c in COVERAGE for c in record["coverage"].values()), "coverage declaration required"
    )
    require(
        isinstance(record["based_on"], list) and all(identifier(i) for i in record["based_on"]),
        "invalid review references",
    )
    require(len(set(record["based_on"])) == len(record["based_on"]), "duplicate review references")
    require(record["supersedes"] is None or identifier(record["supersedes"]), "invalid correction reference")
    for field in ("pii", "mnpi", "exclusions"):
        require(isinstance(record[field], list), f"{field} must be a list")
    seen = set()
    uncertain = False
    for item in record["pii"]:
        keys(item, {"category", "label", "start_char", "end_char", "matched_text", "certainty", "reason"})
        require(item["category"] == "PII" and item["label"] in PII_RULE_MAP, "outside PII target taxonomy")
        span_check(item, text)
        require(item["certainty"] in {"certain", "uncertain", "abstain"}, "invalid certainty")
        require(nonempty(item["reason"]), "annotation reasoning required")
        key = (item["label"], item["start_char"], item["end_char"])
        require(key not in seen, "duplicate PII annotation")
        seen.add(key)
        uncertain |= item["certainty"] != "certain"
    for item in record["exclusions"]:
        keys(item, {"target", "start_char", "end_char", "matched_text", "reason"})
        require(item["target"] in {"PII", "MNPI", "out_of_scope"}, "invalid exclusion target")
        span_check(item, text)
        require(nonempty(item["reason"]), "exclusion reason required")
        if item["target"] in {"PII", "MNPI"}:
            require(record["coverage"][item["target"]] != "exhaustive", "excluded target cannot be exhaustive")
    require(not uncertain or record["coverage"]["PII"] != "exhaustive", "uncertain PII cannot be exhaustive")
    for item in record["mnpi"]:
        keys(
            item,
            {
                "start_char",
                "end_char",
                "matched_text",
                "entity",
                "potential_materiality",
                "public_status",
                "as_of",
                "evidence",
                "ambiguity",
                "human_review_required",
            },
        )
        span_check(item, text)
        require(item["entity"] is None or nonempty(item["entity"]), "invalid entity")
        require(
            item["potential_materiality"] in {"potentially_material", "not_material", "unknown"}, "invalid materiality"
        )
        require(item["public_status"] in {"public", "non_public", "unknown"}, "invalid publicity")
        if item["as_of"] is not None:
            require(isinstance(item["as_of"], str), "invalid as-of date")
            date.fromisoformat(item["as_of"])
        require(
            isinstance(item["ambiguity"], str) and type(item["human_review_required"]) is bool,
            "ambiguity/review required",
        )
        require(isinstance(item["evidence"], list), "evidence must be a list")
        for evidence in item["evidence"]:
            keys(evidence, {"kind", "reference", "provenance"}, {"start_char", "end_char", "matched_text"})
            require(evidence["kind"] in {"document", "external", "unknown"}, "invalid evidence kind")
            require(
                nonempty(evidence["reference"]) and nonempty(evidence["provenance"]), "evidence provenance required"
            )
            if evidence["kind"] == "document":
                span_check(evidence, text)
            else:
                require(
                    not {"start_char", "end_char", "matched_text"} & evidence.keys(),
                    "external evidence has no document offsets",
                )
        unresolved = (
            item["entity"] is None
            or item["potential_materiality"] == "unknown"
            or item["public_status"] == "unknown"
            or item["as_of"] is None
            or not item["evidence"]
            or bool(item["ambiguity"])
            or any(e["kind"] == "unknown" for e in item["evidence"])
        )
        require(not unresolved or item["human_review_required"], "uncertain MNPI requires human review")
        require(not unresolved or record["coverage"]["MNPI"] != "exhaustive", "uncertain MNPI cannot be exhaustive")


def snapshot_content(record):
    return {k: record[k] for k in ("pii", "mnpi", "coverage", "exclusions")}


def validate_reviews(manifest, texts, records):
    docs = {d["document_id"]: d for d in validate_manifest(manifest, development_only=True)}
    require(set(texts) == set(docs), "canonical texts missing or extra")
    for doc_id, text in texts.items():
        require(input_identity(text) == docs[doc_id]["canonical_text_sha256"], "canonical text hash mismatch")
    by_id, latest, accepted = {}, {}, {}
    previous = None
    for r in records:
        require(isinstance(r, dict) and r.get("document_id") in docs, "unknown review document")
        validate_snapshot(r, docs[r["document_id"]], texts[r["document_id"]])
        require(r["record_id"] not in by_id, "duplicate review record ID")
        require(
            r["previous_record_sha256"] == previous and r["record_sha256"] == record_hash(r),
            "review history hash mismatch",
        )
        key = (r["document_id"], r["reviewer_id"])
        require(r["supersedes"] == latest.get(key), "correction must reference reviewer's previous snapshot")
        if r["supersedes"]:
            require(nonempty(r["notes"]), "correction rationale required")
            require(
                timestamp(r["timestamp"]) >= timestamp(by_id[r["supersedes"]]["timestamp"]),
                "correction predates prior snapshot",
            )
        require(
            all(i in by_id and by_id[i]["document_id"] == r["document_id"] for i in r["based_on"]),
            "invalid prior review references",
        )
        active = [
            by_id[i] for (d, _), i in latest.items() if d == r["document_id"] and by_id[i]["stage"] == "submitted"
        ]
        if r["stage"] == "adjudicated":
            require(
                len(active) >= 2 and set(r["based_on"]) == {x["record_id"] for x in active},
                "adjudication needs all active submissions",
            )
            require(
                r["reviewer_id"] not in {x["reviewer_id"] for x in active},
                "adjudicator must be separate from annotators",
            )
            require(nonempty(r["notes"]), "adjudication rationale required")
        elif r["stage"] == "accepted":
            require(len(r["based_on"]) == 1, "acceptance needs an explicitly reviewed snapshot")
            base = by_id[r["based_on"][0]]
            require(base["stage"] in {"submitted", "adjudicated"}, "cannot accept an unsubmitted draft")
            require(
                latest[(base["document_id"], base["reviewer_id"])] == base["record_id"],
                "cannot accept superseded annotation",
            )
            if len(active) > 1:
                require(base["stage"] == "adjudicated", "multiple submissions require recorded adjudication")
            if base["stage"] == "adjudicated":
                require(set(base["based_on"]) == {x["record_id"] for x in active}, "adjudication is stale")
            require(
                snapshot_content(r) == snapshot_content(base), "acceptance cannot silently change annotation contents"
            )
            keys(r["approval"], {"reviewer_id", "timestamp", "reason"})
            require(
                r["approval"]["reviewer_id"] == r["reviewer_id"] and nonempty(r["approval"]["reason"]),
                "explicit human approval required",
            )
            require(
                timestamp(r["approval"]["timestamp"]) >= timestamp(base["timestamp"]),
                "approval predates reviewed snapshot",
            )
            require(timestamp(r["timestamp"]) >= timestamp(r["approval"]["timestamp"]), "snapshot predates approval")
            require(r["provenance"]["label_origin"] == "human", "only explicit human acceptance is supported")
            accepted[r["document_id"]] = r["record_id"]
        else:
            require(not r["based_on"], "blind submissions cannot be based on other annotations")
        if r["stage"] != "accepted":
            require(r["approval"] is None, "approval belongs only to acceptance stage")
            accepted.pop(r["document_id"], None)
        by_id[r["record_id"]] = r
        latest[key] = r["record_id"]
        previous = r["record_sha256"]
    return by_id, latest, accepted


def occurrence_inputs(manifest, texts, records):
    """Convert explicitly accepted development annotations; does not compute metrics."""
    by_id, _, accepted = validate_reviews(manifest, texts, records)
    spans, units, coverage = [], {}, {}
    for doc_id, record_id in accepted.items():
        r = by_id[record_id]
        unit = ("development", doc_id, r["reviewer_id"])
        units[unit], coverage[unit] = texts[doc_id], r["coverage"]["PII"]
        spans.extend(
            Span(unit, x["start_char"], x["end_char"], "PII", x["label"])
            for x in r["pii"]
            if x["certainty"] == "certain"
        )
    return spans, units, coverage


def review_report(manifest, texts, records):
    by_id, latest, accepted = validate_reviews(manifest, texts, records)
    submissions = [by_id[i] for i in latest.values() if by_id[i]["stage"] == "submitted"]
    disagreements = []
    for a, b in combinations(submissions, 2):
        if a["document_id"] == b["document_id"] and snapshot_content(a) != snapshot_content(b):
            disagreements.append([a["record_id"], b["record_id"]])
    accepted_qualifications = {}
    for doc_id, record_id in accepted.items():
        pending, visited, annotations = [record_id], set(), []
        while pending:
            rid = pending.pop()
            if rid in visited:
                continue
            visited.add(rid)
            r = by_id[rid]
            pending.extend(r["based_on"])
            if r["supersedes"]:
                pending.append(r["supersedes"])
            if r["stage"] in {"draft", "submitted"}:
                annotations.append(r)
        accepted_qualifications[doc_id] = {
            "label_origins": sorted({by_id[i]["provenance"]["label_origin"] for i in visited}),
            "annotators": sorted({r["reviewer_id"] for r in annotations}),
            "adjudicated": any(by_id[i]["stage"] == "adjudicated" for i in visited),
            "independence": "declared_not_verified"
            if annotations
            and all(by_id[i]["provenance"]["label_origin"] == "human" for i in visited)
            and all(
                r["provenance"]["label_origin"] == "human"
                and r["provenance"]["blinded_to_junas"] is True
                and r["provenance"]["blinded_to_models"] is True
                and r["provenance"]["blinded_to_other_annotations"] is True
                and r["provenance"]["source_author"] is False
                for r in annotations
            )
            else "not_established",
            "coverage": by_id[record_id]["coverage"],
            "synthetic": next(d["synthetic"] for d in manifest["documents"] if d["document_id"] == doc_id),
            "qualification": "single annotator"
            if len({r["reviewer_id"] for r in annotations}) < 2
            else "multiple declared annotators",
        }
    return {
        "schema_version": "junas.annotation_validation.v1",
        "purpose": manifest["purpose"],
        "validation": "PASS",
        "documents": len(manifest["documents"]),
        "records": len(records),
        "accepted_documents": len(accepted),
        "label_origins": dict(Counter(r["provenance"]["label_origin"] for r in submissions)),
        "synthetic_documents": sum(d["synthetic"] for d in manifest["documents"]),
        "partial_or_unknown_submissions": sum(
            any(v != "exhaustive" for v in r["coverage"].values()) for r in submissions
        ),
        "declared_blind_non_author_submissions": sum(
            r["provenance"]["label_origin"] == "human"
            and r["provenance"]["blinded_to_junas"] is True
            and r["provenance"]["blinded_to_models"] is True
            and r["provenance"]["blinded_to_other_annotations"] is True
            and r["provenance"]["source_author"] is False
            for r in submissions
        ),
        "adjudicated_records": sum(r["stage"] == "adjudicated" for r in records),
        "disagreements": disagreements,
        "accepted_qualifications": accepted_qualifications,
        "independent_ground_truth_readiness": "NOT READY",
        "protected_holdout_readiness": "NOT READY",
        "qualification": "Declarations/hashes do not authenticate human events, access controls or independence.",
        "log_head_sha256": records[-1]["record_sha256"] if records else None,
    }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_reviews(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path, data):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("fingerprint", "validate", "append"):
        p = sub.add_parser(command)
        p.add_argument("manifest", type=Path)
        p.add_argument("--output", type=Path, required=True)
        if command in {"validate", "append"}:
            p.add_argument("--reviews", type=Path, required=command == "validate")
        if command == "append":
            p.add_argument("--entry", type=Path, required=True)
    p = sub.add_parser("partitions")
    p.add_argument("manifests", type=Path, nargs="+")
    p.add_argument(
        "--excluded-hashes", type=Path, help="custodian-owned JSON array of prior-use source/text SHA256 values"
    )
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "partitions":
            excluded = read_json(args.excluded_hashes) if args.excluded_hashes else []
            require(isinstance(excluded, list), "excluded-source registry must be an array")
            result = partition_check([read_json(p) for p in args.manifests], excluded)
        else:
            manifest = read_json(args.manifest)
            manifest, texts = load_development(manifest, args.manifest.parent, verify=args.command != "fingerprint")
            if args.command == "fingerprint":
                result = manifest
            else:
                records = read_reviews(args.reviews) if args.reviews else []
                if args.command == "append":
                    entry = read_json(args.entry)
                    require(
                        not {"previous_record_sha256", "record_sha256"} & entry.keys(),
                        "entry must not supply chain hashes",
                    )
                    entry["previous_record_sha256"] = records[-1]["record_sha256"] if records else None
                    entry["record_sha256"] = record_hash(entry)
                    records.append(entry)
                result = review_report(manifest, texts, records)
                if args.command == "append":
                    write_new(
                        args.output, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records)
                    )
                    print("validated new review log; independence and holdout readiness NOT READY")
                    return 0
        write_new(args.output, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        print("preparation only; independent ground truth and protected holdout NOT READY")
        return 1 if result.get("conflicts") else 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"annotation preparation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
