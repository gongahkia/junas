"""Structured-tokens-in/out LLM mode (item 27).

Four guarantees:

1. In structured mode, the LLM request body contains NO raw document text,
   NO matched_text, NO start_char/end_char, NO exact public-source URLs.
2. The LLM request body DOES contain: rule names, severities, jurisdiction codes,
   SHA-256(body), per-finding context-window hashes, public-evidence summary counts.
3. If the LLM tries to emit a materiality_reason outside the closed vocabulary,
   the server clamps it and sets output_clamped=True.
4. raw_text mode is unaffected: behaviour is byte-identical to before, and the
   new input_mode field reports "raw_text" with output_clamped=False.
"""

import json
import unittest
from types import SimpleNamespace

import httpx

from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator
from kaypoh.workflow.layer8_llm_adjudicator.structured_query import (
    STRUCTURED_REASONS,
    build_structured_query,
    clamp_structured_output,
)


def _llm_settings(*, mode: str = "structured_tokens") -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        provider="vllm",
        api_key="",
        base_url="http://127.0.0.1:8001/v1",
        model="gpt-oss-20b",
        timeout_seconds=2.0,
        allow_remote_base_url=False,
        tenant_opt_in_openai=False,
        llm_input_mode=mode,
    )


def _make_finding(rule: str, matched: str, start: int, end: int, severity: str = "high"):
    return SimpleNamespace(
        rule=rule, category="MNPI", severity=severity, jurisdiction="SG",
        matched_text=matched, start_char=start, end_char=end,
    )


class StructuredQueryBuilderTests(unittest.TestCase):
    def test_query_contains_hashes_not_raw_text(self):
        text = "Confidential acquisition of GlobalTech for $2.5 billion."
        findings = [_make_finding("transaction_codename", "Project X", 5, 14)]
        query = build_structured_query(
            text=text, findings=findings, entity_id="acme-corp",
            current_classification="LOW_RISK", public_evidence=None,
        )
        # the body hash is present
        self.assertEqual(len(query["body_hash"]), 64)
        # per-finding context hash is present
        self.assertEqual(len(query["findings"][0]["context_window_hash"]), 64)
        # NO raw text fields anywhere
        flat = json.dumps(query)
        self.assertNotIn(text, flat)
        self.assertNotIn("Project X", flat)
        self.assertNotIn("$2.5 billion", flat)
        # but rule/severity/jurisdiction ARE present
        self.assertIn("transaction_codename", flat)
        self.assertIn("high", flat)

    def test_public_evidence_summary_carries_counts_not_urls(self):
        findings = []
        pe = {
            "status": "queried",
            "sources": [
                {"url": "https://secret.example.com/leaked-page"},
                {"url": "https://secret.example.com/another"},
            ],
            "queries": [
                {"blocked": True, "reason": "pii in query"},
                {"blocked": False},
            ],
        }
        query = build_structured_query(
            text="x", findings=findings, entity_id=None,
            current_classification="LOW_RISK", public_evidence=pe,
        )
        flat = json.dumps(query)
        self.assertNotIn("secret.example.com", flat)
        self.assertEqual(query["public_evidence_summary"]["source_count"], 2)
        self.assertEqual(query["public_evidence_summary"]["blocked_query_count"], 1)

    def test_entity_id_is_passed_through_unchanged(self):
        # caller is responsible for sanitising entity_id before passing; this layer
        # just forwards what it gets. document the contract.
        query = build_structured_query(
            text="x", findings=[], entity_id="acme-corp",
            current_classification="LOW_RISK", public_evidence=None,
        )
        self.assertEqual(query["entity_id"], "acme-corp")


