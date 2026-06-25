import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class ClassifyRequest(BaseModel):
    text: str
    include_offending_spans: bool = False


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_span(
    text: str,
    matched_text: str,
    *,
    layer: str = "lexicon",
    rule: str = "restricted_list",
    exact: bool = True,
):
    start_char = text.index(matched_text)
    end_char = start_char + len(matched_text)
    return {
        "id": f"{layer}:{rule}:{start_char}:{end_char}:0",
        "layer": layer,
        "rule": rule,
        "severity": "high",
        "matched_text": matched_text,
        "detail": f"test span for {matched_text}",
        "start_char": start_char,
        "end_char": end_char,
        "start_line": 1,
        "start_column": start_char + 1,
        "end_line": 1,
        "end_column": end_char + 1,
        "is_exact": exact,
        "char_length": len(matched_text),
        "line_span": 1,
        "context_before": text[max(0, start_char - 24):start_char],
        "context_after": text[end_char:min(len(text), end_char + 24)],
        "score": 5.0 if exact else 0.91,
        "score_type": "rule_score" if exact else "risk_score",
        "window_index": None if exact else 0,
        "window_count": None if exact else 1,
        "window_token_count": None if exact else 8,
        "window_stride": None if exact else 128,
        "window_max_seq_len": None if exact else 512,
    }


@app.get("/ready")
async def ready():
    return {
        "status": "ok",
        "ready": True,
        "pipeline": ["lexicon", "model1", "model2"],
        "missing_required_layers": [],
        "warming_required_layers": [],
        "reasons": [],
    }


@app.get("/diagnostics")
async def diagnostics():
    return {
        "status": "ok",
        "pipeline": ["lexicon", "model1", "model2"],
        "loaded_layers": ["lexicon", "model1", "model2"],
        "lazy_layers": [],
        "warming_required_layers": [],
        "load_errors": [],
        "startup_timings_ms": {"lexicon": 1.3, "model1": 2.1, "model2": 1.7, "total": 5.1},
        "metrics_mode": "singleprocess",
        "dependency_status": {},
        "runtime_layer_errors": {},
    }


@app.post("/classify")
async def classify(req: ClassifyRequest):
    request_id = str(uuid.uuid4())
    lowered = req.text.lower()
    spans = []

    if "merger secret" in lowered:
        if req.include_offending_spans:
            spans.append(build_span(req.text, "merger secret", layer="model2", rule="sliding_window", exact=False))
        return {
            "request_id": request_id,
            "classification": "HIGH_RISK",
            "lexicon": {
                "flagged": False,
                "high_risk_short_circuit": False,
                "total_score": 0.0,
                "score_threshold": 10.0,
                "score_threshold_exceeded": False,
                "hits": [],
                "restricted_entities": [],
            },
            "model1": {"label": "risk", "confidence": 0.93, "risk_score": 0.93},
            "model2": {"label": "high_risk", "confidence": 0.96, "high_risk_score": 0.96},
            "embedding": None,
            "clustering": None,
            "mosaic": None,
            "regression": None,
            "offending_spans": spans if req.include_offending_spans else None,
            "observability": {
                "degraded": False,
                "cache_status": "disabled",
                "active_pipeline": ["lexicon", "model1", "model2"],
                "executed_layers": ["lexicon", "model1", "model2"],
                "skipped_layers": [],
                "layer_errors": [],
            },
            "timings_ms": {"lexicon": 1.2, "model1": 2.8, "model2": 3.5, "total": 7.9},
        }

    if "acme corp" in lowered or "$5,000,000" in req.text:
        matched_text = "Acme Corp" if "acme corp" in lowered else "$5,000,000"
        if req.include_offending_spans:
            spans.append(build_span(req.text, matched_text))
        return {
            "request_id": request_id,
            "classification": "LOW_RISK",
            "lexicon": {
                "flagged": True,
                "high_risk_short_circuit": False,
                "total_score": 12.0,
                "score_threshold": 10.0,
                "score_threshold_exceeded": True,
                "hits": [
                    {
                        "rule": "restricted_list",
                        "matched_text": matched_text,
                        "severity": "high",
                        "detail": f"test lexicon hit for {matched_text}",
                        "score": 5.0,
                    }
                ],
                "restricted_entities": [{"name": "Acme Corp", "ticker": "ACME"}],
            },
            "model1": {"label": "risk", "confidence": 0.82, "risk_score": 0.82},
            "model2": None,
            "embedding": None,
            "clustering": None,
            "mosaic": None,
            "regression": None,
            "offending_spans": spans if req.include_offending_spans else None,
            "observability": {
                "degraded": False,
                "cache_status": "disabled",
                "active_pipeline": ["lexicon", "model1", "model2"],
                "executed_layers": ["lexicon", "model1"],
                "skipped_layers": ["model2"],
                "layer_errors": [],
            },
            "timings_ms": {"lexicon": 1.1, "model1": 2.4, "total": 4.2},
        }

    return {
        "request_id": request_id,
        "classification": "SAFE",
        "lexicon": {
            "flagged": False,
            "high_risk_short_circuit": False,
            "total_score": 0.0,
            "score_threshold": 10.0,
            "score_threshold_exceeded": False,
            "hits": [],
            "restricted_entities": [],
        },
        "model1": {"label": "safe", "confidence": 0.89, "risk_score": 0.11},
        "model2": None,
        "embedding": None,
        "clustering": None,
        "mosaic": None,
        "regression": None,
        "offending_spans": [] if req.include_offending_spans else None,
        "observability": {
            "degraded": False,
            "cache_status": "disabled",
            "active_pipeline": ["lexicon", "model1", "model2"],
            "executed_layers": ["lexicon", "model1"],
            "skipped_layers": ["model2"],
            "layer_errors": [],
        },
        "timings_ms": {"lexicon": 0.8, "model1": 1.6, "total": 3.0},
    }
