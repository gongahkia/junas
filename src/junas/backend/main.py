import argparse
import base64
import bisect
import hashlib
import hmac
import importlib
import json
import logging
import os
import re
import secrets
import sys
import time
import uuid
from _thread import LockType
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock, Thread
from typing import Any, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

import junas.anonymize.mapping_store as mapping_store_mod
from junas.anonymize import (
    DeterministicAnonymizer,
    MappingStoreError,
)
from junas.anonymize import (
    compute_document_hash as _compute_document_hash,
)
from junas.anonymize import (
    load_mapping as _load_persisted_mapping,
)
from junas.anonymize import (
    reidentify as _reidentify_text,
)
from junas.anonymize import (
    save_mapping as _save_persisted_mapping,
)
from junas.backend.auth import (
    AUDIT_ROLES,
    DECISION_ROLES,
    DISABLED_TENANT_CONTEXT,
    REVIEW_ROLES,
    AuthFailure,
    TenantContext,
    require_roles,
    resolve_tenant_context,
)
from junas.backend.cache import ResponseCache
from junas.backend.local_auth import (
    LOCAL_TOKEN_HEADER,
    LocalDaemonAuthError,
    local_pairing_code_digest,
    origin_allowed,
    resolve_local_daemon_token,
    sign_local_client_token,
    verify_local_client_token,
)
from junas.backend.observability import DependencyStatus, ObservabilityManager, get_metrics_mode
from junas.backend.schemas import (
    AnonymizationMappingEntryResponse,
    AnonymizationReplacementResponse,
    AnonymizeRequest,
    AnonymizeResponse,
    BatchClassifyRequest,
    BatchClassifyResponse,
    CitePublicSourceRequest,
    CitePublicSourceResponse,
    Classification,
    ClassifyRequest,
    ClassifyResponse,
    DependencyStatusResponse,
    DiagnosticsResponse,
    DocumentScrubActionResponse,
    DocumentScrubRequest,
    DocumentScrubResponse,
    HealthResponse,
    HoldUntilPublicReasonResponse,
    HoldUntilPublicRequest,
    HoldUntilPublicResponse,
    LLMAdjudicationResponse,
    LocalPairingApproveResponse,
    LocalPairingClaimResponse,
    LocalPairingCodeRequest,
    LocalPairingStartRequest,
    LocalPairingStartResponse,
    ObservabilityResponse,
    OpaqueRedactionResponse,
    PlaceholderReplacementResponse,
    PolicyDecisionResponse,
    PrivacyLedgerEntryResponse,
    PseudonymizeRequest,
    PseudonymizeResponse,
    PublicEvidenceResponse,
    PublicSourceCitationResponse,
    ReadyResponse,
    RedactPiiRequest,
    RedactPiiResponse,
    RedactRequest,
    RedactResponse,
    ReidentifyRequest,
    ReidentifyResponse,
    RequestApprovalRequest,
    RequestApprovalResponse,
    ReviewApprovalRequestState,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewDocumentMetadataResponse,
    ReviewFindingResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewSessionFindingState,
    ReviewSessionStateResponse,
    ReviewSuggestionResponse,
    SafeRewriteReplacementResponse,
    SafeRewriteRequest,
    SafeRewriteResponse,
    SafeRewriteSkippedFindingResponse,
)
from junas.backend.siem import emit_privacy_ledger_events, emit_security_event
from junas.configs.runtime import RuntimeSettings, get_runtime_settings
from junas.external.privacy_guard import PrivacyGuard
from junas.helper.determinism import configure_determinism
from junas.policy import ACTION_CATALOG, DEFAULT_POLICY_PROFILE, WorkflowContext, evaluate_policy
from junas.review.decisions import (
    Decision,
    ReviewSessionError,
    get_session_state,
    record_approval_request,
    record_decision,
    start_review_session,
)
from junas.review.document import extract_review_document
from junas.review.engine import PreSendReviewEngine, ReviewLayerError
from junas.review.image_scan import (
    ImageScanError,
    append_ocr_text_blocks,
    build_image_scanner,
    health_check_image_scan,
    image_locator_for_span,
    image_ocr_metadata_for_span,
    redacted_document_artifact,
    redacted_image_artifacts,
    scan_image_candidates,
)
from junas.review.metadata import scrub_document
from junas.review.subject_index import SubjectIndexError, index_review_findings, require_subject_index_key

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("junas.backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

_state: dict[str, Any] = {}
_demo_rate_limit_lock = Lock()

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}
LANE_SUPPRESSED_VIEW_ROLES = frozenset({"auditor", "admin"})
APPROVAL_REVIEWER_ROLE_ORDER = ("maker", "checker", "admin")

