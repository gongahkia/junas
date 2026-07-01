import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class BuyerObjectionsDocsTests(unittest.TestCase):
    def test_buyer_objections_doc_covers_required_objections(self):
        text = squash((ROOT / "docs" / "faq" / "buyer-objections.md").read_text(encoding="utf-8"))

        for token in (
            "Buyer Objections",
            "Accuracy proof",
            "Legal liability",
            "Data residency",
            "Admin deployment",
            "User friction",
            "False positives",
            "Existing DLP interoperability",
            "Must not claim",
        ):
            self.assertIn(token, text)

    def test_buyer_objections_doc_points_to_evidence_and_boundaries(self):
        text = squash((ROOT / "docs" / "faq" / "buyer-objections.md").read_text(encoding="utf-8"))

        for token in (
            "docs/accuracy.md",
            "docs/known-limitations.md",
            "docs/deployment-managed-llm.md",
            "docs/security/remote-llm-config.md",
            "docs/integrations/adapter-packaging.md",
            "docs/product/pilot-success-rubric.md",
            "docs/policy/decision-taxonomy.md",
            "docs/faq/operator.md",
            "Replacement of DLP",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_procurement_faq_link_buyer_objections(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        procurement = (ROOT / "docs" / "faq" / "procurement.md").read_text(encoding="utf-8")

        self.assertIn("faq/buyer-objections.md", docs_index)
        self.assertIn("docs/faq/buyer-objections.md", procurement)


if __name__ == "__main__":
    unittest.main()
