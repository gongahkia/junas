"""Canonical Kaypoh package."""

from .backend.schemas import (
    AnonymizeRequest,
    AnonymizeResponse,
    BatchClassifyRequest,
    BatchClassifyResponse,
    Classification,
    ClassifyRequest,
    ClassifyResponse,
    DiagnosticsResponse,
    HealthResponse,
    ReadyResponse,
    ReviewRequest,
    ReviewResponse,
)
from .client import (
    AsyncKaypohClient,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    KaypohAPIError,
    KaypohClient,
    async_classify_text,
    classify_text,
)

__all__ = [
    "AnonymizeRequest",
    "AnonymizeResponse",
    "AsyncKaypohClient",
    "BatchClassifyRequest",
    "BatchClassifyResponse",
    "Classification",
    "ClassifyRequest",
    "ClassifyResponse",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "DiagnosticsResponse",
    "HealthResponse",
    "KaypohAPIError",
    "KaypohClient",
    "ReadyResponse",
    "ReviewRequest",
    "ReviewResponse",
    "async_classify_text",
    "classify_text",
]
