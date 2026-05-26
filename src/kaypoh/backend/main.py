import argparse
import base64
import bisect
import hashlib
import importlib
import json
import logging
import os
import sys
import time
import uuid
from _thread import LockType
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
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
    ObservabilityResponse,
    PrivacyLedgerEntryResponse,
    PublicEvidenceResponse,
    ReadyResponse,
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
from kaypoh.helper.determinism import configure_determinism
from kaypoh.review.decisions import (
    Decision,
    ReviewSessionError,
    get_session_state,
    record_decision,
    start_review_session,
)
from kaypoh.review.document import extract_review_document
from kaypoh.review.engine import PreSendReviewEngine
from kaypoh.review.metadata import scrub_document

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("kaypoh.backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

_state: dict[str, Any] = {}

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}

SUPPRESSED_REQUEST_LOG_PATHS = {"/health", "/ready", "/metrics"}
SPAN_CONTEXT_CHARS = 48
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

- `POST /anonymize` extracts inline text or text/DOCX/PDF payloads, runs the
  PII/MNPI review stack, and returns deterministic placeholders plus a local
  mapping table for safe downstream analysis.
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
    origins = list(current_runtime_settings().api.allowed_origins) or ["http://localhost", "http://127.0.0.1"]

    # Keep Origin: null allowed for local desktop wrappers and manual file:// clients.
    if "null" not in origins:
        origins.append("null")

    return list(dict.fromkeys(origins))


def get_allowed_origin_regex() -> str:
    # Allow localhost origins on any port for local clients and development servers.
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


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

    return {
        "pipeline": pipeline,
        "required_layers": required_layers,
        "warming_layers": warming_layers,
        "missing_layers": missing_layers,
        "ready": len(missing_layers) == 0 and len(warming_layers) == 0,
        "reasons": reasons,
    }


def get_dependency_status() -> dict[str, DependencyStatus]:
    models = _state.get("models", {})
    lazy_loaders = _state.get("lazy_loaders", {})
    settings = current_runtime_settings()
    statuses: dict[str, DependencyStatus] = {}

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

    if settings.llm.enabled:
        statuses["llm_adjudicator"] = DependencyStatus(
            status="unknown",
            configured=True,
            healthy=None,
            detail=f"provider={settings.llm.provider}; model={settings.llm.model}",
        )
    else:
        statuses["llm_adjudicator"] = DependencyStatus(
            status="disabled",
            configured=False,
            healthy=None,
            detail="LLM adjudication is disabled",
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
    """Thin wrapper over engine.review() per ARCHITECTURE-PIVOT-24-MAY.md item 63.

    Legacy 9-layer pipeline (layer1_lexicon through layer6_regression + layer5_mosaic)
    archived 2026-05-26. /classify is retained as a programmatic surface for technical
    clients that want a flat findings dump without /review's session/decision/journal
    state. Legacy fields on the response (lexicon, model1, model2, embedding, clustering,
    mosaic, regression) are permanent None.
    """
    t_start = time.perf_counter()
    observability = get_observability()

    engine = _build_review_engine()
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
    timings_ms = {"total": round((time.perf_counter() - t_start) * 1000.0, 3)}

    public_evidence_resp = None
    if result.public_evidence is not None:
        try:
            public_evidence_resp = PublicEvidenceResponse(**result.public_evidence)
        except Exception:
            public_evidence_resp = None

    llm_adjudication_resp = None
    if result.llm_adjudication is not None:
        try:
            llm_adjudication_resp = LLMAdjudicationResponse(**result.llm_adjudication)
        except Exception:
            llm_adjudication_resp = None

    privacy_ledger_resp = []
    for entry in result.privacy_ledger:
        try:
            privacy_ledger_resp.append(PrivacyLedgerEntryResponse(**entry))
        except Exception:
            continue

    findings_resp = []
    for f in result.findings:
        try:
            findings_resp.append(ReviewFindingResponse.model_validate(f.__dict__))
        except Exception:
            continue

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
            degraded=False,
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
    )

    if observability is not None:
        observability.observe_classification(
            endpoint=endpoint,
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=False,
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
        degraded=False,
        executed_layers=["engine.review"],
        skipped_layers=[],
        layer_error_count=0,
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
        from kaypoh.workflow.layer7_public_evidence.inference import PublicEvidenceRetriever
        from kaypoh.workflow.privacy_guard import PrivacyGuard

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
        from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator

        llm_adjudicator = LocalLLMAdjudicator(settings.llm)

    # audit_grade-only helper: catches preamble defined-term patterns the regex misses.
    # surfaced as a layer model so tests / deployments can swap implementations without
    # touching the engine. when unwired, engine falls through to the deterministic regex.
    llm_defined_term_extractor = get_layer_model("llm_defined_term_extractor")
    # audit_grade-only inverse-audit helper. output is journaled as coverage_warning events.
    # advisory only — engine never acts on these.
    llm_coverage_auditor = get_layer_model("llm_coverage_auditor")

    return PreSendReviewEngine(
        public_evidence_retriever=public_evidence,
        llm_adjudicator=llm_adjudicator,
        llm_defined_term_extractor=llm_defined_term_extractor,
        llm_coverage_auditor=llm_coverage_auditor,
    )


def _build_review_response(
    *,
    req: ReviewRequest,
    request_id: str | None,
    document: Any,
    result: Any,
    timings_ms: dict[str, float],
) -> ReviewResponse:
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
        findings=[
            ReviewFindingResponse(
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
                source_verification=getattr(finding, "source_verification", "not_checked"),
            )
            for finding in result.findings
        ],
        suggestions=[
            ReviewSuggestionResponse(
                id=suggestion.id,
                finding_id=suggestion.finding_id,
                action=suggestion.action,
                replacement_text=suggestion.replacement_text,
                rationale=suggestion.rationale,
            )
            for suggestion in result.suggestions
        ],
        public_evidence=PublicEvidenceResponse(**result.public_evidence) if result.public_evidence else None,
        llm_adjudication=LLMAdjudicationResponse(**result.llm_adjudication) if result.llm_adjudication else None,
        privacy_ledger=[PrivacyLedgerEntryResponse(**entry) for entry in result.privacy_ledger],
        coverage_warnings=list(result.coverage_warnings),
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
    """Journal each LLM inverse-audit warning as a coverage_warning event. Advisory only —
    never gates downstream review state. Requires KAYPOH_REVIEW_PERSIST=1 and a request_id
    (the review-session anchor) just like decision_recorded does."""
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
    start_review_session(
        review_id=request_id,
        text_hash=text_hash,
        document_type=req.document_type,
        source_jurisdiction=req.source_jurisdiction,
        destination_jurisdiction=req.destination_jurisdiction,
        findings=[
            {
                "id": f.id,
                "category": f.category,
                "rule": f.rule,
                "severity": f.severity,
                "matched_text": f.matched_text,
                "start_char": f.start_char,
                "end_char": f.end_char,
            }
            for f in findings
        ],
        tenant_id=tenant_id,
    )


def _run_review_sync(req: ReviewRequest, request_id: str | None, tenant: TenantContext) -> ReviewResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(req, current_runtime_settings().document_ingest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)

    t_review_start = time.perf_counter()
    engine = _build_review_engine()
    result = engine.review(
        text=document.text,
        source_jurisdiction=req.source_jurisdiction,
        destination_jurisdiction=req.destination_jurisdiction,
        entity_id=req.entity_id,
        include_suggestions=req.include_suggestions,
        document_type=req.document_type,
        session_id=req.session_id,
        review_profile=req.review_profile,
        tenant_id=tenant.storage_tenant_id,
    )
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)
    _persist_review_session(
        request_id=request_id,
        req=req,
        document_text=document.text,
        findings=result.findings,
        tenant_id=tenant.storage_tenant_id,
    )
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
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/review",
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=False,
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


