import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.policy import TenantPolicyProfile, WorkflowContext, evaluate_policy


def finding(finding_id: str, category: str, severity: str, **extra):
    payload = {"id": finding_id, "category": category, "severity": severity}
    payload.update(extra)
    return payload


class PolicyEngineTests(unittest.TestCase):
    def test_high_pii_requires_rewrite(self):
        decision = evaluate_policy(findings=[finding("p1", "PII", "high")])

        self.assertEqual(decision.decision, "rewrite_required")
        self.assertFalse(decision.send_allowed)
        self.assertEqual(decision.blocking_findings, ("p1",))
        self.assertIn("safe_rewrite", decision.required_actions)

    def test_high_mnpi_blocks_without_public_evidence_or_approval(self):
        decision = evaluate_policy(findings=[finding("m1", "MNPI", "high")])

        self.assertEqual(decision.decision, "block")
        self.assertFalse(decision.send_allowed)
        self.assertEqual(decision.blocking_findings, ("m1",))
        self.assertIn("hold_until_public", decision.required_actions)

    def test_extended_approval_decision_warns_for_high_mnpi(self):
        decision = evaluate_policy(findings=[finding("m1", "MNPI", "high", decision="approve")])

        self.assertEqual(decision.decision, "warn")
        self.assertTrue(decision.send_allowed)
        self.assertIn("high-risk MNPI has reviewer approval", decision.policy_reasons)

    def test_mixed_pii_mnpi_uses_block_precedence(self):
        decision = evaluate_policy(
            findings=[
                finding("p1", "PII", "high"),
                finding("m1", "MNPI", "high"),
            ]
        )

        self.assertEqual(decision.decision, "block")
        self.assertFalse(decision.send_allowed)
        self.assertEqual(decision.blocking_findings, ("m1", "p1"))
        self.assertIn("safe_rewrite", decision.required_actions)
        self.assertIn("hold_until_public", decision.required_actions)

    def test_cross_border_recipient_warns(self):
        decision = evaluate_policy(
            findings=[],
            context=WorkflowContext(source_jurisdiction="SG", destination_jurisdiction="US"),
        )

        self.assertEqual(decision.decision, "warn")
        self.assertTrue(decision.send_allowed)
        self.assertIn("cross-border destination context should be shown to the user", decision.policy_reasons)

    def test_external_domain_warns(self):
        profile = TenantPolicyProfile(internal_domains=("example.com",))
        decision = evaluate_policy(
            findings=[],
            context=WorkflowContext(recipient_domains=("external.example",)),
            profile=profile,
        )

        self.assertEqual(decision.decision, "warn")
        self.assertTrue(decision.send_allowed)
        self.assertIn("external recipient domain should be shown to the user", decision.policy_reasons)

    def test_degraded_block_send_blocks(self):
        decision = evaluate_policy(
            findings=[],
            degraded_policy="block_send",
            degraded_modes=[{"mode": "pdf_text", "status": "failed"}],
        )

        self.assertEqual(decision.decision, "block")
        self.assertFalse(decision.send_allowed)
        self.assertEqual(decision.required_actions, ("retry_review",))

    def test_reviewer_role_can_request_high_pii_approval(self):
        decision = evaluate_policy(
            findings=[finding("p1", "PII", "high")],
            context=WorkflowContext(actor_role="legal_reviewer"),
        )

        self.assertEqual(decision.decision, "approval_required")
        self.assertFalse(decision.send_allowed)
        self.assertEqual(decision.required_actions, ("request_approval",))

    def test_missing_workflow_context_stays_conservative(self):
        decision = evaluate_policy(findings=[finding("p1", "PII", "high")], context=None)

        self.assertEqual(decision.decision, "rewrite_required")
        self.assertFalse(decision.send_allowed)

    def test_public_evidence_downgrades_high_mnpi_to_warning(self):
        decision = evaluate_policy(
            findings=[finding("m1", "MNPI", "high", source_verification="public_source_matched")]
        )

        self.assertEqual(decision.decision, "warn")
        self.assertTrue(decision.send_allowed)
        self.assertEqual(decision.blocking_findings, ())
        self.assertIn("cite_public_source", decision.recommended_actions)

    def test_public_evidence_recommends_citation_for_medium_mnpi(self):
        decision = evaluate_policy(
            findings=[finding("m1", "MNPI", "medium", source_verification="public_source_matched")]
        )

        self.assertEqual(decision.decision, "warn")
        self.assertIn("cite_public_source", decision.recommended_actions)


if __name__ == "__main__":
    unittest.main()
