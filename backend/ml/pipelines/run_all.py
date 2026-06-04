from __future__ import annotations

from data.ingestion import pdpc as pdpc_ingest
from ml.pipelines.ingest_glossaries import run as run_glossary_ingest
from ml.pipelines.ingest_lecard import run as run_lecard_ingest
from ml.pipelines.ingest_sso import run as run_sso_ingest


def main() -> int:
    total = 0
    total += run_glossary_ingest()
    total += run_sso_ingest()  # SG statutes (replaces ORS path per #25/#28)
    run_lecard_ingest()
    # SG-LegalBench SGLB-01 dataset materialisation (idempotent).
    pdpc_stats = pdpc_ingest.main([])
    total += pdpc_stats if isinstance(pdpc_stats, int) else 0
    return total


if __name__ == "__main__":
    print(main())