def _run_anonymize_sync(req: AnonymizeRequest, request_id: str | None, tenant: TenantContext) -> AnonymizeResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(req, current_runtime_settings().document_ingest)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    timings_ms["extract"] = round((time.perf_counter() - t_extract_start) * 1000.0, 3)

    t_review_start = time.perf_counter()
    engine = _build_review_engine()
    result = engine.review(
        text=document.text,
        source_jurisdiction=req.source_jurisdiction,
        destination_jurisdiction=req.destination_jurisdiction,
        entity_id=req.entity_id,
        include_suggestions=req.include_suggestions,
        document_type=req.document_type,
        session_id=req.session_id,
        review_profile=req.review_profile,
        tenant_id=tenant.storage_tenant_id,
    )
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)

    t_anonymize_start = time.perf_counter()
    anonymization = DeterministicAnonymizer(include_mnpi_scalars=req.include_mnpi_scalars).anonymize(
        text=document.text,
        findings=result.findings,
    )
    timings_ms["anonymize"] = round((time.perf_counter() - t_anonymize_start) * 1000.0, 3)

    document_hash = _compute_document_hash(document.text)
    mapping_persisted = False
    if _review_persistence_enabled() and anonymization.mapping:
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
                    for entry in anonymization.mapping
                ],
                tenant_id=tenant.storage_tenant_id,
            )
            mapping_persisted = True
        except (OSError, MappingStoreError) as exc:
            # persistence is best-effort; the client still has the mapping in the response.
            log_backend_event(logging.WARNING, event="mapping_persist_failed", error=str(exc))
            emit_security_event(
                action="mapping_persist",
                outcome="failed",
                request_id=request_id,
                details={"error": str(exc), "document_hash": document_hash},
                settings=current_runtime_settings().siem,
            )

    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    review_response = _build_review_response(
        req=req,
        request_id=request_id,
        document=document,
        result=result,
        timings_ms=timings_ms,
    )
    response = AnonymizeResponse(
        **review_response.model_dump(mode="python"),
        anonymized_text=anonymization.anonymized_text,
        document_hash=document_hash,
        mapping_persisted=mapping_persisted,
        mapping=[
            AnonymizationMappingEntryResponse(
                placeholder=entry.placeholder,
                entity_type=entry.entity_type,
                original_text=entry.original_text,
                occurrence_count=entry.occurrence_count,
            )
            for entry in anonymization.mapping
        ],
        replacements=[
            AnonymizationReplacementResponse(
                finding_id=replacement.finding_id,
                placeholder=replacement.placeholder,
                entity_type=replacement.entity_type,
                original_text=replacement.original_text,
                start_char=replacement.start_char,
                end_char=replacement.end_char,
            )
            for replacement in anonymization.replacements
        ],
    )

    observability = get_observability()
    if observability is not None:
        observability.observe_classification(
            endpoint="/anonymize",
            classification=result.overall_risk.value,
            cache_status="disabled",
            degraded=False,
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event="anonymize_summary",
        request_id=request_id,
        classification=result.overall_risk.value,
        pii_score=result.pii_score,
        mnpi_score=result.mnpi_score,
        finding_count=len(result.findings),
        replacement_count=len(anonymization.replacements),
        jurisdictions_applied=result.jurisdictions_applied,
        timings_ms=timings_ms,
    )
    emit_privacy_ledger_events(
        result.privacy_ledger,
        request_id=request_id,
        endpoint="/anonymize",
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
                evidence_mod = importlib.import_module("kaypoh.workflow.layer7_public_evidence.inference")
                _state["models"]["public_evidence"] = evidence_mod.PublicEvidenceRetriever.load()

            elif layer == "llm_adjudicator":
                llm_mod = importlib.import_module("kaypoh.workflow.layer8_llm_adjudicator.inference")
                _state["models"]["llm_adjudicator"] = llm_mod.LocalLLMAdjudicator.load()
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
    "/anonymize",
    response_model=AnonymizeResponse,
    dependencies=[Depends(require_review_access)],
    tags=["Anonymization"],
    summary="Anonymize a document before sending",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with deterministic placeholders. "
        "PII findings are replaced by default; exact MNPI scalar findings such as financial amounts and "
        "percentages can also be replaced while broad material-event passages remain review findings."
    ),
)
async def anonymize_document(request: Request, req: AnonymizeRequest):
    return await run_in_threadpool(
        _run_anonymize_sync,
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
                    "/anonymize first with KAYPOH_REVIEW_PERSIST=1"
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
        "Deterministic inverse of /anonymize. Takes anonymized_text plus the caller-supplied "
        "mapping (typically the mapping field from a prior /anonymize response) and restores "
        "the original spans. Runs entirely on the request payload; no document extraction, no "
        "review engine, no model layers."
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


def _serialize_session_state(state: dict[str, Any]) -> ReviewSessionStateResponse:
    decisions_by_id = {d["finding_id"]: d for d in state.get("decisions", [])}
    findings: list[ReviewSessionFindingState] = []
    for finding in state.get("findings", []):
        decision = decisions_by_id.get(finding.get("id"))
        findings.append(
            ReviewSessionFindingState(
                id=finding["id"],
                category=finding["category"],
                rule=finding["rule"],
                severity=finding["severity"],
                matched_text=finding["matched_text"],
                start_char=finding["start_char"],
                end_char=finding["end_char"],
                decision=decision["action"] if decision else None,
                decision_seq=decision["seq"] if decision else None,
                decision_ts=decision["ts"] if decision else None,
                decision_reviewer_id=decision.get("reviewer_id") if decision else None,
            )
        )
    return ReviewSessionStateResponse(
        review_id=state["review_id"],
        text_hash=state.get("text_hash") or "",
        document_type=state.get("document_type") or "generic",
        source_jurisdiction=state.get("source_jurisdiction") or "SG",
        destination_jurisdiction=state.get("destination_jurisdiction") or "SG",
        findings=findings,
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
        "Reviewer identity is sourced from the X-Reviewer-ID header by default; the request body "
        "`reviewer_id` field is used only when the header is absent. "
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
    # header is authoritative because it is closer to the identity-provider edge; body fills in
    # only when the header is missing. both empty is allowed (decision still records).
    resolved_reviewer_id = (x_reviewer_id or req.reviewer_id or "").strip()[:256]
    try:
        result = record_decision(
            review_id=review_id,
            decision=Decision(
                finding_id=req.finding_id,
                action=req.action,
                replacement_text=req.replacement_text,
                rationale=req.rationale,
                reviewer_id=resolved_reviewer_id,
            ),
            tenant_id=tenant_context_from_request(request).storage_tenant_id,
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
    state = get_session_state(review_id=review_id, tenant_id=tenant_context_from_request(request).storage_tenant_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown review_id: {review_id}")
    return _serialize_session_state(state)


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

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
