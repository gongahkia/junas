"""Pipeline entrypoint for CommonLII SG judgment ingestion.

This materialises ``vendor-data/sg_cases/judgments.jsonl`` only; downstream
case parsing/indexing is handled by later SGLB-07 stages.
"""
from __future__ import annotations

from pathlib import Path

from data.ingestion.commonlii_sg import DEFAULT_OUTPUT, run as commonlii_sg_run


def run(
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    court: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    return commonlii_sg_run(
        output_path,
        court=court,
        year=year,
        limit=limit,
        dry_run=dry_run,
        force=force,
    )


if __name__ == "__main__":
    print(run())
