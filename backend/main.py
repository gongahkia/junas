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
from threading import Lock
from typing import Any, Callable

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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
LATENCY_BUCKET_BOUNDS_MS = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0]
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


def build_latency_histogram() -> dict[str, Any]:
    return {
        "bounds": LATENCY_BUCKET_BOUNDS_MS[:],
        "counts": [0 for _ in range(len(LATENCY_BUCKET_BOUNDS_MS) + 1)],
        "count": 0,
        "sum_ms": 0.0,
    }


def observe_latency(histogram: dict[str, Any], latency_ms: float) -> None:
    bounds = histogram.get("bounds", [])
    counts = histogram.get("counts", [])
    idx = len(bounds)
    for i, bound in enumerate(bounds):
        if latency_ms <= bound:
            idx = i
            break
    if idx >= len(counts):
        counts.extend([0] * (idx - len(counts) + 1))
    counts[idx] += 1
    histogram["count"] = int(histogram.get("count", 0)) + 1
    histogram["sum_ms"] = float(histogram.get("sum_ms", 0.0)) + float(latency_ms)


def histogram_percentile_ms(histogram: dict[str, Any], percentile: float) -> float:
    count = int(histogram.get("count", 0))
    if count <= 0:
        return 0.0

    target_rank = max(1, int(round((percentile / 100.0) * count)))
    bounds = histogram.get("bounds", [])
    counts = histogram.get("counts", [])

    running = 0
    for idx, bucket_count in enumerate(counts):
        running += int(bucket_count)
        if running >= target_rank:
            if idx < len(bounds):
                return float(bounds[idx])
            return float(bounds[-1]) if bounds else 0.0
    return float(bounds[-1]) if bounds else 0.0


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


def record_layer_load_error(layer: str, error: Exception, phase: str) -> None:
    _state.setdefault("load_errors", []).append(
        {
            "layer": layer,
            "phase": phase,
            "error": str(error),
        }
    )


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
        try:
            model = loader()
            models[layer] = model
            lazy_loaders.pop(layer, None)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            _state.setdefault("startup_timings_ms", {})[f"{layer}_lazy_load_ms"] = elapsed_ms
            logger.info(json.dumps({"event": "lazy_layer_loaded", "layer": layer, "latency_ms": elapsed_ms}))
            return model
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            lazy_loaders.pop(layer, None)
            record_layer_load_error(layer, e, phase="lazy_load")
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
            return None


def get_layer_model(layer: str):
    model = _state.get("models", {}).get(layer)
    if model is not None:
        return model
    return ensure_layer_loaded(layer)


def _increment_classification_metric(classification: Classification) -> None:
    metrics_state = _state.get("metrics")
    if metrics_state is None:
        return
    counts = metrics_state.get("classification_counts", {})
    counts[classification.value] = counts.get(classification.value, 0) + 1


