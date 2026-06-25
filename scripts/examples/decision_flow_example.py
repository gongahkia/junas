#!/usr/bin/env python3
"""Demonstrate the review → decision → session-state audit flow.

Requires the backend to run with `JUNAS_REVIEW_PERSIST=1`, a journal key, and a
subject-index key. `--reviewer-id` is a local-dev helper and requires `JUNAS_DEV_AUTH=1`;
server deployments attribute decisions to the authenticated JWT/API-key principal.

Run:
    JUNAS_REVIEW_PERSIST=1 JUNAS_DEV_AUTH=1 \\
      JUNAS_JOURNAL_KEY=$(openssl rand -hex 32) \\
      JUNAS_SUBJECT_INDEX_KEY=$(openssl rand -hex 32) \\
      uvicorn junas.backend.main:app --reload --host 0.0.0.0 --port 8000

    python3 scripts/examples/decision_flow_example.py \\
        --reviewer-id "priya.raman@example.bank" \\
        "Send Dr Jane Tan S1234567D the confidential SPA draft. Acquisition value $2.5 billion."
"""

import argparse
import json

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review + decision audit flow demo.")
    parser.add_argument("text", help="Document text to review.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--reviewer-id", default="", help="Dev-only X-Reviewer-ID when JUNAS_DEV_AUTH=1.")
    parser.add_argument("--source", default="SG")
    parser.add_argument("--destination", default="US")
    parser.add_argument("--document-type", default="SPA")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    headers = {"Accept": "application/json"}
    if args.api_key:
        headers["X-API-Key"] = args.api_key
    if args.reviewer_id:
        headers["X-Reviewer-ID"] = args.reviewer_id

    with httpx.Client(base_url=args.base_url, headers=headers, timeout=30.0) as client:
        review = client.post(
            "/review",
            json={
                "text": args.text,
                "source_jurisdiction": args.source,
                "destination_jurisdiction": args.destination,
                "document_type": args.document_type,
            },
        )
        review.raise_for_status()
        review_body = review.json()
        review_id = review_body["request_id"]
        print(f"=== review ===\nreview_id={review_id}  findings={len(review_body['findings'])}")
        for finding in review_body["findings"][:3]:
            print(f"  - {finding['id']} [{finding['category']}/{finding['rule']}] {finding['matched_text']!r}")

        if not review_body["findings"]:
            raise SystemExit("no findings in this document; pick a noisier example.")

        # accept the first finding, reject the second (if present)
        first = review_body["findings"][0]
        second = review_body["findings"][1] if len(review_body["findings"]) > 1 else None

        decision1 = client.post(
            f"/review/{review_id}/decision",
            json={
                "finding_id": first["id"],
                "action": "accept",
                "rationale": "confirmed personal data, redact before send",
            },
        )
        decision1.raise_for_status()
        print(f"\n=== decision 1: accept {first['id']} ===")
        print(json.dumps(decision1.json(), indent=2))

        if second is not None:
            decision2 = client.post(
                f"/review/{review_id}/decision",
                json={
                    "finding_id": second["id"],
                    "action": "reject",
                    "rationale": "defined term in contract preamble, false positive",
                },
            )
            decision2.raise_for_status()
            print(f"\n=== decision 2: reject {second['id']} ===")
            print(json.dumps(decision2.json(), indent=2))

        state = client.get(f"/review/{review_id}")
        state.raise_for_status()
        state_body = state.json()
        print("\n=== session state after decisions ===")
        print(f"decisions_recorded: {state_body['decisions_recorded']}")
        for finding in state_body["findings"]:
            badge = finding["decision"] or "undecided"
            by = f" by {finding['decision_reviewer_id']}" if finding.get("decision_reviewer_id") else ""
            source = finding.get("decision_reviewer_identity_source") or "none"
            print(f"  - {finding['id']} -> {badge}{by} [{source}]")

        print(
            "\nExport an audit pack with:\n"
            f"  python3 scripts/export_audit_pack.py {review_id} --output ./out/audit.zip\n"
            f"  python3 scripts/verify_audit_pack.py ./out/audit.zip"
        )


if __name__ == "__main__":
    main()
