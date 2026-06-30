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
    title: str
    request: dict[str, Any]
    expected_decision: tuple[str, ...]
    expected_send_allowed: bool
    expected_required_action: str | None
    expected_rule: str | None
    expected_findings: bool


CASES: tuple[DemoCase, ...] = (
    DemoCase(
        key="pii",
        title="SG NRIC in a GenAI prompt",
        request={
            "text": (
                "Before using this GenAI prompt, remove Dr Jane Tan S1234567D "
                "from the draft client update."
            ),
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "document_type": "genai_prompt",
            "surface": "browser_genai",
            "workflow": "prompt_submit",
            "requested_action": "send",
            "external_destination": True,
            "include_suggestions": True,
            "review_profile": "strict",
        },
        expected_decision=("rewrite_required", "approval_required", "block"),
        expected_send_allowed=False,
        expected_required_action="redact_pii",
        expected_rule="sg_nric_fin",
        expected_findings=True,
    ),
    DemoCase(
        key="mnpi",
        title="M&A MNPI before announcement",
        request={
            "text": (
                "Project Raven will acquire GlobalTech for USD 2.5 billion before announcement. "
                "Hold until public disclosure."
            ),
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "document_type": "email",
            "surface": "outlook",
            "workflow": "email_send",
            "requested_action": "send",
            "external_destination": True,
            "include_suggestions": True,
            "review_profile": "strict",
        },
        expected_decision=("block",),
        expected_send_allowed=False,
        expected_required_action="hold_until_public",
        expected_rule="material_event",
        expected_findings=True,
    ),
    DemoCase(
        key="clean",
        title="Clean internal text",
        request={
            "text": (
                "Internal lunch menu draft for the Singapore office. "
                "Share the vegetarian options with the team."
            ),
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "SG",
            "document_type": "internal_note",
            "surface": "api",
            "workflow": "api_review",
            "requested_action": "send",
            "external_destination": False,
            "include_suggestions": True,
            "review_profile": "strict",
        },
        expected_decision=("allow",),
        expected_send_allowed=True,
        expected_required_action=None,
        expected_rule=None,
        expected_findings=False,
    ),
)


def _json_request(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} returned {exc.code}: {detail}") from exc


def _get_json(url: str, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            return payload
        return {"raw": payload}


def wait_until_ready(base_url: str, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    ready_url = f"{base_url.rstrip('/')}/ready"
    last_error = ""
    while time.time() < deadline:
        try:
            payload = _get_json(ready_url, timeout=2.0)
            if payload.get("ready") is True:
                return
            last_error = json.dumps(payload, sort_keys=True)
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"backend did not become ready at {ready_url}: {last_error}")


def _first_suggestion(payload: dict[str, Any], finding_id: str) -> str:
    for suggestion in payload.get("suggestions") or []:
        if suggestion.get("finding_id") == finding_id:
            return str(suggestion.get("rationale") or "")
    return ""


def _short(value: str, limit: int = 180) -> str:
    compact = " ".join(value.replace("→", "=>").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def assert_expected(case: DemoCase, payload: dict[str, Any]) -> None:
    policy = payload.get("policy_decision") or {}
    decision = policy.get("decision")
    if decision not in case.expected_decision:
        raise AssertionError(f"{case.key}: decision {decision!r} not in {case.expected_decision!r}")
    if payload.get("send_allowed") is not case.expected_send_allowed:
        raise AssertionError(f"{case.key}: send_allowed mismatch")
    if policy.get("send_allowed") is not case.expected_send_allowed:
        raise AssertionError(f"{case.key}: policy send_allowed mismatch")
    required = set(policy.get("required_actions") or [])
    if case.expected_required_action and case.expected_required_action not in required:
        raise AssertionError(f"{case.key}: missing required action {case.expected_required_action!r}")
    findings = payload.get("findings") or []
    if case.expected_findings and not findings:
        raise AssertionError(f"{case.key}: expected findings")
    if not case.expected_findings and findings:
        raise AssertionError(f"{case.key}: expected no findings, got {len(findings)}")
    if case.expected_rule and not any(finding.get("rule") == case.expected_rule for finding in findings):
        raise AssertionError(f"{case.key}: missing finding rule {case.expected_rule!r}")


def render_case(index: int, case: DemoCase, payload: dict[str, Any]) -> str:
    policy = payload.get("policy_decision") or {}
    lines = [
        f"{index}. {case.title}",
        f"   decision: {policy.get('decision')} | send_allowed: {str(payload.get('send_allowed')).lower()}",
        (
            "   risk: "
            f"{payload.get('overall_risk')} | PII {payload.get('pii_score')} | MNPI {payload.get('mnpi_score')}"
        ),
    ]
    required = policy.get("required_actions") or []
    recommended = policy.get("recommended_actions") or []
    if required:
        lines.append(f"   required_actions: {', '.join(required)}")
    if recommended:
        lines.append(f"   recommended_actions: {', '.join(recommended)}")
    findings = payload.get("findings") or []
    if not findings:
        lines.append("   findings: none")
    else:
        lines.append("   findings:")
        for finding in findings[:3]:
            lines.append(
                "     - "
                f"{finding.get('category')} {finding.get('rule')} {finding.get('severity')}: "
                f"{_short(str(finding.get('matched_text') or ''), 90)}"
            )
            lines.append(f"       legal_basis: {finding.get('legal_basis')}")
            rationale = _first_suggestion(payload, str(finding.get("id") or ""))
            if rationale:
                lines.append(f"       citation: {_short(rationale)}")
    return "\n".join(lines)


def run_demo(base_url: str, *, assert_cases: bool, ready_timeout: float, request_timeout: float) -> None:
    start = time.time()
    base = base_url.rstrip("/")
    wait_until_ready(base, ready_timeout)
    print("Junas deterministic demo")
    print(f"backend: {base}")
    print("profile: strict, offline, no public evidence, no LLM\n")
    for index, case in enumerate(CASES, start=1):
        payload = _json_request(f"{base}/review", case.request, timeout=request_timeout)
        if assert_cases:
            assert_expected(case, payload)
        print(render_case(index, case, payload))
        print("")
    elapsed = time.time() - start
    print(f"demo_completed: true | cases: {len(CASES)} | elapsed_seconds: {elapsed:.2f}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Junas deterministic review demo.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8766")
    parser.add_argument("--ready-timeout", type=float, default=90.0)
    parser.add_argument("--request-timeout", type=float, default=20.0)
    parser.add_argument(
        "--no-assert",
        action="store_true",
        help="Print demo output without checking expected decisions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_demo(
            args.base_url,
            assert_cases=not args.no_assert,
            ready_timeout=args.ready_timeout,
            request_timeout=args.request_timeout,
        )
    except Exception as exc:
        sys.stderr.write(f"demo failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