def _classify_core(req: ClassifyRequest, request_id: str | None) -> ClassifyResponse:
    pipeline = _state.get("pipeline", [])
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()

    cache_key = None
    if should_cache_response(req, pipeline):
        cache_key = build_response_cache_key(req, pipeline)
        cached = response_cache_get(cache_key)
        metrics_state = _state.get("metrics")
        if cached is not None:
            if metrics_state is not None:
                metrics_state["cache_hits_total"] = int(metrics_state.get("cache_hits_total", 0)) + 1

            total_ms = round((time.perf_counter() - t_total_start) * 1000.0, 3)
            cached["request_id"] = request_id
            cached["timings_ms"] = {"cache_hit": 1.0, "total": total_ms}
            cached_class = Classification(cached.get("classification", Classification.SAFE.value))
            _increment_classification_metric(cached_class)

            logger.info(
                json.dumps(
                    {
                        "event": "classify_summary",
                        "request_id": request_id,
                        "classification": cached_class.value,
                        "timings_ms": cached["timings_ms"],
                        "active_pipeline": pipeline,
                        "cache": "hit",
                    }
                )
            )
            return ClassifyResponse(**cached)

        if metrics_state is not None:
            metrics_state["cache_misses_total"] = int(metrics_state.get("cache_misses_total", 0)) + 1

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

    for layer in pipeline:
        t_layer_start = time.perf_counter()
        try:
            if skip_to_regression and layer != "regression":
                continue

            if layer == "lexicon":
                lexicon_filter = get_layer_model("lexicon")
                if lexicon_filter:
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
                if encoder:
                    current_embedding = encoder.encode(req.text)
                    if req.debug:
                        emb_resp = current_embedding.tolist()

            elif layer == "clustering":
                detector = get_layer_model("clustering")
                if detector and current_embedding is not None:
                    clust_resp = detector.score(current_embedding)

            elif layer == "model1":
                model1 = get_layer_model("model1")
                if model1:
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
                    continue
                model2 = get_layer_model("model2")
                if model2:
                    m2_result = model2.predict(req.text)
                    m2_resp = Model2Response(
                        label=m2_result.label,
                        confidence=m2_result.confidence,
                        high_risk_score=m2_result.high_risk_score,
                    )
                    model2_class = (
                        Classification.HIGH_RISK if m2_result.label == "high_risk" else Classification.LOW_RISK
                    )
                    final_classification = max_classification(model2_class, classification_floor)

            elif layer == "mosaic":
                mosaic_agg = get_layer_model("mosaic")
                if mosaic_agg:
                    entity_id = req.entity_id
                    if not entity_id and lex_resp and lex_resp.restricted_entities:
                        entity_id = lex_resp.restricted_entities[0].get("name")

                    if entity_id:
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
                if reg_model:
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
                            Classification.LOW_RISK
                            if reg_result["label"] == "low_risk"
                            else Classification.SAFE
                        )
                    )
                    final_classification = max_classification(reg_class, classification_floor)

        except Exception as e:
            logger.warning(
                json.dumps(
                    {
                        "event": "layer_runtime_error",
                        "request_id": request_id,
                        "layer": layer,
                        "error": str(e),
                    }
                )
            )
        finally:
            timings_ms[layer] = round((time.perf_counter() - t_layer_start) * 1000.0, 3)

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
        timings_ms=timings_ms,
    )

    _increment_classification_metric(final_classification)

    if cache_key is not None:
        cache_payload = response.model_dump(mode="json")
        cache_payload["request_id"] = None
        cache_payload["timings_ms"] = {}
        response_cache_set(cache_key, cache_payload)

    logger.info(
        json.dumps(
            {
                "event": "classify_summary",
                "request_id": request_id,
                "classification": final_classification.value,
                "timings_ms": timings_ms,
                "active_pipeline": pipeline,
                "cache": "miss" if cache_key else "disabled",
            }
        )
    )

    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    layers = load_config()
    lazy_heavy = _is_truthy(os.environ.get("NOUPE_LAZY_LOAD_HEAVY"), default=True)
    optional_layers = get_optional_layers()
    fail_on_layer_load_error = _is_truthy(os.environ.get("NOUPE_FAIL_ON_LAYER_LOAD_ERROR"), default=True)

    _state["pipeline"] = layers
    _state["optional_layers"] = sorted(optional_layers)
    _state["models"] = {}
    _state["lazy_loaders"] = {}
    _state["load_errors"] = []
    _state["load_lock"] = Lock()
    _state["startup_timings_ms"] = {}
    _state["metrics"] = {
        "requests_total": 0,
        "errors_total": 0,
        "cache_hits_total": 0,
        "cache_misses_total": 0,
        "classification_counts": {
            Classification.SAFE.value: 0,
            Classification.LOW_RISK.value: 0,
            Classification.HIGH_RISK.value: 0,
        },
        "latency_histogram_ms": build_latency_histogram(),
    }
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
                mos_mod = load_module_from_path(
                    "mos_inf", str(PROJECT_ROOT / "layer5-mosaic" / "inference.py")
                )
                _state["models"]["mosaic"] = mos_mod.MosaicAggregator.load()
            else:
                raise ValueError(f"unknown pipeline layer: {layer}")

        except Exception as e:
            record_layer_load_error(layer, e, phase="startup")
            logger.warning(json.dumps({"event": "layer_load_failed", "layer": layer, "error": str(e)}))
        finally:
            _state["startup_timings_ms"][layer] = round((time.perf_counter() - t_layer) * 1000.0, 3)

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
            }
        )
    )

    if missing_required_layers and fail_on_layer_load_error:
        raise RuntimeError(
            f"required layers failed to load: {missing_required_layers}. "
            "Set NOUPE_FAIL_ON_LAYER_LOAD_ERROR=0 to allow degraded startup."
        )

    yield
    _state.clear()


