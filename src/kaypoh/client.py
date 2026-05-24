from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .backend.schemas import (
    AnonymizeRequest,
    AnonymizeResponse,
    BatchClassifyRequest,
    BatchClassifyResponse,
    ClassifyRequest,
    ClassifyResponse,
    DiagnosticsResponse,
    HealthResponse,
    ReadyResponse,
    ReidentifyMappingEntry,
    ReidentifyRequest,
    ReidentifyResponse,
    ReviewRequest,
    ReviewResponse,
)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _extract_error_detail(payload: Any) -> str:
    if isinstance(payload, Mapping):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail.strip()
        if isinstance(detail, Sequence) and not isinstance(detail, (str, bytes, bytearray)):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        parts.append(text)
                    continue
                if not isinstance(item, Mapping):
                    continue
                location = ".".join(str(part) for part in item.get("loc", []) if part != "body")
                message = str(item.get("msg", "")).strip()
                if message:
                    parts.append(f"{location}: {message}" if location else message)
            return "; ".join(parts)
    return ""


def _build_api_error(response: httpx.Response) -> "KaypohAPIError":
    body: Any
    detail = ""
    try:
        body = response.json()
        detail = _extract_error_detail(body)
    except ValueError:
        body = response.text
        if isinstance(body, str):
            detail = body.strip()

    message = f"Kaypoh API request failed with status {response.status_code}"
    if detail:
        message = f"{message}: {detail}"

    return KaypohAPIError(
        message,
        status_code=response.status_code,
        detail=detail,
        body=body,
    )


def _coerce_classify_request(
    *,
    request: ClassifyRequest | Mapping[str, Any] | None,
    text: str | None,
    entity_id: str | None,
    debug: bool,
    include_offending_spans: bool,
) -> ClassifyRequest:
    if request is not None:
        if text is not None:
            raise ValueError("pass either request=... or text=..., not both")
        if isinstance(request, ClassifyRequest):
            return request
        return ClassifyRequest.model_validate(request)

    if text is None:
        raise ValueError("text is required when request is not provided")

    return ClassifyRequest(
        text=text,
        entity_id=entity_id,
        debug=debug,
        include_offending_spans=include_offending_spans,
    )


def _coerce_batch_request(
    *,
    request: BatchClassifyRequest | Mapping[str, Any] | None,
    items: Sequence[ClassifyRequest | Mapping[str, Any]] | None,
) -> BatchClassifyRequest:
    if request is not None:
        if items is not None:
            raise ValueError("pass either request=... or items=..., not both")
        if isinstance(request, BatchClassifyRequest):
            return request
        return BatchClassifyRequest.model_validate(request)

    if items is None:
        raise ValueError("items is required when request is not provided")

    normalized_items = [
        item if isinstance(item, ClassifyRequest) else ClassifyRequest.model_validate(item)
        for item in items
    ]
    return BatchClassifyRequest(items=normalized_items)


def _coerce_review_request(
    *,
    request: ReviewRequest | Mapping[str, Any] | None,
    text: str | None,
    document_base64: str | None,
    document_filename: str | None,
    document_mime_type: str | None,
    source_jurisdiction: str,
    destination_jurisdiction: str,
    document_type: str,
    review_profile: str,
    entity_id: str | None,
    include_suggestions: bool,
) -> ReviewRequest:
    if request is not None:
        if text is not None or document_base64 is not None:
            raise ValueError("pass either request=... or text/document_base64=..., not both")
        if isinstance(request, ReviewRequest):
            return request
        return ReviewRequest.model_validate(request)

    return ReviewRequest(
        text=text,
        document_base64=document_base64,
        document_filename=document_filename,
        document_mime_type=document_mime_type,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=destination_jurisdiction,
        document_type=document_type,
        review_profile=review_profile,
        entity_id=entity_id,
        include_suggestions=include_suggestions,
    )


