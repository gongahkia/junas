#!/usr/bin/env python3
"""Run the mock DMS v1 check-in hook against a Junas backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.integrations.dms import DmsCheckInRequest, HttpDmsReviewClient, MockDmsCheckInHook  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a mock DMS check-in review before commit.")
    parser.add_argument("path", type=Path, help="Text document to review before mock check-in.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--bearer-token", default="")
    parser.add_argument("--dms", default="mockdms")
    parser.add_argument("--matter-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--version-id", default="")
    parser.add_argument("--idempotency-key", default="")
    parser.add_argument("--source-jurisdiction", default="SG")
    parser.add_argument("--destination-jurisdiction", default="SG")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    hook = MockDmsCheckInHook(
        HttpDmsReviewClient(base_url=args.base_url, api_key=args.api_key, bearer_token=args.bearer_token)
    )
    result = hook.check_in(
        DmsCheckInRequest(
            dms=args.dms,
            matter_id=args.matter_id,
            document_id=args.document_id,
            dms_version_id=args.version_id,
            text=args.path.read_text(encoding="utf-8"),
            actor_id=args.actor_id,
            source_jurisdiction=args.source_jurisdiction,
            destination_jurisdiction=args.destination_jurisdiction,
            idempotency_key=args.idempotency_key,
        )
    )
    payload = {
        "status": result.status,
        "check_in_allowed": result.check_in_allowed,
        "duplicate": result.duplicate,
        "audit_fields": result.audit_fields,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result.check_in_allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
