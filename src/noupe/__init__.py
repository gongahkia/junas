"""Canonical Noupe package."""

from .backend.schemas import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    Classification,
    ClassifyRequest,
    ClassifyResponse,
    DiagnosticsResponse,
    HealthResponse,
    ReadyResponse,
)
from .client import (
    AsyncNoupeClient,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    NoupeAPIError,
    NoupeClient,
    async_classify_text,
    classify_text,
)

__all__ = [
    "AsyncNoupeClient",
    "BatchClassifyRequest",
    "BatchClassifyResponse",
    "Classification",
    "ClassifyRequest",
    "ClassifyResponse",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "DiagnosticsResponse",
    "HealthResponse",
    "NoupeAPIError",
    "NoupeClient",
    "ReadyResponse",
    "async_classify_text",
    "classify_text",
]
