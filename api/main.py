import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # add project root to path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from api.schemas import ClassifyRequest, ClassifyResponse, Classification, LexiconResponse, LexiconHitResponse, Model1Response, Model2Response, HealthResponse
from fastapi.middleware.cors import CORSMiddleware

_state = {} # mutable singleton for app-scoped resources

@asynccontextmanager
async def lifespan(app: FastAPI):
    from lexicon.filter import LexiconFilter
    _state["lexicon"] = LexiconFilter()
    _state["model1"] = None
    _state["model2"] = None
    try: # lazy-load models; skip if checkpoints don't exist yet
        from importlib.machinery import SourceFileLoader
        m1_mod = SourceFileLoader("m1_inf", os.path.join(os.path.dirname(__file__), "..", "model-1", "inference.py")).load_module()
        _state["model1"] = m1_mod.FinBERTClassifier()
    except Exception:
        pass
    try:
        from importlib.machinery import SourceFileLoader
        m2_mod = SourceFileLoader("m2_inf", os.path.join(os.path.dirname(__file__), "..", "model-2", "inference.py")).load_module()
        _state["model2"] = m2_mod.BERTSeverityClassifier()
    except Exception:
        pass
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
    return HealthResponse(status="ok", lexicon_loaded=_state.get("lexicon") is not None, model1_loaded=_state.get("model1") is not None, model2_loaded=_state.get("model2") is not None)

@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    lexicon_filter = _state.get("lexicon")
    if not lexicon_filter:
        raise HTTPException(status_code=503, detail="lexicon filter not loaded")
    lex_result = lexicon_filter.run(req.text) # layer 1: lexicon check
    lex_resp = LexiconResponse(
        flagged=lex_result.flagged, high_risk_short_circuit=lex_result.high_risk_short_circuit,
        hits=[LexiconHitResponse(rule=h.rule, matched_text=h.matched_text, severity=h.severity, detail=h.detail) for h in lex_result.hits],
        restricted_entities=lex_result.restricted_entities_found,
    )
    if lex_result.high_risk_short_circuit: # short-circuit: restricted list entity or massive financial figure
        return ClassifyResponse(classification=Classification.HIGH_RISK, lexicon=lex_resp)
    model1 = _state.get("model1") # layer 2: model-1 (public vs non-public)
    if not model1:
        final = Classification.HIGH_RISK if lex_result.flagged else Classification.SAFE # fallback: lexicon-only classification
        return ClassifyResponse(classification=final, lexicon=lex_resp)
    m1_result = model1.predict(req.text)
    m1_resp = Model1Response(label=m1_result.label, confidence=m1_result.confidence, risk_score=m1_result.risk_score)
    if m1_result.label == "safe":
        return ClassifyResponse(classification=Classification.SAFE, lexicon=lex_resp, model1=m1_resp)
    model2 = _state.get("model2") # layer 3: model-2 (high risk vs low risk) — only if model-1 flagged risk
    if not model2:
        return ClassifyResponse(classification=Classification.LOW_RISK, lexicon=lex_resp, model1=m1_resp) # fallback: no model-2 → default to low risk
    m2_result = model2.predict(req.text)
    m2_resp = Model2Response(label=m2_result.label, confidence=m2_result.confidence, high_risk_score=m2_result.high_risk_score)
    final = Classification.HIGH_RISK if m2_result.label == "high_risk" else Classification.LOW_RISK
    return ClassifyResponse(classification=final, lexicon=lex_resp, model1=m1_resp, model2=m2_resp)
