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
from dataclasses import replace
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from kaypoh.anonymize import (
    DeterministicAnonymizer,
    MappingStoreError,
)
from kaypoh.anonymize import (
    compute_document_hash as _compute_document_hash,
)
from kaypoh.anonymize import (
    load_mapping as _load_persisted_mapping,
)
from kaypoh.anonymize import (
    reidentify as _reidentify_text,
)
from kaypoh.anonymize import (
    save_mapping as _save_persisted_mapping,
)
from kaypoh.backend.auth import (
    AUDIT_ROLES,
    DECISION_ROLES,
    DISABLED_TENANT_CONTEXT,
    REVIEW_ROLES,
    AuthFailure,
    TenantContext,
    require_roles,
    resolve_tenant_context,
)
from kaypoh.backend.cache import ResponseCache
from kaypoh.backend.local_auth import (
    LOCAL_TOKEN_HEADER,
    LocalDaemonAuthError,
    local_pairing_code_digest,
    origin_allowed,
    resolve_local_daemon_token,
    sign_local_client_token,
    verify_local_client_token,
)
from kaypoh.backend.observability import DependencyStatus, ObservabilityManager, get_metrics_mode
from kaypoh.backend.schemas import (
    AnonymizationMappingEntryResponse,
    AnonymizationReplacementResponse,
    AnonymizeRequest,
    AnonymizeResponse,
    BatchClassifyRequest,
    BatchClassifyResponse,
    Classification,
    ClassifyRequest,
    ClassifyResponse,
    DependencyStatusResponse,
    DiagnosticsResponse,
    DocumentScrubActionResponse,
    DocumentScrubRequest,
    DocumentScrubResponse,
    HealthResponse,
    LLMAdjudicationResponse,
    LocalPairingApproveResponse,
    LocalPairingClaimResponse,
    LocalPairingCodeRequest,
    LocalPairingStartRequest,
    LocalPairingStartResponse,
    ObservabilityResponse,
    OpaqueRedactionResponse,
    PlaceholderReplacementResponse,
    PrivacyLedgerEntryResponse,
    PseudonymizeRequest,
    PseudonymizeResponse,
    PublicEvidenceResponse,
    ReadyResponse,
    RedactRequest,
    RedactResponse,
    ReidentifyRequest,
    ReidentifyResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewDocumentMetadataResponse,
    ReviewFindingResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewSessionFindingState,
    ReviewSessionStateResponse,
    ReviewSuggestionResponse,
)
from kaypoh.backend.siem import emit_privacy_ledger_events, emit_security_event
from kaypoh.configs.runtime import RuntimeSettings, get_runtime_settings
from kaypoh.external.privacy_guard import PrivacyGuard
from kaypoh.helper.determinism import configure_determinism
from kaypoh.review.decisions import (
    Decision,
    ReviewSessionError,
    get_session_state,
    record_decision,
    start_review_session,
)
from kaypoh.review.document import extract_review_document
from kaypoh.review.engine import PreSendReviewEngine, ReviewLayerError
from kaypoh.review.image_scan import (
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
from kaypoh.review.metadata import scrub_document
from kaypoh.review.subject_index import SubjectIndexError, index_review_findings, require_subject_index_key

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("kaypoh.backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

_state: dict[str, Any] = {}

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}
LANE_SUPPRESSED_VIEW_ROLES = frozenset({"auditor", "admin"})

SUPPRESSED_REQUEST_LOG_PATHS = {"/health", "/ready", "/metrics"}
SPAN_CONTEXT_CHARS = 48
LOCAL_PAIRING_TTL_SECONDS = 300
LOCAL_CLIENT_TOKEN_TTL_SECONDS = 90 * 24 * 60 * 60
LOCAL_DAEMON_PROTECTED_PATHS = {
    "/anonymize",
    "/classify",
    "/classify/batch",
    "/documents/scrub",
    "/pseudonymize",
    "/redact",
    "/reidentify",
    "/review",
}
LOCAL_DAEMON_PROTECTED_PREFIXES = ("/review/",)
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
Kaypoh is an API-first pre-send safety engine for PII anonymization and MNPI review.

Key behaviors:

- `POST /pseudonymize` extracts inline text or text/DOCX/PDF payloads, runs the
  PII/MNPI review stack, and returns deterministic placeholders plus a local
  mapping table for reversible downstream analysis.
- `POST /anonymize` returns irreversible placeholder-only output with no mapping.
- `POST /redact` returns irreversible opaque markers and no original matched text
  in redaction findings.
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


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
            from kaypoh.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

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
                from kaypoh.advisory.llm_adjudicator.helpers import (
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

    thread = Thread(target=_runner, name="kaypoh-prewarm", daemon=True)
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

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="kaypoh-batch") as executor:
        results = list(executor.map(_classify_batch_item, enumerate(req.items)))
    return BatchClassifyResponse(results=results)


def _build_review_engine() -> PreSendReviewEngine:
    settings = current_runtime_settings()

    public_evidence = get_layer_model("public_evidence")
    if public_evidence is None and settings.public_evidence.enabled:
        from kaypoh.external.privacy_guard import PrivacyGuard
        from kaypoh.external.public_evidence.inference import PublicEvidenceRetriever

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
        from kaypoh.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

        llm_adjudicator = LocalLLMAdjudicator(settings.llm)

    # audit_grade-only helper: catches preamble defined-term patterns the regex misses.
    # surfaced as a layer model so tests / deployments can swap implementations without
    # touching the engine. when unwired, engine falls through to the deterministic regex.
    llm_defined_term_extractor = get_layer_model("llm_defined_term_extractor")
    if llm_defined_term_extractor is None and settings.llm_helpers.defined_terms_enabled:
        from kaypoh.advisory.llm_adjudicator.helpers import build_llm_defined_term_extractor

        llm_defined_term_extractor = build_llm_defined_term_extractor(settings.llm)
    # audit_grade-only inverse-audit helper. output is journaled as coverage_warning
    # events and promoted to capped origin=llm findings by the engine.
    llm_coverage_auditor = get_layer_model("llm_coverage_auditor")
    if llm_coverage_auditor is None and settings.llm_helpers.coverage_audit_enabled:
        from kaypoh.advisory.llm_adjudicator.helpers import build_llm_coverage_auditor

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
        if "reviewed text layer only" in warning:
            modes.append(_degraded_mode("image_ocr", "skipped", warning))
        if "page(s) for configured image OCR" in warning:
            modes.append(_degraded_mode("image_ocr", "page_rendered", warning))
    return modes


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
    return ReviewResponse(
        request_id=request_id,
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
        degraded_modes=list(degraded_modes or []),
        timings_ms=timings_ms,
    )


def _review_persistence_enabled() -> bool:
    return _is_truthy(os.environ.get("KAYPOH_REVIEW_PERSIST"), default=False)


def _persist_coverage_warnings(
    *,
    request_id: str | None,
    warnings: list[Any],
    tenant_id: str | None = None,
) -> None:
    """Journal each coverage warning. LLM warnings also have capped findings in the session."""
    if not _review_persistence_enabled() or not request_id or not warnings:
        return
    from kaypoh.review.decisions import EVENT_COVERAGE_WARNING
    from kaypoh.review.journal import append_event

    for warning in warnings:
        append_event(
            event_type=EVENT_COVERAGE_WARNING,
            review_id=request_id,
            payload=dict(warning),
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
        from kaypoh.review.surfacing_lane import SurfacingLaneError, apply_surfacing_lanes

        return apply_surfacing_lanes(result.findings, tenant_id=tenant.storage_tenant_id)
    except SurfacingLaneError as exc:
        detail = _layer_error_detail(ReviewLayerError("surfacing_lane", str(exc)))
        raise HTTPException(status_code=503, detail=detail) from exc


def _run_review_sync(req: ReviewRequest, request_id: str | None, tenant: TenantContext) -> ReviewResponse:
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
        raise HTTPException(status_code=422, detail=_image_scan_error_detail(exc)) from exc
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

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/review",
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=bool(degraded_modes),
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event="review_summary",
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
        endpoint="/review",
        settings=current_runtime_settings().siem,
    )
    return response


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
        raise HTTPException(status_code=422, detail=_image_scan_error_detail(exc)) from exc
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
    except (OSError, MappingStoreError) as exc:
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
                evidence_mod = importlib.import_module("kaypoh.external.public_evidence.inference")
                _state["models"]["public_evidence"] = evidence_mod.PublicEvidenceRetriever.load()

            elif layer == "llm_adjudicator":
                llm_mod = importlib.import_module("kaypoh.advisory.llm_adjudicator.inference")
                _state["models"]["llm_adjudicator"] = llm_mod.LocalLLMAdjudicator.load()
            elif layer == "llm_defined_term_extractor":
                helpers_mod = importlib.import_module("kaypoh.advisory.llm_adjudicator.helpers")
                _state["models"]["llm_defined_term_extractor"] = (
                    helpers_mod.build_llm_defined_term_extractor(settings.llm)
                )
            elif layer == "llm_coverage_auditor":
                helpers_mod = importlib.import_module("kaypoh.advisory.llm_adjudicator.helpers")
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
            "Set KAYPOH_FAIL_ON_LAYER_LOAD_ERROR=0 to allow degraded startup."
        )

    if lazy_heavy and prewarm_required_layers and not missing_required_layers:
        start_required_layer_prewarm(optional_layers)

    refresh_observability_state()
    yield
    _state.clear()


