import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.backend.schemas import SafeRewriteRequest, SafeRewriteResponse


def base_review_payload() -> dict:
    return {
        "request_id": "review-1",
        "review_expires_at": "2026-06-14T09:35:00Z",
        "overall_risk": "HIGH_RISK",
        "classification": "HIGH_RISK",
        "document_score": 90.0,
        "pii_score": 85.0,
        "mnpi_score": 0.0,
        "source_jurisdiction": "SG",
        "destination_jurisdiction": "US",
        "jurisdictions_applied": ["SG", "US"],
        "jurisdiction_policy": "strictest_wins",
        "document_type": "email",
        "review_profile": "strict",
        "degraded_policy": "warn",
        "send_allowed": False,
        "policy_decision": {
            "decision": "rewrite_required",
            "send_allowed": False,
            "required_actions": ["redact_pii", "request_approval", "safe_rewrite"],
            "recommended_actions": [],
            "blocking_findings": ["pii:sg_nric_fin:25:34:0"],
            "policy_id": "default",
            "policy_version": "2026-06-14",
            "policy_reasons": ["high-risk PII requires safe rewrite or reviewer approval before send"],
            "review_id": "review-1",
        },
        "action_catalog": ["redact_pii", "safe_rewrite", "request_approval"],
        "document": {
            "filename": "inline.txt",
            "mime_type": "text/plain",
            "extraction_method": "inline_text",
            "page_count": None,
            "char_count": 42,
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
        "timings_ms": {"review": 0.1, "policy_decision_ms": 0.01, "total": 0.11},
    }


class SafeRewriteContractTests(unittest.TestCase):
    def test_request_dedupes_allowed_actions_and_finding_ids(self):
        request = SafeRewriteRequest.model_validate(
            {
                "text": "Send Dr Jane Tan S1234567D.",
                "allowed_actions": ["redact_pii", "safe_rewrite", "redact_pii"],
                "allowed_finding_ids": [" pii:sg_nric_fin:25:34:0 ", "pii:sg_nric_fin:25:34:0", ""],
            }
        )

        self.assertEqual(request.allowed_actions, ["redact_pii", "safe_rewrite"])
        self.assertEqual(request.allowed_finding_ids, ["pii:sg_nric_fin:25:34:0"])

    def test_request_rejects_unsupported_actions(self):
        with self.assertRaises(ValueError):
            SafeRewriteRequest.model_validate(
                {
                    "text": "Send Dr Jane Tan S1234567D.",
                    "allowed_actions": ["pseudonymize"],
                }
            )

    def test_response_preserves_finding_id_and_audit_hash(self):
        payload = base_review_payload()
        payload.update(
            {
                "privacy_operation": "safe_rewrite",
                "rewrite_policy": "deterministic_allowed_spans",
                "rewritten_text": "Send Dr Jane Tan [REDACTED PERSONAL DATA].",
                "document_hash": "a" * 64,
                "mapping_persisted": False,
                "replacements": [
                    {
                        "finding_id": "pii:sg_nric_fin:25:34:0",
                        "action": "redact_pii",
                        "category": "PII",
                        "rule": "sg_nric_fin",
                        "severity": "high",
                        "start_char": 17,
                        "end_char": 26,
                        "replacement_text": "[REDACTED PERSONAL DATA]",
                        "original_text_hash": "b" * 64,
                    }
                ],
                "skipped_findings": [
                    {
                        "finding_id": "mnpi:material_event:42:90:0",
                        "reason": "action not allowed for finding",
                    }
                ],
            }
        )

        response = SafeRewriteResponse.model_validate(payload)

        self.assertEqual(response.replacements[0].finding_id, "pii:sg_nric_fin:25:34:0")
        self.assertEqual(response.replacements[0].original_text_hash, "b" * 64)
        self.assertFalse(response.mapping_persisted)
        self.assertEqual(response.skipped_findings[0].finding_id, "mnpi:material_event:42:90:0")


if __name__ == "__main__":
    unittest.main()