def _coerce_anonymize_request(
    *,
    request: AnonymizeRequest | Mapping[str, Any] | None,
    text: str | None,
    document_base64: str | None,
    document_filename: str | None,
    document_mime_type: str | None,
    source_jurisdiction: str,
    destination_jurisdiction: str,
    document_type: str,
    review_profile: str,
    entity_id: str | None,
    include_suggestions: bool,
    include_mnpi_scalars: bool,
) -> AnonymizeRequest:
    if request is not None:
        if text is not None or document_base64 is not None:
            raise ValueError("pass either request=... or text/document_base64=..., not both")
        if isinstance(request, AnonymizeRequest):
            return request
        return AnonymizeRequest.model_validate(request)

    return AnonymizeRequest(
        text=text,
        document_base64=document_base64,
        document_filename=document_filename,
        document_mime_type=document_mime_type,
        source_jurisdiction=source_jurisdiction,
        destination_jurisdiction=destination_jurisdiction,
        document_type=document_type,
        review_profile=review_profile,
        entity_id=entity_id,
        include_suggestions=include_suggestions,
        include_mnpi_scalars=include_mnpi_scalars,
    )


def _coerce_reidentify_request(
    *,
    request: ReidentifyRequest | Mapping[str, Any] | None,
    anonymized_text: str | None,
    mapping: Sequence[ReidentifyMappingEntry | Mapping[str, Any]] | None,
) -> ReidentifyRequest:
    if request is not None:
        if anonymized_text is not None or mapping is not None:
            raise ValueError("pass either request=... or anonymized_text/mapping=..., not both")
        if isinstance(request, ReidentifyRequest):
            return request
        return ReidentifyRequest.model_validate(request)

    if anonymized_text is None:
        raise ValueError("anonymized_text is required when request is not provided")
    if mapping is None:
        raise ValueError("mapping is required when request is not provided")

    normalized_mapping = [
        entry if isinstance(entry, ReidentifyMappingEntry) else ReidentifyMappingEntry.model_validate(entry)
        for entry in mapping
    ]
    return ReidentifyRequest(anonymized_text=anonymized_text, mapping=normalized_mapping)


class KaypohAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int, detail: str = "", body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail
        self.body = body


