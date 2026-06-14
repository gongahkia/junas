from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

PolicyDecisionName = Literal["allow", "warn", "block", "approval_required", "rewrite_required"]
ACTION_CATALOG: tuple[str, ...] = (
    "redact_pii",
    "pseudonymize",
    "safe_rewrite",
    "cite_public_source",
    "request_approval",
    "hold_until_public",
    "proceed_with_warning",
)

_DECISION_RANK: dict[PolicyDecisionName, int] = {
    "allow": 0,
    "warn": 1,
    "rewrite_required": 2,
    "approval_required": 3,
    "block": 4,
}


@dataclass(frozen=True)
class WorkflowContext:
    source_jurisdiction: str | None = None
    destination_jurisdiction: str | None = None
    surface: str | None = None
    workflow: str | None = None
    actor_role: str | None = None
    recipient_domains: tuple[str, ...] = ()
    recipient_count: int | None = None
    attachment_count: int | None = None
    sensitivity_label: str | None = None
    external_destination: bool | None = None
    requested_action: str | None = None

    @classmethod
    def from_request(cls, request: Any) -> "WorkflowContext":
        domains = getattr(request, "recipient_domains", None) or ()
        return cls(
            source_jurisdiction=getattr(request, "source_jurisdiction", None),
            destination_jurisdiction=getattr(request, "destination_jurisdiction", None),
            surface=getattr(request, "surface", None),
            workflow=getattr(request, "workflow", None),
            actor_role=getattr(request, "actor_role", None),
            recipient_domains=tuple(str(domain).lower() for domain in domains),
            recipient_count=getattr(request, "recipient_count", None),
            attachment_count=getattr(request, "attachment_count", None),
            sensitivity_label=getattr(request, "sensitivity_label", None),
            external_destination=getattr(request, "external_destination", None),
            requested_action=getattr(request, "requested_action", None),
        )


@dataclass(frozen=True)
class TenantPolicyProfile:
    policy_id: str = "default"
    policy_version: str = "2026-06-14"
    internal_domains: tuple[str, ...] = ()
    warn_on_low_risk_findings: bool = True
    degraded_block_action: str = "retry_review"
    high_pii_required_actions: tuple[str, ...] = ("redact_pii", "request_approval", "safe_rewrite")
    high_mnpi_external_actions: tuple[str, ...] = ("hold_until_public", "request_approval")
    public_mnpi_recommended_actions: tuple[str, ...] = ("cite_public_source", "proceed_with_warning")
    reviewer_override_roles: tuple[str, ...] = ("legal_reviewer", "compliance_admin")
    medium_risk_recommended_actions: tuple[str, ...] = ("proceed_with_warning",)
    low_risk_recommended_actions: tuple[str, ...] = ("proceed_with_warning",)


@dataclass(frozen=True)
class PolicyDecision:
    decision: PolicyDecisionName
    send_allowed: bool
    required_actions: tuple[str, ...] = ()
    recommended_actions: tuple[str, ...] = ()
    blocking_findings: tuple[str, ...] = ()
    policy_id: str = "default"
    policy_version: str = "2026-06-14"
    policy_reasons: tuple[str, ...] = ()
    review_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "send_allowed": self.send_allowed,
            "required_actions": list(self.required_actions),
            "recommended_actions": list(self.recommended_actions),
            "blocking_findings": list(self.blocking_findings),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_reasons": list(self.policy_reasons),
            "review_id": self.review_id,
        }


@dataclass
class _DecisionDraft:
    decision: PolicyDecisionName = "allow"
    required_actions: set[str] = field(default_factory=set)
    recommended_actions: set[str] = field(default_factory=set)
    blocking_findings: set[str] = field(default_factory=set)
    policy_reasons: set[str] = field(default_factory=set)

    def promote(self, decision: PolicyDecisionName) -> None:
        if _DECISION_RANK[decision] > _DECISION_RANK[self.decision]:
            self.decision = decision


