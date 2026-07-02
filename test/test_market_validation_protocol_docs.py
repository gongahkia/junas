import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class MarketValidationProtocolDocsTests(unittest.TestCase):
    def test_protocol_exists_without_claiming_validation(self):
        protocol = (ROOT / "docs/product/market-validation-protocol.md").read_text(encoding="utf-8")
        flattened_protocol = " ".join(protocol.split())
        personas = (ROOT / "docs/product/personas.md").read_text(encoding="utf-8")
        value_metrics = (ROOT / "docs/product/value-metrics.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")

        for token in (
            "Status: protocol only",
            "No participant evidence is present",
            "Web check performed 2026-07-02",
            "Use the five-participant TODO as qualitative evidence only",
            "not a statistical proof",
            "Legal reviewer",
            "Compliance/admin",
            "Security/platform",
            "Standalone copy-paste redaction",
            "In-workflow review",
            "reports/market-validation/",
            "Only after that evidence exists should the open TODOs be removed",
        ):
            self.assertIn(token, flattened_protocol)

        self.assertIn("Status: hypothesis personas", personas)
        self.assertIn("No five-participant target-user interview evidence", personas)
        self.assertIn("Manual task-study status: not yet run", value_metrics)
        self.assertIn("no validated comparison", value_metrics)
        self.assertIn("product/market-validation-protocol.md", docs_index)

    def test_product_docs_do_not_claim_completed_market_validation(self):
        combined = "\n".join(
            [
                (ROOT / "docs/product/market-validation-protocol.md").read_text(encoding="utf-8"),
                (ROOT / "docs/product/personas.md").read_text(encoding="utf-8"),
                (ROOT / "docs/product/value-metrics.md").read_text(encoding="utf-8"),
            ]
        )
        for forbidden in (
            "validated workflows and pain points are complete",
            "five target users were interviewed",
            "manual task study is complete",
            "standalone copy-paste redaction has lower adoption",
            "in-workflow review has higher adoption",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
