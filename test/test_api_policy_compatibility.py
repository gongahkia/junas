import sys
import unittest
from pathlib import Path

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.backend.schemas import ReviewResponse


def legacy_review_payload() -> dict:
    return {
        "request_id": "r1",
        "overall_risk": "LOW_RISK",
        "classification": "LOW_RISK",
        "document_score": 40.0,
        "pii_score": 40.0,
        "mnpi_score": 0.0,
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "SG",
        "jurisdictions_applied": ["SG"],
        "jurisdiction_policy": "strictest_wins",
        "document_type": "generic",
        "review_profile": "strict",
        "degraded_policy": "warn",
        "send_allowed": True,
        "document": {
            "filename": "inline.txt",
            "mime_type": "text/plain",
            "extraction_method": "inline_text",
            "page_count": None,
            "char_count": 22,
        },
        "findings": [],
        "lane_suppressed_count": 0,
        "lane_suppressed_findings": [],
        "suggestions": [],
        "public_evidence": None,
        "llm_adjudication": None,
        "privacy_ledger": [],
        "coverage_warnings": [],
        "degraded_modes": [],
        "timings_ms": {"review": 0.1, "total": 0.1},
    }


class LegacySendAllowedView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    send_allowed: bool


class ApiPolicyCompatibilityTests(unittest.TestCase):
    def test_review_response_deserializes_when_policy_fields_absent(self):
        response = ReviewResponse.model_validate(legacy_review_payload())

        self.assertTrue(response.send_allowed)
        self.assertIsNone(response.policy_decision)
        self.assertEqual(response.action_catalog, [])

    def test_legacy_send_allowed_client_ignores_policy_fields(self):
        payload = legacy_review_payload()
        payload["policy_decision"] = {
            "decision": "allow",
            "send_allowed": True,
            "required_actions": [],
            "recommended_actions": [],
            "blocking_findings": [],
            "policy_id": "default",
            "policy_version": "2026-06-14",
            "policy_reasons": [],
            "review_id": "r1",
        }
        payload["action_catalog"] = ["redact_pii", "safe_rewrite"]

        view = LegacySendAllowedView.model_validate(payload)

        self.assertTrue(view.send_allowed)


if __name__ == "__main__":
    unittest.main()
