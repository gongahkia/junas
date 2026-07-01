import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class ClaimReviewChecklistDocsTests(unittest.TestCase):
    def test_claim_review_checklist_requires_evidence_types(self):
        text = squash((ROOT / "docs" / "product" / "claim-review-checklist.md").read_text(encoding="utf-8"))

        for token in (
            "Claim Review Checklist",
            "Every marketing or security claim needs evidence before publication",
            "docs",
            "tests",
            "eval reports",
            "external vendor docs",
            "committed artifact",
            "Evidence link",
            "Allowed wording",
            "Forbidden extrapolation",
        ):
            self.assertIn(token, text)

    def test_claim_review_checklist_blocks_unsupported_claims(self):
        text = squash((ROOT / "docs" / "product" / "claim-review-checklist.md").read_text(encoding="utf-8"))

        for token in (
            "replaces DLP",
            "covers every browser",
            "independent TAB or ai4privacy benchmark scores",
            "sends no data to remote providers",
            "blocks all risky sends",
            "low user friction without pilot success metrics",
            "`approved`",
            "`revise`",
            "`reject`",
            "`external-refresh-required`",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_procurement_link_claim_review_checklist(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        procurement = (ROOT / "docs" / "faq" / "procurement.md").read_text(encoding="utf-8")

        self.assertIn("product/claim-review-checklist.md", docs_index)
        self.assertIn("docs/product/claim-review-checklist.md", procurement)


if __name__ == "__main__":
    unittest.main()
