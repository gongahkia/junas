#!/usr/bin/env python3
"""Offline authored regression gates; passing does not establish independent accuracy."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from junas.review.engine import PreSendReviewEngine  # noqa: E402
from scripts.model_corpus import QUADRANTS  # noqa: E402

# authored development cases exercise independent positive/negative contexts, not model votes.
ENTITY_CASES = {
    "PERSON_NAME": ("Client name: Amara Voss", "Company name: Cedar Vale Ltd.", "Amara Voss"),
    "EMAIL": (
        "Personal email: amara.voss@example.test",
        "Company contact: support@example.test",
        "amara.voss@example.test",
    ),
    "PHONE": ("Personal mobile: +65 8234 5678", "Public hotline telephone: +65 6234 5678", "+65 8234 5678"),
    "POSTAL_ADDRESS": (
        "Home address: 42 Example Grove, Singapore 123456",
        "Office mailing address: 42 Example Grove, Singapore 123456",
        "42 Example Grove, Singapore 123456",
    ),
    "BANK_ACCOUNT": (
        "Personal bank account number: 123456789",
        "Corporate bank account number: 123456789",
        "123456789",
    ),
    "GOVERNMENT_ID": ("Passport number: X8765432", "Company registration number: 202612345A", "X8765432"),
    "PERSONAL_RECORD_ID": ("Staff ID: CV-P0832", "Contract reference: CV-P0832", "CV-P0832"),
    "DATE_OF_BIRTH": ("DOB: 14 March 1988", "Publication date: 14 March 1988", "14 March 1988"),
    "QUASI_IDENTIFIER_COMBINATION": (
        "Only resident uniquely identified: Age: 41; postal code: 123456; occupation: archivist",
        "General statistics: Age: 41; postal code: 123456; occupation: archivist",
        "Age: 41; postal code: 123456; occupation: archivist",
    ),
}
PRIVATE_EVENT = (
    "Cedar Vale Ltd. signed a binding acquisition of all outstanding shares. "
    "This price-sensitive event has not been publicly disclosed."
)
PUBLIC_EVENT = "Cedar Vale Ltd. publicly announced a material acquisition of all outstanding shares."


def cases() -> list[dict]:
    output = []
    for quadrant, (pii, mnpi) in QUADRANTS.items():
        for label, (positive, negative, expected) in ENTITY_CASES.items():
            for variant in range(2):
                entity = positive if pii == "present" else negative
                event = PRIVATE_EVENT if mnpi == "present" else PUBLIC_EVENT
                # reorder and vary line endings; exact offsets must still refer to the source.
                text = entity + ".\n\n" + event if variant == 0 else event + "\r\n\r\n" + entity + "."
                start = text.index(expected) if pii == "present" else None
                output.append(
                    {
                        "id": f"{quadrant}/{label}/{variant}",
                        "quadrant": quadrant,
                        "entity_type": label,
                        "text": text,
                        "expected_pii": pii,
                        "expected_mnpi": mnpi,
                        "span": (start, start + len(expected)) if start is not None else None,
                    }
                )
    return output


def check() -> dict:
    engine = PreSendReviewEngine()
    by_quadrant: dict = defaultdict(Counter)
    by_entity: dict = defaultdict(Counter)
    failures = []
    for case in cases():
        result = engine.review(
            text=case["text"],
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
        )
        output = result.sensitivity
        counts = Counter(documents=1)
        for target in ("pii", "mnpi"):
            state, expected = output[target]["state"], case["expected_" + target]
            kind = (
                "unknown"
                if state == "unknown"
                else ("tp" if state == "present" else "fn")
                if expected == "present"
                else ("fp" if state == "present" else "tn")
            )
            counts[target + "_" + kind] += 1
            if kind in {"fn", "fp", "unknown"}:
                failures.append({"case": case["id"], "kind": target + "_" + kind})
        for target in ("pii", "mnpi"):
            for item in output[target]["evidence"]:
                start, end = item["start_char"], item["end_char"]
                if not 0 <= start < end <= len(case["text"]) or case["text"][start:end] != item["matched_text"]:
                    failures.append({"case": case["id"], "kind": "invalid_evidence"})
        if case["span"]:
            exact = any(
                (s["start_char"], s["end_char"]) == case["span"] and s["label"] == case["entity_type"]
                for s in output["pii"]["evidence"]
            )
            counts["entity_exact_hit" if exact else "entity_exact_miss"] += 1
            if not exact:
                failures.append({"case": case["id"], "kind": "entity_exact_miss"})
            extras = sum(
                (s["start_char"], s["end_char"]) != case["span"] or s["label"] != case["entity_type"]
                for s in output["pii"]["evidence"]
            )
            counts["unexpected_entities"] += extras
            if extras:
                failures.append({"case": case["id"], "kind": "unexpected_entities", "count": extras})
        by_quadrant[case["quadrant"]].update(counts)
        by_entity[case["entity_type"]].update(counts)
    return {
        "schema_version": "junas.reliability_gates.v1",
        "passed": not failures,
        "reference": "authored synthetic development regressions; not independent accuracy",
        "independently_validated_accuracy": None,
        "calibrated_confidence": None,
        "documents": len(cases()),
        "by_quadrant": dict(by_quadrant),
        "by_entity": dict(by_entity),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check()
    if args.output:
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    print(json.dumps({k: report[k] for k in ("passed", "documents", "failures")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
