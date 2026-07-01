import os
import tempfile
import unittest
from pathlib import Path

from junas.policy import evaluate_policy
from junas.review.engine import LLM_TIER_MNPI_UPPER, PreSendReviewEngine, ReviewFinding
from junas.review.surfacing_lane import apply_surfacing_lanes

HIGH_MNPI_TEXT = (
    "Confidential pre-announcement acquisition of GlobalTech for $2.5 billion. "
    "Material non-public information; do not distribute."
)


class PublicEvidenceThatWouldClear:
    def __init__(self):
        self.calls = 0

    def retrieve(self, *, text, entity_id=None, lexicon=None):
        self.calls += 1
        return {
            "status": "queried",
            "provider": "exa",
            "sources": [{"title": "public filing", "url": "https://example.com/filing"}],
            "privacy_ledger": [],
        }


class LLMThatWouldClear:
    def __init__(self):
        self.calls = 0

    def adjudicate(self, **kwargs):
        self.calls += 1
        return {
            "status": "adjudicated",
            "risk_label": "SAFE",
            "public_status": "public",
            "materiality_reason": "synthesised public sources match the claim",
            "input_mode": "structured_tokens",
        }


def _finding(finding_id: str, *, source_verification: str = "not_checked") -> dict[str, str]:
    return {
        "id": finding_id,
        "category": "MNPI",
        "severity": "high",
        "source_verification": source_verification,
    }


class DeterministicHighNonSuppressionTests(unittest.TestCase):
    def test_public_evidence_and_llm_do_not_engage_or_clear_deterministic_high(self):
        public_evidence = PublicEvidenceThatWouldClear()
        llm = LLMThatWouldClear()
        engine = PreSendReviewEngine(public_evidence_retriever=public_evidence, llm_adjudicator=llm)

        result = engine.review(
            text=HIGH_MNPI_TEXT,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id="Acme Corp",
            include_suggestions=False,
            document_type="memo",
            review_profile="audit_grade",
        )

        high_findings = [
            finding
            for finding in result.findings
            if finding.category == "MNPI" and finding.severity == "high"
        ]
        self.assertGreaterEqual(result.mnpi_score, LLM_TIER_MNPI_UPPER)
        self.assertGreater(len(high_findings), 0)
        self.assertIsNone(result.public_evidence)
        self.assertIsNone(result.llm_adjudication)
        self.assertEqual(public_evidence.calls, 0)
        self.assertEqual(llm.calls, 0)
        self.assertNotEqual(result.overall_risk.value, "SAFE")

    def test_surfacing_lane_cannot_hide_deterministic_high_findings(self):
        finding = ReviewFinding(
            id="m1",
            category="MNPI",
            rule="material_event",
            jurisdiction="SG",
            severity="high",
            score=91.0,
            matched_text="Acme acquisition",
            start_char=0,
            end_char=16,
            reason="test",
            legal_basis="SG_SFA_MARKET_MISCONDUCT",
        )
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["JUNAS_TENANT_CONFIG_DIR"] = tmp
            try:
                Path(tmp, "tenant-a.toml").write_text(
                    "[lane.high]\nroute = \"batched\"\ndigest_cadence = \"daily\"\n",
                    encoding="utf-8",
                )
                result = apply_surfacing_lanes([finding], tenant_id="tenant-a")
            finally:
                os.environ.pop("JUNAS_TENANT_CONFIG_DIR", None)

        self.assertEqual([item.id for item in result.visible_findings], ["m1"])
        self.assertEqual(result.suppressed_findings, [])
        lane = result.visible_findings[0].metadata["lane_routing"]
        self.assertFalse(lane["suppressed"])
        self.assertEqual(lane["reason"], "deterministic_high_visible")

    def test_policy_softening_keeps_high_mnpi_visible(self):
        finding = _finding("m1", source_verification="public_source_matched")

        decision = evaluate_policy(findings=[finding])

        self.assertEqual(decision.decision, "warn")
        self.assertTrue(decision.send_allowed)
        self.assertIn("high-risk MNPI has public evidence but should remain visible", decision.policy_reasons)
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["source_verification"], "public_source_matched")


if __name__ == "__main__":
    unittest.main()
