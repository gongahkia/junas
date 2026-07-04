from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

ENV_LOCAL_OCR_LLM_ENABLED = "JUNAS_LOCAL_OCR_LLM_ENABLED"
ENV_LOCAL_OCR_LLM_PROVIDER = "JUNAS_LOCAL_OCR_LLM_PROVIDER"
ENV_LOCAL_OCR_LLM_BASE_URL = "JUNAS_LOCAL_OCR_LLM_BASE_URL"
ENV_LOCAL_OCR_LLM_MODEL = "JUNAS_LOCAL_OCR_LLM_MODEL"
ENV_LOCAL_OCR_LLM_TIMEOUT_SECONDS = "JUNAS_LOCAL_OCR_LLM_TIMEOUT_SECONDS"
ENV_LOCAL_OCR_LLM_CONFIDENCE_THRESHOLD = "JUNAS_LOCAL_OCR_LLM_CONFIDENCE_THRESHOLD"
ENV_LOCAL_OCR_LLM_MAX_CHARS = "JUNAS_LOCAL_OCR_LLM_MAX_CHARS"

ALLOWED_LABELS = frozenset({"secret_shaped", "not_secret", "ambiguous"})
ALLOWED_REASONS = frozenset(
    {
        "token_syntax",
        "credential_keyword",
        "random_high_entropy",
        "ordinary_text",
        "too_short",
        "ambiguous",
    }
)


@dataclass(frozen=True)
class LocalOcrLLMSettings:
    enabled: bool = False
    provider: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = ""
    timeout_seconds: float = 8.0
    confidence_threshold: float = 0.72
    max_chars: int = 160


@dataclass(frozen=True)
class OcrRegionCandidate:
    text: str
    confidence: float
    start_char: int = 0
    end_char: int = 0
    source: str = "image_ocr"


@dataclass(frozen=True)
class LocalOcrLLMResult:
    status: str
    label: str
    confidence: float
    reason: str
    provider: str
    model: str
    input_chars: int
    text_sha256: str


def settings_from_env(env: dict[str, str] | None = None) -> LocalOcrLLMSettings:
    values = os.environ if env is None else env
    return LocalOcrLLMSettings(
        enabled=_truthy(values.get(ENV_LOCAL_OCR_LLM_ENABLED, "")),
        provider=(values.get(ENV_LOCAL_OCR_LLM_PROVIDER, "ollama") or "ollama").strip().lower(),
        base_url=(values.get(ENV_LOCAL_OCR_LLM_BASE_URL, "http://127.0.0.1:11434") or "").strip(),
        model=(values.get(ENV_LOCAL_OCR_LLM_MODEL, "") or "").strip(),
        timeout_seconds=_float_value(values.get(ENV_LOCAL_OCR_LLM_TIMEOUT_SECONDS), 8.0),
        confidence_threshold=_float_value(values.get(ENV_LOCAL_OCR_LLM_CONFIDENCE_THRESHOLD), 0.72),
        max_chars=max(16, int(_float_value(values.get(ENV_LOCAL_OCR_LLM_MAX_CHARS), 160))),
    )


def low_confidence_region_candidates(
    regions: Iterable[Any],
    *,
    threshold: float = 0.72,
) -> list[OcrRegionCandidate]:
    candidates: list[OcrRegionCandidate] = []
    for region in regions:
        confidence = _optional_float(getattr(region, "confidence", None))
        if confidence is None or confidence > threshold:
            continue
        text = str(getattr(region, "text", "") or "").strip()
        if not text:
            continue
        candidates.append(
            OcrRegionCandidate(
                text=text,
                confidence=confidence,
                start_char=int(getattr(region, "start_char", 0) or 0),
                end_char=int(getattr(region, "end_char", len(text)) or len(text)),
            )
        )
    return candidates


class LocalOcrRegionClassifier:
    def __init__(self, settings: LocalOcrLLMSettings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def classify_text(self, text: str, *, confidence: float) -> LocalOcrLLMResult:
        clipped = text[: self.settings.max_chars]
        text_hash = hashlib.sha256(clipped.encode("utf-8")).hexdigest()
        if not self.settings.enabled:
            return self._result("disabled", "ambiguous", 0.0, "ambiguous", clipped, text_hash)
        if self.settings.provider != "ollama":
            return self._result("error", "ambiguous", 0.0, "unsupported_provider", clipped, text_hash)
        if not self.settings.model:
            return self._result("error", "ambiguous", 0.0, "missing_model", clipped, text_hash)
        if not _is_loopback_base_url(self.settings.base_url):
            return self._result("error", "ambiguous", 0.0, "non_loopback_base_url", clipped, text_hash)
        if confidence > self.settings.confidence_threshold:
            return self._result("skipped", "ambiguous", 0.0, "confidence_above_threshold", clipped, text_hash)
        payload = {
            "model": self.settings.model,
            "stream": False,
            "prompt": _prompt(clipped, confidence),
            "options": {"temperature": 0},
        }
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds, transport=self.transport) as client:
                response = client.post(self.settings.base_url.rstrip("/") + "/api/generate", json=payload)
                response.raise_for_status()
            response_text = str(response.json().get("response", "") or "")
            parsed = _json_object_from_text(response_text)
        except Exception:
            return self._result("error", "ambiguous", 0.0, "model_call_failed", clipped, text_hash)
        label = str(parsed.get("label", "") or "").strip().lower()
        if label not in ALLOWED_LABELS:
            label = "ambiguous"
        reason = str(parsed.get("reason", "") or "").strip().lower()
        if reason not in ALLOWED_REASONS:
            reason = "ambiguous"
        return self._result(
            "classified", label, _clamp_confidence(parsed.get("confidence")), reason, clipped, text_hash
        )

    def _result(
        self,
        status: str,
        label: str,
        confidence: float,
        reason: str,
        text: str,
        text_hash: str,
    ) -> LocalOcrLLMResult:
        return LocalOcrLLMResult(
            status=status,
            label=label,
            confidence=confidence,
            reason=reason,
            provider=self.settings.provider,
            model=self.settings.model,
            input_chars=len(text),
            text_sha256=text_hash,
        )


def _prompt(text: str, confidence: float) -> str:
    reasons = ", ".join(sorted(ALLOWED_REASONS))
    return (
        "Classify this low-confidence OCR fragment as secret-shaped credential text or not. "
        "Return JSON only with keys label, confidence, reason. "
        "label must be secret_shaped, not_secret, or ambiguous. "
        f"reason must be one of: {reasons}. "
        f"OCR confidence: {confidence:.3f}. Fragment: {json.dumps(text)}"
    )


def _json_object_from_text(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("local OCR LLM response must be a JSON object")
    return parsed


def _is_loopback_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: str | None, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _clamp_confidence(value: Any) -> float:
    parsed = _optional_float(value)
    if parsed is None:
        return 0.0
    return max(0.0, min(1.0, parsed))
