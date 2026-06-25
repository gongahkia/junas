#!/usr/bin/env python3

import argparse
import json
import sys

from junas import JunasClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review stdin and print the policy decision JSON.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--source", default="SG")
    parser.add_argument("--destination", default="US")
    parser.add_argument("--document-type", default="generic")
    parser.add_argument("--degraded-policy", choices=["allow", "warn", "block_send"], default="warn")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    text = sys.stdin.read()
    if not text.strip():
        sys.stderr.write("stdin is empty\n")
        return 2

    with JunasClient(args.base_url, api_key=args.api_key) as client:
        review = client.review(
            text=text,
            source_jurisdiction=args.source,
            destination_jurisdiction=args.destination,
            document_type=args.document_type,
            degraded_policy=args.degraded_policy,
        )

    if review.policy_decision is not None:
        print(review.policy_decision.model_dump_json(indent=2))
    else:
        print(
            json.dumps(
                {
                    "decision": review.policy_decision_name,
                    "send_allowed": review.policy_send_allowed,
                    "required_actions": review.policy_required_actions,
                    "recommended_actions": review.policy_recommended_actions,
                    "review_id": review.request_id,
                },
                indent=2,
            )
        )
    return 0 if review.policy_send_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
