#!/usr/bin/env python3
"""One-document Azure audit-grade smoke test.

Runs Kaypoh's actual `azure_openai` adapter through `PreSendReviewEngine.review()`
against one existing score-band candidate fixture. This spends at most one LLM
request and does not write reports or recall locks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

DEFAULT_FIXTURE = (
    REPO_ROOT
    / "test/fixtures/legal-corpus-candidates/ae/quasi_identifiers/"
    "ae_quasi_identifiers_privacy_notice_negative_001.txt"
)


def _export_azure_mini_aliases() -> None:
    mappings = {
        "KAYPOH_LLM_ENABLED": "1",
        "KAYPOH_LLM_PROVIDER": "azure_openai",
        "KAYPOH_LLM_BASE_URL": os.environ.get("GPT5_MINI_ENDPOINT", ""),
        "KAYPOH_LLM_MODEL": os.environ.get("GPT5_MINI_DEPLOYMENT", ""),
        "KAYPOH_LLM_AZURE_API_VERSION": os.environ.get("GPT5_MINI_API_VERSION", ""),
        "KAYPOH_LLM_API_KEY": (
            os.environ.get("GPT5_MINI_API_KEY", "") or os.environ.get("KAYPOH_LLM_API_KEY", "")
        ),
        "KAYPOH_LLM_TENANT_OPT_IN_AZURE_OPENAI": "1",
        "KAYPOH_LLM_ALLOW_REMOTE_BASE_URL": "1",
        "KAYPOH_LLM_INPUT_MODE": "structured_tokens",
        "KAYPOH_LLM_TIMEOUT_SECONDS": os.environ.get("KAYPOH_LLM_TIMEOUT_SECONDS", "60"),
    }
    for key, value in mappings.items():
        if value:
            os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test Azure audit-grade LLM wiring")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--use-gpt5-mini-env", action="store_true")
    args = parser.parse_args(argv)

    if args.use_gpt5_mini_env:
        _export_azure_mini_aliases()

    from kaypoh.configs.runtime import get_runtime_settings
    from kaypoh.review.engine import PreSendReviewEngine
    from kaypoh.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

    fixture = args.fixture if args.fixture.is_absolute() else REPO_ROOT / args.fixture
    labels = json.loads(fixture.with_suffix(".labels.json").read_text(encoding="utf-8"))
    settings = get_runtime_settings()
    engine = PreSendReviewEngine(llm_adjudicator=LocalLLMAdjudicator(settings.llm))
    result = engine.review(
        text=fixture.read_text(encoding="utf-8"),
        source_jurisdiction=labels.get("source_jurisdiction", "SG"),
        destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=labels.get("document_type", "generic"),
        review_profile="audit_grade",
    )
    payload = {
        "ok": True,
        "fixture": str(fixture.relative_to(REPO_ROOT)),
        "provider": settings.llm.provider,
        "model": settings.llm.model,
        "input_mode": settings.llm.llm_input_mode,
        "timeout_seconds": settings.llm.timeout_seconds,
        "findings": len(result.findings),
        "mnpi_score": result.mnpi_score,
        "ledger_ops": [entry.get("operation") for entry in result.privacy_ledger],
        "ledger_allowed": [entry.get("allowed") for entry in result.privacy_ledger],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
