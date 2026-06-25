import os
from dataclasses import dataclass
from types import ModuleType

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

prometheus_multiprocess: ModuleType | None
try:
    from prometheus_client import multiprocess as _prometheus_multiprocess
except ImportError:  # pragma: no cover
    prometheus_multiprocess = None
else:
    prometheus_multiprocess = _prometheus_multiprocess


def get_metrics_mode() -> str:
    return "multiprocess" if os.environ.get("PROMETHEUS_MULTIPROC_DIR") else "singleprocess"


@dataclass
class DependencyStatus:
    status: str
    configured: bool
    healthy: bool | None = None
    detail: str = ""


class ObservabilityManager:
    def __init__(self) -> None:
        self.mode = get_metrics_mode()
        self.registry = CollectorRegistry(auto_describe=True) if self.mode == "singleprocess" else REGISTRY

        self.http_requests_total = Counter(
            "junas_http_requests_total",
            "Total HTTP requests handled by the API.",
            labelnames=("endpoint", "method", "status_code"),
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "junas_http_request_duration_seconds",
            "HTTP request duration in seconds.",
            labelnames=("endpoint", "method", "status_code"),
            registry=self.registry,
        )
        self.classification_results_total = Counter(
            "junas_classification_results_total",
            "Total classification results emitted by classification endpoints.",
            labelnames=("endpoint", "classification", "cache_status", "degraded"),
            registry=self.registry,
        )
        self.classification_duration_seconds = Histogram(
            "junas_classification_duration_seconds",
            "Classification duration in seconds.",
            labelnames=("endpoint", "classification", "cache_status", "degraded"),
            registry=self.registry,
        )
        self.policy_decision_duration_seconds = Histogram(
            "junas_policy_decision_duration_seconds",
            "Policy decision evaluation duration in seconds.",
            labelnames=("decision",),
            registry=self.registry,
        )
        self.layer_execution_total = Counter(
            "junas_layer_execution_total",
            "Layer execution attempts grouped by outcome.",
            labelnames=("layer", "outcome"),
            registry=self.registry,
        )
        self.layer_execution_duration_seconds = Histogram(
            "junas_layer_execution_duration_seconds",
            "Layer execution duration in seconds grouped by outcome.",
            labelnames=("layer", "outcome"),
            registry=self.registry,
        )
        self.layer_load_total = Counter(
            "junas_layer_load_total",
            "Layer load and runtime failure events grouped by phase and outcome.",
            labelnames=("layer", "phase", "outcome"),
            registry=self.registry,
        )
        self.layer_load_duration_seconds = Histogram(
            "junas_layer_load_duration_seconds",
            "Layer load and runtime failure duration in seconds grouped by phase and outcome.",
            labelnames=("layer", "phase", "outcome"),
            registry=self.registry,
        )
        self.required_layer_configured = Gauge(
            "junas_required_layer_configured",
            "Whether a required layer is configured for the active pipeline.",
            labelnames=("layer",),
            multiprocess_mode="livemin",
            registry=self.registry,
        )
        self.required_layer_available = Gauge(
            "junas_required_layer_available",
            "Whether a required layer is currently available for execution.",
            labelnames=("layer",),
            multiprocess_mode="livemin",
            registry=self.registry,
        )
        self.required_layer_warming = Gauge(
            "junas_required_layer_warming",
            "Whether a required layer is still warming.",
            labelnames=("layer",),
            multiprocess_mode="livemin",
            registry=self.registry,
        )
        self.dependency_configured = Gauge(
            "junas_dependency_configured",
            "Whether an external dependency is configured for the active runtime.",
            labelnames=("dependency",),
            multiprocess_mode="livemin",
            registry=self.registry,
        )
        self.dependency_healthy = Gauge(
            "junas_dependency_healthy",
            "Whether an external dependency is currently healthy.",
            labelnames=("dependency",),
            multiprocess_mode="livemin",
            registry=self.registry,
        )

    def observe_http_request(self, endpoint: str, method: str, status_code: int, duration_seconds: float) -> None:
        status = str(int(status_code))
        self.http_requests_total.labels(endpoint=endpoint, method=method, status_code=status).inc()
        self.http_request_duration_seconds.labels(
            endpoint=endpoint,
            method=method,
            status_code=status,
        ).observe(max(0.0, duration_seconds))

    def observe_classification(
        self,
        endpoint: str,
        classification: str,
        cache_status: str,
        degraded: bool,
        duration_seconds: float,
    ) -> None:
        degraded_label = "true" if degraded else "false"
        self.classification_results_total.labels(
            endpoint=endpoint,
            classification=classification,
            cache_status=cache_status,
            degraded=degraded_label,
        ).inc()
        self.classification_duration_seconds.labels(
            endpoint=endpoint,
            classification=classification,
            cache_status=cache_status,
            degraded=degraded_label,
        ).observe(max(0.0, duration_seconds))

    def observe_policy_decision(self, decision: str, duration_seconds: float) -> None:
        self.policy_decision_duration_seconds.labels(decision=decision).observe(max(0.0, duration_seconds))

    def observe_layer_execution(self, layer: str, outcome: str, duration_seconds: float) -> None:
        self.layer_execution_total.labels(layer=layer, outcome=outcome).inc()
        self.layer_execution_duration_seconds.labels(layer=layer, outcome=outcome).observe(max(0.0, duration_seconds))

    def observe_layer_load(self, layer: str, phase: str, outcome: str, duration_seconds: float) -> None:
        self.layer_load_total.labels(layer=layer, phase=phase, outcome=outcome).inc()
        self.layer_load_duration_seconds.labels(layer=layer, phase=phase, outcome=outcome).observe(
            max(0.0, duration_seconds)
        )

    def set_required_layer_state(self, layer: str, configured: bool, available: bool, warming: bool) -> None:
        self.required_layer_configured.labels(layer=layer).set(1.0 if configured else 0.0)
        self.required_layer_available.labels(layer=layer).set(1.0 if available else 0.0)
        self.required_layer_warming.labels(layer=layer).set(1.0 if warming else 0.0)

    def set_dependency_state(self, dependency: str, configured: bool, healthy: bool | None) -> None:
        self.dependency_configured.labels(dependency=dependency).set(1.0 if configured else 0.0)
        self.dependency_healthy.labels(dependency=dependency).set(1.0 if healthy else 0.0)

    def render_metrics(self) -> bytes:
        if self.mode == "multiprocess":
            if prometheus_multiprocess is None:  # pragma: no cover
                raise RuntimeError("prometheus_client multiprocess support is unavailable")
            registry = CollectorRegistry()
            prometheus_multiprocess.MultiProcessCollector(registry)
            return generate_latest(registry)
        return generate_latest(self.registry)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST
