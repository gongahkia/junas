"""Durable continuation of one capped job; incomplete candidates are never replayed."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from pathlib import Path


def atomic_snapshot(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def recover(config: dict, auth: dict, source: Path) -> dict:
    from scripts import model_corpus as c

    cap = c.validate_authorization(auth, config)
    visited: set[Path] = set()
    fingerprints: set[str] = set()
    records: dict[str, dict] = {}
    charged = Decimal(0)
    last_call = 0
    segments = []

    def load(directory: Path) -> None:
        nonlocal charged, last_call
        directory = directory.resolve()
        c.require(directory not in visited, "cyclic recovery chain")
        visited.add(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        c.require((directory / "ready.json").is_file(), "segment was not initialized for execution")
        c.require(manifest.get("recovery_version") == 1, "legacy run requires a separately audited migration")
        c.require(manifest["config_sha256"] == c.identity(config), "recovery configuration mismatch")
        c.require(manifest["prompt_version"] == c.PROMPT_VERSION, "recovery prompt mismatch")
        c.require(Decimal(manifest["authorized_budget_usd"]) == cap, "recovery cannot change original aggregate cap")
        c.require(manifest["authorization_sha256"] == c.identity(auth), "recovery authorization mismatch")
        parent = manifest.get("parent_segment")
        if parent:
            claim = json.loads((Path(parent) / "continued-to.json").read_text())
            c.require(Path(claim["output"]).resolve() == directory, "invalid continuation linkage")
            load(Path(parent))
        events: dict[int, dict] = {}
        payloads: dict[str, list[dict]] = {}
        journal = directory / "requests.jsonl"
        if journal.exists():
            lines = journal.read_text().splitlines(keepends=True)
            for line in lines:
                if not line.endswith("\n"):
                    raise ValueError("torn spending journal; manual audit required")
                event = json.loads(line)
                call, status = event["call"], event["status"]
                c.require(c.integer(call, 1, config["max_candidates"] * 7), "invalid journal call")
                last_call = max(last_call, call)
                if status == "preflight":
                    c.require(
                        call not in events and event["request_sha256"] not in fingerprints,
                        "replayed request or call number",
                    )
                    fingerprints.add(event["request_sha256"])
                    events[call] = {"event": event, "state": "preflight", "cost": Decimal(0)}
                    continue
                c.require(call in events, "journal event has no durable preflight")
                item = events[call]
                c.require(item["event"]["request_sha256"] == event["request_sha256"], "journal request mismatch")
                model = (
                    config["generator"]
                    if event["role"] == "generator"
                    else next((m for m in config["judges"] if m["model"] == event["model"]), None)
                )
                if model is None:
                    raise ValueError("journal model mismatch")
                c.require(model["model"] == event["model"], "journal model mismatch")
                if status == "reserved":
                    c.require(item["state"] == "preflight", "duplicate reservation")
                    inputs = event["input_tokens"]
                    c.require(c.integer(inputs, 0, model["max_input_tokens"]), "invalid reserved input")
                    cost = c.token_cost(model, inputs, model["max_output_tokens"])
                    c.require(Decimal(event["reserved_usd"]) == cost, "invalid reservation cost")
                    item.update(state="reserved", cost=cost, inputs=inputs)
                elif status == "received":
                    c.require(item["state"] == "reserved", "duplicate or unreserved settlement")
                    usage = event["usage"]
                    c.require(
                        c.integer(usage["input_tokens"], 0, item["inputs"])
                        and c.integer(usage["output_tokens"], 0, model["max_output_tokens"]),
                        "invalid settlement usage",
                    )
                    cost = c.token_cost(model, usage["input_tokens"], usage["output_tokens"])
                    c.require(Decimal(event["cost_ceiling_usd"]) == cost, "invalid settlement cost")
                    raw = json.loads((directory / f"response-{call:05d}.json").read_text())
                    c.require(c.identity(raw["request"]) == event["request_sha256"], "response request mismatch")
                    c.require(raw["response"]["usage"] == usage, "response usage mismatch")
                    c.require(
                        raw["response"]["model"] == model["model"]
                        and raw["response"].get("service_tier", "default") == "default",
                        "response billing mismatch",
                    )
                    try:
                        payload = c.response_payload(raw["response"])
                    except (ValueError, KeyError, TypeError):
                        payload = None
                    payloads.setdefault(event["candidate"], []).append(
                        {
                            "role": event["role"],
                            "model": model["model"],
                            "output": payload,
                            "input": json.loads(raw["request"]["input"]),
                        }
                    )
                    item.update(state="received", cost=cost)
                elif status == "uncertain":
                    c.require(item["state"] == "reserved", "uncertain event without reservation")
                    item["state"] = "uncertain"
                else:
                    raise ValueError("unknown journal status")
            charged += sum((item["cost"] for item in events.values()), Decimal(0))
        for snapshot in sorted(directory.glob("candidate-*.json")):
            record = json.loads(snapshot.read_text())
            document_id = record["document_id"]
            c.require(document_id not in records, "candidate replay across segments")
            sources = [
                p["output"]
                for p in payloads.get(document_id, [])
                if p["role"] == "generator"
                and isinstance(p["output"], dict)
                and isinstance(p["output"].get("text"), str)
            ]
            if sources and "text" not in record:
                record.update(text=sources[0]["text"], text_sha256=c.input_identity(sources[0]["text"]))
            if "text" in record:
                c.require(
                    any(p.get("text") == record["text"] for p in sources), "source not linked to received generator"
                )
                c.require(c.input_identity(record["text"]) == record["text_sha256"], "candidate source mismatch")
            if record["status"] == "completed":
                annotations = record["annotations"]
                c.require(len(annotations) == 3, "incomplete completed candidate")
                for annotation in annotations:
                    c.validate_annotations(annotation["output"], record["text"])
                    c.require(
                        any(
                            p["role"] == "judge"
                            and p["model"] == annotation["model"]
                            and p["output"] == annotation["output"]
                            and p["input"]["text"] == record["text"]
                            and p["input"]["judge_pass"] == annotation["judge_pass"]
                            for p in payloads.get(document_id, [])
                        ),
                        "annotation not linked to received judge",
                    )
                c.require(record["consensus"] == c.consensus([a["output"] for a in annotations]), "modified consensus")
            else:
                record.update(status="error", accepted=False, selection_reason="incomplete_candidate_skipped_on_resume")
            records[document_id] = record
        c.require(
            all(item["event"]["candidate"] in records for item in events.values()),
            "journal candidate missing from durable snapshots",
        )
        segments.append(
            {
                "path": str(directory),
                "manifest_sha256": c.input_identity((directory / "manifest.json").read_text()),
                "journal_sha256": c.input_identity(journal.read_text()) if journal.exists() else None,
            }
        )

    load(source)
    ordered = [records[k] for k in sorted(records)]
    c.require(
        [r["document_id"] for r in ordered] == [f"synthetic-{i + 1:04d}" for i in range(len(ordered))],
        "noncontiguous candidate checkpoint",
    )
    c.require(0 <= charged <= cap, "recovered costs exceed aggregate budget")
    prefix: list[dict] = []
    for record in ordered:
        expected = False
        if record["status"] == "completed":
            q = record["consensus"]["quadrant"]
            expected = q in c.QUADRANTS and c.quadrant_coverage(prefix, config)["shortfall"][q] > 0
        c.require(record["accepted"] == expected, "checkpoint acceptance mismatch")
        prefix.append(record)
    counts = c.quadrant_coverage(ordered, config)["accepted"]
    c.require(all(counts[q] <= config["quadrant_targets"][q] for q in c.QUADRANTS), "invalid checkpoint quotas")
    return {
        "records": ordered,
        "charged": charged,
        "last_call": last_call,
        "request_hashes": fingerprints,
        "segments": segments,
    }
