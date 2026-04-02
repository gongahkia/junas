#!/usr/bin/env python3

import argparse
import asyncio

from noupe import AsyncNoupeClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one classify request through the asynchronous Noupe client.")
    parser.add_argument("text", help="Text payload to classify.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Noupe backend base URL.")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--entity-id", default=None, help="Optional entity id for mosaic correlation.")
    parser.add_argument(
        "--include-offending-spans",
        action="store_true",
        help="Request exact lexicon spans and approximate classifier windows when available.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Request heavyweight debug payloads such as embeddings.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with AsyncNoupeClient(args.base_url, api_key=args.api_key) as client:
        result = await client.classify(
            text=args.text,
            entity_id=args.entity_id,
            include_offending_spans=args.include_offending_spans,
            debug=args.debug,
        )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
