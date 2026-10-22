"""Every eligible detected character must be covered, including crossing spans."""

import unittest

import junas.backend.main as main
from junas.anonymize.engine import DeterministicAnonymizer, reidentify
from junas.backend.schemas import PolicyDecisionResponse, SafeRewriteRequest
from junas.review.citations import pii_rationale


def finding(identifier, start, end, severity="high"):
    return {
        "id": identifier,
        "category": "PII",
        "rule": "email_address",
        "severity": severity,
        "start_char": start,
        "end_char": end,
    }


def covered(spans):
    return {index for span in spans for index in range(span.start_char, span.end_char)}


class OverlapCoverageTests(unittest.TestCase):
    text = "🙂ABCDEFGHIJKL中文MNOPQ public"
    cases = [
        [finding("first", 1, 6), finding("crossing", 4, 11)],
        [finding("short-high", 1, 5), finding("long-low", 1, 13, "low")],
        [finding("a", 1, 6), finding("b", 3, 10), finding("c", 8, 15)],
        [finding("a", 1, 6), finding("nested", 2, 4), finding("separate", 10, 15)],
        [finding("a", 1, 6), finding("adjacent", 6, 11)],
    ]

    def test_anonymization_covers_the_exact_union_and_roundtrips_unicode(self):
        for findings in self.cases:
            for ordered in (findings, list(reversed(findings))):
                with self.subTest(findings=ordered):
                    result = DeterministicAnonymizer().anonymize(text=self.text, findings=ordered)
                    expected = {i for f in findings for i in range(f["start_char"], f["end_char"])}
                    self.assertEqual(covered(result.replacements), expected)
                    self.assertEqual(
                        reidentify(anonymized_text=result.anonymized_text, mapping=result.mapping)[0], self.text
                    )

    def test_safe_rewrite_covers_every_eligible_span_without_replacing_public_gaps(self):
        policy = PolicyDecisionResponse(
            decision="rewrite_required",
            send_allowed=False,
            required_actions=["redact_pii"],
            policy_id="synthetic",
            policy_version="1",
            review_id="synthetic-review",
        )
        for findings in self.cases:
            with self.subTest(findings=findings):
                plan, _ = main._safe_rewrite_plan(
                    text=self.text, findings=findings, policy_decision=policy, req=SafeRewriteRequest(text=self.text)
                )
                expected = {i for f in findings for i in range(f["start_char"], f["end_char"])}
                self.assertEqual(covered(plan), expected)
                self.assertTrue(main._apply_safe_rewrite(self.text, plan).endswith(" public"))

    def test_safe_rewrite_never_expands_into_an_unapproved_finding(self):
        findings = [finding("approved", 1, 6), finding("unapproved", 4, 11)]
        policy = PolicyDecisionResponse(
            decision="rewrite_required",
            send_allowed=False,
            required_actions=["redact_pii"],
            policy_id="synthetic",
            policy_version="1",
            review_id="synthetic-review",
        )
        plan, skipped = main._safe_rewrite_plan(
            text=self.text,
            findings=findings,
            policy_decision=policy,
            req=SafeRewriteRequest(text=self.text, allowed_finding_ids=["approved"]),
        )
        self.assertEqual(covered(plan), set(range(1, 6)))
        self.assertEqual([item.finding_id for item in skipped], ["unapproved"])

    def test_sg_nric_rationale_distinguishes_lawful_exceptions_from_masking_policy(self):
        rationale = pii_rationale(rule="sg_nric_fin", jurisdiction="SG")
        self.assertNotIn("effective 31 Dec 2026", rationale)
        self.assertIn("deemed consent", rationale)
        self.assertIn("authorised", rationale)
        self.assertIn("Mask before send", rationale)
