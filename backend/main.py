import argparse
import hashlib
import importlib.util
import json
import logging
import os
import sys
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock, Thread
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAT_FRONTEND_ROOT = PROJECT_ROOT / "frontend-chat"
sys.path.insert(0, str(PROJECT_ROOT))

from backend.observability import DependencyStatus, ObservabilityManager, get_metrics_mode  # noqa: E402
from backend.schemas import (  # noqa: E402
    BatchClassifyRequest,
    BatchClassifyResponse,
    Classification,
    ClassifyRequest,
    ClassifyResponse,
    DiagnosticsResponse,
    HealthResponse,
    LexiconHitResponse,
    LexiconResponse,
    Model1Response,
    Model2Response,
    MosaicResponse,
    ReadyResponse,
    RegressionResponse,
)
from config import _cfg  # noqa: E402
from helper.determinism import configure_determinism  # noqa: E402

logger = logging.getLogger("noupe.backend")
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


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    env_val = os.environ.get("NOUPE_OPTIONAL_LAYERS")
    if env_val is not None:
        return set(_parse_layers_list(env_val))
    cfg_val = _cfg.get("pipeline", {}).get("optional_layers")
    parsed_cfg = _parse_layers_list(cfg_val)
    if parsed_cfg:
        return set(parsed_cfg)
    return set(DEFAULT_OPTIONAL_LAYERS)


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
    env_val = os.environ.get("NOUPE_ALLOWED_ORIGINS")
    origins: list[str] = []

    if env_val:
        origins.extend([o.strip() for o in env_val.split(",") if o.strip()])
    else:
        cfg_val = _cfg.get("api", {}).get("allowed_origins")
        if isinstance(cfg_val, list):
            origins.extend([str(o).strip() for o in cfg_val if str(o).strip()])
        elif isinstance(cfg_val, str):
            origins.extend([o.strip() for o in cfg_val.split(",") if o.strip()])

    if not origins:
        origins = ["http://localhost", "http://127.0.0.1"]

    # run_dev.sh opens frontend/index.html directly (file://), which uses Origin: null.
    if "null" not in origins:
        origins.append("null")

    return list(dict.fromkeys(origins))


def get_allowed_origin_regex() -> str:
    # Allow localhost origins on any port for local frontend servers.
    return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.environ.get("NOUPE_API_KEY", "").strip()
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")


def load_config() -> list[str]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--layers", type=str)
    args, _ = parser.parse_known_args()

    if args.layers:
        return [l.strip() for l in args.layers.split(",") if l.strip()]

    env_layers = os.environ.get("PIPELINE_LAYERS")
    if env_layers:
        return [l.strip() for l in env_layers.split(",") if l.strip()]

    config_path = os.environ.get("NOUPE_CONFIG", str(PROJECT_ROOT / "config.toml"))
    if os.path.exists(config_path):
        with open(config_path, "rb") as f:
            try:
                cfg = tomllib.load(f)
                return cfg.get(
                    "pipeline",
                    {},
                ).get("layers", ["lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"])
            except Exception as e:
                logger.warning(json.dumps({"event": "config_parse_error", "error": str(e)}))

    return ["lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"]


def get_response_cache_settings() -> dict[str, float | int]:
    raw_size = os.environ.get("NOUPE_RESPONSE_CACHE_SIZE", "256")
    raw_ttl = os.environ.get("NOUPE_RESPONSE_CACHE_TTL_SECONDS", "60")
    try:
        size = max(0, int(raw_size))
    except ValueError:
        size = 256
    try:
        ttl = max(0.0, float(raw_ttl))
    except ValueError:
        ttl = 60.0
    return {"size": size, "ttl_seconds": ttl}


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
        detail = latest_error.get("error", "mosaic layer is unavailable") if latest_error else "mosaic layer is unavailable"
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

    thread = Thread(target=_runner, name="noupe-prewarm", daemon=True)
    _state["prewarm_thread"] = thread
    thread.start()


