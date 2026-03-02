import sys
import os
import argparse

try:
    import tomllib
except ImportError:
    import tomli as tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # add project root to path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.schemas import ClassifyRequest, ClassifyResponse, Classification, LexiconResponse, LexiconHitResponse, Model1Response, Model2Response, HealthResponse, RegressionResponse, MosaicResponse
from fastapi.middleware.cors import CORSMiddleware

_state = {}

RISK_ORDER = {
    Classification.SAFE: 0,
    Classification.LOW_RISK: 1,
    Classification.HIGH_RISK: 2,
}


def max_classification(a: Classification, b: Classification) -> Classification:
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b

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

    from importlib.machinery import SourceFileLoader

    for layer in layers:
        if layer == "lexicon":
            try:
                lex_mod = SourceFileLoader("lex_filter", os.path.join(os.path.dirname(__file__), "..", "layer1-lexicon", "filter.py")).load_module()
                _state["models"]["lexicon"] = lex_mod.LexiconFilter()
            except Exception as e:
                print(f"Failed to load lexicon: {e}")

        elif layer == "embedding":
            try:
                emb_mod = SourceFileLoader("emb_inf", os.path.join(os.path.dirname(__file__), "..", "layer2-embeddings", "inference.py")).load_module()
                _state["models"]["embedding"] = emb_mod.EmbeddingsEncoder.get_instance()
            except Exception as e:
                print(f"Failed to load embedding: {e}")

        elif layer == "clustering":
            try:
                clust_mod = SourceFileLoader("clust_inf", os.path.join(os.path.dirname(__file__), "..", "layer3-clustering", "isolation_forest.py")).load_module()
                _state["models"]["clustering"] = clust_mod.MNPIAnomalyDetector.load()
            except Exception as e:
                print(f"Failed to load clustering: {e}")

        elif layer == "model1":
            try:
                m1_mod = SourceFileLoader("m1_inf", os.path.join(os.path.dirname(__file__), "..", "layer4-classification", "model-1", "inference.py")).load_module()
                _state["models"]["model1"] = m1_mod.FinBERTClassifier()
            except Exception as e:
                print(f"Failed to load model1: {e}")

        elif layer == "model2":
            try:
                m2_mod = SourceFileLoader("m2_inf", os.path.join(os.path.dirname(__file__), "..", "layer4-classification", "model-2", "inference.py")).load_module()
                _state["models"]["model2"] = m2_mod.BERTSeverityClassifier()
            except Exception as e:
                print(f"Failed to load model2: {e}")

        elif layer == "regression":
            try:
                reg_mod = SourceFileLoader("reg_inf", os.path.join(os.path.dirname(__file__), "..", "layer6-regression", "inference.py")).load_module()
                _state["models"]["regression"] = reg_mod.XGBoostRegression()
            except Exception as e:
                print(f"Failed to load regression: {e}")

        elif layer == "mosaic":
            try:
                mos_mod = SourceFileLoader("mos_inf", os.path.join(os.path.dirname(__file__), "..", "layer5-mosaic", "inference.py")).load_module()
                _state["models"]["mosaic"] = mos_mod.MosaicAggregator.load()
            except Exception as e:
                print(f"Failed to load mosaic: {e}")

    print(f"Initialized pipeline layers: {layers}")
    yield
    _state.clear()

app = FastAPI(title="Noupe MNPI Classifier", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    pipeline = _state.get("pipeline", [])
    models = _state.get("models", {})

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
        if skip_to_regression and layer != "regression":
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

    return ClassifyResponse(
        classification=final_classification,
        lexicon=lex_resp,
        model1=m1_resp,
        model2=m2_resp,
        embedding=emb_resp,
        clustering=clust_resp,
        mosaic=mosaic_resp,
        regression=reg_resp
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
