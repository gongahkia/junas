import sys
import os
import argparse
import importlib.util
import json
import logging
import time
import uuid

try:
    import tomllib
except ImportError:
    import tomli as tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # add project root to path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response
from backend.schemas import ClassifyRequest, ClassifyResponse, Classification, LexiconResponse, LexiconHitResponse, Model1Response, Model2Response, HealthResponse, RegressionResponse, MosaicResponse, ReadyResponse, DiagnosticsResponse
from fastapi.middleware.cors import CORSMiddleware
from config import _cfg
from helper.determinism import configure_determinism

_state = {}
logger = logging.getLogger("noupe.backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")
_det_info = configure_determinism()
logger.info(json.dumps({"event": "determinism", **_det_info}))

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}


def max_classification(a: Classification, b: Classification) -> Classification:
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b


def load_module_from_path(module_name: str, path: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_allowed_origins() -> list[str]:
    env_val = os.environ.get("NOUPE_ALLOWED_ORIGINS")
    if env_val:
        return [o.strip() for o in env_val.split(",") if o.strip()]

    cfg_val = _cfg.get("api", {}).get("allowed_origins")
    if isinstance(cfg_val, list):
        return [str(o).strip() for o in cfg_val if str(o).strip()]
    if isinstance(cfg_val, str):
        return [o.strip() for o in cfg_val.split(",") if o.strip()]

    return ["http://localhost", "http://127.0.0.1", "null"]


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = os.environ.get("NOUPE_API_KEY", "").strip()
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing API key")

def load_config():
    # 1. Parse from CLI flags if passed
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--layers", type=str)
    args, _ = parser.parse_known_args()

    if args.layers:
        return [l.strip() for l in args.layers.split(",") if l.strip()]

    # 2. Parse from env vars
    env_layers = os.environ.get("PIPELINE_LAYERS")
    if env_layers:
         return [l.strip() for l in env_layers.split(",") if l.strip()]

    # 3. Parse from config.toml
    config_path = os.environ.get("NOUPE_CONFIG", os.path.join(os.path.dirname(__file__), "..", "config.toml"))
    if os.path.exists(config_path):
        with open(config_path, "rb") as f:
            try:
                cfg = tomllib.load(f)
                return cfg.get("pipeline", {}).get("layers", ["lexicon", "model1", "model2"])
            except Exception as e:
                print(f"Error parsing config.toml: {e}")
                
    # Default fallback
    return ["lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    layers = load_config()
    _state["pipeline"] = layers
    _state["models"] = {}
    _state["load_errors"] = []

    for layer in layers:
        if layer == "lexicon":
            try:
                lex_mod = load_module_from_path("lex_filter", os.path.join(os.path.dirname(__file__), "..", "layer1-lexicon", "filter.py"))
                _state["models"]["lexicon"] = lex_mod.LexiconFilter()
            except Exception as e:
                print(f"Failed to load lexicon: {e}")
                _state["load_errors"].append({"layer": "lexicon", "error": str(e)})

        elif layer == "embedding":
            try:
                emb_mod = load_module_from_path("emb_inf", os.path.join(os.path.dirname(__file__), "..", "layer2-embeddings", "inference.py"))
                _state["models"]["embedding"] = emb_mod.EmbeddingsEncoder.get_instance()
            except Exception as e:
                print(f"Failed to load embedding: {e}")
                _state["load_errors"].append({"layer": "embedding", "error": str(e)})

        elif layer == "clustering":
            try:
                clust_mod = load_module_from_path("clust_inf", os.path.join(os.path.dirname(__file__), "..", "layer3-clustering", "isolation_forest.py"))
                _state["models"]["clustering"] = clust_mod.MNPIAnomalyDetector.load()
            except Exception as e:
                print(f"Failed to load clustering: {e}")
                _state["load_errors"].append({"layer": "clustering", "error": str(e)})

        elif layer == "model1":
            try:
                m1_mod = load_module_from_path("m1_inf", os.path.join(os.path.dirname(__file__), "..", "layer4-classification", "model-1", "inference.py"))
                _state["models"]["model1"] = m1_mod.FinBERTClassifier()
            except Exception as e:
                print(f"Failed to load model1: {e}")
                _state["load_errors"].append({"layer": "model1", "error": str(e)})

        elif layer == "model2":
            try:
                m2_mod = load_module_from_path("m2_inf", os.path.join(os.path.dirname(__file__), "..", "layer4-classification", "model-2", "inference.py"))
                _state["models"]["model2"] = m2_mod.BERTSeverityClassifier()
            except Exception as e:
                print(f"Failed to load model2: {e}")
                _state["load_errors"].append({"layer": "model2", "error": str(e)})

        elif layer == "regression":
            try:
                reg_mod = load_module_from_path("reg_inf", os.path.join(os.path.dirname(__file__), "..", "layer6-regression", "inference.py"))
                _state["models"]["regression"] = reg_mod.XGBoostRegression()
            except Exception as e:
                print(f"Failed to load regression: {e}")
                _state["load_errors"].append({"layer": "regression", "error": str(e)})

        elif layer == "mosaic":
            try:
                mos_mod = load_module_from_path("mos_inf", os.path.join(os.path.dirname(__file__), "..", "layer5-mosaic", "inference.py"))
                _state["models"]["mosaic"] = mos_mod.MosaicAggregator.load()
            except Exception as e:
                print(f"Failed to load mosaic: {e}")
                _state["load_errors"].append({"layer": "mosaic", "error": str(e)})

    print(f"Initialized pipeline layers: {layers}")
    yield
    _state.clear()

app = FastAPI(title="Noupe MNPI Classifier", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        dt_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        logger.info(json.dumps({
            "event": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
            "latency_ms": dt_ms,
        }))
        raise

    dt_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    response.headers["X-Request-ID"] = request_id
    logger.info(json.dumps({
        "event": "request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "latency_ms": dt_ms,
    }))
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
        regression_loaded="regression" in models
    )


@app.get("/ready", response_model=ReadyResponse)
async def ready():
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})

    # Optional layers can be down without blocking core readiness.
    optional_layers = {"mosaic", "regression"}
    required_layers = [layer for layer in pipeline if layer not in optional_layers]
    missing = [layer for layer in required_layers if layer not in models]
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
        load_errors=_state.get("load_errors", []),
    )

