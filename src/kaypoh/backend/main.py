import argparse
import bisect
import hashlib
import importlib
import importlib.util
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
    compute_document_hash as _compute_document_hash,
    load_mapping as _load_persisted_mapping,
    reidentify as _reidentify_text,
    save_mapping as _save_persisted_mapping,
)
from kaypoh.review.decisions import (
    Decision,
    ReviewSessionError,
    findings_after_decisions,
    get_session_state,
    record_decision,
    start_review_session,
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
    HealthResponse,
    LayerErrorResponse,
    LexiconHitResponse,
    LexiconResponse,
    LLMAdjudicationResponse,
    Model1Response,
    Model2Response,
    MosaicResponse,
    ObservabilityResponse,
    OffendingSpanResponse,
    PrivacyLedgerEntryResponse,
    PublicEvidenceResponse,
    ReadyResponse,
    RegressionResponse,
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
from kaypoh.configs.artifacts import get_artifact_path
from kaypoh.configs.runtime import RuntimeSettings, get_runtime_settings
from kaypoh.helper.determinism import configure_determinism
from kaypoh.review.document import extract_review_document
from kaypoh.review.engine import PreSendReviewEngine

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger("kaypoh.backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

_state: dict[str, Any] = {}

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}

MODEL_WEIGHT_EXTS = ("safetensors", "bin", "pt", "ckpt")
SUPPRESSED_REQUEST_LOG_PATHS = {"/health", "/ready", "/metrics"}
DEFAULT_OPTIONAL_LAYERS = {"mosaic"}
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
- `POST /classify` accepts a single text document and returns a document-level
  legacy MNPI classification of `SAFE`, `LOW_RISK`, or `HIGH_RISK`.
- `POST /classify/batch` processes up to 32 classify requests with bounded
  in-process concurrency while preserving result order.
- `include_offending_spans=true` adds exact lexicon spans and approximate
  classifier-window spans when the final response is `LOW_RISK` or `HIGH_RISK`.
- Chain-of-evidence is exposed through findings, suggestions, public-source
  summaries, and privacy-ledger entries. Raw chain-of-thought is not exposed.
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


def _parse_layers_list(raw: str | list[Any] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [v.strip() for v in raw.split(",") if v.strip()]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return []


def get_optional_layers() -> set[str]:
    return set(current_runtime_settings().pipeline.optional_layers) or set(DEFAULT_OPTIONAL_LAYERS)


def max_classification(a: Classification, b: Classification) -> Classification:
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b


def load_module_from_path(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def has_model_weights(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    for ext in MODEL_WEIGHT_EXTS:
        if any(path.glob(f"*.{ext}")):
            return True
    return False


def get_allowed_origins() -> list[str]:
    origins = list(current_runtime_settings().api.allowed_origins) or ["http://localhost", "http://127.0.0.1"]

    # Keep Origin: null allowed for local desktop wrappers and manual file:// clients.
    if "null" not in origins:
        origins.append("null")

    return list(dict.fromkeys(origins))


def get_allowed_origin_regex() -> str:
    # Allow localhost origins on any port for local clients and development servers.
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = current_runtime_settings().api.api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


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
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    lazy_loaders = _state.get("lazy_loaders", {})
    statuses: dict[str, DependencyStatus] = {}

    mosaic_configured = "mosaic" in pipeline
    if not mosaic_configured:
        statuses["redis"] = DependencyStatus(
            status="disabled",
            configured=False,
            healthy=None,
            detail="mosaic layer is not configured in the active pipeline",
        )
        return statuses

    mosaic_model = models.get("mosaic")
    if mosaic_model is None and "mosaic" in lazy_loaders:
        statuses["redis"] = DependencyStatus(
            status="unknown",
            configured=True,
            healthy=None,
            detail="mosaic layer is configured but has not been loaded yet",
        )
        return statuses

    if mosaic_model is None:
        latest_error = _get_latest_load_error("mosaic")
        detail = (
            latest_error.get("error", "mosaic layer is unavailable")
            if latest_error
            else "mosaic layer is unavailable"
        )
        statuses["redis"] = DependencyStatus(
            status="down",
            configured=True,
            healthy=False,
            detail=detail,
        )
        return statuses

    healthy = bool(getattr(mosaic_model, "connected", False))
    statuses["redis"] = DependencyStatus(
        status="up" if healthy else "down",
        configured=True,
        healthy=healthy,
        detail=f"redis target {getattr(mosaic_model, 'host', 'unknown')}:{getattr(mosaic_model, 'port', 'unknown')}",
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
    # Mosaic mutates state (Redis counters), so keep cache disabled when mosaic layer is active.
    if "mosaic" in pipeline:
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


def build_offending_spans(text: str, lex_hits: list[Any]) -> list[OffendingSpanResponse]:
    line_starts = _build_line_starts(text)
    spans: list[OffendingSpanResponse] = []

    for index, hit in enumerate(lex_hits):
        start_char = getattr(hit, "start_char", None)
        end_char = getattr(hit, "end_char", None)
        if start_char is None or end_char is None:
            continue

        start = max(0, int(start_char))
        end = min(len(text), int(end_char))
        if end < start:
            continue

        start_line, start_column = _offset_to_line_column(line_starts, start)
        end_line, end_column = _offset_to_line_column(line_starts, end)
        matched_text = text[start:end]
        context_before, context_after = _build_context_window(text, start, end)
        score = _optional_float(getattr(hit, "score", None))
        spans.append(
            OffendingSpanResponse(
                id=f"lexicon:{getattr(hit, 'rule', 'unknown')}:{start}:{end}:{index}",
                layer="lexicon",
                rule=str(getattr(hit, "rule", "")),
                severity=str(getattr(hit, "severity", "")),
                matched_text=matched_text if matched_text else str(getattr(hit, "matched_text", "")),
                detail=str(getattr(hit, "detail", "")),
                start_char=start,
                end_char=end,
                start_line=start_line,
                start_column=start_column,
                end_line=end_line,
                end_column=end_column,
                is_exact=True,
                char_length=end - start,
                line_span=max(1, end_line - start_line + 1),
                window_index=None,
                window_count=None,
                window_token_count=None,
                window_stride=None,
                window_max_seq_len=None,
                context_before=context_before,
                context_after=context_after,
                score=score,
                score_type="rule_score" if score is not None else None,
            )
        )

    return spans


def build_classifier_offending_spans(
    text: str,
    model1_result: Any | None,
    model2_result: Any | None,
    final_classification: Classification,
) -> list[OffendingSpanResponse]:
    line_starts = _build_line_starts(text)
    spans: list[OffendingSpanResponse] = []

    model_specs = [
        (
            "model1",
            model1_result,
            "risk_score",
            getattr(model1_result, "label", "") == "risk" if model1_result is not None else False,
        ),
        (
            "model2",
            model2_result,
            "high_risk_score",
            model2_result is not None,
        ),
    ]

    for index, (layer, result, score_field, should_include) in enumerate(model_specs):
        if not should_include or result is None:
            continue

        top_window = getattr(result, "top_window", None)
        if not isinstance(top_window, dict):
            continue

        start = max(0, int(top_window.get("start_char", 0)))
        end = min(len(text), int(top_window.get("end_char", 0)))
        if end <= start:
            continue

        start_line, start_column = _offset_to_line_column(line_starts, start)
        end_line, end_column = _offset_to_line_column(line_starts, end)
        score_value = float(top_window.get(score_field, getattr(result, score_field, 0.0)))
        severity = "high" if final_classification == Classification.HIGH_RISK else "info"
        context_before, context_after = _build_context_window(text, start, end)
        window_index = _optional_int(top_window.get("window_index"))
        window_count = _optional_int(getattr(result, "window_count", 1))
        window_token_count = _optional_int(top_window.get("token_count"))
        window_stride = _optional_int(top_window.get("window_stride"))
        window_max_seq_len = _optional_int(top_window.get("max_seq_len"))
        matched_text = str(top_window.get("text") or text[start:end])

        spans.append(
            OffendingSpanResponse(
                id=f"{layer}:sliding_window:{start}:{end}:{index}",
                layer=layer,
                rule="sliding_window",
                severity=severity,
                matched_text=matched_text,
                detail=(
                    f"approximate classifier window from {layer}; "
                    f"{score_field}={score_value:.3f}; "
                    f"window_index={window_index if window_index is not None else 0}; "
                    f"windows={window_count if window_count is not None else 1}"
                ),
                start_char=start,
                end_char=end,
                start_line=start_line,
                start_column=start_column,
                end_line=end_line,
                end_column=end_column,
                is_exact=False,
                char_length=end - start,
                line_span=max(1, end_line - start_line + 1),
                context_before=context_before,
                context_after=context_after,
                score=score_value,
                score_type=score_field,
                window_index=window_index,
                window_count=window_count,
                window_token_count=window_token_count,
                window_stride=window_stride,
                window_max_seq_len=window_max_seq_len,
            )
        )

    return spans


def _classify_core(req: ClassifyRequest, request_id: str | None, endpoint: str) -> ClassifyResponse:
    pipeline = _state.get("pipeline", [])
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    observability = get_observability()

    cache_key = None
    cache_status = "disabled"
    if should_cache_response(req, pipeline):
        cache_key = build_response_cache_key(req, pipeline)
        cached = response_cache_get(cache_key)
        if cached is not None:
            cache_status = "hit"
            total_ms = round((time.perf_counter() - t_total_start) * 1000.0, 3)
            cached["request_id"] = request_id
            cached["timings_ms"] = {"cache_hit": 1.0, "total": total_ms}
            cached_observability = dict(cached.get("observability", {}))
            cached_observability["cache_status"] = cache_status
            cached["observability"] = cached_observability
            cached_class = Classification(cached.get("classification", Classification.SAFE.value))
            degraded = bool(cached_observability.get("degraded", False))
            if observability is not None:
                observability.observe_classification(
                    endpoint=endpoint,
                    classification=cached_class.value,
                    cache_status=cache_status,
                    degraded=degraded,
                    duration_seconds=total_ms / 1000.0,
                )

            log_backend_event(
                logging.INFO,
                event="classify_summary",
                request_id=request_id,
                classification=cached_class.value,
                timings_ms=cached["timings_ms"],
                active_pipeline=pipeline,
                cache_status=cache_status,
                degraded=degraded,
                executed_layers=cached_observability.get("executed_layers", []),
                skipped_layers=cached_observability.get("skipped_layers", []),
                layer_error_count=len(cached_observability.get("layer_errors", [])),
            )
            return ClassifyResponse(**cached)
        cache_status = "miss"

    lex_resp = None
    lex_hits: list[Any] = []
    m1_result = None
    m2_result = None
    m1_resp = None
    m2_resp = None
    emb_resp = None
    clust_resp = None
    mosaic_resp = None
    reg_resp = None
    public_evidence_resp = None
    llm_adjudication_resp = None
    privacy_ledger: list[dict[str, Any]] = []

    final_classification = Classification.SAFE
    classification_floor = Classification.SAFE
    current_embedding = None

    skip_to_regression = False
    # Model-2 is strictly gated by Model-1 risk output.
    skip_model2 = True
    degraded = False
    layer_errors: list[dict[str, str]] = []
    executed_layers: list[str] = []
    skipped_layers: list[str] = []

    for layer in pipeline:
        t_layer_start = time.perf_counter()
        outcome = "executed"
        try:
            if skip_to_regression and layer != "regression":
                outcome = "skipped"
                skipped_layers.append(layer)
                continue

            if layer == "lexicon":
                lexicon_filter = get_layer_model("lexicon")
                if lexicon_filter is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                lex_result = lexicon_filter.run(req.text)
                lex_hits = list(lex_result.hits)
                lex_resp = LexiconResponse(
                    flagged=lex_result.flagged,
                    high_risk_short_circuit=lex_result.high_risk_short_circuit,
                    total_score=lex_result.total_score,
                    score_threshold=lex_result.score_threshold,
                    score_threshold_exceeded=lex_result.score_threshold_exceeded,
                    hits=[
                        LexiconHitResponse(
                            rule=h.rule,
                            matched_text=h.matched_text,
                            severity=h.severity,
                            detail=h.detail,
                            score=h.score,
                        )
                        for h in lex_result.hits
                    ],
                    restricted_entities=lex_result.restricted_entities_found,
                )
                if lex_result.high_risk_short_circuit:
                    classification_floor = Classification.HIGH_RISK
                    final_classification = Classification.HIGH_RISK
                    skip_to_regression = True
                elif lex_result.flagged:
                    classification_floor = max_classification(classification_floor, Classification.LOW_RISK)
                    final_classification = max_classification(final_classification, classification_floor)

            elif layer == "embedding":
                encoder = get_layer_model("embedding")
                if encoder is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                current_embedding = encoder.encode(req.text)
                if req.debug:
                    emb_resp = current_embedding.tolist()

            elif layer == "clustering":
                if current_embedding is None:
                    outcome = "skipped"
                    skipped_layers.append(layer)
                    continue
                detector = get_layer_model("clustering")
                if detector is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                clust_resp = detector.score(current_embedding)

            elif layer == "model1":
                model1 = get_layer_model("model1")
                if model1 is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                m1_result = model1.predict(req.text)
                m1_resp = Model1Response(
                    label=m1_result.label,
                    confidence=m1_result.confidence,
                    risk_score=m1_result.risk_score,
                )
                if m1_result.label == "safe":
                    final_classification = max_classification(Classification.SAFE, classification_floor)
                    skip_model2 = True
                else:
                    skip_model2 = False
                    final_classification = max_classification(Classification.LOW_RISK, classification_floor)

            elif layer == "model2":
                if skip_model2:
                    outcome = "skipped"
                    skipped_layers.append(layer)
                    continue
                model2 = get_layer_model("model2")
                if model2 is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                m2_result = model2.predict(req.text)
                m2_resp = Model2Response(
                    label=m2_result.label,
                    confidence=m2_result.confidence,
                    high_risk_score=m2_result.high_risk_score,
                )
                model2_class = Classification.HIGH_RISK if m2_result.label == "high_risk" else Classification.LOW_RISK
                final_classification = max_classification(model2_class, classification_floor)

            elif layer == "mosaic":
                entity_id = req.entity_id
                if not entity_id and lex_resp and lex_resp.restricted_entities:
                    entity_id = lex_resp.restricted_entities[0].get("name")

                if not entity_id:
                    outcome = "skipped"
                    skipped_layers.append(layer)
                    continue

                mosaic_agg = get_layer_model("mosaic")
                if mosaic_agg is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                is_lr = final_classification == Classification.LOW_RISK
                m_result = mosaic_agg.aggregate(
                    entity_id=entity_id,
                    is_low_risk=is_lr,
                    fragment_text=req.text,
                    request_id=request_id,
                    classification=final_classification.value,
                    model_scores={
                        "model1": m1_resp.risk_score if m1_resp else None,
                        "model2": m2_resp.high_risk_score if m2_resp else None,
                    },
                )
                mosaic_resp = MosaicResponse(
                    entity_id=str(m_result.get("entity_id", entity_id)),
                    escalated=bool(m_result.get("escalate_to_high_risk", False)),
                    recent_event_count=int(m_result.get("recent_event_count", 0)),
                    unique_fragment_count=int(m_result.get("unique_fragment_count", m_result.get("count", 0))),
                    window_hours=float(m_result.get("window_hours", 0.0)),
                    threshold=int(m_result.get("threshold", 0)),
                    escalation_reason=str(m_result.get("escalation_reason", "")),
                    matched_event_ids=[str(item) for item in m_result.get("matched_event_ids", [])],
                )

                if is_lr and m_result["escalate_to_high_risk"]:
                    classification_floor = Classification.HIGH_RISK
                    final_classification = Classification.HIGH_RISK

            elif layer == "public_evidence":
                if final_classification == Classification.SAFE and not (lex_resp and lex_resp.flagged):
                    outcome = "skipped"
                    skipped_layers.append(layer)
                    continue

                retriever = get_layer_model("public_evidence")
                if retriever is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                evidence_result = retriever.retrieve(
                    text=req.text,
                    entity_id=req.entity_id,
                    lexicon=lex_resp,
                )
                public_evidence_resp = PublicEvidenceResponse(**evidence_result)
                privacy_ledger.extend(evidence_result.get("privacy_ledger", []))

            elif layer == "llm_adjudicator":
                adjudicator = get_layer_model("llm_adjudicator")
                if adjudicator is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                if final_classification == Classification.SAFE and public_evidence_resp is None:
                    outcome = "skipped"
                    skipped_layers.append(layer)
                    continue
                adjudication_result = adjudicator.adjudicate(
                    text=req.text,
                    current_classification=final_classification.value,
                    lexicon=lex_resp,
                    model1=m1_resp,
                    model2=m2_resp,
                    public_evidence=public_evidence_resp,
                )
                llm_adjudication_resp = LLMAdjudicationResponse(**adjudication_result)
                if llm_adjudication_resp.status == "adjudicated" and llm_adjudication_resp.risk_label is not None:
                    if classification_floor == Classification.HIGH_RISK:
                        final_classification = max_classification(
                            llm_adjudication_resp.risk_label,
                            classification_floor,
                        )
                    else:
                        final_classification = llm_adjudication_resp.risk_label

            elif layer == "regression":
                reg_model = get_layer_model("regression")
                if reg_model is None:
                    degraded = True
                    outcome = "unavailable"
                    layer_errors.append(build_layer_error(layer))
                    continue
                lex_score = lex_resp.total_score if lex_resp else 0.0
                lex_threshold = float(getattr(lex_resp, "score_threshold", 0.0) or 0.0)
                lex_score_over_threshold = max(0.0, lex_score - lex_threshold)
                m1_score = m1_resp.risk_score if m1_resp else 0.0
                m2_score = m2_resp.high_risk_score if m2_resp else 0.0
                clust_score = clust_resp.get("anomaly_score", 0.0) if clust_resp else 0.0
                m_count = mosaic_resp.unique_fragment_count if mosaic_resp else 0

                feature_payload = {
                    "lex_score": lex_score,
                    "lex_threshold": lex_threshold,
                    "lex_score_over_threshold": lex_score_over_threshold,
                    "m1_score": m1_score,
                    "m2_score": m2_score,
                    "clust_score": clust_score,
                    "mosaic_count": m_count,
                }
                reg_result = reg_model.predict(feature_payload)
                reg_resp = RegressionResponse(
                    risk_score=reg_result["risk_score"],
                    reasoning=reg_result["reasoning"],
                )

                reg_class = (
                    Classification.HIGH_RISK
                    if reg_result["label"] == "high_risk"
                    else (
                        Classification.LOW_RISK if reg_result["label"] == "low_risk" else Classification.SAFE
                    )
                )
                final_classification = max_classification(reg_class, classification_floor)

        except Exception as e:
            outcome = "error"
            degraded = True
            message = str(e)
            layer_errors.append({"layer": layer, "phase": "runtime", "message": message})
            record_runtime_layer_error(layer, message)
            if observability is not None:
                observability.observe_layer_load(
                    layer=layer,
                    phase="runtime",
                    outcome="error",
                    duration_seconds=max(0.0, time.perf_counter() - t_layer_start),
                )
            log_backend_event(
                logging.WARNING,
                event="layer_runtime_error",
                request_id=request_id,
                layer=layer,
                error=message,
            )
        finally:
            timings_ms[layer] = round((time.perf_counter() - t_layer_start) * 1000.0, 3)
            if outcome == "executed":
                executed_layers.append(layer)
            if observability is not None:
                observability.observe_layer_execution(
                    layer=layer,
                    outcome=outcome,
                    duration_seconds=timings_ms[layer] / 1000.0,
                )

    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)

    offending_spans = None
    if req.include_offending_spans and final_classification in {Classification.LOW_RISK, Classification.HIGH_RISK}:
        offending_spans = []
        if lex_resp and lex_resp.flagged:
            offending_spans.extend(build_offending_spans(req.text, lex_hits))
        offending_spans.extend(build_classifier_offending_spans(req.text, m1_result, m2_result, final_classification))

    response = ClassifyResponse(
        request_id=request_id,
        classification=final_classification,
        lexicon=lex_resp,
        model1=m1_resp,
        model2=m2_resp,
        embedding=emb_resp,
        clustering=clust_resp,
        mosaic=mosaic_resp,
        regression=reg_resp,
        public_evidence=public_evidence_resp,
        llm_adjudication=llm_adjudication_resp,
        privacy_ledger=[PrivacyLedgerEntryResponse(**entry) for entry in privacy_ledger],
        offending_spans=offending_spans,
        observability=ObservabilityResponse(
            degraded=degraded,
            cache_status=cache_status,
            active_pipeline=list(pipeline),
            executed_layers=executed_layers,
            skipped_layers=skipped_layers,
            layer_errors=[LayerErrorResponse(**error) for error in layer_errors],
        ),
        timings_ms=timings_ms,
    )

    if cache_key is not None:
        cache_payload = response.model_dump(mode="json")
        cache_payload["request_id"] = None
        cache_payload["timings_ms"] = {}
        response_cache_set(cache_key, cache_payload)

    if observability is not None:
        observability.observe_classification(
            endpoint=endpoint,
            classification=final_classification.value,
            cache_status=cache_status,
            degraded=degraded,
            duration_seconds=timings_ms["total"] / 1000.0,
        )

    log_backend_event(
        logging.INFO,
        event="classify_summary",
        request_id=request_id,
        classification=final_classification.value,
        timings_ms=timings_ms,
        active_pipeline=pipeline,
        cache_status=cache_status,
        degraded=degraded,
        executed_layers=executed_layers,
        skipped_layers=skipped_layers,
        layer_error_count=len(layer_errors),
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

    return PreSendReviewEngine(
        public_evidence_retriever=public_evidence,
        llm_adjudicator=llm_adjudicator,
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
        timings_ms=timings_ms,
    )


def _review_persistence_enabled() -> bool:
    return _is_truthy(os.environ.get("KAYPOH_REVIEW_PERSIST"), default=False)


def _persist_review_session(*, request_id: str | None, req: ReviewRequest, document_text: str, findings: list[Any]) -> None:
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
    )


def _run_review_sync(req: ReviewRequest, request_id: str | None) -> ReviewResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(req)
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
    )
    timings_ms["review"] = round((time.perf_counter() - t_review_start) * 1000.0, 3)
    _persist_review_session(request_id=request_id, req=req, document_text=document.text, findings=result.findings)
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
    return response


def _run_anonymize_sync(req: AnonymizeRequest, request_id: str | None) -> AnonymizeResponse:
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()
    t_extract_start = time.perf_counter()
    try:
        document = extract_review_document(req)
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
            )
            mapping_persisted = True
        except OSError as exc:
            # persistence is best-effort; the client still has the mapping in the response.
            log_backend_event(logging.WARNING, event="mapping_persist_failed", error=str(exc))

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
            if layer == "lexicon":
                lex_mod = importlib.import_module("kaypoh.workflow.layer1_lexicon.filter")
                _state["models"]["lexicon"] = lex_mod.LexiconFilter()

            elif layer == "embedding":

                def _load_embedding():
                    emb_mod = importlib.import_module("kaypoh.workflow.layer2_embeddings.inference")
                    return emb_mod.EmbeddingsEncoder.get_instance()

                if lazy_heavy:
                    _state["lazy_loaders"]["embedding"] = _load_embedding
                else:
                    _state["models"]["embedding"] = _load_embedding()

            elif layer == "clustering":
                clust_ckpt = get_artifact_path("clustering")
                if not clust_ckpt.exists():
                    raise FileNotFoundError(f"clustering checkpoint missing: {clust_ckpt}")
                clust_mod = importlib.import_module("kaypoh.workflow.layer3_clustering.isolation_forest")
                _state["models"]["clustering"] = clust_mod.MNPIAnomalyDetector.load(str(clust_ckpt))

            elif layer == "model1":
                model1_ckpt = get_artifact_path("model1")
                if not has_model_weights(model1_ckpt):
                    raise FileNotFoundError(f"model1 weights missing: {model1_ckpt}")

                def _load_model1():
                    m1_mod = importlib.import_module("kaypoh.workflow.layer4_classification.model1.inference")
                    return m1_mod.FinBERTClassifier(checkpoint_dir=str(model1_ckpt))

                if lazy_heavy:
                    _state["lazy_loaders"]["model1"] = _load_model1
                else:
                    _state["models"]["model1"] = _load_model1()

            elif layer == "model2":
                model2_ckpt = get_artifact_path("model2")
                if not has_model_weights(model2_ckpt):
                    raise FileNotFoundError(f"model2 weights missing: {model2_ckpt}")

                def _load_model2():
                    m2_mod = importlib.import_module("kaypoh.workflow.layer4_classification.model2.inference")
                    return m2_mod.BERTSeverityClassifier(checkpoint_dir=str(model2_ckpt))

                if lazy_heavy:
                    _state["lazy_loaders"]["model2"] = _load_model2
                else:
                    _state["models"]["model2"] = _load_model2()

            elif layer == "regression":
                reg_dir = get_artifact_path("regression")
                reg_model = reg_dir / "risk_regressor.json"
                reg_meta = reg_dir / "metadata.json"
                if not reg_model.exists() or not reg_meta.exists():
                    raise FileNotFoundError(
                        f"regression artifacts missing: {reg_model} and/or {reg_meta}"
                    )

                reg_mod = importlib.import_module("kaypoh.workflow.layer6_regression.inference")
                _state["models"]["regression"] = reg_mod.XGBoostRegression(
                    model_path=str(reg_model),
                    metadata_path=str(reg_meta),
                )

            elif layer == "mosaic":
                def _load_mosaic():
                    mos_mod = importlib.import_module("kaypoh.workflow.layer5_mosaic.inference")
                    return mos_mod.MosaicAggregator.load()

                _state["lazy_loaders"]["mosaic"] = _load_mosaic

            elif layer == "public_evidence":
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
    summary="Get layer load health",
    description="Return a lightweight snapshot of which runtime layers are currently loaded in memory.",
)
async def health():
    models = _state.get("models", {})
    return HealthResponse(
        status="ok",
        lexicon_loaded="lexicon" in models,
        model1_loaded="model1" in models,
        model2_loaded="model2" in models,
        embedding_loaded="embedding" in models,
        clustering_loaded="clustering" in models,
        mosaic_loaded="mosaic" in models,
        regression_loaded="regression" in models,
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
    dependencies=[Depends(require_api_key)],
    tags=["Classification"],
    summary="Classify one document",
    description=(
        "Classify a single text document for MNPI sensitivity. "
        "Set `include_offending_spans=true` to request exact lexicon spans and approximate classifier-window spans "
        "when the final result is `LOW_RISK` or `HIGH_RISK`."
    ),
)
async def classify(request: Request, req: ClassifyRequest):
    return await run_in_threadpool(_run_classify_sync, req, getattr(request.state, "request_id", None), "/classify")


@app.post(
    "/classify/batch",
    response_model=BatchClassifyResponse,
    dependencies=[Depends(require_api_key)],
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
    dependencies=[Depends(require_api_key)],
    tags=["Anonymization"],
    summary="Review a document before sending",
    description=(
        "Run a pre-send review for PII and MNPI risk over inline text or a base64-encoded text, DOCX, or PDF "
        "document. The endpoint applies source and destination jurisdictions using a strictest-wins policy, "
        "returns localized findings, and suggests redactions or rewrites."
    ),
)
async def review_document(request: Request, req: ReviewRequest):
    return await run_in_threadpool(_run_review_sync, req, getattr(request.state, "request_id", None))


@app.post(
    "/anonymize",
    response_model=AnonymizeResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Anonymization"],
    summary="Anonymize a document before sending",
    description=(
        "Run the pre-send PII/MNPI review and return extracted text with deterministic placeholders. "
        "PII findings are replaced by default; exact MNPI scalar findings such as financial amounts and "
        "percentages can also be replaced while broad material-event passages remain review findings."
    ),
)
async def anonymize_document(request: Request, req: AnonymizeRequest):
    return await run_in_threadpool(_run_anonymize_sync, req, getattr(request.state, "request_id", None))


def _run_reidentify_sync(req: ReidentifyRequest, request_id: str | None) -> ReidentifyResponse:
    t_total_start = time.perf_counter()

    mapping_dicts: list[dict[str, Any]]
    if req.mapping:
        mapping_dicts = [entry.model_dump() for entry in req.mapping]
    else:
        # `mapping` is empty and the model validator already guaranteed `document_hash` is present.
        persisted = _load_persisted_mapping(req.document_hash or "")
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
    dependencies=[Depends(require_api_key)],
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
    return await run_in_threadpool(_run_reidentify_sync, req, getattr(request.state, "request_id", None))


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
    dependencies=[Depends(require_api_key)],
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
        )
    except ReviewSessionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReviewDecisionResponse(**result)


@app.get(
    "/review/{review_id}",
    response_model=ReviewSessionStateResponse,
    dependencies=[Depends(require_api_key)],
    tags=["Anonymization"],
    summary="Inspect review session state",
    description=(
        "Reconstruct the current state of a review session from the journal: findings merged "
        "with the most recent decision per finding. Requires KAYPOH_REVIEW_PERSIST=1."
    ),
)
async def get_review_session(review_id: str):
    _ensure_persistence_enabled()
    state = get_session_state(review_id=review_id)
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