SUPPRESSED_REQUEST_LOG_PATHS = {"/health", "/ready", "/metrics"}
SPAN_CONTEXT_CHARS = 48
LOCAL_PAIRING_TTL_SECONDS = 300
LOCAL_CLIENT_TOKEN_TTL_SECONDS = 90 * 24 * 60 * 60
REVIEW_DECISION_VALIDITY_SECONDS = 5 * 60
LOCAL_DAEMON_PROTECTED_PATHS = {
    "/anonymize",
    "/classify",
    "/classify/batch",
    "/cite-public-source",
    "/documents/scrub",
    "/hold-until-public",
    "/pseudonymize",
    "/redact",
    "/redact-pii",
    "/reidentify",
    "/request-approval",
    "/review",
    "/safe-rewrite",
}
LOCAL_DAEMON_PROTECTED_PREFIXES = ("/review/",)
PUBLIC_DEMO_BODY_MAX_BYTES = 8 * 1024
PUBLIC_DEMO_TEXT_MAX_CHARS = 4000
PUBLIC_DEMO_RATE_LIMIT_REQUESTS = 30
PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS = 60
OPENAPI_TAGS = [
    {
        "name": "Runtime",
        "description": "Health, readiness, diagnostics, and metrics endpoints for the active backend runtime.",
    },
    {
        "name": "Classification",
        "description": "Document classification endpoints for single-request and batch MNPI screening.",
    },
    {
        "name": "Anonymization",
        "description": "Pre-send document review and deterministic local anonymization endpoints.",
    },
    {
        "name": "Documents",
        "description": "Document metadata inspection and scrubbing endpoints.",
    },
]
OPENAPI_DESCRIPTION = """
Junas is an API-first pre-send safety engine for PII anonymization and MNPI review.

Key behaviors:

- `POST /pseudonymize` extracts inline text or text/DOCX/PDF payloads, runs the
  PII/MNPI review stack, and returns deterministic placeholders plus a local
  mapping table for reversible downstream analysis.
- `POST /anonymize` returns irreversible placeholder-only output with no mapping.
- `POST /redact` returns irreversible opaque markers and no original matched text
  in redaction findings.
- `POST /redact-pii` returns deterministic PII-only replacements while leaving
  MNPI passages visible and flagged in findings.
- `POST /hold-until-public` returns deterministic high-severity MNPI hold text
  with display-safe and audit-ready reasons.
- `POST /cite-public-source` returns audit-grade public-source citations with
  source URL, retrieval timestamp, and privacy-ledger evidence.
- `POST /request-approval` records a pending approval request in the review
  journal and returns reviewer-role requirements.
- `POST /safe-rewrite` returns deterministic policy-approved span replacements
  without calling an LLM or persisting a reidentification mapping.
- `POST /review` runs the same evidence-first pre-send review without rewriting
  the document, returning localized findings, remediation suggestions,
  jurisdiction coverage, and separate PII/MNPI scores.
- `POST /classify` is a compatibility shim over the deterministic review engine
  and returns a document-level `SAFE`, `LOW_RISK`, or `HIGH_RISK` label plus
  review findings.
- `POST /classify/batch` processes up to 32 classify requests with bounded
  in-process concurrency while preserving result order.
- `include_offending_spans` is retained for older clients; the active response
  surface is the deterministic findings list.
- Chain-of-evidence is exposed through findings, suggestions, public-source
  summaries, and privacy-ledger entries. Raw chain-of-thought is not exposed.
- `POST /documents/scrub` removes supported DOCX/PDF/image metadata leakage before
  sharing a file outside the tenant boundary.
- `GET /ready` and `GET /diagnostics` expose degraded startup, lazy-layer warming, and dependency state.
""".strip()
PUBLIC_DEMO_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Junas deterministic demo</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f7f7f2; color: #161a1d; }
    main { max-width: 1120px; margin: 0 auto; padding: 28px; }
    textarea { width: 100%; min-height: 180px; font: 14px ui-monospace, monospace; }
    select, button { font: inherit; padding: 8px; }
    button { cursor: pointer; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
    .panel { border: 1px solid #d8d8d0; background: #fff; padding: 14px; border-radius: 6px; }
    .finding { border-top: 1px solid #e5e5dc; padding-top: 10px; margin-top: 10px; }
    .muted { color: #586069; }
    .risk { font-weight: 700; }
    @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>Junas deterministic demo</h1>
  <p class="muted">Strict-profile demo. No LLM, no public evidence, no persistence. Use synthetic text only.</p>
  <div class="row">
    <button type="button" data-example="pii">SG NRIC prompt</button>
    <button type="button" data-example="mnpi">M&amp;A MNPI email</button>
    <button type="button" data-example="clean">Clean internal note</button>
  </div>
  <div class="grid">
    <section class="panel">
      <label for="text">Text</label>
      <textarea id="text"></textarea>
      <div class="row">
        <label>Source <select id="source"></select></label>
        <label>Destination <select id="destination"></select></label>
        <label>Profile <select id="profile"><option value="strict">strict deterministic</option></select></label>
        <button id="review" type="button">Review</button>
      </div>
      <p class="muted">Requests are capped and rate-limited. Do not submit confidential or personal data.</p>
    </section>
    <section class="panel" id="result">
      <p class="muted">Run a review to see policy decision, required actions, findings, and citations.</p>
    </section>
  </div>
</main>
<script>
const jurisdictions = ["SG","US","UK","EU","HK","AU","JP","KR","MY","ID","TH","PH","VN","IN","CN","AE","SA"];
const examples = {
  pii: "Before using this GenAI prompt, remove Dr Jane Tan S1234567D from the draft client update.",
  mnpi: "Project Raven will acquire GlobalTech for USD 2.5 billion before announcement. Hold until public disclosure.",
  clean: "Internal lunch menu draft for the Singapore office. Share the vegetarian options with the team."
};
const text = document.getElementById("text");
const result = document.getElementById("result");
for (const id of ["source", "destination"]) {
  const select = document.getElementById(id);
  for (const code of jurisdictions) {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = code;
    select.appendChild(option);
  }
}
document.getElementById("destination").value = "US";
text.value = examples.pii;
document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => { text.value = examples[button.dataset.example]; });
});
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}
function render(payload) {
  const policy = payload.policy_decision || {};
  const findings = payload.findings || [];
  result.innerHTML = `
    <p class="risk">${escapeHtml(policy.decision)} · send_allowed: ${escapeHtml(payload.send_allowed)}</p>
    <p>PII ${escapeHtml(payload.pii_score)} · MNPI ${escapeHtml(payload.mnpi_score)}
      · ${escapeHtml(payload.overall_risk)}</p>
    <p>Required actions: ${escapeHtml((policy.required_actions || []).join(", ") || "none")}</p>
    ${findings.map((finding) => `
      <div class="finding">
        <strong>${escapeHtml(finding.category)}:${escapeHtml(finding.rule)}</strong>
        <p>${escapeHtml(finding.severity)} · ${escapeHtml(finding.legal_basis)}</p>
        <p>${escapeHtml(finding.reason)}</p>
      </div>
    `).join("") || "<p>No findings.</p>"}
  `;
}
document.getElementById("review").addEventListener("click", async () => {
  result.innerHTML = '<p class="muted">Reviewing...</p>';
  const response = await fetch("/demo/review", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      text: text.value,
      source_jurisdiction: document.getElementById("source").value,
      destination_jurisdiction: document.getElementById("destination").value,
      review_profile: "strict"
    })
  });
  const payload = await response.json();
  if (!response.ok) {
    result.innerHTML = `<p class="risk">Error ${response.status}</p>
      <p>${escapeHtml(payload.detail || "review failed")}</p>`;
    return;
  }
  render(payload);
});
</script>
</body>
</html>
""".strip()


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


def _public_demo_enabled() -> bool:
    return _is_truthy(os.environ.get("JUNAS_PUBLIC_DEMO_ENABLED"), default=False)


def _public_demo_limits() -> tuple[int, int, int, int]:
    return (
        _int_env("JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES", PUBLIC_DEMO_BODY_MAX_BYTES, minimum=512, maximum=64 * 1024),
        _int_env("JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS", PUBLIC_DEMO_TEXT_MAX_CHARS, minimum=100, maximum=16000),
        _int_env("JUNAS_PUBLIC_DEMO_RATE_LIMIT", PUBLIC_DEMO_RATE_LIMIT_REQUESTS, minimum=1, maximum=300),
        _int_env(
            "JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS",
            PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS,
            minimum=1,
            maximum=3600,
        ),
    )


def _runtime_cli_overrides() -> dict[str, Any]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--config", type=str)
    parser.add_argument("--layers", type=str)
    args, _ = parser.parse_known_args()

    overrides: dict[str, Any] = {}
    if args.config:
        overrides["config_path"] = args.config
    if args.layers:
        overrides["pipeline.layers"] = [layer.strip() for layer in args.layers.split(",") if layer.strip()]
    return overrides


def resolve_runtime_settings() -> RuntimeSettings:
    return get_runtime_settings(_runtime_cli_overrides())


def current_runtime_settings() -> RuntimeSettings:
    settings = _state.get("settings")
    if isinstance(settings, RuntimeSettings):
        return settings
    return resolve_runtime_settings()


def should_pretty_logs() -> bool:
    return current_runtime_settings().startup.pretty_logs


def render_backend_log(payload: dict[str, Any]) -> str:
    dump_kwargs: dict[str, Any] = {"ensure_ascii": False}
    if should_pretty_logs():
        dump_kwargs["indent"] = 2
    return json.dumps(payload, **dump_kwargs)


def log_backend_event(level: int, **payload: Any) -> None:
    logger.log(level, render_backend_log(payload))


class PrettyJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        ).encode("utf-8")


def get_optional_layers() -> set[str]:
    return set(current_runtime_settings().pipeline.optional_layers)


def get_allowed_origins() -> list[str]:
    settings = current_runtime_settings()
    origins = list(settings.api.allowed_origins) or ["http://localhost", "http://127.0.0.1"]
    if settings.local_daemon.acl_enabled:
        origins.extend(origin for origin in settings.local_daemon.allowed_origins if "*" not in origin)

    # Keep Origin: null allowed for local desktop wrappers and manual file:// clients.
    if "null" not in origins:
        origins.append("null")

    return list(dict.fromkeys(origins))


def get_allowed_origin_regex() -> str:
    # Allow localhost origins on any port for local clients and development servers.
    patterns = [r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"]
    settings = current_runtime_settings()
    if settings.local_daemon.acl_enabled:
        for origin in settings.local_daemon.allowed_origins:
            if "*" in origin:
                patterns.append("^" + re.escape(origin).replace(r"\*", ".*") + "$")
    return "|".join(f"(?:{pattern})" for pattern in patterns)


def _local_daemon_protected_path(path: str) -> bool:
    return path in LOCAL_DAEMON_PROTECTED_PATHS or any(
        path.startswith(prefix) for prefix in LOCAL_DAEMON_PROTECTED_PREFIXES
    )


def _local_daemon_token() -> str:
    cached = _state.get("local_daemon_token")
    if isinstance(cached, str) and cached:
        return cached
    token = resolve_local_daemon_token(current_runtime_settings().local_daemon)
    if token:
        _state["local_daemon_token"] = token
    return token


def _local_daemon_token_valid(supplied: str, expected: str) -> bool:
    if hmac.compare_digest(supplied, expected):
        return True
    return verify_local_client_token(expected, supplied)


def _pending_pairings() -> dict[str, dict[str, Any]]:
    store = _state.setdefault("local_pairing_requests", {})
    if not isinstance(store, dict):
        store = {}
        _state["local_pairing_requests"] = store
    now = int(time.time())
    for key, value in list(store.items()):
        if not isinstance(value, dict) or int(value.get("expires_at", 0)) <= now:
            store.pop(key, None)
    return store


def _require_access(
    request: Request,
    allowed_roles: frozenset[str],
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> TenantContext:
    settings = current_runtime_settings()
    request_id = getattr(request.state, "request_id", None)
    try:
        context = resolve_tenant_context(
            settings=settings,
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            x_api_key=x_api_key,
            authorization=authorization,
        )
        require_roles(
            context,
            allowed_roles,
            settings=settings,
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
    except AuthFailure as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    request.state.tenant_context = context
    return context


def require_review_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> TenantContext:
    return _require_access(request, REVIEW_ROLES, x_api_key=x_api_key, authorization=authorization)


def require_decision_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> TenantContext:
    return _require_access(request, DECISION_ROLES, x_api_key=x_api_key, authorization=authorization)


def require_audit_access(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> TenantContext:
    return _require_access(request, AUDIT_ROLES, x_api_key=x_api_key, authorization=authorization)


def tenant_context_from_request(request: Request) -> TenantContext:
    context = getattr(request.state, "tenant_context", None)
    return context if isinstance(context, TenantContext) else DISABLED_TENANT_CONTEXT


def _public_demo_client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _enforce_public_demo_rate_limit(request: Request) -> None:
    _, _, limit, window_seconds = _public_demo_limits()
    key = _public_demo_client_key(request)
    now = time.monotonic()
    cutoff = now - float(window_seconds)
    with _demo_rate_limit_lock:
        buckets = _state.setdefault("public_demo_rate_limit", {})
        if not isinstance(buckets, dict):
            buckets = {}
            _state["public_demo_rate_limit"] = buckets
        history = [stamp for stamp in buckets.get(key, []) if float(stamp) >= cutoff]
        if len(history) >= limit:
            raise HTTPException(status_code=429, detail="public demo rate limit exceeded")
        history.append(now)
        buckets[key] = history


def _public_demo_review_request(raw_body: bytes) -> ReviewRequest:
    body_cap, text_cap, _, _ = _public_demo_limits()
    if len(raw_body) > body_cap:
        raise HTTPException(status_code=413, detail="public demo request body too large")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="public demo expects JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="public demo expects a JSON object")
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=422, detail="public demo text is required")
    if len(text) > text_cap:
        raise HTTPException(status_code=413, detail="public demo text is too large")

    try:
        return ReviewRequest.model_validate(
            {
                "text": text,
                "source_jurisdiction": str(payload.get("source_jurisdiction") or "SG"),
                "destination_jurisdiction": str(payload.get("destination_jurisdiction") or "US"),
                "document_type": "genai_prompt",
                "surface": "api",
                "workflow": "api_review",
                "requested_action": "send",
                "external_destination": True,
                "include_suggestions": True,
                "review_profile": "strict",
                "degraded_policy": "block_send",
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail="public demo request validation failed") from exc


def _can_view_lane_suppressed(tenant: TenantContext) -> bool:
    return (not tenant.enabled) or bool(tenant.roles & LANE_SUPPRESSED_VIEW_ROLES)


def load_config() -> list[str]:
    return list(current_runtime_settings().pipeline.layers)


def get_response_cache_settings() -> dict[str, float | int]:
    cache_settings = current_runtime_settings().response_cache
    return {"size": cache_settings.size, "ttl_seconds": cache_settings.ttl_seconds}


def get_observability() -> ObservabilityManager | None:
    observability = _state.get("observability")
    if isinstance(observability, ObservabilityManager):
        return observability
    return None


def _get_latest_load_error(layer: str) -> dict[str, Any] | None:
    for item in reversed(_state.get("load_errors", [])):
        if item.get("layer") == layer:
            return item
    return None


def record_layer_load_error(layer: str, error: Exception | str, phase: str) -> None:
    message = str(error)
    _state.setdefault("load_errors", []).append(
        {
            "layer": layer,
            "phase": phase,
            "error": message,
        }
    )


def record_runtime_layer_error(layer: str, message: str) -> None:
    lock: Lock | None = _state.get("runtime_error_lock")
    if lock is None:
        runtime_errors = _state.setdefault("runtime_layer_errors", {})
        entry = runtime_errors.setdefault(
            layer,
            {
                "count": 0,
                "last_seen": None,
                "last_message": "",
            },
        )
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry["last_message"] = message
        return

    with lock:
        runtime_errors = _state.setdefault("runtime_layer_errors", {})
        entry = runtime_errors.setdefault(
            layer,
            {
                "count": 0,
                "last_seen": None,
                "last_message": "",
            },
        )
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry["last_message"] = message


def build_ready_snapshot() -> dict[str, Any]:
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    lazy_loaders = _state.get("lazy_loaders", {})
    optional_layers = set(_state.get("optional_layers", []))
    required_layers = [layer for layer in pipeline if layer not in optional_layers]
    warming_layers = [layer for layer in _get_warming_required_layers() if layer in required_layers]

    available_layers = set(models.keys()) | set(lazy_loaders.keys())
    missing_layers = sorted([layer for layer in required_layers if layer not in available_layers])
    reasons: list[str] = []
    if missing_layers:
        reasons.append(f"missing required layers: {', '.join(missing_layers)}")
    if warming_layers:
        reasons.append(f"warming required layers: {', '.join(warming_layers)}")
    dependency_status = get_dependency_status()
    image_status = dependency_status.get("image_scan")
    image_scan_ready = True
    if image_status is not None and image_status.configured and image_status.healthy is False:
        image_scan_ready = False
        reasons.append(f"image_scan unavailable: {image_status.detail}")
    helper_ready = True
    for helper_name in ("llm_defined_term_extractor", "llm_coverage_auditor"):
        status = dependency_status.get(helper_name)
        if status is not None and status.configured and status.healthy is False:
            helper_ready = False
            reasons.append(f"{helper_name} unavailable: {status.detail}")

    return {
        "pipeline": pipeline,
        "required_layers": required_layers,
        "warming_layers": warming_layers,
        "missing_layers": missing_layers,
        "ready": len(missing_layers) == 0 and len(warming_layers) == 0 and image_scan_ready and helper_ready,
        "reasons": reasons,
    }


def get_dependency_status() -> dict[str, DependencyStatus]:
    models = _state.get("models", {})
    lazy_loaders = _state.get("lazy_loaders", {})
    settings = current_runtime_settings()
    statuses: dict[str, DependencyStatus] = {}

    def _status_from_health(health: dict[str, Any], *, configured_default: bool) -> DependencyStatus:
        return DependencyStatus(
            status=str(health.get("status", "unknown")),
            configured=bool(health.get("configured", configured_default)),
            healthy=health.get("healthy"),
            detail=str(health.get("detail", "")),
        )

    if settings.public_evidence.enabled:
        loaded = "public_evidence" in models or "public_evidence" in lazy_loaders
        statuses["public_evidence"] = DependencyStatus(
            status="unknown" if loaded else "configured",
            configured=True,
            healthy=None,
            detail=f"provider={settings.public_evidence.provider}",
        )
    else:
        statuses["public_evidence"] = DependencyStatus(
            status="disabled",
            configured=False,
            healthy=None,
            detail="public evidence retrieval is disabled",
        )

    llm_adjudicator = models.get("llm_adjudicator")
    if llm_adjudicator is not None and hasattr(llm_adjudicator, "health"):
        statuses["llm_adjudicator"] = _status_from_health(
            llm_adjudicator.health(),
            configured_default=settings.llm.enabled,
        )
    elif settings.llm.enabled:
        try:
            from junas.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

            statuses["llm_adjudicator"] = _status_from_health(
                LocalLLMAdjudicator(settings.llm).health(),
                configured_default=True,
            )
        except Exception as exc:
            statuses["llm_adjudicator"] = DependencyStatus(
                status="down",
                configured=True,
                healthy=False,
                detail=f"LLM adjudicator status check failed: {exc}",
            )
    else:
        statuses["llm_adjudicator"] = DependencyStatus(
            status="disabled",
            configured=False,
            healthy=None,
            detail="LLM adjudication is disabled",
        )
    for helper_name, enabled in (
        ("llm_defined_term_extractor", settings.llm_helpers.defined_terms_enabled),
        ("llm_coverage_auditor", settings.llm_helpers.coverage_audit_enabled),
    ):
        helper = models.get(helper_name)
        if helper is not None and hasattr(helper, "health"):
            statuses[helper_name] = _status_from_health(helper.health(), configured_default=enabled)
        elif enabled:
            try:
                from junas.advisory.llm_adjudicator.helpers import (
                    build_llm_coverage_auditor,
                    build_llm_defined_term_extractor,
                )

                helper = (
                    build_llm_defined_term_extractor(settings.llm)
                    if helper_name == "llm_defined_term_extractor"
                    else build_llm_coverage_auditor(settings.llm)
                )
                health = helper.health()
                statuses[helper_name] = DependencyStatus(
                    status=str(health.get("status", "unknown")),
                    configured=True,
                    healthy=health.get("healthy"),
                    detail=(
                        "requires llm.enabled=true"
                        if not settings.llm.enabled
                        else str(health.get("detail", ""))
                    ),
                )
            except Exception as exc:
                statuses[helper_name] = DependencyStatus(
                    status="down",
                    configured=True,
                    healthy=False,
                    detail=f"LLM helper status check failed: {exc}",
                )
        else:
            statuses[helper_name] = DependencyStatus(
                status="disabled",
                configured=False,
                healthy=None,
                detail=f"{helper_name} is disabled",
            )
    image_scan_status = health_check_image_scan(settings.image_scan)
    statuses["image_scan"] = DependencyStatus(
        status=str(image_scan_status["status"]),
        configured=bool(image_scan_status["configured"]),
        healthy=image_scan_status["healthy"],
        detail=str(image_scan_status["detail"]),
    )
    return statuses


def refresh_observability_state() -> None:
    observability = get_observability()
    if observability is None:
        return

    ready_state = build_ready_snapshot()
    required_layers = ready_state["required_layers"]
    warming_layers = set(ready_state["warming_layers"])
    available_layers = set(_state.get("models", {}).keys()) | set(_state.get("lazy_loaders", {}).keys())
    for layer in required_layers:
        observability.set_required_layer_state(
            layer=layer,
            configured=True,
            available=layer in available_layers,
            warming=layer in warming_layers,
        )

    for dependency, status in get_dependency_status().items():
        observability.set_dependency_state(
            dependency=dependency,
            configured=status.configured,
            healthy=status.healthy,
        )


def _set_warming_required_layers(layers: list[str]) -> None:
    lock: Lock | None = _state.get("warming_lock")
    normalized = sorted(dict.fromkeys(layers))
    if lock is None:
        _state["warming_required_layers"] = normalized
        refresh_observability_state()
        return
    with lock:
        _state["warming_required_layers"] = normalized
    refresh_observability_state()


def _get_warming_required_layers() -> list[str]:
    lock: Lock | None = _state.get("warming_lock")
    if lock is None:
        return list(_state.get("warming_required_layers", []))
    with lock:
        return list(_state.get("warming_required_layers", []))


def _mark_required_layer_warmed(layer: str) -> None:
    lock: Lock | None = _state.get("warming_lock")
    if lock is None:
        current = [name for name in _state.get("warming_required_layers", []) if name != layer]
        _state["warming_required_layers"] = current
        refresh_observability_state()
        return
    with lock:
        current = [name for name in _state.get("warming_required_layers", []) if name != layer]
        _state["warming_required_layers"] = current
    refresh_observability_state()


def start_required_layer_prewarm(optional_layers: set[str]) -> None:
    warming_layers = [
        layer for layer in sorted(_state.get("lazy_loaders", {}).keys())
        if layer not in optional_layers
    ]
    if not warming_layers:
        _set_warming_required_layers([])
        return

    _set_warming_required_layers(warming_layers)

    def _runner() -> None:
        for layer in warming_layers:
            try:
                ensure_layer_loaded(layer)
            finally:
                _mark_required_layer_warmed(layer)

    thread = Thread(target=_runner, name="junas-prewarm", daemon=True)
    _state["prewarm_thread"] = thread
    thread.start()


def build_response_cache_key(req: ClassifyRequest, pipeline: list[str]) -> str:
    payload = {
        "text": req.text,
        "entity_id": req.entity_id or "",
        "include_offending_spans": req.include_offending_spans,
        "pipeline": pipeline,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest


def response_cache_get(key: str) -> dict[str, Any] | None:
    store = _state.get("response_cache_store")
    if isinstance(store, ResponseCache):
        return store.get(key)

    cache = _state.get("response_cache")
    lock = _state.get("response_cache_lock")
    cfg = _state.get("cache_cfg", {})
    if cache is None or lock is None:
        return None

    ttl_seconds = float(cfg.get("ttl_seconds", 0.0))
    now = time.monotonic()
    with lock:
        entry = cache.get(key)
        if entry is None:
            return None
        if ttl_seconds > 0 and now - float(entry.get("ts", 0.0)) > ttl_seconds:
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        payload = entry.get("payload")
        if isinstance(payload, dict):
            return dict(payload)
    return None


def response_cache_set(key: str, payload: dict[str, Any]) -> None:
    store = _state.get("response_cache_store")
    if isinstance(store, ResponseCache):
        store.set(key, payload)
        return

    cache = _state.get("response_cache")
    lock = _state.get("response_cache_lock")
    cfg = _state.get("cache_cfg", {})
    if cache is None or lock is None:
        return

    size = int(cfg.get("size", 0))
    if size <= 0:
        return

    with lock:
        cache[key] = {"ts": time.monotonic(), "payload": payload}
        cache.move_to_end(key)
        while len(cache) > size:
            cache.popitem(last=False)


def should_cache_response(req: ClassifyRequest, pipeline: list[str]) -> bool:
    cfg = _state.get("cache_cfg", {})
    if int(cfg.get("size", 0)) <= 0:
        return False
    if float(cfg.get("ttl_seconds", 0.0)) <= 0:
        return False
    if req.debug:
        return False
    if req.entity_id:
        return False
    # Public retrieval and local adjudication depend on current external/local service state.
    if "public_evidence" in pipeline or "llm_adjudicator" in pipeline:
        return False
    return True


def ensure_layer_loaded(layer: str):
    models = _state.get("models", {})
    existing = models.get(layer)
    if existing is not None:
        return existing

    lazy_loaders = _state.get("lazy_loaders", {})
    loader = lazy_loaders.get(layer)
    if loader is None:
        return None

    lock = _state.get("load_lock")
    if not isinstance(lock, LockType):
        return None

    with lock:
        existing = models.get(layer)
        if existing is not None:
            return existing

        t0 = time.perf_counter()
        observability = get_observability()
        try:
            model = loader()
            models[layer] = model
            lazy_loaders.pop(layer, None)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            _state.setdefault("startup_timings_ms", {})[f"{layer}_lazy_load_ms"] = elapsed_ms
            if observability is not None:
                observability.observe_layer_load(
                    layer=layer,
                    phase="lazy_load",
                    outcome="success",
                    duration_seconds=elapsed_ms / 1000.0,
                )
            log_backend_event(logging.INFO, event="lazy_layer_loaded", layer=layer, latency_ms=elapsed_ms)
            refresh_observability_state()
            return model
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            lazy_loaders.pop(layer, None)
            record_layer_load_error(layer, e, phase="lazy_load")
            if observability is not None:
                observability.observe_layer_load(
                    layer=layer,
                    phase="lazy_load",
                    outcome="error",
                    duration_seconds=elapsed_ms / 1000.0,
                )
            log_backend_event(
                logging.WARNING,
                event="lazy_layer_failed",
                layer=layer,
                latency_ms=elapsed_ms,
                error=str(e),
            )
            refresh_observability_state()
            return None


def get_layer_model(layer: str):
    model = _state.get("models", {}).get(layer)
    if model is not None:
        return model
    return ensure_layer_loaded(layer)

def build_layer_error(
    layer: str,
    *,
    default_phase: str = "runtime",
    default_message: str = "layer unavailable",
) -> dict[str, str]:
    latest_error = _get_latest_load_error(layer)
    if latest_error:
        return {
            "layer": layer,
            "phase": str(latest_error.get("phase", default_phase)),
            "message": str(latest_error.get("error", default_message)),
        }
    return {
        "layer": layer,
        "phase": default_phase,
        "message": default_message,
    }


def _build_line_starts(text: str) -> list[int]:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _offset_to_line_column(line_starts: list[int], offset: int) -> tuple[int, int]:
    line_index = max(0, bisect.bisect_right(line_starts, offset) - 1)
    line_start = line_starts[line_index]
    return (line_index + 1, (offset - line_start) + 1)


def _build_context_window(text: str, start: int, end: int, radius: int = SPAN_CONTEXT_CHARS) -> tuple[str, str]:
    before = text[max(0, start - radius):start]
    after = text[end:min(len(text), end + radius)]
    return (before, after)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _classify_core(req: ClassifyRequest, request_id: str | None, endpoint: str) -> ClassifyResponse:
    """Thin wrapper over engine.review().

    Legacy 9-layer pipeline (layer1_lexicon through layer6_regression + layer5_mosaic)
    archived 2026-05-26. /classify is retained as a programmatic surface for technical
    clients that want a flat findings dump without /review's session/decision/journal
    state. Legacy fields on the response (lexicon, model1, model2, embedding, clustering,
    mosaic, regression) are permanent None.
    """
    t_start = time.perf_counter()
    observability = get_observability()

    engine = _build_review_engine()
    try:
        result = engine.review(
            text=req.text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=req.entity_id,
            include_suggestions=False,
            document_type="generic",
            review_profile="strict",
            tenant_id=None,
        )
    except ReviewLayerError as exc:
        raise HTTPException(status_code=503, detail=_layer_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detector_error_detail(exc)) from exc
    degraded_modes = list(getattr(result, "degraded_modes", []) or [])
    timings_ms = {"total": round((time.perf_counter() - t_start) * 1000.0, 3)}

    public_evidence_resp = None
    if result.public_evidence is not None:
        try:
            public_evidence_resp = PublicEvidenceResponse(**result.public_evidence)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=_layer_error_detail(
                    ReviewLayerError("public_evidence", f"public-evidence response validation failed: {exc}")
                ),
            ) from exc

    llm_adjudication_resp = None
    if result.llm_adjudication is not None:
        try:
            llm_adjudication_resp = LLMAdjudicationResponse(**result.llm_adjudication)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=_layer_error_detail(
                    ReviewLayerError("llm_adjudicator", f"LLM adjudication response validation failed: {exc}")
                ),
            ) from exc

    privacy_ledger_resp = []
    for entry in result.privacy_ledger:
        try:
            privacy_ledger_resp.append(PrivacyLedgerEntryResponse(**entry))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=_layer_error_detail(
                    ReviewLayerError("privacy_ledger", f"privacy ledger response validation failed: {exc}")
                ),
            ) from exc

    findings_resp = []
    for f in result.findings:
        try:
            findings_resp.append(ReviewFindingResponse.model_validate(f.__dict__))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=_detector_error_detail(exc),
            ) from exc

    response = ClassifyResponse(
        request_id=request_id,
        classification=result.overall_risk,
        lexicon=None,
        model1=None,
        model2=None,
        embedding=None,
        clustering=None,
        mosaic=None,
        regression=None,
        public_evidence=public_evidence_resp,
        llm_adjudication=llm_adjudication_resp,
        privacy_ledger=privacy_ledger_resp,
        offending_spans=None,
        observability=ObservabilityResponse(
            degraded=bool(degraded_modes),
            cache_status="disabled",
            active_pipeline=["engine.review"],
            executed_layers=["engine.review"],
            skipped_layers=[],
            layer_errors=[],
        ),
        timings_ms=timings_ms,
        pii_score=result.pii_score,
        mnpi_score=result.mnpi_score,
        findings=findings_resp,
        coverage_warnings=list(result.coverage_warnings),
        degraded_modes=degraded_modes,
    )

    if observability is not None:
        observability.observe_classification(
            endpoint=endpoint,
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=bool(degraded_modes),
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event="classify_summary",
        request_id=request_id,
        classification=result.overall_risk.value,
        timings_ms=timings_ms,
        active_pipeline=["engine.review"],
        cache_status="disabled",
        degraded=bool(degraded_modes),
        executed_layers=["engine.review"],
        skipped_layers=[],
        layer_error_count=len(degraded_modes),
    )
    emit_privacy_ledger_events(
        result.privacy_ledger,
        request_id=request_id,
        endpoint=endpoint,
        settings=current_runtime_settings().siem,
    )

    return response


def _run_classify_sync(req: ClassifyRequest, request_id: str | None, endpoint: str) -> ClassifyResponse:
    return _classify_core(req, request_id, endpoint)


def get_batch_max_concurrency(item_count: int) -> int:
    configured = current_runtime_settings().startup.batch_max_concurrency
    return max(1, min(int(configured), int(item_count)))


def _run_batch_classify_sync(req: BatchClassifyRequest, base_request_id: str | None) -> BatchClassifyResponse:
    if not req.items:
        return BatchClassifyResponse(results=[])

    def _classify_batch_item(payload: tuple[int, ClassifyRequest]) -> ClassifyResponse:
        idx, item = payload
        item_request_id = f"{base_request_id}:{idx}" if base_request_id else None
        return _classify_core(item, item_request_id, "/classify/batch")

    max_workers = get_batch_max_concurrency(len(req.items))
    if max_workers == 1:
        results = [_classify_batch_item((idx, item)) for idx, item in enumerate(req.items)]
        return BatchClassifyResponse(results=results)

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="junas-batch") as executor:
        results = list(executor.map(_classify_batch_item, enumerate(req.items)))
    return BatchClassifyResponse(results=results)


def _build_review_engine() -> PreSendReviewEngine:
    settings = current_runtime_settings()

    public_evidence = get_layer_model("public_evidence")
    if public_evidence is None and settings.public_evidence.enabled:
        from junas.external.privacy_guard import PrivacyGuard
        from junas.external.public_evidence.inference import PublicEvidenceRetriever

        public_evidence = PublicEvidenceRetriever(
            settings.public_evidence,
            PrivacyGuard(
                external_query_policy=settings.privacy.external_query_policy,
                max_query_chars=settings.privacy.max_query_chars,
                redact_exact_numbers=settings.privacy.redact_exact_numbers,
            ),
        )

    llm_adjudicator = get_layer_model("llm_adjudicator")
    if llm_adjudicator is None and settings.llm.enabled:
        from junas.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

        llm_adjudicator = LocalLLMAdjudicator(settings.llm)

    # audit_grade-only helper: catches preamble defined-term patterns the regex misses.
    # surfaced as a layer model so tests / deployments can swap implementations without
    # touching the engine. when unwired, engine falls through to the deterministic regex.
    llm_defined_term_extractor = get_layer_model("llm_defined_term_extractor")
    if llm_defined_term_extractor is None and settings.llm_helpers.defined_terms_enabled:
        from junas.advisory.llm_adjudicator.helpers import build_llm_defined_term_extractor

        llm_defined_term_extractor = build_llm_defined_term_extractor(settings.llm)
    # audit_grade-only inverse-audit helper. output is journaled as coverage_warning
    # events and promoted to capped origin=llm findings by the engine.
    llm_coverage_auditor = get_layer_model("llm_coverage_auditor")
    if llm_coverage_auditor is None and settings.llm_helpers.coverage_audit_enabled:
        from junas.advisory.llm_adjudicator.helpers import build_llm_coverage_auditor

        llm_coverage_auditor = build_llm_coverage_auditor(settings.llm)

    return PreSendReviewEngine(
        public_evidence_retriever=public_evidence,
        llm_adjudicator=llm_adjudicator,
        llm_defined_term_extractor=llm_defined_term_extractor,
        llm_coverage_auditor=llm_coverage_auditor,
    )


def _image_scan_enabled() -> bool:
    return str(current_runtime_settings().image_scan.provider or "none").lower() != "none"


def _build_privacy_guard() -> PrivacyGuard:
    settings = current_runtime_settings()
    return PrivacyGuard(
        external_query_policy=settings.privacy.external_query_policy,
        max_query_chars=settings.privacy.max_query_chars,
        redact_exact_numbers=settings.privacy.redact_exact_numbers,
    )


def _scan_document_images(document: Any, *, tenant_id: str | None) -> tuple[Any, list[dict[str, Any]]]:
    settings = current_runtime_settings().image_scan
    provider = str(getattr(settings, "provider", "none") or "none").lower()
    if provider == "none":
        return document, []

    candidates = list(getattr(document, "image_candidates", []) or [])
    if not candidates:
        return document, []

    scanner = get_layer_model("image_scanner")
    try:
        if scanner is None:
            scanner = build_image_scanner(settings, _build_privacy_guard(), tenant_id=tenant_id)
        if scanner is None:
            raise ImageScanError("image OCR provider is disabled")
        results, privacy_ledger = scan_image_candidates(
            candidates,
            scanner=scanner,
            settings=settings,
        )
        text, spans = append_ocr_text_blocks(document.text, results)
    except ImageScanError:
        raise
    except Exception as exc:
        raise ImageScanError(f"image OCR failed: {exc}") from exc

    if not text.strip():
        raise ImageScanError("image OCR produced no reviewable text")

    warnings = list(getattr(document, "extraction_warnings", []) or [])
    if results:
        warnings.append(f"Image OCR scanned {len(results)} image(s) with provider {provider}")
    return (
        replace(
            document,
            text=text,
            extraction_quality="accepted",
            extraction_warnings=warnings,
            image_text_spans=spans,
            image_scan_provider=provider,
        ),
        privacy_ledger,
    )


def _annotate_image_ocr_findings(document: Any, findings: list[Any]) -> None:
    spans = list(getattr(document, "image_text_spans", []) or [])
    if not spans:
        return
    for finding in findings:
        locator = image_locator_for_span(spans, int(finding.start_char), int(finding.end_char))
        if locator is None:
            continue
        metadata = image_ocr_metadata_for_span(spans, int(finding.start_char), int(finding.end_char)) or {}
        finding.source = "image_ocr"
        finding.image_locator = locator
        finding.image_ocr_confidence = metadata.get("confidence")
        finding.image_ocr_regions = metadata.get("regions", [])


def _degraded_mode(mode: str, status: str, reason: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"mode": mode, "status": status, "reason": reason}
    if detail:
        payload["detail"] = detail
    return payload


def _image_scan_error_detail(exc: Exception) -> dict[str, Any]:
    reason = str(exc)
    return {
        "message": reason,
        "degraded_modes": [
            _degraded_mode("image_ocr", "failed_closed", reason),
        ],
    }


def _layer_error_detail(exc: ReviewLayerError) -> dict[str, Any]:
    reason = str(exc)
    return {
        "message": reason,
        "degraded_modes": [
            _degraded_mode(exc.layer, "failed_closed", reason),
        ],
    }


def _detector_error_detail(exc: Exception) -> dict[str, Any]:
    reason = str(exc)
    return {
        "message": f"deterministic review failed closed: {reason}",
        "degraded_modes": [
            _degraded_mode("detector", "failed_closed", reason),
        ],
    }


def _document_degraded_modes(document: Any) -> list[dict[str, Any]]:
    modes: list[dict[str, Any]] = []
    for warning in list(getattr(document, "extraction_warnings", []) or []):
        if "fail-open:" in warning:
            modes.append(_degraded_mode("document_ingest", "failed_open", warning))
        if "reviewed text layer only" in warning:
            modes.append(_degraded_mode("image_ocr", "skipped", warning))
        if "page(s) for configured image OCR" in warning:
            modes.append(_degraded_mode("image_ocr", "page_rendered", warning))
    return modes


def _degraded_send_allowed(req: ReviewRequest, degraded_modes: list[dict[str, Any]]) -> bool:
    return not (req.degraded_policy == "block_send" and bool(degraded_modes))


def _utc_now_rfc3339() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _review_expires_at() -> str:
    expires_at = datetime.now(UTC) + timedelta(seconds=REVIEW_DECISION_VALIDITY_SECONDS)
    return expires_at.isoformat(timespec="seconds").replace("+00:00", "Z")


def _policy_decision_response(
    *,
    req: ReviewRequest,
    request_id: str | None,
    findings: list[Any],
    degraded_modes: list[dict[str, Any]],
) -> tuple[PolicyDecisionResponse, float]:
    t_policy_start = time.perf_counter()
    decision = evaluate_policy(
        findings=findings,
        context=WorkflowContext.from_request(req),
        degraded_policy=req.degraded_policy,
        degraded_modes=degraded_modes,
        review_id=request_id or "",
    )
    response = PolicyDecisionResponse.model_validate(decision.as_dict())
    policy_decision_ms = round((time.perf_counter() - t_policy_start) * 1000.0, 3)
    observability = get_observability()
    if observability is not None:
        observability.observe_policy_decision(response.decision, policy_decision_ms / 1000.0)
    return response, policy_decision_ms


@dataclass(frozen=True)
class _SafeRewriteCandidate:
    finding: Any
    finding_id: str
    action: str
    replacement_text: str
    start_char: int
    end_char: int
    priority: int


def _finding_attr(finding: Any, name: str, default: Any = "") -> Any:
    if isinstance(finding, dict):
        return finding.get(name, default)
    return getattr(finding, name, default)


def _safe_rewrite_action(
    *,
    finding: Any,
    policy_actions: set[str],
    allowed_actions: set[str],
) -> tuple[str | None, str]:
    category = str(_finding_attr(finding, "category", "")).upper()
    severity = str(_finding_attr(finding, "severity", "")).lower()
    if category == "PII":
        if "redact_pii" in policy_actions and "redact_pii" in allowed_actions:
            return "redact_pii", "[REDACTED PERSONAL DATA]"
        if "safe_rewrite" in policy_actions and "safe_rewrite" in allowed_actions:
            return "safe_rewrite", "[REDACTED PERSONAL DATA]"
        return None, "no policy-approved PII rewrite action"
    if category == "MNPI" and severity == "high":
        if "redact_pii" in allowed_actions and "hold_until_public" not in allowed_actions:
            return None, "redact_pii leaves MNPI visible for policy review"
        if "hold_until_public" in policy_actions and "hold_until_public" in allowed_actions:
            return "hold_until_public", "[HOLD UNTIL PUBLIC DISCLOSURE OR APPROVAL]"
        return None, "no policy-approved MNPI hold action"
    return None, "finding category or severity is not safe-rewrite eligible"


def _safe_rewrite_priority(finding: Any) -> int:
    category = str(_finding_attr(finding, "category", "")).upper()
    severity = str(_finding_attr(finding, "severity", "")).lower()
    category_priority = 100 if category == "PII" else 50
    severity_priority = {"high": 30, "medium": 20, "low": 10}.get(severity, 0)
    return category_priority + severity_priority


def _safe_rewrite_plan(
    *,
    text: str,
    findings: list[Any],
    policy_decision: PolicyDecisionResponse,
    req: SafeRewriteRequest,
) -> tuple[list[_SafeRewriteCandidate], list[SafeRewriteSkippedFindingResponse]]:
    policy_actions = set(policy_decision.required_actions) | set(policy_decision.recommended_actions)
    allowed_actions = set(req.allowed_actions)
    allowed_finding_ids = set(req.allowed_finding_ids or [])
    candidates: list[_SafeRewriteCandidate] = []
    skipped: dict[str, str] = {}

    def skip(finding_id: str, reason: str) -> None:
        if finding_id and finding_id not in skipped:
            skipped[finding_id] = reason

    for finding in findings:
        finding_id = str(_finding_attr(finding, "id", ""))
        if allowed_finding_ids and finding_id not in allowed_finding_ids:
            skip(finding_id, "finding not in allowed_finding_ids")
            continue
        start = int(_finding_attr(finding, "start_char", -1))
        end = int(_finding_attr(finding, "end_char", -1))
        if start < 0 or end <= start or end > len(text):
            skip(finding_id, "invalid finding span")
            continue
        action, replacement_text = _safe_rewrite_action(
            finding=finding,
            policy_actions=policy_actions,
            allowed_actions=allowed_actions,
        )
        if action is None:
            skip(finding_id, replacement_text)
            continue
        candidates.append(
            _SafeRewriteCandidate(
                finding=finding,
                finding_id=finding_id,
                action=action,
                replacement_text=replacement_text,
                start_char=start,
                end_char=end,
                priority=_safe_rewrite_priority(finding),
            )
        )

    accepted: list[_SafeRewriteCandidate] = []
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.start_char,
            -item.priority,
            -(item.end_char - item.start_char),
            item.end_char,
        ),
    )
    for candidate in ordered:
        if any(
            candidate.start_char < existing.end_char and existing.start_char < candidate.end_char
            for existing in accepted
        ):
            skip(candidate.finding_id, "overlaps with higher-priority replacement")
            continue
        accepted.append(candidate)

    skipped_findings = [
        SafeRewriteSkippedFindingResponse(finding_id=finding_id, reason=reason)
        for finding_id, reason in sorted(skipped.items())
    ]
    return sorted(accepted, key=lambda item: (item.start_char, item.end_char)), skipped_findings


def _apply_safe_rewrite(text: str, replacements: list[_SafeRewriteCandidate]) -> str:
    rewritten_text = text
    for replacement in sorted(replacements, key=lambda item: item.start_char, reverse=True):
        rewritten_text = (
            rewritten_text[: replacement.start_char]
            + replacement.replacement_text
            + rewritten_text[replacement.end_char :]
        )
    return rewritten_text


def _safe_rewrite_replacements(
    *,
    text: str,
    replacements: list[_SafeRewriteCandidate],
) -> list[SafeRewriteReplacementResponse]:
    responses: list[SafeRewriteReplacementResponse] = []
    for replacement in replacements:
        original_text = text[replacement.start_char : replacement.end_char]
        responses.append(
            SafeRewriteReplacementResponse(
                finding_id=replacement.finding_id,
                action=replacement.action,
                category=str(_finding_attr(replacement.finding, "category", "")),
                rule=str(_finding_attr(replacement.finding, "rule", "")),
                severity=str(_finding_attr(replacement.finding, "severity", "")),
                start_char=replacement.start_char,
                end_char=replacement.end_char,
                replacement_text=replacement.replacement_text,
                original_text_hash=hashlib.sha256(original_text.encode("utf-8")).hexdigest(),
            )
        )
    return responses


def _finding_response(finding: Any) -> ReviewFindingResponse:
    return ReviewFindingResponse(
        id=finding.id,
        category=finding.category,
        rule=finding.rule,
        jurisdiction=finding.jurisdiction,
        severity=finding.severity,
        score=finding.score,
        matched_text=finding.matched_text,
        start_char=finding.start_char,
        end_char=finding.end_char,
        reason=finding.reason,
        legal_basis=finding.legal_basis,
        source=getattr(finding, "source", "text"),
        image_locator=getattr(finding, "image_locator", None),
        image_ocr_confidence=getattr(finding, "image_ocr_confidence", None),
        image_ocr_regions=getattr(finding, "image_ocr_regions", []),
        source_verification=getattr(finding, "source_verification", "not_checked"),
        metadata=getattr(finding, "metadata", {}),
    )


def _build_review_response(
    *,
    req: ReviewRequest,
    request_id: str | None,
    document: Any,
    result: Any,
    timings_ms: dict[str, float],
    degraded_modes: list[dict[str, Any]] | None = None,
    visible_findings: list[Any] | None = None,
    lane_suppressed_findings: list[Any] | None = None,
    lane_suppressed_count: int = 0,
) -> ReviewResponse:
    response_findings = list(result.findings if visible_findings is None else visible_findings)
    suppressed_findings = list(lane_suppressed_findings or [])
    visible_ids = {finding.id for finding in response_findings}
    modes = list(degraded_modes or [])
    policy_decision, policy_decision_ms = _policy_decision_response(
        req=req,
        request_id=request_id,
        findings=list(result.findings),
        degraded_modes=modes,
    )
    timings_ms["policy_decision_ms"] = policy_decision_ms
    timings_ms["total"] = round(timings_ms.get("total", 0.0) + policy_decision_ms, 3)
    return ReviewResponse(
        request_id=request_id,
        review_expires_at=_review_expires_at(),
        overall_risk=result.overall_risk,
        classification=result.overall_risk,
        document_score=result.document_score,
        pii_score=result.pii_score,
        mnpi_score=result.mnpi_score,
        source_jurisdiction=req.source_jurisdiction,
        destination_jurisdiction=req.destination_jurisdiction,
        jurisdictions_applied=result.jurisdictions_applied,
        jurisdiction_policy=result.jurisdiction_policy,
        document_type=req.document_type,
        review_profile=req.review_profile,
        degraded_policy=req.degraded_policy,
        send_allowed=policy_decision.send_allowed,
        policy_decision=policy_decision,
        action_catalog=list(ACTION_CATALOG),
        document=ReviewDocumentMetadataResponse(
            filename=document.filename,
            mime_type=document.mime_type,
            extraction_method=document.extraction_method,
            page_count=document.page_count,
            char_count=len(document.text),
            extraction_quality=getattr(document, "extraction_quality", "accepted"),
            extraction_warnings=list(getattr(document, "extraction_warnings", []) or []),
            metadata_findings=list(getattr(document, "metadata_findings", []) or []),
        ),
        findings=[_finding_response(finding) for finding in response_findings],
        lane_suppressed_count=lane_suppressed_count,
        lane_suppressed_findings=[_finding_response(finding) for finding in suppressed_findings],
        suggestions=[
            ReviewSuggestionResponse(
                id=suggestion.id,
                finding_id=suggestion.finding_id,
                action=suggestion.action,
                replacement_text=suggestion.replacement_text,
                rationale=suggestion.rationale,
            )
            for suggestion in result.suggestions
            if suggestion.finding_id in visible_ids
        ],
        public_evidence=PublicEvidenceResponse(**result.public_evidence) if result.public_evidence else None,
        llm_adjudication=LLMAdjudicationResponse(**result.llm_adjudication) if result.llm_adjudication else None,
        privacy_ledger=[PrivacyLedgerEntryResponse(**entry) for entry in result.privacy_ledger],
        coverage_warnings=list(result.coverage_warnings),
        degraded_modes=modes,
        timings_ms=timings_ms,
    )


def _review_persistence_enabled() -> bool:
    return _is_truthy(os.environ.get("JUNAS_REVIEW_PERSIST"), default=False)


def _persist_coverage_warnings(
    *,
    request_id: str | None,
    warnings: list[Any],
    tenant_id: str | None = None,
) -> None:
    """Journal each coverage warning. LLM warnings also have capped findings in the session."""
    if not _review_persistence_enabled() or not request_id or not warnings:
        return
    from junas.review.decisions import EVENT_COVERAGE_WARNING
    from junas.review.journal import append_event

    for warning in warnings:
        append_event(
            event_type=EVENT_COVERAGE_WARNING,
            review_id=request_id,
            payload=dict(warning),
            tenant_id=tenant_id,
        )


def _hash_policy_values(values: list[str]) -> list[str]:
    return sorted(hashlib.sha256(value.encode("utf-8")).hexdigest() for value in values)


def _persist_policy_decision_event(
    *,
    request_id: str | None,
    document_text: str,
    policy_decision: PolicyDecisionResponse | None,
    finding_count: int,
    degraded_modes: list[dict[str, Any]],
    tenant_id: str | None = None,
) -> None:
    if not _review_persistence_enabled() or not request_id or policy_decision is None:
        return
    from junas.review.decisions import EVENT_POLICY_DECISION_RECORDED
    from junas.review.journal import append_event

    append_event(
        event_type=EVENT_POLICY_DECISION_RECORDED,
        review_id=request_id,
        payload={
            "document_hash": hashlib.sha256(document_text.encode("utf-8")).hexdigest(),
            "decision": policy_decision.decision,
            "send_allowed": policy_decision.send_allowed,
            "policy_id": policy_decision.policy_id,
            "policy_version": policy_decision.policy_version,
            "finding_count": int(finding_count),
            "degraded_mode_count": len(degraded_modes),
            "blocking_finding_count": len(policy_decision.blocking_findings),
            "blocking_finding_hashes": _hash_policy_values(policy_decision.blocking_findings),
            "required_action_count": len(policy_decision.required_actions),
            "required_action_hashes": _hash_policy_values(policy_decision.required_actions),
            "recommended_action_count": len(policy_decision.recommended_actions),
            "recommended_action_hashes": _hash_policy_values(policy_decision.recommended_actions),
            "policy_reason_count": len(policy_decision.policy_reasons),
            "policy_reason_hashes": _hash_policy_values(policy_decision.policy_reasons),
        },
        tenant_id=tenant_id,
    )


def _persist_review_session(
    *,
    request_id: str | None,
    req: ReviewRequest,
    document_text: str,
    findings: list[Any],
    tenant_id: str | None = None,
) -> None:
    if not _review_persistence_enabled() or not request_id:
        return
    text_hash = hashlib.sha256(document_text.encode("utf-8")).hexdigest()
    serialized_findings = [
        {
            "id": f.id,
            "category": f.category,
            "rule": f.rule,
            "severity": f.severity,
            "matched_text": f.matched_text,
            "start_char": f.start_char,
            "end_char": f.end_char,
            "source": getattr(f, "source", "text"),
            "image_locator": getattr(f, "image_locator", None),
            "image_ocr_confidence": getattr(f, "image_ocr_confidence", None),
            "image_ocr_regions": getattr(f, "image_ocr_regions", []),
            "metadata": getattr(f, "metadata", {}),
        }
        for f in findings
    ]
    require_subject_index_key()
    start_review_session(
        review_id=request_id,
        text_hash=text_hash,
        document_type=req.document_type,
        source_jurisdiction=req.source_jurisdiction,
        destination_jurisdiction=req.destination_jurisdiction,
        findings=serialized_findings,
        tenant_id=tenant_id,
    )
    index_review_findings(
        review_id=request_id,
        document_hash=text_hash,
        findings=serialized_findings,
        tenant_id=tenant_id,
    )


def _apply_surfacing_lanes_to_result(result: Any, tenant: TenantContext) -> Any:
    try:
        from junas.review.surfacing_lane import SurfacingLaneError, apply_surfacing_lanes

        return apply_surfacing_lanes(result.findings, tenant_id=tenant.storage_tenant_id)
    except SurfacingLaneError as exc:
        detail = _layer_error_detail(ReviewLayerError("surfacing_lane", str(exc)))
        raise HTTPException(status_code=503, detail=detail) from exc


def _run_review_sync(
    req: ReviewRequest,
    request_id: str | None,
    tenant: TenantContext,
    *,
    endpoint: str = "/review",
    log_event: str = "review_summary",
) -> ReviewResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(
            req,
            current_runtime_settings().document_ingest,
            image_scan_enabled=_image_scan_enabled(),
            image_scan_settings=current_runtime_settings().image_scan,
        )
    except (ValueError, ImageScanError) as exc:
        detail = _image_scan_error_detail(exc) if isinstance(exc, ImageScanError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)
    degraded_modes = _document_degraded_modes(document)

    t_image_scan_start = time.perf_counter()
    try:
        document, image_privacy_ledger = _scan_document_images(
            document,
            tenant_id=tenant.tenant_id if tenant.enabled else None,
        )
    except ImageScanError as exc:
        if current_runtime_settings().document_ingest.fail_closed:
            raise HTTPException(status_code=422, detail=_image_scan_error_detail(exc)) from exc
        image_privacy_ledger = []
        degraded_modes.append(_degraded_mode("image_ocr", "failed_open", str(exc)))
    if image_privacy_ledger:
        timings_ms["image_ocr"] = round((time.perf_counter() - t_image_scan_start) * 1000.0, 3)

    t_review_start = time.perf_counter()
    engine = _build_review_engine()
    try:
        result = engine.review(
            text=document.text,
            source_jurisdiction=req.source_jurisdiction,
            destination_jurisdiction=req.destination_jurisdiction,
            entity_id=req.entity_id,
            include_suggestions=req.include_suggestions,
            document_type=req.document_type,
            session_id=req.session_id,
            matter_id=req.matter_id,
            review_profile=req.review_profile,
            tenant_id=tenant.storage_tenant_id,
            document_structure=getattr(document, "document_structure", None),
        )
    except ReviewLayerError as exc:
        raise HTTPException(status_code=503, detail=_layer_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detector_error_detail(exc)) from exc
    _annotate_image_ocr_findings(document, result.findings)
    lane_result = _apply_surfacing_lanes_to_result(result, tenant)
    result.privacy_ledger = image_privacy_ledger + list(result.privacy_ledger)
    degraded_modes.extend(list(getattr(result, "degraded_modes", []) or []))
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)
    try:
        _persist_review_session(
            request_id=request_id,
            req=req,
            document_text=document.text,
            findings=result.findings,
            tenant_id=tenant.storage_tenant_id,
        )
    except SubjectIndexError as exc:
        log_backend_event(logging.WARNING, event="review_subject_index_failed", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"review persistence failed closed: {exc}",
                "degraded_modes": [
                    _degraded_mode("subject_index", "failed_closed", str(exc), {})
                ],
            },
        ) from exc
    _persist_coverage_warnings(
        request_id=request_id,
        warnings=result.coverage_warnings,
        tenant_id=tenant.storage_tenant_id,
    )
    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    response = _build_review_response(
        req=req,
        request_id=request_id,
        document=document,
        result=result,
        timings_ms=timings_ms,
        degraded_modes=degraded_modes,
        visible_findings=lane_result.visible_findings,
        lane_suppressed_findings=(
            lane_result.suppressed_findings if _can_view_lane_suppressed(tenant) else []
        ),
        lane_suppressed_count=lane_result.suppressed_count,
    )
    _persist_policy_decision_event(
        request_id=request_id,
        document_text=document.text,
        policy_decision=response.policy_decision,
        finding_count=len(result.findings),
        degraded_modes=degraded_modes,
        tenant_id=tenant.storage_tenant_id,
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint=endpoint,
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=bool(degraded_modes),
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event=log_event,
        request_id=request_id,
        classification=result.overall_risk.value,
        pii_score=result.pii_score,
        mnpi_score=result.mnpi_score,
        finding_count=len(result.findings),
        jurisdictions_applied=result.jurisdictions_applied,
        timings_ms=timings_ms,
    )
    emit_privacy_ledger_events(
        result.privacy_ledger,
        request_id=request_id,
        endpoint=endpoint,
        settings=current_runtime_settings().siem,
    )
    return response


def _run_public_demo_review_sync(req: ReviewRequest, request_id: str | None) -> ReviewResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(
            req,
            current_runtime_settings().document_ingest,
            image_scan_enabled=False,
            image_scan_settings=current_runtime_settings().image_scan,
        )
    except (ValueError, ImageScanError) as exc:
        detail = _image_scan_error_detail(exc) if isinstance(exc, ImageScanError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)
    degraded_modes = _document_degraded_modes(document)

    t_review_start = time.perf_counter()
    engine = PreSendReviewEngine()
    try:
        result = engine.review(
            text=document.text,
            source_jurisdiction=req.source_jurisdiction,
            destination_jurisdiction=req.destination_jurisdiction,
            entity_id=req.entity_id,
            include_suggestions=req.include_suggestions,
            document_type=req.document_type,
            session_id=None,
            matter_id=None,
            review_profile="strict",
            tenant_id=None,
            document_structure=getattr(document, "document_structure", None),
        )
    except ReviewLayerError as exc:
        raise HTTPException(status_code=503, detail=_layer_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detector_error_detail(exc)) from exc
    degraded_modes.extend(list(getattr(result, "degraded_modes", []) or []))
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)
    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    response = _build_review_response(
        req=req,
        request_id=request_id,
        document=document,
        result=result,
        timings_ms=timings_ms,
        degraded_modes=degraded_modes,
        visible_findings=result.findings,
        lane_suppressed_findings=[],
        lane_suppressed_count=0,
    )
    return response


def _public_source_citations(
    response: ReviewResponse,
    retrieval_timestamp: str,
) -> list[PublicSourceCitationResponse]:
    public_evidence = response.public_evidence
    if public_evidence is None:
        return []
    ledger_entries = list(public_evidence.privacy_ledger) + list(response.privacy_ledger)
    privacy_ledger_entry = next(
        (
            entry
            for entry in ledger_entries
            if entry.allowed and entry.operation == "external_query"
        ),
        None,
    )
    if privacy_ledger_entry is None:
        return []
    finding_ids = [
        finding.id
        for finding in response.findings
        if finding.category == "MNPI" and finding.source_verification == "public_source_matched"
    ]
    if not finding_ids:
        return []
    if response.policy_decision is None:
        policy_ref = "unknown@unknown"
    else:
        policy_ref = f"{response.policy_decision.policy_id}@{response.policy_decision.policy_version}"
    citations: list[PublicSourceCitationResponse] = []
    for source in public_evidence.sources:
        source_url = source.url.strip()
        if not source_url:
            continue
        citations.append(
            PublicSourceCitationResponse(
                source_url=source_url,
                retrieval_timestamp=retrieval_timestamp,
                privacy_ledger_entry=privacy_ledger_entry,
                finding_ids=finding_ids,
                audit_rationale=(
                    f"cite_public_source recorded {source_url} for {len(finding_ids)} MNPI findings "
                    f"under policy {policy_ref}."
                ),
            )
        )
    return citations


def _run_cite_public_source_sync(
    req: CitePublicSourceRequest,
    request_id: str | None,
    tenant: TenantContext,
) -> CitePublicSourceResponse:
    t_cite_start = time.perf_counter()
    review_response = _run_review_sync(
        req,
        request_id,
        tenant,
        endpoint="/cite-public-source",
        log_event="cite_public_source_review_summary",
    )
    retrieval_timestamp = _utc_now_rfc3339()
    citations = _public_source_citations(review_response, retrieval_timestamp)
    if not citations:
        raise HTTPException(
            status_code=409,
            detail=(
                "cite_public_source requires audit_grade public evidence with source URL "
                "and allowed privacy-ledger entry"
            ),
        )
    timings_ms = dict(review_response.timings_ms)
    timings_ms["cite_public_source"] = round((time.perf_counter() - t_cite_start) * 1000.0, 3)
    timings_ms["total"] = round(timings_ms.get("total", 0.0) + timings_ms["cite_public_source"], 3)
    base_response = review_response.model_dump(mode="python")
    base_response["timings_ms"] = timings_ms
    return CitePublicSourceResponse(
        **base_response,
        privacy_operation="cite_public_source",
        citation_policy="audit_grade_public_evidence",
        citations=citations,
    )


def _run_safe_rewrite_sync(
    req: SafeRewriteRequest,
    request_id: str | None,
    tenant: TenantContext,
    *,
    endpoint: str = "/safe-rewrite",
    privacy_operation: str = "safe_rewrite",
    rewrite_policy: str = "deterministic_allowed_spans",
    timing_key: str = "safe_rewrite",
    response_type: type[SafeRewriteResponse] = SafeRewriteResponse,
) -> SafeRewriteResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(
            req,
            current_runtime_settings().document_ingest,
            image_scan_enabled=_image_scan_enabled(),
            image_scan_settings=current_runtime_settings().image_scan,
        )
    except (ValueError, ImageScanError) as exc:
        detail = _image_scan_error_detail(exc) if isinstance(exc, ImageScanError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)
    degraded_modes = _document_degraded_modes(document)

    t_image_scan_start = time.perf_counter()
    try:
        document, image_privacy_ledger = _scan_document_images(
            document,
            tenant_id=tenant.tenant_id if tenant.enabled else None,
        )
    except ImageScanError as exc:
        if current_runtime_settings().document_ingest.fail_closed:
            raise HTTPException(status_code=422, detail=_image_scan_error_detail(exc)) from exc
        image_privacy_ledger = []
        degraded_modes.append(_degraded_mode("image_ocr", "failed_open", str(exc)))
    if image_privacy_ledger:
        timings_ms["image_ocr"] = round((time.perf_counter() - t_image_scan_start) * 1000.0, 3)

    t_review_start = time.perf_counter()
    engine = _build_review_engine()
    try:
        result = engine.review(
            text=document.text,
            source_jurisdiction=req.source_jurisdiction,
            destination_jurisdiction=req.destination_jurisdiction,
            entity_id=req.entity_id,
            include_suggestions=req.include_suggestions,
            document_type=req.document_type,
            session_id=req.session_id,
            matter_id=req.matter_id,
            review_profile=req.review_profile,
            tenant_id=tenant.storage_tenant_id,
            document_structure=getattr(document, "document_structure", None),
        )
    except ReviewLayerError as exc:
        raise HTTPException(status_code=503, detail=_layer_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detector_error_detail(exc)) from exc
    _annotate_image_ocr_findings(document, result.findings)
    lane_result = _apply_surfacing_lanes_to_result(result, tenant)
    result.privacy_ledger = image_privacy_ledger + list(result.privacy_ledger)
    degraded_modes.extend(list(getattr(result, "degraded_modes", []) or []))
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)
    try:
        _persist_review_session(
            request_id=request_id,
            req=req,
            document_text=document.text,
            findings=result.findings,
            tenant_id=tenant.storage_tenant_id,
        )
    except SubjectIndexError as exc:
        log_backend_event(logging.WARNING, event="review_subject_index_failed", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"review persistence failed closed: {exc}",
                "degraded_modes": [
                    _degraded_mode("subject_index", "failed_closed", str(exc), {})
                ],
            },
        ) from exc
    _persist_coverage_warnings(
        request_id=request_id,
        warnings=result.coverage_warnings,
        tenant_id=tenant.storage_tenant_id,
    )
    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    review_response = _build_review_response(
        req=req,
        request_id=request_id,
        document=document,
        result=result,
        timings_ms=timings_ms,
        degraded_modes=degraded_modes,
        visible_findings=lane_result.visible_findings,
        lane_suppressed_findings=(
            lane_result.suppressed_findings if _can_view_lane_suppressed(tenant) else []
        ),
        lane_suppressed_count=lane_result.suppressed_count,
    )
    _persist_policy_decision_event(
        request_id=request_id,
        document_text=document.text,
        policy_decision=review_response.policy_decision,
        finding_count=len(result.findings),
        degraded_modes=degraded_modes,
        tenant_id=tenant.storage_tenant_id,
    )

    t_safe_rewrite_start = time.perf_counter()
    replacements, skipped_findings = _safe_rewrite_plan(
        text=document.text,
        findings=list(result.findings),
        policy_decision=review_response.policy_decision,
        req=req,
    )
    rewritten_text = _apply_safe_rewrite(document.text, replacements)
    rewrite_replacements = _safe_rewrite_replacements(text=document.text, replacements=replacements)
    timings_ms[timing_key] = round((time.perf_counter() - t_safe_rewrite_start) * 1000.0, 3)
    timings_ms["total"] = round(timings_ms.get("total", 0.0) + timings_ms[timing_key], 3)
    base_response = review_response.model_dump(mode="python")
    base_response["timings_ms"] = dict(timings_ms)
    response = response_type(
        **base_response,
        privacy_operation=privacy_operation,
        rewrite_policy=rewrite_policy,
        rewritten_text=rewritten_text,
        document_hash=_compute_document_hash(document.text),
        mapping_persisted=False,
        replacements=rewrite_replacements,
        skipped_findings=skipped_findings,
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint=endpoint,
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=bool(degraded_modes),
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event=f"{privacy_operation}_summary",
        request_id=request_id,
        classification=result.overall_risk.value,
        pii_score=result.pii_score,
        mnpi_score=result.mnpi_score,
        finding_count=len(result.findings),
        replacement_count=len(replacements),
        jurisdictions_applied=result.jurisdictions_applied,
        timings_ms=timings_ms,
    )
    emit_privacy_ledger_events(
        result.privacy_ledger,
        request_id=request_id,
        endpoint=endpoint,
        settings=current_runtime_settings().siem,
    )
    return response


def _run_redact_pii_sync(req: RedactPiiRequest, request_id: str | None, tenant: TenantContext) -> RedactPiiResponse:
    redact_req = req.model_copy(update={"requested_action": "redact_pii", "allowed_actions": ["redact_pii"]})
    return cast(
        RedactPiiResponse,
        _run_safe_rewrite_sync(
            redact_req,
            request_id,
            tenant,
            endpoint="/redact-pii",
            privacy_operation="redact_pii",
            rewrite_policy="pii_only_allowed_spans",
            timing_key="redact_pii",
            response_type=RedactPiiResponse,
        ),
    )


def _hold_until_public_reasons(
    replacements: list[SafeRewriteReplacementResponse],
    policy_decision: PolicyDecisionResponse | None,
) -> list[HoldUntilPublicReasonResponse]:
    if policy_decision is None:
        policy_ref = "unknown@unknown"
    else:
        policy_ref = f"{policy_decision.policy_id}@{policy_decision.policy_version}"
    reasons: list[HoldUntilPublicReasonResponse] = []
    for replacement in replacements:
        if replacement.action != "hold_until_public":
            continue
        reasons.append(
            HoldUntilPublicReasonResponse(
                finding_id=replacement.finding_id,
                user_reason=(
                    "This passage appears to contain high-severity MNPI. Wait for public disclosure "
                    "or reviewer approval before sharing."
                ),
                audit_rationale=(
                    f"hold_until_public applied to finding {replacement.finding_id} "
                    f"({replacement.rule}, {replacement.severity} MNPI) under policy {policy_ref}; "
                    "sharing remains blocked until public evidence or reviewer approval is recorded."
                ),
            )
        )
    return reasons


def _run_hold_until_public_sync(
    req: HoldUntilPublicRequest,
    request_id: str | None,
    tenant: TenantContext,
) -> HoldUntilPublicResponse:
    hold_req = req.model_copy(
        update={"requested_action": "hold_until_public", "allowed_actions": ["hold_until_public"]}
    )
    response = cast(
        HoldUntilPublicResponse,
        _run_safe_rewrite_sync(
            hold_req,
            request_id,
            tenant,
            endpoint="/hold-until-public",
            privacy_operation="hold_until_public",
            rewrite_policy="mnpi_hold_allowed_spans",
            timing_key="hold_until_public",
            response_type=HoldUntilPublicResponse,
        ),
    )
    return cast(
        HoldUntilPublicResponse,
        response.model_copy(
            update={"hold_reasons": _hold_until_public_reasons(response.replacements, response.policy_decision)}
        ),
    )


def _run_placeholder_review_sync(
    req: Any,
    request_id: str | None,
    tenant: TenantContext,
    *,
    timing_key: str,
) -> dict[str, Any]:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(
            req,
            current_runtime_settings().document_ingest,
            image_scan_enabled=_image_scan_enabled(),
            image_scan_settings=current_runtime_settings().image_scan,
        )
    except (ValueError, ImageScanError) as exc:
        detail = _image_scan_error_detail(exc) if isinstance(exc, ImageScanError) else str(exc)
        raise HTTPException(status_code=422, detail=detail) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)
    degraded_modes = _document_degraded_modes(document)

    t_image_scan_start = time.perf_counter()
    try:
        document, image_privacy_ledger = _scan_document_images(
            document,
            tenant_id=tenant.tenant_id if tenant.enabled else None,
        )
    except ImageScanError as exc:
        if current_runtime_settings().document_ingest.fail_closed:
            raise HTTPException(status_code=422, detail=_image_scan_error_detail(exc)) from exc
        image_privacy_ledger = []
        degraded_modes.append(_degraded_mode("image_ocr", "failed_open", str(exc)))
    if image_privacy_ledger:
        timings_ms["image_ocr"] = round((time.perf_counter() - t_image_scan_start) * 1000.0, 3)

    t_review_start = time.perf_counter()
    engine = _build_review_engine()
    try:
        result = engine.review(
            text=document.text,
            source_jurisdiction=req.source_jurisdiction,
            destination_jurisdiction=req.destination_jurisdiction,
            entity_id=req.entity_id,
            include_suggestions=req.include_suggestions,
            document_type=req.document_type,
            session_id=req.session_id,
            matter_id=req.matter_id,
            review_profile=req.review_profile,
            tenant_id=tenant.storage_tenant_id,
            document_structure=getattr(document, "document_structure", None),
        )
    except ReviewLayerError as exc:
        raise HTTPException(status_code=503, detail=_layer_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=_detector_error_detail(exc)) from exc
    _annotate_image_ocr_findings(document, result.findings)
    lane_result = _apply_surfacing_lanes_to_result(result, tenant)
    result.privacy_ledger = image_privacy_ledger + list(result.privacy_ledger)
    degraded_modes.extend(list(getattr(result, "degraded_modes", []) or []))
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)

    t_anonymize_start = time.perf_counter()
    anonymization = DeterministicAnonymizer(include_mnpi_scalars=req.include_mnpi_scalars).anonymize(
        text=document.text,
        findings=result.findings,
    )
    redacted_images, redaction_degraded_modes = redacted_image_artifacts(
        list(getattr(document, "image_candidates", []) or []),
        list(getattr(document, "image_text_spans", []) or []),
        [(replacement.start_char, replacement.end_char) for replacement in anonymization.replacements],
    )
    degraded_modes.extend(redaction_degraded_modes)
    redacted_document, document_redaction_degraded_modes = redacted_document_artifact(
        original_data=getattr(document, "original_data", None),
        filename=document.filename,
        mime_type=document.mime_type,
        candidates=list(getattr(document, "image_candidates", []) or []),
        spans=list(getattr(document, "image_text_spans", []) or []),
        replacement_spans=[
            (replacement.start_char, replacement.end_char)
            for replacement in anonymization.replacements
        ],
    )
    degraded_modes.extend(document_redaction_degraded_modes)
    timings_ms[timing_key] = round((time.perf_counter() - t_anonymize_start) * 1000.0, 3)

    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    review_response = _build_review_response(
        req=req,
        request_id=request_id,
        document=document,
        result=result,
        timings_ms=timings_ms,
        degraded_modes=degraded_modes,
        visible_findings=lane_result.visible_findings,
        lane_suppressed_findings=(
            lane_result.suppressed_findings if _can_view_lane_suppressed(tenant) else []
        ),
        lane_suppressed_count=lane_result.suppressed_count,
    )
    _persist_policy_decision_event(
        request_id=request_id,
        document_text=document.text,
        policy_decision=review_response.policy_decision,
        finding_count=len(result.findings),
        degraded_modes=degraded_modes,
        tenant_id=tenant.storage_tenant_id,
    )
    return {
        "document": document,
        "result": result,
        "anonymization": anonymization,
        "redacted_images": redacted_images,
        "redacted_document": redacted_document,
        "document_hash": _compute_document_hash(document.text),
        "review_response": review_response,
        "timings_ms": timings_ms,
        "degraded_modes": degraded_modes,
    }


def _persist_pseudonymization_mapping(
    *,
    req: PseudonymizeRequest,
    request_id: str | None,
    tenant: TenantContext,
    document_hash: str,
    mapping: list[Any],
) -> bool:
    if not req.persist_mapping or not _review_persistence_enabled() or not mapping:
        return False
    try:
        _save_persisted_mapping(
            document_hash=document_hash,
            mapping=[
                {
                    "placeholder": entry.placeholder,
                    "entity_type": entry.entity_type,
                    "original_text": entry.original_text,
                    "occurrence_count": entry.occurrence_count,
                }
                for entry in mapping
            ],
            tenant_id=tenant.storage_tenant_id,
        )
        return True
    except SubjectIndexError as exc:
        log_backend_event(logging.WARNING, event="mapping_subject_index_failed", error=str(exc))
        emit_security_event(
            action="mapping_persist",
            outcome="failed",
            request_id=request_id,
            details={"error": str(exc), "document_hash": document_hash},
            settings=current_runtime_settings().siem,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"subject-index persistence failed closed: {exc}",
                "degraded_modes": [
                    _degraded_mode("subject_index", "failed_closed", str(exc), {"document_hash": document_hash})
                ],
            },
        ) from exc
    except (OSError, MappingStoreError, mapping_store_mod.MappingStoreError) as exc:
        log_backend_event(logging.WARNING, event="mapping_persist_failed", error=str(exc))
        emit_security_event(
            action="mapping_persist",
            outcome="failed",
            request_id=request_id,
            details={"error": str(exc), "document_hash": document_hash},
            settings=current_runtime_settings().siem,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"mapping-store persistence failed closed: {exc}",
                "degraded_modes": [
                    _degraded_mode("mapping_store", "failed_closed", str(exc), {"document_hash": document_hash})
                ],
            },
        ) from exc


def _pseudonymization_mapping_entries(anonymization: Any) -> list[AnonymizationMappingEntryResponse]:
    return [
        AnonymizationMappingEntryResponse(
            placeholder=entry.placeholder,
            entity_type=entry.entity_type,
            original_text=entry.original_text,
            occurrence_count=entry.occurrence_count,
        )
        for entry in anonymization.mapping
    ]


def _pseudonymization_replacements(anonymization: Any) -> list[AnonymizationReplacementResponse]:
    return [
        AnonymizationReplacementResponse(
            finding_id=replacement.finding_id,
            placeholder=replacement.placeholder,
            entity_type=replacement.entity_type,
            original_text=replacement.original_text,
            start_char=replacement.start_char,
            end_char=replacement.end_char,
        )
        for replacement in anonymization.replacements
    ]


def _placeholder_replacements(anonymization: Any) -> list[PlaceholderReplacementResponse]:
    return [
        PlaceholderReplacementResponse(
            finding_id=replacement.finding_id,
            placeholder=replacement.placeholder,
            entity_type=replacement.entity_type,
            start_char=replacement.start_char,
            end_char=replacement.end_char,
        )
        for replacement in anonymization.replacements
    ]


def _opaque_redactions(*, text: str, anonymization: Any) -> tuple[str, list[OpaqueRedactionResponse]]:
    redacted_text = text
    redactions: list[OpaqueRedactionResponse] = []
    ordered = sorted(anonymization.replacements, key=lambda item: (item.start_char, item.end_char))
    marker_by_placeholder: OrderedDict[str, str] = OrderedDict()
    for replacement in ordered:
        marker = marker_by_placeholder.get(replacement.placeholder)
        if marker is None:
            marker = f"[REDACTED_{len(marker_by_placeholder) + 1}]"
            marker_by_placeholder[replacement.placeholder] = marker
        redactions.append(
            OpaqueRedactionResponse(
                finding_id=replacement.finding_id,
                marker=marker,
                start_char=replacement.start_char,
                end_char=replacement.end_char,
            )
        )
    for replacement, redaction in sorted(
        zip(ordered, redactions, strict=True),
        key=lambda pair: pair[0].start_char,
        reverse=True,
    ):
        redacted_text = (
            redacted_text[: replacement.start_char]
            + redaction.marker
            + redacted_text[replacement.end_char :]
        )
    return redacted_text, redactions


def _run_pseudonymize_sync(
    req: PseudonymizeRequest, request_id: str | None, tenant: TenantContext
) -> PseudonymizeResponse:
    payload = _run_placeholder_review_sync(req, request_id, tenant, timing_key="pseudonymize")
    anonymization = payload["anonymization"]
    document_hash = payload["document_hash"]
    mapping_persisted = _persist_pseudonymization_mapping(
        req=req,
        request_id=request_id,
        tenant=tenant,
        document_hash=document_hash,
        mapping=list(anonymization.mapping),
    )
    response = PseudonymizeResponse(
        **payload["review_response"].model_dump(mode="python"),
        privacy_operation="pseudonymize",
        pseudonymized_text=anonymization.anonymized_text,
        anonymized_text=anonymization.anonymized_text,
        document_hash=document_hash,
        mapping_persisted=mapping_persisted,
        mapping=_pseudonymization_mapping_entries(anonymization),
        replacements=_pseudonymization_replacements(anonymization),
        redacted_images=payload["redacted_images"],
        redacted_document=payload["redacted_document"],
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/pseudonymize",
            classification=payload["result"].overall_risk.value,
            cache_status="disabled",
            degraded=bool(payload["degraded_modes"]),
            duration_seconds=payload["timings_ms"]["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event="pseudonymize_summary",
        request_id=request_id,
        classification=payload["result"].overall_risk.value,
        pii_score=payload["result"].pii_score,
        mnpi_score=payload["result"].mnpi_score,
        finding_count=len(payload["result"].findings),
        replacement_count=len(anonymization.replacements),
        jurisdictions_applied=payload["result"].jurisdictions_applied,
        timings_ms=payload["timings_ms"],
    )
    emit_privacy_ledger_events(
        payload["result"].privacy_ledger,
        request_id=request_id,
        endpoint="/pseudonymize",
        settings=current_runtime_settings().siem,
    )
    return response


def _run_anonymize_sync(req: AnonymizeRequest, request_id: str | None, tenant: TenantContext) -> AnonymizeResponse:
    payload = _run_placeholder_review_sync(req, request_id, tenant, timing_key="anonymize")
    anonymization = payload["anonymization"]
    response = AnonymizeResponse(
        **payload["review_response"].model_dump(mode="python"),
        privacy_operation="anonymize",
        anonymization_mode="placeholder_only",
        anonymized_text=anonymization.anonymized_text,
        document_hash=payload["document_hash"],
        mapping_persisted=False,
        replacements=_placeholder_replacements(anonymization),
        redacted_images=payload["redacted_images"],
        redacted_document=payload["redacted_document"],
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/anonymize",
            classification=payload["result"].overall_risk.value,
            cache_status="disabled",
            degraded=bool(payload["degraded_modes"]),
            duration_seconds=payload["timings_ms"]["total"] / 1000.0,
        )
    log_backend_event(
        logging.INFO,
        event="anonymize_summary",
        request_id=request_id,
        classification=payload["result"].overall_risk.value,
        pii_score=payload["result"].pii_score,
        mnpi_score=payload["result"].mnpi_score,
        finding_count=len(payload["result"].findings),
        replacement_count=len(anonymization.replacements),
        jurisdictions_applied=payload["result"].jurisdictions_applied,
        timings_ms=payload["timings_ms"],
    )
    emit_privacy_ledger_events(
        payload["result"].privacy_ledger,
        request_id=request_id,
        endpoint="/anonymize",
        settings=current_runtime_settings().siem,
    )
    return response


def _run_redact_sync(req: RedactRequest, request_id: str | None, tenant: TenantContext) -> RedactResponse:
    payload = _run_placeholder_review_sync(req, request_id, tenant, timing_key="redact")
    redacted_text, redactions = _opaque_redactions(
        text=payload["document"].text,
        anonymization=payload["anonymization"],
    )
    base_response = payload["review_response"].model_dump(mode="python")
    base_response["suggestions"] = []
    response = RedactResponse(
        **base_response,
        privacy_operation="redact",
        redaction_style="opaque_text_marker",
        redacted_text=redacted_text,
        document_hash=payload["document_hash"],
        mapping_persisted=False,
        redactions=redactions,
        redacted_images=payload["redacted_images"],
        redacted_document=payload["redacted_document"],
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/redact",
            classification=payload["result"].overall_risk.value,
            cache_status="disabled",
            degraded=bool(payload["degraded_modes"]),
            duration_seconds=payload["timings_ms"]["total"] / 1000.0,
        )
    log_backend_event(
        logging.INFO,
        event="redact_summary",
        request_id=request_id,
        classification=payload["result"].overall_risk.value,
        pii_score=payload["result"].pii_score,
        mnpi_score=payload["result"].mnpi_score,
        finding_count=len(payload["result"].findings),
        redaction_count=len(redactions),
        jurisdictions_applied=payload["result"].jurisdictions_applied,
        timings_ms=payload["timings_ms"],
    )
    emit_privacy_ledger_events(
        payload["result"].privacy_ledger,
        request_id=request_id,
        endpoint="/redact",
        settings=current_runtime_settings().siem,
    )
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    det_info = configure_determinism()
    log_backend_event(logging.INFO, event="determinism", **det_info)

    settings = resolve_runtime_settings()
    layers = load_config()
    lazy_heavy = settings.startup.lazy_load_heavy
    prewarm_required_layers = settings.startup.prewarm_required_layers
    optional_layers = get_optional_layers()
    fail_on_layer_load_error = settings.startup.fail_on_layer_load_error

    _state["settings"] = settings
    _state["pipeline"] = layers
    _state["optional_layers"] = sorted(optional_layers)
    _state["models"] = {}
    _state["lazy_loaders"] = {}
    _state["load_errors"] = []
    _state["load_lock"] = Lock()
    _state["warming_lock"] = Lock()
    _state["warming_required_layers"] = []
    _state["startup_timings_ms"] = {}
    _state["runtime_layer_errors"] = {}
    _state["runtime_error_lock"] = Lock()
    _state["observability"] = ObservabilityManager()
    _state["cache_cfg"] = {
        "size": settings.response_cache.size,
        "ttl_seconds": settings.response_cache.ttl_seconds,
    }
    _state["response_cache"] = OrderedDict()
    _state["response_cache_lock"] = Lock()
    _state["response_cache_store"] = ResponseCache(**_state["cache_cfg"])

    t_startup_total = time.perf_counter()

    for layer in layers:
        t_layer = time.perf_counter()
        try:
            if layer == "public_evidence":
                evidence_mod = importlib.import_module("junas.external.public_evidence.inference")
                _state["models"]["public_evidence"] = evidence_mod.PublicEvidenceRetriever.load()

            elif layer == "llm_adjudicator":
                llm_mod = importlib.import_module("junas.advisory.llm_adjudicator.inference")
                _state["models"]["llm_adjudicator"] = llm_mod.LocalLLMAdjudicator.load()
            elif layer == "llm_defined_term_extractor":
                helpers_mod = importlib.import_module("junas.advisory.llm_adjudicator.helpers")
                _state["models"]["llm_defined_term_extractor"] = (
                    helpers_mod.build_llm_defined_term_extractor(settings.llm)
                )
            elif layer == "llm_coverage_auditor":
                helpers_mod = importlib.import_module("junas.advisory.llm_adjudicator.helpers")
                _state["models"]["llm_coverage_auditor"] = helpers_mod.build_llm_coverage_auditor(settings.llm)
            else:
                raise ValueError(f"unknown pipeline layer: {layer}")

        except Exception as e:
            record_layer_load_error(layer, e, phase="startup")
            observability = get_observability()
            if observability is not None:
                observability.observe_layer_load(
                    layer=layer,
                    phase="startup",
                    outcome="error",
                    duration_seconds=max(0.0, time.perf_counter() - t_layer),
                )
            log_backend_event(logging.WARNING, event="layer_load_failed", layer=layer, error=str(e))
        finally:
            elapsed_ms = round((time.perf_counter() - t_layer) * 1000.0, 3)
            _state["startup_timings_ms"][layer] = elapsed_ms
            latest_error = _get_latest_load_error(layer)
            if latest_error is None or latest_error.get("phase") != "startup":
                observability = get_observability()
                if observability is not None:
                    observability.observe_layer_load(
                        layer=layer,
                        phase="startup",
                        outcome="success",
                        duration_seconds=elapsed_ms / 1000.0,
                    )

    available_layers = set(_state.get("models", {}).keys()) | set(_state.get("lazy_loaders", {}).keys())
    missing_required_layers = sorted(
        [layer for layer in layers if layer not in optional_layers and layer not in available_layers]
    )
    _state["missing_required_layers"] = missing_required_layers

    _state["startup_timings_ms"]["total"] = round((time.perf_counter() - t_startup_total) * 1000.0, 3)

    log_backend_event(
        logging.INFO,
        event="startup_summary",
        pipeline=layers,
        loaded_layers=sorted(_state.get("models", {}).keys()),
        lazy_layers=sorted(_state.get("lazy_loaders", {}).keys()),
        optional_layers=sorted(optional_layers),
        missing_required_layers=missing_required_layers,
        startup_timings_ms=_state.get("startup_timings_ms", {}),
        load_errors=_state.get("load_errors", []),
        cache_cfg=_state.get("cache_cfg", {}),
        metrics_mode=get_metrics_mode(),
    )

    if missing_required_layers and fail_on_layer_load_error:
        raise RuntimeError(
            f"required layers failed to load: {missing_required_layers}. "
            "Set JUNAS_FAIL_ON_LAYER_LOAD_ERROR=0 to allow degraded startup."
        )

    if lazy_heavy and prewarm_required_layers and not missing_required_layers:
        start_required_layer_prewarm(optional_layers)

    refresh_observability_state()
    yield
    _state.clear()


app = FastAPI(
    title="Junas Document Safety API",
    version="0.1.0",
    summary="API-first PII anonymization and MNPI review service.",
    description=OPENAPI_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    default_response_class=PrettyJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=get_allowed_origin_regex(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def api_request_guard_middleware(request: Request, call_next):
    if request.method.upper() in {"POST", "PUT", "PATCH"}:
        max_bytes = current_runtime_settings().api.max_request_bytes
        raw_length = request.headers.get("content-length", "").strip()
        if raw_length:
            try:
                content_length = int(raw_length)
            except ValueError:
                return PrettyJSONResponse(status_code=400, content={"detail": "invalid Content-Length header"})
            if content_length > max_bytes:
                return PrettyJSONResponse(
                    status_code=413,
                    content={"detail": f"request body exceeds configured limit of {max_bytes} bytes"},
                )
        body = await request.body()
        if len(body) > max_bytes:
            return PrettyJSONResponse(
                status_code=413,
                content={"detail": f"request body exceeds configured limit of {max_bytes} bytes"},
            )

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive
    return await call_next(request)


@app.middleware("http")
async def local_daemon_acl_middleware(request: Request, call_next):
    settings = current_runtime_settings().local_daemon
    if not settings.acl_enabled:
        return await call_next(request)

    origin = request.headers.get("Origin")
    if not origin_allowed(origin, settings.allowed_origins):
        return PrettyJSONResponse(status_code=403, content={"detail": "origin not allowed for local daemon"})

    if request.method.upper() != "OPTIONS" and _local_daemon_protected_path(request.url.path):
        try:
            expected = _local_daemon_token()
        except LocalDaemonAuthError as exc:
            return PrettyJSONResponse(
                status_code=503,
                content={"detail": f"local daemon token not provisioned: {exc}"},
            )
        supplied = request.headers.get(LOCAL_TOKEN_HEADER, "")
        if not expected or not supplied or not _local_daemon_token_valid(supplied, expected):
            return PrettyJSONResponse(status_code=401, content={"detail": "missing or invalid local daemon token"})

    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def pretty_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return PrettyJSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def pretty_validation_exception_handler(request: Request, exc: RequestValidationError):
    return PrettyJSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    t0 = time.perf_counter()
    request_error: Exception | None = None

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        request_error = e
        status_code = 500
        response = None

    dt_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    observability = get_observability()
    if observability is not None:
        observability.observe_http_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=status_code,
            duration_seconds=dt_ms / 1000.0,
        )

    should_log = request.url.path not in SUPPRESSED_REQUEST_LOG_PATHS or status_code >= 400
    if should_log:
        log_backend_event(
            logging.INFO,
            event="request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            latency_ms=dt_ms,
        )
    if status_code >= 400:
        emit_security_event(
            action="http_request",
            outcome="error",
            request_id=request_id,
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
            },
            settings=current_runtime_settings().siem,
        )

    if response is None:
        if request_error is not None:
            raise request_error
        raise RuntimeError("Unhandled request failure")

    response.headers["X-Request-ID"] = request_id
    return response


@app.get(
    "/local/pairing/status",
    tags=["Runtime"],
    summary="Get local daemon pairing status",
    description=(
        "Return whether the local desktop daemon ACL is enabled and whether a local token "
        "has been provisioned. The token value is never returned."
    ),
)
async def local_pairing_status():
    settings = current_runtime_settings().local_daemon
    token_provisioned = False
    token_error = ""
    if settings.acl_enabled:
        try:
            token_provisioned = bool(_local_daemon_token())
        except LocalDaemonAuthError as exc:
            token_error = str(exc)
    return {
        "acl_enabled": settings.acl_enabled,
        "token_provisioned": token_provisioned,
        "allowed_origins": list(settings.allowed_origins),
        "socket_path": settings.socket_path,
        "socket_enabled": bool(settings.socket_path),
        "pending_pairings": len(_pending_pairings()),
        "token_error": token_error,
    }


@app.post(
    "/local/pairing/start",
    response_model=LocalPairingStartResponse,
    tags=["Runtime"],
    summary="Start local daemon pairing",
    description="Create a short-lived first-connect pairing request for browser and Office clients.",
)
async def local_pairing_start(req: LocalPairingStartRequest, request: Request):
    settings = current_runtime_settings().local_daemon
    if not settings.acl_enabled:
        return PrettyJSONResponse(status_code=409, content={"detail": "local daemon ACL is disabled"})
    try:
        secret = _local_daemon_token()
    except LocalDaemonAuthError as exc:
        return PrettyJSONResponse(status_code=503, content={"detail": f"local daemon token not provisioned: {exc}"})

    client_name = req.client_name.strip()[:120] or "junas-local-client"
    origin = request.headers.get("Origin", "")
    pairing_id = uuid.uuid4().hex
    pairing_code = f"{secrets.randbelow(1_000_000):06d}"
    now = int(time.time())
    _pending_pairings()[pairing_id] = {
        "client_name": client_name,
        "code_digest": local_pairing_code_digest(secret, pairing_code),
        "created_at": now,
        "expires_at": now + LOCAL_PAIRING_TTL_SECONDS,
        "origin": origin,
    }
    return {
        "pairing_id": pairing_id,
        "pairing_code": pairing_code,
        "expires_at": now + LOCAL_PAIRING_TTL_SECONDS,
        "token_ttl_seconds": LOCAL_CLIENT_TOKEN_TTL_SECONDS,
    }


@app.post(
    "/local/pairing/approve",
    response_model=LocalPairingApproveResponse,
    tags=["Runtime"],
    summary="Approve local daemon pairing",
    description="Approve a pending pairing request from a desktop/tray process that already has the daemon secret.",
)
async def local_pairing_approve(
    req: LocalPairingCodeRequest,
    x_junas_local_token: str | None = Header(default=None, alias=LOCAL_TOKEN_HEADER),
):
    settings = current_runtime_settings().local_daemon
    if not settings.acl_enabled:
        return PrettyJSONResponse(status_code=409, content={"detail": "local daemon ACL is disabled"})
    try:
        secret = _local_daemon_token()
    except LocalDaemonAuthError as exc:
        return PrettyJSONResponse(status_code=503, content={"detail": f"local daemon token not provisioned: {exc}"})
    if not x_junas_local_token or not hmac.compare_digest(x_junas_local_token, secret):
        return PrettyJSONResponse(status_code=401, content={"detail": "missing or invalid local daemon approval token"})

    pairing_id = req.pairing_id
    pairing_code = req.pairing_code
    entry = _pending_pairings().get(pairing_id)
    if entry is None:
        return PrettyJSONResponse(status_code=404, content={"detail": "pairing request not found"})
    if not hmac.compare_digest(entry["code_digest"], local_pairing_code_digest(secret, pairing_code)):
        return PrettyJSONResponse(status_code=401, content={"detail": "invalid pairing code"})

    client_id = uuid.uuid4().hex
    expires_at = int(time.time()) + LOCAL_CLIENT_TOKEN_TTL_SECONDS
    entry["approved"] = True
    entry["client_id"] = client_id
    entry["client_token"] = sign_local_client_token(
        secret,
        client_id=client_id,
        client_name=str(entry["client_name"]),
        origin=str(entry["origin"]),
        ttl_seconds=LOCAL_CLIENT_TOKEN_TTL_SECONDS,
    )
    entry["client_token_expires_at"] = expires_at
    return {
        "approved": True,
        "pairing_id": pairing_id,
        "client_id": client_id,
        "expires_at": expires_at,
    }


@app.post(
    "/local/pairing/claim",
    response_model=LocalPairingClaimResponse,
    tags=["Runtime"],
    summary="Claim approved local daemon pairing",
    description="Return the signed local client token after the desktop/tray approval step completes.",
)
async def local_pairing_claim(req: LocalPairingCodeRequest):
    settings = current_runtime_settings().local_daemon
    if not settings.acl_enabled:
        return PrettyJSONResponse(status_code=409, content={"detail": "local daemon ACL is disabled"})
    try:
        secret = _local_daemon_token()
    except LocalDaemonAuthError as exc:
        return PrettyJSONResponse(status_code=503, content={"detail": f"local daemon token not provisioned: {exc}"})

    pairing_id = req.pairing_id
    pairing_code = req.pairing_code
    store = _pending_pairings()
    entry = store.get(pairing_id)
    if entry is None:
        return PrettyJSONResponse(status_code=404, content={"detail": "pairing request not found"})
    if not hmac.compare_digest(entry["code_digest"], local_pairing_code_digest(secret, pairing_code)):
        return PrettyJSONResponse(status_code=401, content={"detail": "invalid pairing code"})
    if not entry.get("approved"):
        return PrettyJSONResponse(status_code=202, content={"approved": False, "expires_at": entry["expires_at"]})

    token = str(entry["client_token"])
    client_id = str(entry["client_id"])
    expires_at = int(entry["client_token_expires_at"])
    store.pop(pairing_id, None)
    return {
        "approved": True,
        "client_id": client_id,
        "client_token": token,
        "expires_at": expires_at,
        "token_type": "junas-local-client+jwt",
    }


@app.get(
    "/demo",
    response_class=HTMLResponse,
    tags=["Runtime"],
    summary="Serve deterministic public demo playground",
    description="Serves a static deterministic-only playground when JUNAS_PUBLIC_DEMO_ENABLED=1.",
)
async def public_demo_page():
    if not _public_demo_enabled():
        raise HTTPException(status_code=404, detail="public demo is disabled")
    return HTMLResponse(PUBLIC_DEMO_HTML)


@app.post(
    "/demo/review",
    response_model=ReviewResponse,
    tags=["Runtime"],
    summary="Run deterministic public demo review",
    description=(
        "Unauthenticated public-demo review path. Enabled only with JUNAS_PUBLIC_DEMO_ENABLED=1. "
        "Forces strict text-only review, caps request size, rate-limits by client, and persists nothing."
    ),
)
async def public_demo_review(request: Request):
    if not _public_demo_enabled():
        raise HTTPException(status_code=404, detail="public demo is disabled")
    _enforce_public_demo_rate_limit(request)
    req = _public_demo_review_request(await request.body())
    return await run_in_threadpool(
        _run_public_demo_review_sync,
        req,
        getattr(request.state, "request_id", None),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Runtime"],
    summary="Get runtime health",
    description="Return a lightweight snapshot of active optional runtime helpers.",
)
async def health():
    models = _state.get("models", {})
    return HealthResponse(
        status="ok",
        lexicon_loaded=False,
        model1_loaded=False,
        model2_loaded=False,
        embedding_loaded=False,
        clustering_loaded=False,
        mosaic_loaded=False,
        regression_loaded=False,
        public_evidence_loaded="public_evidence" in models,
        llm_adjudicator_loaded="llm_adjudicator" in models,
        llm_defined_term_extractor_loaded="llm_defined_term_extractor" in models,
        llm_coverage_auditor_loaded="llm_coverage_auditor" in models,
    )


@app.get(
    "/ready",
    response_model=ReadyResponse,
    tags=["Runtime"],
    summary="Get backend readiness",
    description=(
        "Return whether all required configured layers are available and warmed. "
        "This endpoint remains degraded while required lazy layers are still warming."
    ),
)
async def ready():
    ready_state = build_ready_snapshot()
    refresh_observability_state()

    return ReadyResponse(
        status="ok" if ready_state["ready"] else "degraded",
        ready=ready_state["ready"],
        pipeline=ready_state["pipeline"],
        missing_required_layers=ready_state["missing_layers"],
        warming_required_layers=ready_state["warming_layers"],
        reasons=ready_state["reasons"],
    )


@app.get(
    "/diagnostics",
    response_model=DiagnosticsResponse,
    tags=["Runtime"],
    summary="Get runtime diagnostics",
    description=(
        "Return the active pipeline, loaded and lazy layers, startup timings, dependency health, "
        "and accumulated runtime layer failures."
    ),
)
async def diagnostics():
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    refresh_observability_state()
    return DiagnosticsResponse(
        status="ok",
        pipeline=pipeline,
        loaded_layers=sorted(models.keys()),
        lazy_layers=sorted(_state.get("lazy_loaders", {}).keys()),
        warming_required_layers=sorted(_get_warming_required_layers()),
        load_errors=_state.get("load_errors", []),
        startup_timings_ms=_state.get("startup_timings_ms", {}),
        metrics_mode=get_metrics_mode(),
        dependency_status={
            name: DependencyStatusResponse(
                status=status.status,
                configured=status.configured,
                healthy=status.healthy,
                detail=status.detail,
            )
            for name, status in get_dependency_status().items()
        },
        runtime_layer_errors=dict(_state.get("runtime_layer_errors", {})),
    )


@app.get(
    "/metrics",
    tags=["Runtime"],
    summary="Get Prometheus metrics",
    description="Return Prometheus-formatted metrics for HTTP traffic, layer loads, classifications, and dependencies.",
)
async def metrics():
    refresh_observability_state()
    observability = get_observability()
    if observability is None:
        raise HTTPException(status_code=503, detail="observability not initialized")
    return Response(content=observability.render_metrics(), media_type=observability.content_type)


@app.post(
    "/classify",
    response_model=ClassifyResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Classification"],
    summary="Classify one document",
    description=(
        "Classify a single text document through the deterministic review engine. "
        "`include_offending_spans` is retained for older clients; use `findings` for current span evidence."
    ),
)
async def classify(request: Request, req: ClassifyRequest):
    return await run_in_threadpool(_run_classify_sync, req, getattr(request.state, "request_id", None), "/classify")


@app.post(
    "/classify/batch",
    response_model=BatchClassifyResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Classification"],
    summary="Classify multiple documents",
    description=(
        "Process up to 32 classify requests in one HTTP call with bounded in-process concurrency. "
        "Each result preserves the same response shape as `POST /classify`."
    ),
)
async def classify_batch(request: Request, req: BatchClassifyRequest):
    return await run_in_threadpool(_run_batch_classify_sync, req, getattr(request.state, "request_id", None))


@app.post(
    "/review",
    response_model=ReviewResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Review a document before sending",
    description=(
        "Run a pre-send review for PII and MNPI risk over inline text or a base64-encoded text, DOCX, or PDF "
        "document. The endpoint applies source and destination jurisdictions using a strictest-wins policy, "
        "returns localized findings, and suggests redactions or rewrites."
    ),
)
async def review_document(request: Request, req: ReviewRequest):
    return await run_in_threadpool(
        _run_review_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/cite-public-source",
    response_model=CitePublicSourceResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Cite audit-grade public evidence",
    description=(
        "Run audit-grade review and return public-source citations. Each citation requires a source URL, "
        "server retrieval timestamp, and allowed privacy-ledger entry for the outbound evidence query."
    ),
)
async def cite_public_source_document(request: Request, req: CitePublicSourceRequest):
    return await run_in_threadpool(
        _run_cite_public_source_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


def _run_request_approval_sync(
    req: RequestApprovalRequest,
    tenant: TenantContext,
    requester_id: str,
    requester_identity_source: str,
) -> RequestApprovalResponse:
    _ensure_persistence_enabled()
    try:
        result = record_approval_request(
            review_id=req.review_id,
            finding_ids=req.finding_ids,
            required_reviewer_roles=_required_reviewer_roles(),
            required_policy_actor_roles=_required_policy_actor_roles(),
            reason_code=req.reason_code,
            requester_id=requester_id,
            requester_identity_source=requester_identity_source,
            tenant_id=tenant.storage_tenant_id,
        )
    except ReviewSessionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RequestApprovalResponse(**result)


@app.post(
    "/request-approval",
    response_model=RequestApprovalResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Request reviewer approval",
    description=(
        "Record a pending approval request for a prior /review session in the append-only journal. "
        "The response returns the reviewer roles required to complete the downstream approval decision. "
        "Requires JUNAS_REVIEW_PERSIST=1; otherwise 409."
    ),
)
async def request_review_approval(
    request: Request,
    req: RequestApprovalRequest,
    x_reviewer_id: str | None = Header(default=None, alias="X-Reviewer-ID"),
):
    tenant = tenant_context_from_request(request)
    requester_id, requester_identity_source = _resolve_reviewer_identity(
        tenant=tenant,
        x_reviewer_id=x_reviewer_id,
    )
    return await run_in_threadpool(
        _run_request_approval_sync,
        req,
        tenant,
        requester_id,
        requester_identity_source,
    )


@app.post(
    "/redact-pii",
    response_model=RedactPiiResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Redact PII only",
    description=(
        "Run the pre-send PII/MNPI review and return text with deterministic PII replacements only. "
        "MNPI passages remain visible in rewritten_text and flagged in findings; this endpoint does not "
        "call an LLM or persist a reidentification mapping."
    ),
)
async def redact_pii_document(request: Request, req: RedactPiiRequest):
    return await run_in_threadpool(
        _run_redact_pii_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/hold-until-public",
    response_model=HoldUntilPublicResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Hold high-risk MNPI until public",
    description=(
        "Run the pre-send PII/MNPI review and return hold text for high-severity MNPI spans, plus "
        "display-safe user reasons and audit-ready rationale. This endpoint does not call an LLM or "
        "persist a reidentification mapping."
    ),
)
async def hold_until_public_document(request: Request, req: HoldUntilPublicRequest):
    return await run_in_threadpool(
        _run_hold_until_public_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/safe-rewrite",
    response_model=SafeRewriteResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Safely rewrite a document deterministically",
    description=(
        "Run the pre-send PII/MNPI review and return text with deterministic, policy-approved "
        "span replacements. This endpoint does not call an LLM and does not persist a reidentification mapping."
    ),
)
async def safe_rewrite_document(request: Request, req: SafeRewriteRequest):
    return await run_in_threadpool(
        _run_safe_rewrite_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/pseudonymize",
    response_model=PseudonymizeResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Pseudonymize a document before sending",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with deterministic reversible "
        "placeholders plus the local mapping table. When JUNAS_REVIEW_PERSIST=1 and "
        "persist_mapping=true, POST /reidentify can restore by document_hash."
    ),
)
async def pseudonymize_document(request: Request, req: PseudonymizeRequest):
    return await run_in_threadpool(
        _run_pseudonymize_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/anonymize",
    response_model=AnonymizeResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Anonymize a document irreversibly",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with deterministic placeholders "
        "without returning or persisting a mapping. This is irreversible v2: use POST /pseudonymize "
        "when callers need reidentification."
    ),
)
async def anonymize_document(request: Request, req: AnonymizeRequest):
    return await run_in_threadpool(
        _run_anonymize_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


@app.post(
    "/redact",
    response_model=RedactResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Redact a document with opaque markers",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with opaque redaction markers. "
        "The response contains no mapping and no original matched text beyond the review findings."
    ),
)
async def redact_document(request: Request, req: RedactRequest):
    return await run_in_threadpool(
        _run_redact_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


def _infer_scrub_mime_type(filename: str, mime_type: str | None) -> str:
    if mime_type:
        return mime_type.strip().lower()
    lower = filename.lower()
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".png"):
        return "image/png"
    return "application/octet-stream"


def _run_document_scrub_sync(req: DocumentScrubRequest, request_id: str | None) -> DocumentScrubResponse:
    filename = str(req.document_filename or "document")
    mime_type = _infer_scrub_mime_type(filename, req.document_mime_type)
    try:
        data = base64.b64decode(req.document_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="document_base64 must be valid base64") from exc
    try:
        result = scrub_document(data, filename=filename, mime_type=mime_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DocumentScrubResponse(
        request_id=request_id,
        document_base64=base64.b64encode(result.data).decode("ascii"),
        document_filename=result.filename,
        document_mime_type=result.mime_type,
        scrubbed=result.scrubbed,
        actions=[DocumentScrubActionResponse(**action) for action in result.actions],
        metadata_findings=[finding.to_dict() for finding in result.original_findings],
        remaining_warnings=[finding.to_dict() for finding in result.remaining_findings],
    )


@app.post(
    "/documents/scrub",
    response_model=DocumentScrubResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Documents"],
    summary="Scrub document metadata",
    description=(
        "Remove supported metadata leakage from DOCX, PDF, JPEG, or PNG payloads. "
        "Visible document text is preserved where practical; metadata findings and scrub actions are returned."
    ),
)
async def scrub_document_metadata(request: Request, req: DocumentScrubRequest):
    return await run_in_threadpool(_run_document_scrub_sync, req, getattr(request.state, "request_id", None))


def _run_reidentify_sync(req: ReidentifyRequest, request_id: str | None, tenant: TenantContext) -> ReidentifyResponse:
    t_total_start = time.perf_counter()

    mapping_dicts: list[dict[str, Any]]
    if req.mapping:
        mapping_dicts = [entry.model_dump() for entry in req.mapping]
    else:
        if not _review_persistence_enabled():
            raise HTTPException(
                status_code=409,
                detail="review persistence is disabled; supply inline mapping or set JUNAS_REVIEW_PERSIST=1",
            )
        # `mapping` is empty and the model validator already guaranteed `document_hash` is present.
        try:
            persisted = _load_persisted_mapping(req.document_hash or "", tenant_id=tenant.storage_tenant_id)
        except (MappingStoreError, mapping_store_mod.MappingStoreError) as exc:
            emit_security_event(
                action="mapping_reidentify",
                outcome="failed",
                request_id=request_id,
                details={"error": str(exc), "document_hash": req.document_hash or ""},
                settings=current_runtime_settings().siem,
            )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not persisted:
            raise HTTPException(
                status_code=404,
                detail=(
                    "no persisted mapping for document_hash; supply `mapping` inline or call "
                    "/pseudonymize first with JUNAS_REVIEW_PERSIST=1 and persist_mapping=true"
                ),
            )
        mapping_dicts = persisted

    text, count = _reidentify_text(anonymized_text=req.anonymized_text, mapping=mapping_dicts)
    total_ms = round((time.perf_counter() - t_total_start) * 1000.0, 3)
    return ReidentifyResponse(
        request_id=request_id,
        text=text,
        replacement_count=count,
        timings_ms={"reidentify": total_ms, "total": total_ms},
    )


@app.post(
    "/reidentify",
    response_model=ReidentifyResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Reidentify previously anonymized text",
    description=(
        "Deterministic inverse of /pseudonymize. Takes anonymized_text plus the caller-supplied "
        "mapping (typically the mapping field from a prior /pseudonymize response) or a persisted "
        "document_hash and restores the original spans. Irreversible /anonymize and /redact outputs "
        "cannot be restored by document_hash."
    ),
)
async def reidentify_document(request: Request, req: ReidentifyRequest):
    return await run_in_threadpool(
        _run_reidentify_sync,
        req,
        getattr(request.state, "request_id", None),
        tenant_context_from_request(request),
    )


def _ensure_persistence_enabled() -> None:
    if not _review_persistence_enabled():
        raise HTTPException(
            status_code=409,
            detail="review persistence is disabled; set JUNAS_REVIEW_PERSIST=1 to enable",
        )


def _resolve_reviewer_identity(
    *,
    tenant: TenantContext,
    x_reviewer_id: str | None,
) -> tuple[str, str]:
    if tenant.enabled:
        reviewer_id = (tenant.subject or tenant.tenant_id or "").strip()[:256]
        return reviewer_id, tenant.auth_mode if tenant.auth_mode in {"api_key", "jwt"} else "authenticated"
    dev_reviewer_id = (x_reviewer_id or "").strip()
    if _is_truthy(os.environ.get("JUNAS_DEV_AUTH")) and dev_reviewer_id:
        return dev_reviewer_id[:256], "dev_header"
    return "", "none"


def _required_reviewer_roles() -> list[str]:
    ordered = [role for role in APPROVAL_REVIEWER_ROLE_ORDER if role in DECISION_ROLES]
    extras = sorted(role for role in DECISION_ROLES if role not in ordered)
    return ordered + extras


def _required_policy_actor_roles() -> list[str]:
    return list(DEFAULT_POLICY_PROFILE.reviewer_override_roles)


def _session_finding_state(finding: dict[str, Any], decision: dict[str, Any] | None) -> ReviewSessionFindingState:
    return ReviewSessionFindingState(
        id=finding["id"],
        category=finding["category"],
        rule=finding["rule"],
        severity=finding["severity"],
        matched_text=finding["matched_text"],
        start_char=finding["start_char"],
        end_char=finding["end_char"],
        source=finding.get("source", "text"),
        image_locator=finding.get("image_locator"),
        image_ocr_confidence=finding.get("image_ocr_confidence"),
        image_ocr_regions=finding.get("image_ocr_regions", []),
        metadata=finding.get("metadata", {}),
        decision=decision["action"] if decision else None,
        decision_seq=decision["seq"] if decision else None,
        decision_ts=decision["ts"] if decision else None,
        decision_reviewer_id=decision.get("reviewer_id") if decision else None,
        decision_reviewer_identity_source=(
            decision.get("reviewer_identity_source") if decision else None
        ),
    )


def _session_approval_state(approval: dict[str, Any]) -> ReviewApprovalRequestState:
    return ReviewApprovalRequestState(
        approval_status="pending",
        finding_ids=list(approval.get("finding_ids", [])),
        required_reviewer_roles=list(approval.get("required_reviewer_roles", [])),
        required_policy_actor_roles=list(approval.get("required_policy_actor_roles", [])),
        reason_code=approval.get("reason_code", "policy_block"),
        requester_id=approval.get("requester_id", ""),
        requester_identity_source=approval.get("requester_identity_source", "none"),
        seq=approval["seq"],
        ts=approval["ts"],
    )


def _serialize_session_state(
    state: dict[str, Any],
    *,
    include_lane_suppressed: bool = False,
) -> ReviewSessionStateResponse:
    from junas.review.surfacing_lane import partition_persisted_findings

    decisions_by_id = {d["finding_id"]: d for d in state.get("decisions", [])}
    visible_raw, suppressed_raw = partition_persisted_findings(list(state.get("findings", [])))
    findings = [
        _session_finding_state(finding, decisions_by_id.get(finding.get("id")))
        for finding in visible_raw
    ]
    suppressed_findings = [
        _session_finding_state(finding, decisions_by_id.get(finding.get("id")))
        for finding in suppressed_raw
    ] if include_lane_suppressed else []
    return ReviewSessionStateResponse(
        review_id=state["review_id"],
        text_hash=state.get("text_hash") or "",
        document_type=state.get("document_type") or "generic",
        source_jurisdiction=state.get("source_jurisdiction") or "SG",
        destination_jurisdiction=state.get("destination_jurisdiction") or "SG",
        findings=findings,
        lane_suppressed_count=len(suppressed_raw),
        lane_suppressed_findings=suppressed_findings,
        decisions_recorded=len(state.get("decisions", [])),
        audit_exports=list(state.get("audit_exports", [])),
        pending_approvals=[
            _session_approval_state(approval)
            for approval in state.get("approval_requests", [])
            if approval.get("approval_status") == "pending"
        ],
        approvals_requested=len(state.get("approval_requests", [])),
    )


@app.post(
    "/review/{review_id}/decision",
    response_model=ReviewDecisionResponse,
    dependencies=[Depends(require_decision_access)],
    tags=["Anonymization"],
    summary="Record a per-finding decision",
    description=(
        "Append a reviewer decision for a finding from a prior /review response. "
        "Accepted actions are documented in docs/policy/journal-replay.md. "
        "Decisions are persisted to the append-only HMAC-chained journal under JUNAS_JOURNAL_DIR. "
        "Reviewer identity is resolved from the authenticated JWT/API-key principal. "
        "X-Reviewer-ID is accepted only when JUNAS_DEV_AUTH=1 for local development; "
        "the request body `reviewer_id` field is retained for compatibility but is not authoritative. "
        "Requires JUNAS_REVIEW_PERSIST=1; otherwise 409."
    ),
)
async def post_review_decision(
    request: Request,
    review_id: str,
    req: ReviewDecisionRequest,
    x_reviewer_id: str | None = Header(default=None, alias="X-Reviewer-ID"),
):
    _ensure_persistence_enabled()
    tenant = tenant_context_from_request(request)
    resolved_reviewer_id, reviewer_identity_source = _resolve_reviewer_identity(
        tenant=tenant,
        x_reviewer_id=x_reviewer_id,
    )
    try:
        result = record_decision(
            review_id=review_id,
            decision=Decision(
                finding_id=req.finding_id,
                action=req.action,
                replacement_text=req.replacement_text,
                rationale=req.rationale,
                reviewer_id=resolved_reviewer_id,
                reviewer_identity_source=reviewer_identity_source,
            ),
            tenant_id=tenant.storage_tenant_id,
        )
    except ReviewSessionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewDecisionResponse(**result)


@app.get(
    "/review/{review_id}",
    response_model=ReviewSessionStateResponse,
    dependencies=[Depends(require_audit_access)],
    tags=["Anonymization"],
    summary="Inspect review session state",
    description=(
        "Reconstruct the current state of a review session from the journal: findings merged "
        "with the most recent decision per finding. Requires JUNAS_REVIEW_PERSIST=1."
    ),
)
async def get_review_session(request: Request, review_id: str):
    _ensure_persistence_enabled()
    tenant = tenant_context_from_request(request)
    state = get_session_state(review_id=review_id, tenant_id=tenant.storage_tenant_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown review_id: {review_id}")
    return _serialize_session_state(state, include_lane_suppressed=_can_view_lane_suppressed(tenant))


if __name__ == "__main__":
    import uvicorn

    filtered_args = []
    i = 0
    while i < len(sys.argv):
        if sys.argv[i] == "--layers":
            i += 2
        else:
            filtered_args.append(sys.argv[i])
            i += 1
    sys.argv = filtered_args

    uvicorn.run("junas.backend.main:app", host="0.0.0.0", port=8000, reload=True)
