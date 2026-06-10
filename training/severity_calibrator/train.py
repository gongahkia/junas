#!/usr/bin/env python3
"""Train a small decision-table severity calibrator from sanitized preferences.

This is the item 31 substrate. It intentionally avoids sklearn in v1: the output
is a transparent table keyed by rule/jurisdiction/severity with accept/reject
rates. A later server-only model can consume the same JSONL.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def train(rows: list[dict[str, Any]], *, min_rows: int = 3) -> dict[str, Any]:
    cells: dict[str, dict[str, int]] = defaultdict(lambda: {"accept": 0, "reject": 0})
    for row in rows:
        key = "|".join(
            [
                str(row.get("rule") or ""),
                str(row.get("jurisdiction") or ""),
                str(row.get("severity") or ""),
            ]
        )
        chosen = str(row.get("chosen") or "")
        if chosen in {"accept", "reject"}:
            cells[key][chosen] += 1
    recommendations: dict[str, dict[str, Any]] = {}
    for key, counts in sorted(cells.items()):
        total = counts["accept"] + counts["reject"]
        accept_rate = counts["accept"] / total if total else 0.0
        if total < min_rows:
            action = "insufficient_data"
        elif accept_rate < 0.25:
            action = "consider_soften"
        elif accept_rate > 0.85:
            action = "keep_or_tighten"
        else:
            action = "no_change"
        recommendations[key] = {
            "accept": counts["accept"],
            "reject": counts["reject"],
            "accept_rate": round(accept_rate, 4),
            "recommendation": action,
        }
    return {"min_rows": min_rows, "cells": recommendations}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build severity calibration decision table")
    parser.add_argument("--preferences", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-rows", type=int, default=3)
    args = parser.parse_args(argv)
    payload = train(_read_jsonl(args.preferences), min_rows=max(1, args.min_rows))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"cells": len(payload["cells"]), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