class StructuredOutputClampingTests(unittest.TestCase):
    def test_known_reason_passes_through(self):
        payload = {
            "risk_label": "SAFE",
            "materiality_reason": "public_source_match",
            "matched_public_sources": [],
            "unverified_claims": [],
            "review_recommendation": "no escalation",
        }
        clamped, was_clamped = clamp_structured_output(payload)
        self.assertFalse(was_clamped)
        self.assertEqual(clamped["materiality_reason"], "public_source_match")

    def test_freeform_reason_is_clamped(self):
        payload = {
            "risk_label": "SAFE",
            "materiality_reason": "the document mentions a confidential acquisition of Acme",
            "matched_public_sources": [],
            "unverified_claims": [],
            "review_recommendation": "ok",
        }
        clamped, was_clamped = clamp_structured_output(payload)
        self.assertTrue(was_clamped)
        self.assertEqual(clamped["materiality_reason"], "ambiguous_unconstrained")

    def test_matched_public_sources_always_empty_in_structured_mode(self):
        # even if the LLM tries to echo back URLs, the clamp strips them.
        payload = {
            "risk_label": "SAFE",
            "materiality_reason": "public_source_match",
            "matched_public_sources": ["https://leak.example.com"],
            "unverified_claims": [],
            "review_recommendation": "ok",
        }
        clamped, _ = clamp_structured_output(payload)
        self.assertEqual(clamped["matched_public_sources"], [])

    def test_long_review_recommendation_is_clamped(self):
        payload = {
            "risk_label": "SAFE",
            "materiality_reason": "public_source_match",
            "matched_public_sources": [],
            "unverified_claims": [],
            "review_recommendation": "x" * 200,  # too long, looks like free-form text
        }
        clamped, was_clamped = clamp_structured_output(payload)
        self.assertTrue(was_clamped)
        self.assertEqual(clamped["review_recommendation"], "see_audit_pack")

    def test_structured_reasons_is_a_closed_vocabulary(self):
        # if this assertion ever fails, someone widened the closed vocabulary —
        # which is fine, but it should be a deliberate edit. flag it.
        self.assertIn("ambiguous_unconstrained", STRUCTURED_REASONS)
        self.assertIn("public_source_match", STRUCTURED_REASONS)
        self.assertGreaterEqual(len(STRUCTURED_REASONS), 5)


class AdjudicatorStructuredModeTests(unittest.TestCase):
    def _mock_chat_completion(self, materiality_reason: str = "public_source_match"):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "risk_label": "SAFE",
                            "public_status": "public",
                            "confidence": 0.9,
                            "materiality_reason": materiality_reason,
                            "matched_public_sources": [],
                            "unverified_claims": [],
                            "review_recommendation": "ok",
                        })
                    }
                }
            ]
        }

    def _run_with_mock_transport(self, settings, *, materiality_reason: str, **adjudicate_kwargs):
        adj = LocalLLMAdjudicator(settings)
        captured_body: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=self._mock_chat_completion(materiality_reason))

        transport = httpx.MockTransport(handler)
        original = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        httpx.Client = factory  # type: ignore[assignment]
        try:
            result = adj.adjudicate(**adjudicate_kwargs)
        finally:
            httpx.Client = original  # type: ignore[assignment]
        return result, captured_body

    def test_structured_mode_does_not_send_raw_text(self):
        text = "Acme will acquire GlobalTech for $2.5 billion before announcement."
        findings = [_make_finding("transaction_codename", "GlobalTech", 17, 27)]
        result, captured = self._run_with_mock_transport(
            _llm_settings(mode="structured_tokens"),
            materiality_reason="public_source_match",
            text=text, current_classification="LOW_RISK",
            findings=findings, entity_id="acme-corp",
        )
        user_message = next(m for m in captured["body"]["messages"] if m["role"] == "user")
        self.assertNotIn(text, user_message["content"])
        self.assertNotIn("GlobalTech", user_message["content"])
        self.assertNotIn("$2.5 billion", user_message["content"])
        # but the body hash IS there
        body_hash_expected = json.loads(user_message["content"])["body_hash"]
        self.assertEqual(len(body_hash_expected), 64)
        # result reports the mode + clamp status
        self.assertEqual(result["input_mode"], "structured_tokens")
        self.assertFalse(result["output_clamped"])

    def test_structured_mode_clamps_freeform_response(self):
        # the model tries to emit free-form prose; the server clamps and flags it
        result, _ = self._run_with_mock_transport(
            _llm_settings(mode="structured_tokens"),
            materiality_reason="the document discusses a sensitive deal",
            text="x", current_classification="LOW_RISK",
            findings=[], entity_id=None,
        )
        self.assertEqual(result["materiality_reason"], "ambiguous_unconstrained")
        self.assertTrue(result["output_clamped"])

    def test_raw_text_mode_sends_document_text(self):
        # control: raw_text mode is unchanged. document text IS in the request body.
        text = "Acme will acquire GlobalTech."
        result, captured = self._run_with_mock_transport(
            _llm_settings(mode="raw_text"),
            materiality_reason="something",
            text=text, current_classification="LOW_RISK",
            findings=[], entity_id=None,
        )
        user_message = next(m for m in captured["body"]["messages"] if m["role"] == "user")
        self.assertIn(text, user_message["content"])
        # raw_text mode does NOT clamp materiality_reason
        self.assertEqual(result["materiality_reason"], "something")
        self.assertEqual(result["input_mode"], "raw_text")
        self.assertFalse(result["output_clamped"])


if __name__ == "__main__":
    unittest.main()
