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

# previous holdout families remain valid for historical replay, but are consumed.
FRESH_HOLDOUT_GROUPS = [
    {"id": "holdout-escrow-v2", "scenario": "fictional escrow release reconciliation note"},
    {"id": "holdout-shareplan-v2", "scenario": "fictional employee share-plan exercise settlement instruction"},
    {"id": "holdout-recall-v2", "scenario": "fictional listed issuer product recall briefing"},
    {"id": "holdout-consultation-v2", "scenario": "fictional public exchange consultation digest"},
]

FRESH_HOLDOUT_V3_GROUPS = [
    {
        "id": "holdout-refinancing-v3",
        "scenario": "fictional listed issuer emergency refinancing allocation instruction",
    },
    {"id": "holdout-licence-v3", "scenario": "fictional listed issuer operating licence suspension chronology"},
    {"id": "holdout-tender-v3", "scenario": "fictional tender-offer withdrawal registrar reconciliation"},
    {"id": "holdout-education-v3", "scenario": "fictional public investment education erratum"},
]


def validate_sampling(sampling: dict) -> dict:
    if not isinstance(sampling, dict) or set(sampling) != {"split", "groups"}:
        raise ValueError("sampling requires split and groups")
    split = sampling["split"]
    allowed = [SCENARIO_GROUPS.get(split)]
    if split == "holdout":
        allowed.extend((FRESH_HOLDOUT_GROUPS, FRESH_HOLDOUT_V3_GROUPS))
    if split not in SCENARIO_GROUPS or sampling["groups"] not in allowed:
        raise ValueError("use the reserved scenario/template groups for this partition")
    return sampling


def sampling_slot(sampling: dict, index: int) -> dict:
    validate_sampling(sampling)
    group = sampling["groups"][(index // 4) % len(sampling["groups"])]
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
    registry = exclusion_registry(development)
    for record in holdout if development else []:
        check_exclusions(record["text"], record["template_group"], registry)


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


def exclusion_registry(records: list[dict]) -> dict:
    from scripts.prepare_evaluation_dataset import fingerprints

    return {
        "schema_version": "junas.source_exclusions.v1",
        "entries": [
            {
                "template_group": r.get("template_group", "legacy-development"),
                "source_hashes": sorted(source_fingerprints(r["text"])),
                "shingles": fingerprints(r["text"]),
            }
            for r in records
            if "text" in r
        ],
    }


def validate_exclusion_registry(registry: dict) -> None:
    if not isinstance(registry, dict) or registry.get("schema_version") != "junas.source_exclusions.v1":
        raise ValueError("invalid development exclusion registry")
    if not isinstance(registry.get("entries"), list) or not registry["entries"]:
        raise ValueError("development exclusion registry cannot be empty")
    for entry in registry["entries"]:
        if not isinstance(entry, dict) or set(entry) != {"template_group", "source_hashes", "shingles"}:
            raise ValueError("invalid exclusion entry")
        if not isinstance(entry["template_group"], str) or not entry["template_group"]:
            raise ValueError("invalid exclusion group")
        for field in ("source_hashes", "shingles"):
            if (
                not isinstance(entry[field], list)
                or not entry[field]
                or not all(isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) for h in entry[field])
            ):
                raise ValueError("invalid exclusion fingerprints")


def check_exclusions(text: str, group: str, registry: dict) -> None:
    from scripts.prepare_evaluation_dataset import NEAR_DUPLICATE_THRESHOLD, fingerprints

    validate_exclusion_registry(registry)
    hashes, shingles = source_fingerprints(text), set(fingerprints(text))
    for entry in registry["entries"]:
        other = set(entry["shingles"])
        union = shingles | other
        if (
            group == entry["template_group"]
            or hashes & set(entry["source_hashes"])
            or (union and len(shingles & other) / len(union) >= NEAR_DUPLICATE_THRESHOLD)
        ):
            raise ValueError("source conflicts with the development exclusion registry")


def main() -> int:
    import argparse
    import json
    from pathlib import Path

    from scripts.model_corpus import identity, write_new

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bind-config", type=Path, help="Write new holdout config with this exclusion registry hash")
    parser.add_argument("--config", type=Path, help="Existing holdout proposal; never modified in place")
    args = parser.parse_args()
    records = [json.loads(line) for path in args.records for line in path.read_text().splitlines() if line.strip()]
    if any(r.get("split", "development") != "development" for r in records):
        raise ValueError("exclusions require development sources only")
    if args.bind_config and not args.config:
        raise ValueError("--bind-config requires --config")
    registry = exclusion_registry(records)
    validate_exclusion_registry(registry)
    write_new(args.output, registry)
    if args.bind_config:
        config = json.loads(args.config.read_text())
        config["exclusion_registry_sha256"] = identity(registry)
        write_new(args.bind_config, config)
    return 0


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
