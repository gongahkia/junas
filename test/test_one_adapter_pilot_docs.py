import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class OneAdapterPilotDocsTests(unittest.TestCase):
    def test_pilot_docs_warn_against_all_adapter_rollout(self):
        rollout = squash((ROOT / "docs" / "deployment-pilot-rollout.md").read_text(encoding="utf-8"))
        no_single_pathway = squash(
            (ROOT / "docs" / "integrations" / "no-single-pathway.md").read_text(encoding="utf-8")
        )

        for text in (rollout, no_single_pathway):
            self.assertIn("Do not deploy all adapters at once", text)
            self.assertIn("direct", text)
            self.assertIn("one supported", text.lower())

        for token in (
            "direct API/backend contract plus one supported adapter",
            "Add a second adapter only after the first surface",
            "auth, policy, telemetry, audit export, support, rollback, and success-metric evidence",
            "keeps failures attributable to one workflow",
        ):
            self.assertIn(token, rollout)


if __name__ == "__main__":
    unittest.main()
