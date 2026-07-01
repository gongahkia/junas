import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def squash(text: str) -> str:
    return " ".join(text.split())


class PilotRolloutDocsTests(unittest.TestCase):
    def test_pilot_rollout_doc_covers_required_gates(self):
        text = squash((ROOT / "docs" / "deployment-pilot-rollout.md").read_text(encoding="utf-8"))

        for token in (
            "Pilot Rollout Checklist",
            "Tenant/auth mode",
            "JUNAS_TENANCY_ENABLED=1",
            "Policy profile",
            "JUNAS_POLICY_CONFIG",
            "Exactly one supported workflow adapter",
            "Audit exports",
            "scripts/export_audit_pack.py",
            "scripts/verify_audit_pack.py",
            "scripts/verify_journal.py",
            "Telemetry",
            "Support path",
            "Rollback",
            "docs/deployment-rollback.md",
            "Success metrics",
        ):
            self.assertIn(token, text)

    def test_pilot_rollout_doc_lists_success_metrics(self):
        text = squash((ROOT / "docs" / "deployment-pilot-rollout.md").read_text(encoding="utf-8"))

        for token in (
            "Activation rate",
            "Reviewed-send rate",
            "Accepted-finding rate",
            "False-positive override rate",
            "Safe-rewrite usage",
            "Blocked-send rate",
            "Audit-pack export rate",
            "denominator confidence",
            "backend-local",
            "SIEM-exported",
        ):
            self.assertIn(token, text)

    def test_docs_index_and_no_single_pathway_link_pilot_rollout(self):
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        no_single_pathway = (ROOT / "docs" / "integrations" / "no-single-pathway.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("deployment-pilot-rollout.md", docs_index)
        self.assertIn("docs/deployment-pilot-rollout.md", no_single_pathway)


if __name__ == "__main__":
    unittest.main()
