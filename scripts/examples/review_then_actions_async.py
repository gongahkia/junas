#!/usr/bin/env python3

import argparse
import asyncio

from kaypoh import AsyncKaypohClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Async review text, then run a follow-up user action.")
    parser.add_argument("text", help="Text to review before action.")
    parser.add_argument("--flow", choices=["safe-rewrite", "request-approval"], required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--source", default="SG")
    parser.add_argument("--destination", default="US")
    parser.add_argument("--document-type", default="email")
    return parser.parse_args()


def _action_finding_ids(review) -> list[str]:
    if review.policy_decision is not None and review.policy_decision.blocking_findings:
        return list(review.policy_decision.blocking_findings)
    return [finding.id for finding in review.findings]


def _approval_reason(decision_name: str | None) -> str:
    if decision_name == "rewrite_required":
        return "rewrite_required"
    if decision_name == "approval_required":
        return "approval_required"
    if decision_name == "block":
        return "policy_block"
    return "user_requested"


async def main() -> None:
    args = parse_args()
    async with AsyncKaypohClient(args.base_url, api_key=args.api_key) as client:
        review = await client.review(
            text=args.text,
            source_jurisdiction=args.source,
            destination_jurisdiction=args.destination,
            document_type=args.document_type,
        )
        finding_ids = _action_finding_ids(review)
        print(f"review_id={review.request_id}")
        print(f"decision={review.policy_decision_name} send_allowed={review.policy_send_allowed}")
        print(f"required_actions={review.policy_required_actions}")
        print(f"available_actions={review.available_actions}")

        if args.flow == "safe-rewrite":
            rewritten = await client.safe_rewrite(
                text=args.text,
                source_jurisdiction=args.source,
                destination_jurisdiction=args.destination,
                document_type=args.document_type,
                allowed_actions=["safe_rewrite", "redact_pii", "hold_until_public"],
                allowed_finding_ids=finding_ids or None,
            )
            print(rewritten.model_dump_json(indent=2))
            return

        if review.request_id is None:
            raise SystemExit("request approval requires a review_id in the review response")
        if not finding_ids:
            raise SystemExit("request approval needs at least one finding id")
        approval = await client.request_approval(
            review_id=review.request_id,
            finding_ids=finding_ids,
            reason_code=_approval_reason(review.policy_decision_name),
        )
        print(approval.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
