from collections import OrderedDict
from contextlib import asynccontextmanager
from threading import Lock
from types import SimpleNamespace

import backend.main as main
from backend.observability import ObservabilityManager


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class DummyVector:
    def __init__(self, values=None):
        self.values = values or [0.1, 0.2, 0.3]

    def tolist(self):
        return list(self.values)


class DummyLexiconFilter:
    def __init__(
        self,
        *,
        flagged: bool = False,
        short_circuit: bool = False,
        total_score: float = 0.0,
        restricted_entities: list[dict] | None = None,
        hits: list | None = None,
    ):
        self.flagged = flagged
        self.short_circuit = short_circuit
        self.total_score = total_score
        self.restricted_entities = restricted_entities or []
        self.hits = list(hits or [])

    def run(self, text: str):
        return SimpleNamespace(
            flagged=self.flagged,
            high_risk_short_circuit=self.short_circuit,
            total_score=self.total_score,
            score_threshold=10.0,
            score_threshold_exceeded=self.total_score >= 10.0,
            hits=list(self.hits),
            restricted_entities_found=list(self.restricted_entities),
        )


class DummyEmbedding:
    def __init__(self, values=None):
        self.vector = DummyVector(values)

    def encode(self, text: str):
        return self.vector


class DummyClustering:
    def __init__(self, anomaly_score: float = 0.1):
        self.anomaly_score = anomaly_score

    def score(self, embedding):
        return {
            "anomaly_score": self.anomaly_score,
            "is_anomaly": self.anomaly_score >= 0.5,
            "raw_score": self.anomaly_score,
        }


class DummyModel1:
    def __init__(
        self,
        label: str = "safe",
        confidence: float = 0.9,
        risk_score: float = 0.1,
        top_window: dict | None = None,
        window_count: int = 1,
    ):
        self.label = label
        self.confidence = confidence
        self.risk_score = risk_score
        self.top_window = top_window
        self.window_count = window_count

    def predict(self, text: str):
        return SimpleNamespace(
            label=self.label,
            confidence=self.confidence,
            risk_score=self.risk_score,
            top_window=self.top_window,
            window_count=self.window_count,
        )


class DummyModel2:
    def __init__(
        self,
        label: str = "low_risk",
        confidence: float = 0.7,
        high_risk_score: float = 0.2,
        top_window: dict | None = None,
        window_count: int = 1,
    ):
        self.label = label
        self.confidence = confidence
        self.high_risk_score = high_risk_score
        self.top_window = top_window
        self.window_count = window_count

    def predict(self, text: str):
        return SimpleNamespace(
            label=self.label,
            confidence=self.confidence,
            high_risk_score=self.high_risk_score,
            top_window=self.top_window,
            window_count=self.window_count,
        )


class DummyRegression:
    def __init__(self, label: str = "safe", risk_score: float = 0.2, reasoning: str = "stub"):
        self.label = label
        self.risk_score = risk_score
        self.reasoning = reasoning

    def predict(self, features: dict):
        return {
            "label": self.label,
            "risk_score": self.risk_score,
            "reasoning": self.reasoning,
        }


class DummyMosaic:
    def __init__(self, *, escalated: bool = False, count: int = 0, connected: bool = True):
        self.escalated = escalated
        self.count = count
        self.connected = connected
        self.host = "localhost"
        self.port = 6379

    def aggregate(self, entity_id: str, is_low_risk: bool):
        return {
            "escalate_to_high_risk": self.escalated,
            "count": self.count,
        }


def seed_test_state(
    *,
    pipeline: list[str] | None = None,
    optional_layers: list[str] | None = None,
    models: dict | None = None,
    lazy_loaders: dict | None = None,
    load_errors: list[dict] | None = None,
):
    main._state.clear()
    main._state.update(
        {
            "pipeline": list(pipeline or []),
            "optional_layers": list(optional_layers or []),
            "models": dict(models or {}),
            "lazy_loaders": dict(lazy_loaders or {}),
            "load_errors": list(load_errors or []),
            "load_lock": Lock(),
            "warming_lock": Lock(),
            "warming_required_layers": [],
            "startup_timings_ms": {},
            "runtime_layer_errors": {},
            "observability": ObservabilityManager(),
            "cache_cfg": {"size": 32, "ttl_seconds": 60.0},
            "response_cache": OrderedDict(),
            "response_cache_lock": Lock(),
        }
    )
    main.refresh_observability_state()


seed_test_state(
    pipeline=["lexicon", "embedding", "clustering", "model1", "model2"],
    models={
        "lexicon": DummyLexiconFilter(),
        "embedding": DummyEmbedding(),
        "clustering": DummyClustering(),
        "model1": DummyModel1(label="safe"),
        "model2": DummyModel2(label="low_risk"),
    },
)

app = main.app
