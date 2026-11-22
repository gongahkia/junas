"""Offline grouped sampling reservations; reservations are not collected holdout data."""

from __future__ import annotations

import hashlib
import re

SCENARIO_GROUPS = {
    "development": [
        {"id": "dev-intake-v1", "scenario": "fictional individual client intake form"},
        {"id": "dev-payroll-v1", "scenario": "fictional payroll correction request"},
        {"id": "dev-board-v1", "scenario": "fictional listed issuer board memorandum"},
        {"id": "dev-public-v1", "scenario": "fictional already published investor announcement"},
    ],
    "holdout": [
        {"id": "holdout-estate-v1", "scenario": "fictional estate administration ledger entry"},
        {"id": "holdout-benefits-v1", "scenario": "fictional benefits eligibility appeal"},
        {"id": "holdout-covenant-v1", "scenario": "fictional issuer covenant waiver exchange"},
        {"id": "holdout-research-v1", "scenario": "fictional market research corrections bulletin"},
    ],
}


def validate_sampling(sampling: dict) -> dict:
    if not isinstance(sampling, dict) or set(sampling) != {"split", "groups"}:
        raise ValueError("sampling requires split and groups")
    split = sampling["split"]
    if split not in SCENARIO_GROUPS or sampling["groups"] != SCENARIO_GROUPS[split]:
        raise ValueError("use the reserved scenario/template groups for this partition")
    return sampling


def sampling_slot(sampling: dict, index: int) -> dict:
    validate_sampling(sampling)
    group = sampling["groups"][index % len(sampling["groups"])]
    return {"split": sampling["split"], "template_group": group["id"], "scenario": group["scenario"]}


def source_fingerprints(text: str) -> set[str]:
    normalized = " ".join(text.casefold().split())
    # entity/number substitutions must not let the same template cross partitions.
    skeleton = re.sub(r"[\w.+-]+@[\w.-]+|\d+", "<value>", normalized)
    return {hashlib.sha256(s.encode()).hexdigest() for s in (normalized, skeleton)}


def validate_partition_records(development: list[dict], holdout: list[dict]) -> None:
    groups, fingerprints = [], []
    for split, records in (("development", development), ("holdout", holdout)):
        current_groups, current_hashes = set(), set()
        for record in records:
            if record.get("split", "development") != split:
                raise ValueError("record has the wrong partition")
            if split == "holdout" and not record.get("template_group"):
                raise ValueError("holdout requires a reserved template group")
            current_groups.add(record.get("template_group", "legacy-development"))
            current_hashes.update(source_fingerprints(record["text"]))
        groups.append(current_groups)
        fingerprints.append(current_hashes)
    if groups[0] & groups[1] or fingerprints[0] & fingerprints[1]:
        raise ValueError("cross-partition group or source contamination")


def reservation() -> dict:
    return {
        "schema_version": "junas.partition_reservation.v1",
        "groups": SCENARIO_GROUPS,
        "existing_corpus_split": "development",
        "fresh_holdout_documents": 40,
        "fresh_holdout_per_quadrant": 10,
        "status": "reserved_not_generated",
        "holdout_established": False,
        "independent_ground_truth": False,
        "policy": "holdout is excluded from development evaluation; one-shot release consumes it",
    }