@app.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify(request: Request, req: ClassifyRequest):
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})
    timings_ms: dict[str, float] = {}
    t_total_start = time.perf_counter()

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
    skip_model2 = False

    for layer in pipeline:
        t_layer_start = time.perf_counter()
        if skip_to_regression and layer != "regression":
            timings_ms[layer] = round((time.perf_counter() - t_layer_start) * 1000.0, 3)
            continue

        if layer == "lexicon":
            lexicon_filter = models.get("lexicon")
            if lexicon_filter:
                lex_result = lexicon_filter.run(req.text)
                lex_resp = LexiconResponse(
                    flagged=lex_result.flagged, high_risk_short_circuit=lex_result.high_risk_short_circuit,
                    total_score=lex_result.total_score,
                    hits=[LexiconHitResponse(rule=h.rule, matched_text=h.matched_text, severity=h.severity, detail=h.detail, score=h.score) for h in lex_result.hits],
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
            encoder = models.get("embedding")
            if encoder:
                current_embedding = encoder.encode(req.text)
                if req.debug:
                    emb_resp = current_embedding.tolist()

        elif layer == "clustering":
            detector = models.get("clustering")
            if detector and current_embedding is not None:
                clust_resp = detector.score(current_embedding)

        elif layer == "model1":
            model1 = models.get("model1")
            if model1:
                m1_result = model1.predict(req.text)
                m1_resp = Model1Response(label=m1_result.label, confidence=m1_result.confidence, risk_score=m1_result.risk_score)
                if m1_result.label == "safe":
                    final_classification = max_classification(Classification.SAFE, classification_floor)
                    skip_model2 = True
                else:
                    final_classification = max_classification(Classification.LOW_RISK, classification_floor)

        elif layer == "model2":
            if skip_model2:
                continue
            model2 = models.get("model2")
            if model2:
                m2_result = model2.predict(req.text)
                m2_resp = Model2Response(label=m2_result.label, confidence=m2_result.confidence, high_risk_score=m2_result.high_risk_score)
                model2_class = Classification.HIGH_RISK if m2_result.label == "high_risk" else Classification.LOW_RISK
                final_classification = max_classification(model2_class, classification_floor)


        elif layer == "mosaic":
            mosaic_agg = models.get("mosaic")
            if mosaic_agg:
                entity_id = req.entity_id
                if not entity_id and lex_resp and lex_resp.restricted_entities:
                    entity_id = lex_resp.restricted_entities[0].get("name")
                    
                if entity_id:
                    is_lr = (final_classification == Classification.LOW_RISK)
                    m_result = mosaic_agg.aggregate(entity_id=entity_id, is_low_risk=is_lr)
                    mosaic_resp = MosaicResponse(escalated=m_result["escalate_to_high_risk"], count=m_result["count"])
                    
                    if is_lr and m_result["escalate_to_high_risk"]:
                        classification_floor = Classification.HIGH_RISK
                        final_classification = Classification.HIGH_RISK

        elif layer == "regression":
            reg_model = models.get("regression")
            if reg_model:
                lex_score = lex_resp.total_score if lex_resp else 0.0
                m1_score = m1_resp.risk_score if m1_resp else 0.0
                m2_score = m2_resp.high_risk_score if m2_resp else 0.0
                clust_score = clust_resp.get("anomaly_score", 0.0) if clust_resp else 0.0
                m_count = mosaic_resp.count if mosaic_resp else 0
                
                features = [lex_score, m1_score, m2_score, clust_score, m_count]
                reg_result = reg_model.predict(features)
                reg_resp = RegressionResponse(risk_score=reg_result["risk_score"], reasoning=reg_result["reasoning"])
                
                reg_class = Classification.HIGH_RISK if reg_result["label"] == "high_risk" else (Classification.LOW_RISK if reg_result["label"] == "low_risk" else Classification.SAFE)
                final_classification = max_classification(reg_class, classification_floor)
        timings_ms[layer] = round((time.perf_counter() - t_layer_start) * 1000.0, 3)

    timings_ms["total"] = round((time.perf_counter() - t_total_start) * 1000.0, 3)
    logger.info(json.dumps({
        "event": "classify_summary",
        "request_id": getattr(request.state, "request_id", None),
        "classification": final_classification.value,
        "timings_ms": timings_ms,
        "active_pipeline": pipeline,
    }))

    return ClassifyResponse(
        request_id=getattr(request.state, "request_id", None),
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