class KaypohClient:
    """Typed Python client for the Kaypoh backend HTTP API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        api_key: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "KaypohClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = self._client.request(method, path, json=json_body)
        if response.is_error:
            raise _build_api_error(response)
        return response.json()

    def health(self) -> HealthResponse:
        return HealthResponse.model_validate(self._request_json("GET", "/health"))

    def ready(self) -> ReadyResponse:
        return ReadyResponse.model_validate(self._request_json("GET", "/ready"))

    def diagnostics(self) -> DiagnosticsResponse:
        return DiagnosticsResponse.model_validate(self._request_json("GET", "/diagnostics"))

    def metrics(self) -> str:
        response = self._client.get("/metrics")
        if response.is_error:
            raise _build_api_error(response)
        return response.text

    def classify(
        self,
        text: str | None = None,
        *,
        entity_id: str | None = None,
        debug: bool = False,
        include_offending_spans: bool = False,
        request: ClassifyRequest | Mapping[str, Any] | None = None,
    ) -> ClassifyResponse:
        payload = _coerce_classify_request(
            request=request,
            text=text,
            entity_id=entity_id,
            debug=debug,
            include_offending_spans=include_offending_spans,
        )
        return ClassifyResponse.model_validate(
            self._request_json(
                "POST",
                "/classify",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    def classify_batch(
        self,
        items: Sequence[ClassifyRequest | Mapping[str, Any]] | None = None,
        *,
        request: BatchClassifyRequest | Mapping[str, Any] | None = None,
    ) -> BatchClassifyResponse:
        payload = _coerce_batch_request(request=request, items=items)
        return BatchClassifyResponse.model_validate(
            self._request_json(
                "POST",
                "/classify/batch",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    def classify_many(
        self,
        items: Sequence[ClassifyRequest | Mapping[str, Any]],
    ) -> list[ClassifyResponse]:
        return self.classify_batch(items=items).results

    def review(
        self,
        text: str | None = None,
        *,
        document_base64: str | None = None,
        document_filename: str | None = None,
        document_mime_type: str | None = None,
        source_jurisdiction: str = "SG",
        destination_jurisdiction: str = "SG",
        document_type: str = "generic",
        review_profile: str = "strict",
        entity_id: str | None = None,
        include_suggestions: bool = True,
        request: ReviewRequest | Mapping[str, Any] | None = None,
    ) -> ReviewResponse:
        payload = _coerce_review_request(
            request=request,
            text=text,
            document_base64=document_base64,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            document_type=document_type,
            review_profile=review_profile,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
        )
        return ReviewResponse.model_validate(
            self._request_json(
                "POST",
                "/review",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    def anonymize(
        self,
        text: str | None = None,
        *,
        document_base64: str | None = None,
        document_filename: str | None = None,
        document_mime_type: str | None = None,
        source_jurisdiction: str = "SG",
        destination_jurisdiction: str = "SG",
        document_type: str = "generic",
        review_profile: str = "strict",
        entity_id: str | None = None,
        include_suggestions: bool = True,
        include_mnpi_scalars: bool = True,
        request: AnonymizeRequest | Mapping[str, Any] | None = None,
    ) -> AnonymizeResponse:
        payload = _coerce_anonymize_request(
            request=request,
            text=text,
            document_base64=document_base64,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            document_type=document_type,
            review_profile=review_profile,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
            include_mnpi_scalars=include_mnpi_scalars,
        )
        return AnonymizeResponse.model_validate(
            self._request_json(
                "POST",
                "/anonymize",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    def reidentify(
        self,
        anonymized_text: str | None = None,
        *,
        mapping: Sequence[ReidentifyMappingEntry | Mapping[str, Any]] | None = None,
        request: ReidentifyRequest | Mapping[str, Any] | None = None,
    ) -> ReidentifyResponse:
        payload = _coerce_reidentify_request(
            request=request,
            anonymized_text=anonymized_text,
            mapping=mapping,
        )
        return ReidentifyResponse.model_validate(
            self._request_json(
                "POST",
                "/reidentify",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )


class AsyncKaypohClient:
    """Async typed Python client for the Kaypoh backend HTTP API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        api_key: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncKaypohClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = await self._client.request(method, path, json=json_body)
        if response.is_error:
            raise _build_api_error(response)
        return response.json()

    async def health(self) -> HealthResponse:
        return HealthResponse.model_validate(await self._request_json("GET", "/health"))

    async def ready(self) -> ReadyResponse:
        return ReadyResponse.model_validate(await self._request_json("GET", "/ready"))

    async def diagnostics(self) -> DiagnosticsResponse:
        return DiagnosticsResponse.model_validate(await self._request_json("GET", "/diagnostics"))

    async def metrics(self) -> str:
        response = await self._client.get("/metrics")
        if response.is_error:
            raise _build_api_error(response)
        return response.text

    async def classify(
        self,
        text: str | None = None,
        *,
        entity_id: str | None = None,
        debug: bool = False,
        include_offending_spans: bool = False,
        request: ClassifyRequest | Mapping[str, Any] | None = None,
    ) -> ClassifyResponse:
        payload = _coerce_classify_request(
            request=request,
            text=text,
            entity_id=entity_id,
            debug=debug,
            include_offending_spans=include_offending_spans,
        )
        return ClassifyResponse.model_validate(
            await self._request_json(
                "POST",
                "/classify",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    async def classify_batch(
        self,
        items: Sequence[ClassifyRequest | Mapping[str, Any]] | None = None,
        *,
        request: BatchClassifyRequest | Mapping[str, Any] | None = None,
    ) -> BatchClassifyResponse:
        payload = _coerce_batch_request(request=request, items=items)
        return BatchClassifyResponse.model_validate(
            await self._request_json(
                "POST",
                "/classify/batch",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    async def classify_many(
        self,
        items: Sequence[ClassifyRequest | Mapping[str, Any]],
    ) -> list[ClassifyResponse]:
        return (await self.classify_batch(items=items)).results

    async def review(
        self,
        text: str | None = None,
        *,
        document_base64: str | None = None,
        document_filename: str | None = None,
        document_mime_type: str | None = None,
        source_jurisdiction: str = "SG",
        destination_jurisdiction: str = "SG",
        document_type: str = "generic",
        review_profile: str = "strict",
        entity_id: str | None = None,
        include_suggestions: bool = True,
        request: ReviewRequest | Mapping[str, Any] | None = None,
    ) -> ReviewResponse:
        payload = _coerce_review_request(
            request=request,
            text=text,
            document_base64=document_base64,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            document_type=document_type,
            review_profile=review_profile,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
        )
        return ReviewResponse.model_validate(
            await self._request_json(
                "POST",
                "/review",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    async def anonymize(
        self,
        text: str | None = None,
        *,
        document_base64: str | None = None,
        document_filename: str | None = None,
        document_mime_type: str | None = None,
        source_jurisdiction: str = "SG",
        destination_jurisdiction: str = "SG",
        document_type: str = "generic",
        review_profile: str = "strict",
        entity_id: str | None = None,
        include_suggestions: bool = True,
        include_mnpi_scalars: bool = True,
        request: AnonymizeRequest | Mapping[str, Any] | None = None,
    ) -> AnonymizeResponse:
        payload = _coerce_anonymize_request(
            request=request,
            text=text,
            document_base64=document_base64,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            document_type=document_type,
            review_profile=review_profile,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
            include_mnpi_scalars=include_mnpi_scalars,
        )
        return AnonymizeResponse.model_validate(
            await self._request_json(
                "POST",
                "/anonymize",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )

    async def reidentify(
        self,
        anonymized_text: str | None = None,
        *,
        mapping: Sequence[ReidentifyMappingEntry | Mapping[str, Any]] | None = None,
        request: ReidentifyRequest | Mapping[str, Any] | None = None,
    ) -> ReidentifyResponse:
        payload = _coerce_reidentify_request(
            request=request,
            anonymized_text=anonymized_text,
            mapping=mapping,
        )
        return ReidentifyResponse.model_validate(
            await self._request_json(
                "POST",
                "/reidentify",
                json_body=payload.model_dump(mode="json", exclude_none=True),
            )
        )


def classify_text(
    text: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
    entity_id: str | None = None,
    debug: bool = False,
    include_offending_spans: bool = False,
    timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.BaseTransport | None = None,
) -> ClassifyResponse:
    with KaypohClient(
        base_url,
        api_key=api_key,
        timeout=timeout,
        transport=transport,
    ) as client:
        return client.classify(
            text=text,
            entity_id=entity_id,
            debug=debug,
            include_offending_spans=include_offending_spans,
        )


async def async_classify_text(
    text: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
    entity_id: str | None = None,
    debug: bool = False,
    include_offending_spans: bool = False,
    timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS,
    transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
) -> ClassifyResponse:
    async with AsyncKaypohClient(
        base_url,
        api_key=api_key,
        timeout=timeout,
        transport=transport,
    ) as client:
        return await client.classify(
            text=text,
            entity_id=entity_id,
            debug=debug,
            include_offending_spans=include_offending_spans,
        )


__all__ = [
    "AnonymizeRequest",
    "AnonymizeResponse",
    "AsyncKaypohClient",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "KaypohAPIError",
    "KaypohClient",
    "ReidentifyMappingEntry",
    "ReidentifyRequest",
    "ReidentifyResponse",
    "async_classify_text",
    "classify_text",
]