app = FastAPI(title="Noupe MNPI Classifier", version="0.1.0", lifespan=lifespan)

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

    metrics = _state.get("metrics")
    if metrics is not None:
        metrics["requests_total"] = int(metrics.get("requests_total", 0)) + 1
        if status_code >= 500:
            metrics["errors_total"] = int(metrics.get("errors_total", 0)) + 1
        observe_latency(metrics.get("latency_histogram_ms", {}), dt_ms)

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
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    lazy_loaders = _state.get("lazy_loaders", {})
    optional_layers = set(_state.get("optional_layers", []))
    required_layers = [layer for layer in pipeline if layer not in optional_layers]

    available_layers = set(models.keys()) | set(lazy_loaders.keys())
    missing = [layer for layer in required_layers if layer not in available_layers]
    is_ready = len(missing) == 0

    return ReadyResponse(
        status="ok" if is_ready else "degraded",
        ready=is_ready,
        pipeline=pipeline,
        missing_required_layers=missing,
    )


@app.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics():
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    return DiagnosticsResponse(
        status="ok",
        pipeline=pipeline,
        loaded_layers=sorted(models.keys()),
        lazy_layers=sorted(_state.get("lazy_loaders", {}).keys()),
        load_errors=_state.get("load_errors", []),
        startup_timings_ms=_state.get("startup_timings_ms", {}),
    )


@app.get("/metrics")
async def metrics():
    m = _state.get("metrics", {})
    hist = m.get("latency_histogram_ms", {})
    p50 = histogram_percentile_ms(hist, 50.0)
    p95 = histogram_percentile_ms(hist, 95.0)

    class_counts = m.get("classification_counts", {})
    lines = [
        f'noupe_requests_total {int(m.get("requests_total", 0))}',
        f'noupe_errors_total {int(m.get("errors_total", 0))}',
        f'noupe_cache_hits_total {int(m.get("cache_hits_total", 0))}',
        f'noupe_cache_misses_total {int(m.get("cache_misses_total", 0))}',
        f'noupe_request_latency_p50_ms {p50:.3f}',
        f'noupe_request_latency_p95_ms {p95:.3f}',
        f'noupe_request_latency_sum_ms {float(hist.get("sum_ms", 0.0)):.3f}',
        f'noupe_request_latency_count {int(hist.get("count", 0))}',
    ]

    bounds = hist.get("bounds", [])
    counts = hist.get("counts", [])
    for idx, bucket_count in enumerate(counts):
        le = str(bounds[idx]) if idx < len(bounds) else "+Inf"
        lines.append(f'noupe_request_latency_bucket_ms{{le="{le}"}} {int(bucket_count)}')

    lines.extend(
        [
            f'noupe_classification_total{{classification="SAFE"}} {int(class_counts.get("SAFE", 0))}',
            f'noupe_classification_total{{classification="LOW_RISK"}} {int(class_counts.get("LOW_RISK", 0))}',
            f'noupe_classification_total{{classification="HIGH_RISK"}} {int(class_counts.get("HIGH_RISK", 0))}',
        ]
    )

    return Response(content="\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify(request: Request, req: ClassifyRequest):
    return _classify_core(req, getattr(request.state, "request_id", None))


@app.post("/classify/batch", response_model=BatchClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify_batch(request: Request, req: BatchClassifyRequest):
    base_request_id = getattr(request.state, "request_id", None)
    results = []
    for idx, item in enumerate(req.items):
        item_request_id = f"{base_request_id}:{idx}" if base_request_id else None
        results.append(_classify_core(item, item_request_id))
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
