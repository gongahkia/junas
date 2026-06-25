#!/usr/bin/env python3
"""End-to-end anonymise → external-LLM → reidentify demo.

Shows both reidentify paths:
  1. Inline mapping (works without JUNAS_REVIEW_PERSIST)
  2. document_hash only (requires JUNAS_REVIEW_PERSIST=1 on the backend)

Run:
    python3 scripts/examples/round_trip_example.py \
        "Send Dr Jane Tan S1234567D the confidential SPA draft."

    JUNAS_REVIEW_PERSIST=1 path:
    python3 scripts/examples/round_trip_example.py \
        --use-document-hash \
        "Send Dr Jane Tan S1234567D the confidential SPA draft."
"""

import argparse

from junas import JunasClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anonymise then re-identify through Junas.")
    parser.add_argument("text", help="Document text to anonymise.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="Optional X-API-Key value.")
    parser.add_argument("--source", default="SG", help="Source jurisdiction.")
    parser.add_argument("--destination", default="US", help="Destination jurisdiction.")
    parser.add_argument("--document-type", default="SPA", help="Document type (drives severity overrides).")
    parser.add_argument(
        "--use-document-hash",
        action="store_true",
        help="Reidentify using only the document_hash (backend must have JUNAS_REVIEW_PERSIST=1).",
    )
    return parser.parse_args()


def _simulate_external_llm(anonymised_text: str) -> str:
    # placeholder: in production this is where you'd call an external LLM with the redacted text.
    # the placeholders pass straight through unmodified for the round-trip to validate.
    return anonymised_text


def main() -> None:
    args = parse_args()
    with JunasClient(args.base_url, api_key=args.api_key) as client:
        anon = client.anonymize(
            text=args.text,
            source_jurisdiction=args.source,
            destination_jurisdiction=args.destination,
            document_type=args.document_type,
        )

        print("=== anonymised text (safe to send externally) ===")
        print(anon.anonymized_text)
        print(f"\ndocument_hash: {anon.document_hash}")
        print(f"mapping_persisted: {anon.mapping_persisted}")
        print(f"mapping entries: {len(anon.mapping)}")

        # simulate handing off to an external LLM and getting placeholders back
        llm_output = _simulate_external_llm(anon.anonymized_text)

        if args.use_document_hash:
            if not anon.mapping_persisted:
                raise SystemExit(
                    "--use-document-hash requires the backend to have JUNAS_REVIEW_PERSIST=1; "
                    "mapping_persisted came back False."
                )
            restored = client.reidentify(anonymized_text=llm_output, document_hash=anon.document_hash)
            print("\n=== reidentified via document_hash (no mapping in request) ===")
        else:
            restored = client.reidentify(
                anonymized_text=llm_output,
                mapping=[
                    {"placeholder": entry.placeholder, "original_text": entry.original_text}
                    for entry in anon.mapping
                ],
            )
            print("\n=== reidentified via inline mapping ===")

        print(restored.text)
        print(f"\nreplacements applied: {restored.replacement_count}")


if __name__ == "__main__":
    main()