def build_response_cache_key(req: ClassifyRequest, pipeline: list[str]) -> str:
    payload = {
        "text": req.text,
        "entity_id": req.entity_id or "",
        "pipeline": pipeline,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest


def response_cache_get(key: str) -> dict[str, Any] | None:
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

    lock: Lock = _state.get("load_lock")
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
            logger.info(json.dumps({"event": "lazy_layer_loaded", "layer": layer, "latency_ms": elapsed_ms}))
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
            logger.warning(
                json.dumps(
                    {
                        "event": "lazy_layer_failed",
                        "layer": layer,
                        "latency_ms": elapsed_ms,
                        "error": str(e),
                    }
                )
            )
            refresh_observability_state()
            return None


def get_layer_model(layer: str):
    model = _state.get("models", {}).get(layer)
    if model is not None:
        return model
    return ensure_layer_loaded(layer)

def build_layer_error(layer: str, *, default_phase: str = "runtime", default_message: str = "layer unavailable") -> dict[str, str]:
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

            logger.info(
                json.dumps(
                    {
                        "event": "classify_summary",
                        "request_id": request_id,
                        "classification": cached_class.value,
                        "timings_ms": cached["timings_ms"],
                        "active_pipeline": pipeline,
                        "cache_status": cache_status,
                        "degraded": degraded,
                        "executed_layers": cached_observability.get("executed_layers", []),
                        "skipped_layers": cached_observability.get("skipped_layers", []),
                        "layer_error_count": len(cached_observability.get("layer_errors", [])),
                    }
                )
            )
            return ClassifyResponse(**cached)
        cache_status = "miss"

    lex_resp = None
    m1_resp = None
    m2_resp = None
    emb_resp = None
    clust_resp = None
    mosaic_resp = None
    reg_resp = None

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
                m_result = mosaic_agg.aggregate(entity_id=entity_id, is_low_risk=is_lr)
                mosaic_resp = MosaicResponse(
                    escalated=m_result["escalate_to_high_risk"],
                    count=m_result["count"],
                )

                if is_lr and m_result["escalate_to_high_risk"]:
                    classification_floor = Classification.HIGH_RISK
                    final_classification = Classification.HIGH_RISK

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
                m_count = mosaic_resp.count if mosaic_resp else 0

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
            logger.warning(
                json.dumps(
                    {
                        "event": "layer_runtime_error",
                        "request_id": request_id,
                        "layer": layer,
                        "error": message,
                    }
                )
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
        observability={
            "degraded": degraded,
            "cache_status": cache_status,
            "active_pipeline": list(pipeline),
            "executed_layers": executed_layers,
            "skipped_layers": skipped_layers,
            "layer_errors": layer_errors,
        },
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

    logger.info(
        json.dumps(
            {
                "event": "classify_summary",
                "request_id": request_id,
                "classification": final_classification.value,
                "timings_ms": timings_ms,
                "active_pipeline": pipeline,
                "cache_status": cache_status,
                "degraded": degraded,
                "executed_layers": executed_layers,
                "skipped_layers": skipped_layers,
                "layer_error_count": len(layer_errors),
            }
        )
    )

    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    layers = load_config()
    lazy_heavy = _is_truthy(os.environ.get("NOUPE_LAZY_LOAD_HEAVY"), default=True)
    prewarm_required_layers = _is_truthy(os.environ.get("NOUPE_PREWARM_REQUIRED_LAYERS"), default=True)
    optional_layers = get_optional_layers()
    fail_on_layer_load_error = _is_truthy(os.environ.get("NOUPE_FAIL_ON_LAYER_LOAD_ERROR"), default=False)

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
    _state["observability"] = ObservabilityManager()
    _state["cache_cfg"] = get_response_cache_settings()
    _state["response_cache"] = OrderedDict()
    _state["response_cache_lock"] = Lock()

    t_startup_total = time.perf_counter()

    for layer in layers:
        t_layer = time.perf_counter()
        try:
            if layer == "lexicon":
                lex_mod = load_module_from_path(
                    "lex_filter", str(PROJECT_ROOT / "layer1-lexicon" / "filter.py")
                )
                _state["models"]["lexicon"] = lex_mod.LexiconFilter()

            elif layer == "embedding":

                def _load_embedding():
                    emb_mod = load_module_from_path(
                        "emb_inf", str(PROJECT_ROOT / "layer2-embeddings" / "inference.py")
                    )
                    return emb_mod.EmbeddingsEncoder.get_instance()

                if lazy_heavy:
                    _state["lazy_loaders"]["embedding"] = _load_embedding
                else:
                    _state["models"]["embedding"] = _load_embedding()

            elif layer == "clustering":
                clust_ckpt = PROJECT_ROOT / "layer3-clustering" / "checkpoints" / "anomaly_detector.joblib"
                if not clust_ckpt.exists():
                    raise FileNotFoundError(f"clustering checkpoint missing: {clust_ckpt}")
                clust_mod = load_module_from_path(
                    "clust_inf", str(PROJECT_ROOT / "layer3-clustering" / "isolation_forest.py")
                )
                _state["models"]["clustering"] = clust_mod.MNPIAnomalyDetector.load()

            elif layer == "model1":
                model1_ckpt = PROJECT_ROOT / "layer4-classification" / "model-1" / "checkpoints" / "best"
                if not has_model_weights(model1_ckpt):
                    raise FileNotFoundError(f"model1 weights missing: {model1_ckpt}")

                def _load_model1():
                    m1_mod = load_module_from_path(
                        "m1_inf", str(PROJECT_ROOT / "layer4-classification" / "model-1" / "inference.py")
                    )
                    return m1_mod.FinBERTClassifier(checkpoint_dir=str(model1_ckpt))

                if lazy_heavy:
                    _state["lazy_loaders"]["model1"] = _load_model1
                else:
                    _state["models"]["model1"] = _load_model1()

            elif layer == "model2":
                model2_ckpt = PROJECT_ROOT / "layer4-classification" / "model-2" / "checkpoints" / "best"
                if not has_model_weights(model2_ckpt):
                    raise FileNotFoundError(f"model2 weights missing: {model2_ckpt}")

                def _load_model2():
                    m2_mod = load_module_from_path(
                        "m2_inf", str(PROJECT_ROOT / "layer4-classification" / "model-2" / "inference.py")
                    )
                    return m2_mod.BERTSeverityClassifier(checkpoint_dir=str(model2_ckpt))

                if lazy_heavy:
                    _state["lazy_loaders"]["model2"] = _load_model2
                else:
                    _state["models"]["model2"] = _load_model2()

            elif layer == "regression":
                reg_model = PROJECT_ROOT / "layer6-regression" / "checkpoints" / "risk_regressor.json"
                reg_meta = PROJECT_ROOT / "layer6-regression" / "checkpoints" / "metadata.json"
                if not reg_model.exists() or not reg_meta.exists():
                    raise FileNotFoundError(
                        f"regression artifacts missing: {reg_model} and/or {reg_meta}"
                    )

                reg_mod = load_module_from_path(
                    "reg_inf", str(PROJECT_ROOT / "layer6-regression" / "inference.py")
                )
                _state["models"]["regression"] = reg_mod.XGBoostRegression()

            elif layer == "mosaic":
                def _load_mosaic():
                    mos_mod = load_module_from_path(
                        "mos_inf", str(PROJECT_ROOT / "layer5-mosaic" / "inference.py")
                    )
                    return mos_mod.MosaicAggregator.load()

                _state["lazy_loaders"]["mosaic"] = _load_mosaic
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
            logger.warning(json.dumps({"event": "layer_load_failed", "layer": layer, "error": str(e)}))
        finally:
            elapsed_ms = round((time.perf_counter() - t_layer) * 1000.0, 3)
            _state["startup_timings_ms"][layer] = elapsed_ms
            if _get_latest_load_error(layer) is None or _get_latest_load_error(layer).get("phase") != "startup":
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

    logger.info(
        json.dumps(
            {
                "event": "startup_summary",
                "pipeline": layers,
                "loaded_layers": sorted(_state.get("models", {}).keys()),
                "lazy_layers": sorted(_state.get("lazy_loaders", {}).keys()),
                "optional_layers": sorted(optional_layers),
                "missing_required_layers": missing_required_layers,
                "startup_timings_ms": _state.get("startup_timings_ms", {}),
                "load_errors": _state.get("load_errors", []),
                "cache_cfg": _state.get("cache_cfg", {}),
                "metrics_mode": get_metrics_mode(),
            }
        )
    )

    if missing_required_layers and fail_on_layer_load_error:
        raise RuntimeError(
            f"required layers failed to load: {missing_required_layers}. "
            "Set NOUPE_FAIL_ON_LAYER_LOAD_ERROR=0 to allow degraded startup."
        )

    if lazy_heavy and prewarm_required_layers and not missing_required_layers:
        start_required_layer_prewarm(optional_layers)

    refresh_observability_state()
    yield
    _state.clear()


app = FastAPI(title="Noupe MNPI Classifier", version="0.1.0", lifespan=lifespan)

if CHAT_FRONTEND_ROOT.exists():
    app.mount("/chat", StaticFiles(directory=str(CHAT_FRONTEND_ROOT), html=True), name="chat-frontend")

_det_info = configure_determinism()
logger.info(json.dumps({"event": "determinism", **_det_info}))

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=get_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": dt_ms,
                }
            )
        )

    if response is None:
        if request_error is not None:
            raise request_error
        raise RuntimeError("Unhandled request failure")

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
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


@app.get("/ready", response_model=ReadyResponse)
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


@app.get("/diagnostics", response_model=DiagnosticsResponse)
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
            name: {
                "status": status.status,
                "configured": status.configured,
                "healthy": status.healthy,
                "detail": status.detail,
            }
            for name, status in get_dependency_status().items()
        },
        runtime_layer_errors=dict(_state.get("runtime_layer_errors", {})),
    )


@app.get("/metrics")
async def metrics():
    refresh_observability_state()
    observability = get_observability()
    if observability is None:
        raise HTTPException(status_code=503, detail="observability not initialized")
    return Response(content=observability.render_metrics(), media_type=observability.content_type)


@app.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify(request: Request, req: ClassifyRequest):
    return _classify_core(req, getattr(request.state, "request_id", None), "/classify")


@app.post("/classify/batch", response_model=BatchClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify_batch(request: Request, req: BatchClassifyRequest):
    base_request_id = getattr(request.state, "request_id", None)
    results = []
    for idx, item in enumerate(req.items):
        item_request_id = f"{base_request_id}:{idx}" if base_request_id else None
        results.append(_classify_core(item, item_request_id, "/classify/batch"))
    return BatchClassifyResponse(results=results)


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