class TenantPolicy:
    def __init__(self, profile: TenantPolicyProfile | None = None):
        self.profile = profile or DEFAULT_POLICY_PROFILE

    def evaluate(
        self,
        *,
        findings: list[Any],
        context: WorkflowContext | None = None,
        degraded_policy: str = "warn",
        degraded_modes: list[Any] | tuple[Any, ...] = (),
        review_id: str = "",
    ) -> PolicyDecision:
        context = context or WorkflowContext()
        draft = _DecisionDraft()

        if degraded_policy == "block_send" and degraded_modes:
            draft.promote("block")
            draft.required_actions.add(self.profile.degraded_block_action)
            draft.policy_reasons.add("degraded review coverage requires retry before send")
        if _is_cross_border_context(context):
            draft.promote("warn")
            draft.recommended_actions.update(self.profile.medium_risk_recommended_actions)
            draft.policy_reasons.add("cross-border destination context should be shown to the user")
        if _is_external_context(context, self.profile):
            draft.promote("warn")
            draft.recommended_actions.update(self.profile.medium_risk_recommended_actions)
            draft.policy_reasons.add("external recipient domain should be shown to the user")

        for finding in findings:
            self._evaluate_finding(finding, context, draft)

        if draft.decision == "allow" and findings and self.profile.warn_on_low_risk_findings:
            draft.promote("warn")
            draft.policy_reasons.add("review findings present but no blocking policy rule matched")

        return PolicyDecision(
            decision=draft.decision,
            send_allowed=draft.decision in {"allow", "warn"},
            required_actions=tuple(sorted(draft.required_actions)),
            recommended_actions=tuple(sorted(draft.recommended_actions)),
            blocking_findings=tuple(sorted(draft.blocking_findings)),
            policy_id=self.profile.policy_id,
            policy_version=self.profile.policy_version,
            policy_reasons=tuple(sorted(draft.policy_reasons)),
            review_id=review_id,
        )

    def _evaluate_finding(self, finding: Any, context: WorkflowContext, draft: _DecisionDraft) -> None:
        category = _finding_value(finding, "category").upper()
        severity = _finding_value(finding, "severity").lower()
        finding_id = _finding_value(finding, "id")

        if category == "MNPI" and severity == "high":
            if _has_public_evidence(finding):
                draft.promote("warn")
                draft.recommended_actions.update(self.profile.public_mnpi_recommended_actions)
                draft.policy_reasons.add("high-risk MNPI has public evidence but should remain visible")
            elif _has_reviewer_approval(finding):
                draft.promote("warn")
                draft.recommended_actions.update(self.profile.medium_risk_recommended_actions)
                draft.policy_reasons.add("high-risk MNPI has reviewer approval")
            else:
                draft.promote("block")
                draft.required_actions.update(self.profile.high_mnpi_external_actions)
                draft.policy_reasons.add("high-risk MNPI requires public evidence or reviewer approval before send")
                draft.blocking_findings.add(finding_id)
            return

        if category == "PII" and severity == "high":
            if _has_reviewer_approval(finding):
                draft.promote("warn")
                draft.recommended_actions.update(self.profile.medium_risk_recommended_actions)
                draft.policy_reasons.add("high-risk PII has reviewer approval")
            elif (
                context.requested_action == "request_approval"
                or context.actor_role in self.profile.reviewer_override_roles
            ):
                draft.promote("approval_required")
                draft.required_actions.add("request_approval")
                draft.blocking_findings.add(finding_id)
                draft.policy_reasons.add("high-risk PII requires reviewer approval before send")
            else:
                draft.promote("rewrite_required")
                draft.required_actions.update(self.profile.high_pii_required_actions)
                draft.blocking_findings.add(finding_id)
                draft.policy_reasons.add("high-risk PII requires safe rewrite or reviewer approval before send")
            return

        if severity in {"low", "medium"}:
            draft.promote("warn")
            if severity == "medium":
                draft.recommended_actions.update(self.profile.medium_risk_recommended_actions)
            else:
                draft.recommended_actions.update(self.profile.low_risk_recommended_actions)
            draft.policy_reasons.add(f"{severity}-risk finding should be shown to the user")


def evaluate_policy(
    *,
    findings: list[Any],
    context: WorkflowContext | None = None,
    profile: TenantPolicyProfile | None = None,
    degraded_policy: str = "warn",
    degraded_modes: list[Any] | tuple[Any, ...] = (),
    review_id: str = "",
) -> PolicyDecision:
    return TenantPolicy(profile).evaluate(
        findings=findings,
        context=context,
        degraded_policy=degraded_policy,
        degraded_modes=degraded_modes,
        review_id=review_id,
    )


def _finding_value(finding: Any, key: str) -> str:
    if isinstance(finding, dict):
        return str(finding.get(key, ""))
    return str(getattr(finding, key, ""))


def _finding_metadata(finding: Any) -> dict[str, Any]:
    if isinstance(finding, dict):
        metadata = finding.get("metadata", {})
    else:
        metadata = getattr(finding, "metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _has_public_evidence(finding: Any) -> bool:
    public_states = {"public", "public_source_matched", "public_source_match"}
    if _finding_value(finding, "source_verification").lower() in public_states:
        return True
    metadata = _finding_metadata(finding)
    for key in ("public_status", "materiality_reason", "source_verification"):
        if str(metadata.get(key, "")).lower() in public_states:
            return True
    return bool(metadata.get("public_evidence_confirmed"))


def _has_reviewer_approval(finding: Any) -> bool:
    approval_states = {"approve", "approved", "approval_granted", "policy_exception", "accept_risk"}
    if _finding_value(finding, "decision").lower() in approval_states:
        return True
    metadata = _finding_metadata(finding)
    if bool(metadata.get("reviewer_approved") or metadata.get("policy_exception_approved")):
        return True
    return str(metadata.get("approval_status", "")).lower() in approval_states


def _is_external_context(context: WorkflowContext, profile: TenantPolicyProfile) -> bool:
    if context.external_destination is not None:
        return context.external_destination
    if not context.recipient_domains or not profile.internal_domains:
        return False
    return any(not _matches_internal_domain(domain, profile.internal_domains) for domain in context.recipient_domains)


def _is_cross_border_context(context: WorkflowContext) -> bool:
    if not context.source_jurisdiction or not context.destination_jurisdiction:
        return False
    return context.source_jurisdiction.upper() != context.destination_jurisdiction.upper()


def _matches_internal_domain(domain: str, internal_domains: tuple[str, ...]) -> bool:
    normalized = domain.lower().rstrip(".")
    for internal in internal_domains:
        candidate = internal.lower().rstrip(".")
        if normalized == candidate or normalized.endswith(f".{candidate}"):
            return True
    return False


DEFAULT_POLICY_PROFILE = TenantPolicyProfile()
