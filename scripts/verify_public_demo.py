#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DemoCase:
    key: str
    request: dict[str, Any]
    expected_decision: tuple[str, ...]
    expected_send_allowed: bool
    expected_required_action: str | None
    expected_category: str | None
    expected_rule: str | None


PAGE_TOKENS = (
    "Junas deterministic demo",
    "Strict-profile demo",
    "No LLM, no public evidence, no persistence",
    "Use synthetic text only",
    "SG NRIC prompt",
    "M&amp;A MNPI email",
    "Clean internal note",
    "/demo/review",
)

CASES = (
    DemoCase(
        key="pii",
        request={
            "text": "Remove Dr Jane Tan S1234567D before sending this GenAI prompt to a vendor.",
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "review_profile": "audit_grade",
        },
        expected_decision=("rewrite_required", "approval_required", "block"),
        expected_send_allowed=False,
        expected_required_action="redact_pii",
        expected_category="PII",
        expected_rule="sg_nric_fin",
    ),
    DemoCase(
        key="mnpi",
        request={
            "text": "Project Raven will acquire GlobalTech for USD 2.5 billion before announcement.",
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "review_profile": "strict",
        },
        expected_decision=("block",),
        expected_send_allowed=False,
        expected_required_action="hold_until_public",
        expected_category="MNPI",
        expected_rule="material_event",
    ),
    DemoCase(
        key="clean",
        request={
            "text": "Internal lunch menu draft for the Singapore office. Share vegetarian options with the team.",
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "SG",
            "review_profile": "strict",
        },
        expected_decision=("allow", "warn"),
        expected_send_allowed=True,
        expected_required_action=None,
        expected_category=None,
        expected_rule=None,
    ),
)


def _get_text(url: str, timeout: float) -> str:
    request = urllib.request.Request(url, headers={"Accept": "text/html"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {detail}") from exc


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {detail}") from exc
    if not isinstance(decoded, dict):
        raise AssertionError(f"{url} did not return a JSON object")
    return decoded


def assert_demo_page(html: str) -> None:
    missing = [token for token in PAGE_TOKENS if token not in html]
    if missing:
        raise AssertionError(f"/demo page missing tokens: {', '.join(missing)}")


def assert_demo_payload(case: DemoCase, payload: dict[str, Any]) -> None:
    policy = payload.get("policy_decision")
    if not isinstance(policy, dict):
        raise AssertionError(f"{case.key}: missing policy_decision")
    decision = policy.get("decision")
    if decision not in case.expected_decision:
        raise AssertionError(f"{case.key}: decision {decision!r} not in {case.expected_decision!r}")
    if payload.get("send_allowed") is not case.expected_send_allowed:
        raise AssertionError(f"{case.key}: send_allowed mismatch")
    if policy.get("send_allowed") is not case.expected_send_allowed:
        raise AssertionError(f"{case.key}: policy send_allowed mismatch")
    if payload.get("review_profile") != "strict":
        raise AssertionError(f"{case.key}: hosted demo must force strict review_profile")
    if payload.get("public_evidence") is not None:
        raise AssertionError(f"{case.key}: public_evidence must be disabled")
    if payload.get("llm_adjudication") is not None:
        raise AssertionError(f"{case.key}: llm_adjudication must be disabled")
    if payload.get("privacy_ledger") not in (None, []):
        raise AssertionError(f"{case.key}: privacy_ledger must be empty")

    required = set(policy.get("required_actions") or [])
    if case.expected_required_action and case.expected_required_action not in required:
        raise AssertionError(f"{case.key}: missing required action {case.expected_required_action!r}")

    findings = payload.get("findings") or []
    if case.expected_category is None:
        if findings:
            raise AssertionError(f"{case.key}: expected no findings, got {len(findings)}")
        return
    matching = [
        finding
        for finding in findings
        if finding.get("category") == case.expected_category and finding.get("rule") == case.expected_rule
    ]
    if not matching:
        raise AssertionError(f"{case.key}: missing {case.expected_category}/{case.expected_rule} finding")
    if not all(str(finding.get("legal_basis") or "").strip() for finding in matching):
        raise AssertionError(f"{case.key}: matching findings must include legal_basis citations")


def wait_for_demo(base_url: str, *, ready_timeout: float, request_timeout: float) -> str:
    deadline = time.time() + ready_timeout
    demo_url = f"{base_url.rstrip('/')}/demo"
    last_error = ""
    while time.time() < deadline:
        try:
            html = _get_text(demo_url, timeout=request_timeout)
            assert_demo_page(html)
            return html
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2.0)
    raise RuntimeError(f"public demo did not become ready at {demo_url}: {last_error}")


def verify_public_demo(base_url: str, *, ready_timeout: float, request_timeout: float) -> None:
    base = base_url.rstrip("/")
    wait_for_demo(base, ready_timeout=ready_timeout, request_timeout=request_timeout)
    review_url = f"{base}/demo/review"
    for case in CASES:
        payload = _post_json(review_url, case.request, timeout=request_timeout)
        assert_demo_payload(case, payload)
        policy = payload["policy_decision"]
        print(f"{case.key}: decision={policy.get('decision')} send_allowed={str(payload.get('send_allowed')).lower()}")
    print(f"public_demo_verified: true | base_url: {base} | cases: {len(CASES)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a hosted Junas public demo URL.")
    parser.add_argument("--base-url", required=True, help="Direct app URL, e.g. https://owner-space.hf.space")
    parser.add_argument("--ready-timeout", type=float, default=300.0)
    parser.add_argument("--request-timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        verify_public_demo(args.base_url, ready_timeout=args.ready_timeout, request_timeout=args.request_timeout)
    except Exception as exc:
        sys.stderr.write(f"public demo verification failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