app = FastAPI(
    title="Kaypoh Document Safety API",
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    client_name = req.client_name.strip()[:120] or "kaypoh-local-client"
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
    x_kaypoh_local_token: str | None = Header(default=None, alias=LOCAL_TOKEN_HEADER),
):
    settings = current_runtime_settings().local_daemon
    if not settings.acl_enabled:
        return PrettyJSONResponse(status_code=409, content={"detail": "local daemon ACL is disabled"})
    try:
        secret = _local_daemon_token()
    except LocalDaemonAuthError as exc:
        return PrettyJSONResponse(status_code=503, content={"detail": f"local daemon token not provisioned: {exc}"})
    if not x_kaypoh_local_token or not hmac.compare_digest(x_kaypoh_local_token, secret):
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
        "token_type": "kaypoh-local-client+jwt",
    }


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
    "/pseudonymize",
    response_model=PseudonymizeResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Pseudonymize a document before sending",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with deterministic reversible "
        "placeholders plus the local mapping table. When KAYPOH_REVIEW_PERSIST=1 and "
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
        # `mapping` is empty and the model validator already guaranteed `document_hash` is present.
        try:
            persisted = _load_persisted_mapping(req.document_hash or "", tenant_id=tenant.storage_tenant_id)
        except MappingStoreError as exc:
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
                    "/pseudonymize first with KAYPOH_REVIEW_PERSIST=1 and persist_mapping=true"
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
            detail="review persistence is disabled; set KAYPOH_REVIEW_PERSIST=1 to enable",
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
    if _is_truthy(os.environ.get("KAYPOH_DEV_AUTH")) and dev_reviewer_id:
        return dev_reviewer_id[:256], "dev_header"
    return "", "none"


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


def _serialize_session_state(
    state: dict[str, Any],
    *,
    include_lane_suppressed: bool = False,
) -> ReviewSessionStateResponse:
    from kaypoh.review.surfacing_lane import partition_persisted_findings

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
    )


@app.post(
    "/review/{review_id}/decision",
    response_model=ReviewDecisionResponse,
    dependencies=[Depends(require_decision_access)],
    tags=["Anonymization"],
    summary="Record a per-finding decision",
    description=(
        "Append an accept | reject | rewrite decision for a finding from a prior /review response. "
        "Decisions are persisted to the append-only HMAC-chained journal under KAYPOH_JOURNAL_DIR. "
        "Reviewer identity is resolved from the authenticated JWT/API-key principal. "
        "X-Reviewer-ID is accepted only when KAYPOH_DEV_AUTH=1 for local development; "
        "the request body `reviewer_id` field is retained for compatibility but is not authoritative. "
        "Requires KAYPOH_REVIEW_PERSIST=1; otherwise 409."
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
        "with the most recent decision per finding. Requires KAYPOH_REVIEW_PERSIST=1."
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

    uvicorn.run("kaypoh.backend.main:app", host="0.0.0.0", port=8000, reload=True)
