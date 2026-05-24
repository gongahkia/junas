from __future__ import annotations

import ipaddress
import json
from typing import Any
from urllib.parse import urlparse

import httpx


ALLOWED_LABELS = {"SAFE", "LOW_RISK", "HIGH_RISK"}
ALLOWED_PUBLIC_STATUS = {"public", "not_public", "ambiguous", "not_checked"}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _is_private_or_local_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return host.endswith(".local")


class LocalLLMAdjudicator:
    def __init__(self, settings: Any):
        self.enabled = bool(getattr(settings, "enabled", False))
        self.provider = str(getattr(settings, "provider", "vllm") or "vllm").lower()
        self.api_key = str(getattr(settings, "api_key", "") or "")
        self.base_url = str(getattr(settings, "base_url", "http://127.0.0.1:8001/v1") or "").rstrip("/")
        self.model = str(getattr(settings, "model", "gpt-oss-20b") or "gpt-oss-20b")
        self.timeout_seconds = max(0.1, float(getattr(settings, "timeout_seconds", 20.0) or 20.0))
        self.allow_remote_base_url = bool(getattr(settings, "allow_remote_base_url", False))

    def _disabled(self, detail: str) -> dict[str, Any]:
        return {
            "status": "disabled",
            "provider": self.provider,
            "model": self.model,
            "risk_label": None,
            "public_status": "not_checked",
            "confidence": 0.0,
            "materiality_reason": "",
            "matched_public_sources": [],
            "unverified_claims": [],
            "review_recommendation": detail,
        }

    def _build_messages(
        self,
        *,
        text: str,
        current_classification: str,
        lexicon: Any,
        model1: Any,
        model2: Any,
        public_evidence: Any,
    ) -> list[dict[str, str]]:
        context = {
            "current_classification": current_classification,
            "lexicon": _as_dict(lexicon),
            "model1": _as_dict(model1),
            "model2": _as_dict(model2),
            "public_evidence": _as_dict(public_evidence),
        }
        return [
            {
                "role": "system",
                "content": (
                    "You are a local-only compliance adjudicator for MNPI triage. "
                    "Classify the document using the local text and public evidence. "
                    "Return only compact JSON with keys: risk_label, public_status, confidence, "
                    "materiality_reason, matched_public_sources, unverified_claims, review_recommendation. "
                    "risk_label must be SAFE, LOW_RISK, or HIGH_RISK. "
                    "public_status must be public, not_public, ambiguous, or not_checked."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "document_text": text,
                        "runtime_context": context,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _call_openai_compatible(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self._chat_completions_url(), headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()

        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
        )
        if isinstance(content, dict):
            return content
        return json.loads(str(content))

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        risk_label = str(payload.get("risk_label", "") or "").upper()
        if risk_label not in ALLOWED_LABELS:
            risk_label = ""
        public_status = str(payload.get("public_status", "ambiguous") or "ambiguous").lower()
        if public_status not in ALLOWED_PUBLIC_STATUS:
            public_status = "ambiguous"
        try:
            confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "status": "adjudicated" if risk_label else "error",
            "provider": self.provider,
            "model": self.model,
            "risk_label": risk_label or None,
            "public_status": public_status,
            "confidence": confidence,
            "materiality_reason": str(payload.get("materiality_reason", "") or ""),
            "matched_public_sources": [str(item) for item in payload.get("matched_public_sources", []) or []],
            "unverified_claims": [str(item) for item in payload.get("unverified_claims", []) or []],
            "review_recommendation": str(payload.get("review_recommendation", "") or ""),
        }

    def adjudicate(
        self,
        *,
        text: str,
        current_classification: str,
        lexicon: Any = None,
        model1: Any = None,
        model2: Any = None,
        public_evidence: Any = None,
    ) -> dict[str, Any]:
        if not self.enabled or self.provider == "none":
            return self._disabled("local LLM adjudication is disabled")
        if not self.base_url:
            return self._disabled("local LLM base URL is not configured")
        if not self.allow_remote_base_url and not _is_private_or_local_base_url(self.base_url):
            return {
                "status": "error",
                "provider": self.provider,
                "model": self.model,
                "risk_label": None,
                "public_status": "not_checked",
                "confidence": 0.0,
                "materiality_reason": "",
                "matched_public_sources": [],
                "unverified_claims": [],
                "review_recommendation": "LLM base URL is not local/private; refusing to send document text",
            }
        if self.provider not in {"vllm", "ollama"}:
            return {
                "status": "error",
                "provider": self.provider,
                "model": self.model,
                "risk_label": None,
                "public_status": "not_checked",
                "confidence": 0.0,
                "materiality_reason": "",
                "matched_public_sources": [],
                "unverified_claims": [],
                "review_recommendation": f"unsupported local LLM provider: {self.provider}",
            }

        try:
            messages = self._build_messages(
                text=text,
                current_classification=current_classification,
                lexicon=lexicon,
                model1=model1,
                model2=model2,
                public_evidence=public_evidence,
            )
            payload = self._call_openai_compatible(messages)
            return self._normalize_payload(payload)
        except Exception as exc:
            return {
                "status": "error",
                "provider": self.provider,
                "model": self.model,
                "risk_label": None,
                "public_status": "not_checked",
                "confidence": 0.0,
                "materiality_reason": "",
                "matched_public_sources": [],
                "unverified_claims": [],
                "review_recommendation": str(exc),
            }

    @classmethod
    def load(cls) -> "LocalLLMAdjudicator":
        from kaypoh.configs.runtime import get_runtime_settings

        return cls(get_runtime_settings().llm)
