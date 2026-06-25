#!/usr/bin/env python3

import argparse

from junas import JunasClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one classify request through the synchronous Junas client.")
    parser.add_argument("text", help="Text payload to classify.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Junas backend base URL.")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--entity-id", default=None, help="Optional issuer/entity context for audit-grade checks.")
    parser.add_argument(
        "--include-offending-spans",
        action="store_true",
        help="Deprecated compatibility flag; current span evidence is in findings.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Request debug metadata when supported by the backend.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with JunasClient(args.base_url, api_key=args.api_key) as client:
        result = client.classify(
            text=args.text,
            entity_id=args.entity_id,
            include_offending_spans=args.include_offending_spans,
            debug=args.debug,
        )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
