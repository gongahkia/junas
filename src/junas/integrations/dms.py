"""Read-side DMS batch scanner substrate for iManage / NetDocuments exports.

The first supported shape is a neutral JSON manifest exported by the DMS layer.
This avoids writing back to customer systems until each pilot validates its own
API credentials, matter identifiers, and write-back approvals.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from junas.review.engine import PreSendReviewEngine


@dataclass(frozen=True)
class DmsDocument:
    dms: str
    matter_id: str
    document_id: str
    path: Path
    source_jurisdiction: str = "SG"
    destination_jurisdiction: str = "SG"
    document_type: str = "generic"


class DmsHookError(RuntimeError):
    """Base error for DMS hook transport failures."""


class DmsBackendTimeout(DmsHookError):
    """Raised when backend review times out."""


class DmsAuthError(DmsHookError):
    """Raised when backend auth fails."""


class DmsValidationError(DmsHookError):
    """Raised when hook metadata or backend request validation fails."""


class DmsBackendError(DmsHookError):
    """Raised when backend review fails without a more specific class."""


@dataclass(frozen=True)
class DmsCheckInRequest:
    dms: str
    matter_id: str
    document_id: str
    text: str
    actor_id: str
    source_jurisdiction: str = "SG"
    destination_jurisdiction: str = "SG"
    document_type: str = "dms_document"
    dms_version_id: str = ""
    external_destination: bool = False
    recipient_domains: tuple[str, ...] = ()
    attachment_count: int = 1
    sensitivity_label: str = ""
    idempotency_key: str = ""


@dataclass(frozen=True)
class DmsCheckInResult:
    status: str
    check_in_allowed: bool
    idempotency_key_hash: str
    audit_fields: dict[str, Any]
    duplicate: bool = False


class InMemoryDmsAuditRepository:
    def __init__(self) -> None:
        self._records: dict[str, DmsCheckInResult] = {}

    @property
    def count(self) -> int:
        return len(self._records)

    def get(self, idempotency_key_hash: str) -> DmsCheckInResult | None:
        return self._records.get(idempotency_key_hash)

    def record_once(self, result: DmsCheckInResult) -> DmsCheckInResult:
        prior = self._records.get(result.idempotency_key_hash)
        if prior is not None:
            return DmsCheckInResult(
                status=prior.status,
                check_in_allowed=prior.check_in_allowed,
                idempotency_key_hash=prior.idempotency_key_hash,
                audit_fields=dict(prior.audit_fields),
                duplicate=True,
            )
        self._records[result.idempotency_key_hash] = result
        return result


class HttpDmsReviewClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        bearer_token: str = "",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.timeout_seconds = timeout_seconds

    def review(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        review_request = request.Request(f"{self.base_url}/review", data=body, headers=headers, method="POST")
        try:
            with request.urlopen(review_request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise DmsBackendTimeout("backend timeout") from exc
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code in {401, 403}:
                raise DmsAuthError("backend auth failure") from exc
            if exc.code == 422:
                raise DmsValidationError("backend validation failure") from exc
            raise DmsBackendError(f"backend returned {exc.code}: {detail[:120]}") from exc
        except error.URLError as exc:
            reason = str(getattr(exc, "reason", "") or exc)
            if "timed out" in reason.lower():
                raise DmsBackendTimeout("backend timeout") from exc
            raise DmsBackendError("backend unavailable") from exc
        if not isinstance(decoded, dict):
            raise DmsBackendError("backend returned non-object response")
        return decoded


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_idempotency_key(req: DmsCheckInRequest) -> str:
    if req.idempotency_key:
        return req.idempotency_key
    parts = [
        req.dms,
        req.matter_id,
        req.document_id,
        req.dms_version_id,
        req.source_jurisdiction,
        req.destination_jurisdiction,
        req.document_type,
        _sha256_text(req.text),
    ]
    return "dms:" + _sha256_text("\x1f".join(parts))


def _validate_check_in_request(req: DmsCheckInRequest) -> None:
    if not req.dms.strip():
        raise DmsValidationError("dms is required")
    if not req.matter_id.strip():
        raise DmsValidationError("matter_id is required")
    if not req.document_id.strip():
        raise DmsValidationError("document_id is required")
    if not req.actor_id.strip():
        raise DmsValidationError("actor_id is required")
    if not req.text.strip():
        raise DmsValidationError("text is required")
    if req.attachment_count < 0:
        raise DmsValidationError("attachment_count must be non-negative")


def build_dms_review_payload(req: DmsCheckInRequest) -> dict[str, Any]:
    return {
        "text": req.text,
        "source_jurisdiction": req.source_jurisdiction,
        "destination_jurisdiction": req.destination_jurisdiction,
        "document_type": req.document_type,
        "surface": "dms",
        "workflow": "document_upload",
        "actor_role": "service_account",
        "matter_id": req.matter_id,
        "external_destination": req.external_destination,
        "recipient_domains": list(req.recipient_domains),
        "recipient_count": len(req.recipient_domains),
        "attachment_count": req.attachment_count,
        "sensitivity_label": req.sensitivity_label,
        "review_profile": "strict",
        "degraded_policy": "block_send",
        "include_suggestions": False,
    }


def _finding_rules(findings: Any) -> list[str]:
    if not isinstance(findings, list):
        return []
    rules = {
        str(finding.get("rule") or finding.get("rule_id") or "").strip()
        for finding in findings
        if isinstance(finding, dict)
    }
    return sorted(rule for rule in rules if rule)


def _degraded_modes(payload: dict[str, Any]) -> list[str]:
    modes = payload.get("degraded_modes")
    if not isinstance(modes, list):
        return []
    names: list[str] = []
    for item in modes:
        if isinstance(item, dict):
            mode = str(item.get("mode") or item.get("name") or "").strip()
        else:
            mode = str(item or "").strip()
        if mode:
            names.append(mode)
    return sorted(set(names))


def _policy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    policy = payload.get("policy_decision")
    return dict(policy) if isinstance(policy, dict) else {}


def map_dms_review_status(payload: dict[str, Any]) -> tuple[str, bool]:
    if _degraded_modes(payload):
        return "held_degraded", False
    policy = _policy_payload(payload)
    decision = str(policy.get("decision") or "").strip()
    send_allowed = bool(policy.get("send_allowed", payload.get("send_allowed", False)))
    if decision == "allow":
        return "allowed", True
    if decision == "warn":
        return "warned", send_allowed
    if decision == "approval_required":
        return "held_for_approval", False
    if decision == "rewrite_required":
        return "held_for_rewrite", False
    if decision == "block":
        return "blocked", False
    return "backend_failure", False


def _audit_from_review(
    req: DmsCheckInRequest,
    payload: dict[str, Any],
    *,
    idempotency_key_hash: str,
) -> dict[str, Any]:
    policy = _policy_payload(payload)
    findings = payload.get("findings")
    finding_count = len(findings) if isinstance(findings, list) else int(payload.get("finding_count", 0) or 0)
    return {
        "schema_version": "junas.dms.audit.v1",
        "dms": req.dms,
        "matter_id": req.matter_id,
        "matter_id_hash": _sha256_text(req.matter_id),
        "document_id": req.document_id,
        "document_id_hash": _sha256_text(req.document_id),
        "dms_version_id": req.dms_version_id,
        "actor_id_hash": _sha256_text(req.actor_id),
        "idempotency_key_hash": idempotency_key_hash,
        "text_hash": _sha256_text(req.text),
        "request_id": str(payload.get("request_id") or ""),
        "review_id": str(payload.get("review_id") or payload.get("request_id") or ""),
        "policy_decision": {
            "decision": str(policy.get("decision") or ""),
            "send_allowed": bool(policy.get("send_allowed", payload.get("send_allowed", False))),
            "required_actions": list(policy.get("required_actions") or []),
            "recommended_actions": list(policy.get("recommended_actions") or []),
        },
        "policy_id": str(policy.get("policy_id") or ""),
        "policy_version": str(policy.get("policy_version") or ""),
        "review_expires_at": str(payload.get("review_expires_at") or ""),
        "degraded_modes": _degraded_modes(payload),
        "overall_risk": str(payload.get("overall_risk") or ""),
        "pii_score": float(payload.get("pii_score", 0.0) or 0.0),
        "mnpi_score": float(payload.get("mnpi_score", 0.0) or 0.0),
        "finding_count": finding_count,
        "finding_rules": _finding_rules(findings),
    }


def _audit_from_failure(
    req: DmsCheckInRequest,
    *,
    idempotency_key_hash: str,
    status: str,
    error_type: str,
) -> dict[str, Any]:
    return {
        "schema_version": "junas.dms.audit.v1",
        "dms": req.dms,
        "matter_id": req.matter_id,
        "matter_id_hash": _sha256_text(req.matter_id),
        "document_id": req.document_id,
        "document_id_hash": _sha256_text(req.document_id),
        "dms_version_id": req.dms_version_id,
        "actor_id_hash": _sha256_text(req.actor_id),
        "idempotency_key_hash": idempotency_key_hash,
        "text_hash": _sha256_text(req.text),
        "policy_decision": {
            "decision": status,
            "send_allowed": False,
            "required_actions": [],
            "recommended_actions": [],
        },
        "failure_mode": status,
        "error_type": error_type,
        "degraded_modes": [],
        "finding_count": 0,
        "finding_rules": [],
    }


class MockDmsCheckInHook:
    """Concrete v1 DMS mock hook for pre-commit/check-in review."""

    def __init__(self, review_client: Any, repository: InMemoryDmsAuditRepository | None = None) -> None:
        self.review_client = review_client
        self.repository = repository or InMemoryDmsAuditRepository()

    def check_in(self, req: DmsCheckInRequest) -> DmsCheckInResult:
        raw_key = _stable_idempotency_key(req)
        key_hash = _sha256_text(raw_key)
        prior = self.repository.get(key_hash)
        if prior is not None:
            return DmsCheckInResult(
                status=prior.status,
                check_in_allowed=prior.check_in_allowed,
                idempotency_key_hash=prior.idempotency_key_hash,
                audit_fields=dict(prior.audit_fields),
                duplicate=True,
            )
        try:
            _validate_check_in_request(req)
            payload = build_dms_review_payload(req)
            review = self.review_client.review(payload, idempotency_key=raw_key)
            status, allowed = map_dms_review_status(review)
            audit_fields = _audit_from_review(req, review, idempotency_key_hash=key_hash)
        except DmsValidationError:
            status, allowed = "validation_failed", False
            audit_fields = _audit_from_failure(
                req,
                idempotency_key_hash=key_hash,
                status=status,
                error_type="validation_failure",
            )
        except DmsAuthError:
            status, allowed = "auth_failed", False
            audit_fields = _audit_from_failure(
                req,
                idempotency_key_hash=key_hash,
                status=status,
                error_type="auth_failure",
            )
        except DmsBackendTimeout:
            status, allowed = "backend_timeout", False
            audit_fields = _audit_from_failure(
                req,
                idempotency_key_hash=key_hash,
                status=status,
                error_type="timeout",
            )
        except DmsHookError:
            status, allowed = "backend_failure", False
            audit_fields = _audit_from_failure(
                req,
                idempotency_key_hash=key_hash,
                status=status,
                error_type="backend_failure",
            )
        result = DmsCheckInResult(
            status=status,
            check_in_allowed=allowed,
            idempotency_key_hash=key_hash,
            audit_fields=audit_fields,
        )
        return self.repository.record_once(result)


def load_manifest(path: Path) -> list[DmsDocument]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_documents = payload.get("documents", payload if isinstance(payload, list) else [])
    if not isinstance(raw_documents, list):
        raise ValueError("DMS manifest must be a list or an object with documents=[]")
    base = path.parent
    documents: list[DmsDocument] = []
    for item in raw_documents:
        if not isinstance(item, dict):
            raise ValueError("DMS manifest entries must be objects")
        document_path = Path(str(item.get("path") or ""))
        if not document_path.is_absolute():
            document_path = base / document_path
        documents.append(
            DmsDocument(
                dms=str(item.get("dms") or payload.get("dms") or "unknown"),
                matter_id=str(item.get("matter_id") or payload.get("matter_id") or ""),
                document_id=str(item.get("document_id") or document_path.stem),
                path=document_path,
                source_jurisdiction=str(item.get("source_jurisdiction") or "SG"),
                destination_jurisdiction=str(item.get("destination_jurisdiction") or "SG"),
                document_type=str(item.get("document_type") or "generic"),
            )
        )
    return documents


def scan_manifest(path: Path, *, review_profile: str = "strict") -> dict[str, Any]:
    engine = PreSendReviewEngine()
    results: list[dict[str, Any]] = []
    for document in load_manifest(path):
        text = document.path.read_text(encoding="utf-8")
        review = engine.review(
            text=text,
            source_jurisdiction=document.source_jurisdiction,
            destination_jurisdiction=document.destination_jurisdiction,
            entity_id=None,
            include_suggestions=False,
            document_type=document.document_type,
            matter_id=document.matter_id or None,
            review_profile=review_profile,
        )
        results.append(
            {
                "dms": document.dms,
                "matter_id": document.matter_id,
                "document_id": document.document_id,
                "path": str(document.path),
                "findings": len(review.findings),
                "pii_score": review.pii_score,
                "mnpi_score": review.mnpi_score,
                "degraded_modes": review.degraded_modes,
                "rules": sorted({finding.rule for finding in review.findings}),
            }
        )
    return {"documents": results, "count": len(results), "review_profile": review_profile}
