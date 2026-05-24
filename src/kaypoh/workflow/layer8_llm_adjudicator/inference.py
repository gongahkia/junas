from __future__ import annotations

import ipaddress
import json
import os
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
        # Tenant-level opt-in for OpenAI specifically. Only consulted when provider=openai.
        # Defaults to False to preserve the "private-by-default" posture.
        self.tenant_opt_in_openai = bool(getattr(settings, "tenant_opt_in_openai", False))
        # Privacy-hardened input mode. `raw_text` (default) ships document text; in
        # `structured_tokens`, the adjudicator only ships abstract tokens + hashes.
        self.llm_input_mode = str(getattr(settings, "llm_input_mode", "raw_text") or "raw_text")
        # provider=local_distilled config: the LoRA adapter directory and the HF base
        # model id. Read from settings or env (env wins, matches the rest of the
        # runtime). Only consulted when provider=local_distilled.
        self.distilled_adapter_path = str(
            getattr(settings, "distilled_adapter_path", "") or os.environ.get(
                "KAYPOH_LLM_DISTILLED_ADAPTER_PATH", "",
            ) or ""
        )
        self.distilled_base_model = str(
            getattr(settings, "distilled_base_model", "") or os.environ.get(
                "KAYPOH_LLM_DISTILLED_BASE_MODEL", "",
            ) or "Qwen/Qwen2.5-1.5B-Instruct"
        )
        # cached student adjudicator (lazy-built on first local_distilled call)
        self._distilled_student: Any | None = None

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

    def _build_structured_messages(
        self,
        *,
        structured_query: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Build the system+user messages for structured-tokens mode. The LLM sees only
        the structured query (rule names, severities, jurisdiction codes, body hash,
        per-finding context-window hashes) — no raw document text."""
        from kaypoh.workflow.layer8_llm_adjudicator.structured_query import STRUCTURED_REASONS

        allowed_reasons = ", ".join(sorted(STRUCTURED_REASONS))
        return [
            {
                "role": "system",
                "content": (
                    "You are a privacy-hardened compliance adjudicator. You do NOT receive "
                    "the document text; you receive only structured tokens describing the "
                    "deterministic findings and a SHA-256 hash of the document body. "
                    "Reason about materiality and public-status from the token shape alone. "
                    "Return only compact JSON with keys: risk_label, public_status, confidence, "
                    "materiality_reason, matched_public_sources, unverified_claims, review_recommendation. "
                    "risk_label must be SAFE, LOW_RISK, or HIGH_RISK. "
                    "public_status must be public, not_public, ambiguous, or not_checked. "
                    f"materiality_reason MUST be one of: {allowed_reasons}. "
                    "matched_public_sources MUST be an empty list (you have no URL access). "
                    "unverified_claims MUST be an empty list. "
                    "review_recommendation MUST be ≤80 characters and contain no document text."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(structured_query, ensure_ascii=False, sort_keys=True),
            },
        ]

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
        findings: list | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled or self.provider == "none":
            return self._disabled("local LLM adjudication is disabled")
        # local_distilled is a fully-local provider: no base_url, no remote-URL gate,
        # no tenant opt-in. It's the "shipped student model" path — runs entirely on
        # CPU/GPU inside the kaypoh-server process. Delegate to LocalDistilledAdjudicator.
        if self.provider == "local_distilled":
            return self._adjudicate_via_local_distilled(
                text=text,
                current_classification=current_classification,
                findings=findings,
                entity_id=entity_id,
            )
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
        if self.provider not in {"vllm", "ollama", "openai", "local_distilled"}:
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
                "review_recommendation": f"unsupported LLM provider: {self.provider}",
            }
        # Tenant-level OpenAI opt-in gate. Mirrors the config-load check so a runtime
        # mutation (test harness, hot-reload) can't bypass the tenant opt-in either.
        if self.provider == "openai" and not self.tenant_opt_in_openai:
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
                "review_recommendation": (
                    "provider=openai requires tenant_opt_in_openai=true; refusing to send"
                ),
            }

        try:
            if self.llm_input_mode == "structured_tokens":
                # privacy-hardened path: no raw text or matched_text leaves the process.
                # builder, transport, and response-clamp all live in structured_query.py.
                from kaypoh.workflow.layer8_llm_adjudicator.structured_query import (
                    build_structured_query,
                    clamp_structured_output,
                )

                structured_query = build_structured_query(
                    text=text,
                    findings=list(findings or []),
                    entity_id=entity_id,
                    current_classification=current_classification,
                    public_evidence=public_evidence if isinstance(public_evidence, dict) else None,
                )
                messages = self._build_structured_messages(structured_query=structured_query)
                payload = self._call_openai_compatible(messages)
                clamped, was_clamped = clamp_structured_output(payload)
                normalized = self._normalize_payload(clamped)
                normalized["input_mode"] = "structured_tokens"
                normalized["output_clamped"] = was_clamped
                return normalized

            messages = self._build_messages(
                text=text,
                current_classification=current_classification,
                lexicon=lexicon,
                model1=model1,
                model2=model2,
                public_evidence=public_evidence,
            )
            payload = self._call_openai_compatible(messages)
            normalized = self._normalize_payload(payload)
            normalized["input_mode"] = "raw_text"
            normalized["output_clamped"] = False
            return normalized
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

    def _adjudicate_via_local_distilled(
        self,
        *,
        text: str,
        current_classification: str,
        findings: list | None,
        entity_id: str | None,
    ) -> dict[str, Any]:
        """Delegate to the local_distilled student. Lazy-loads the
        LocalDistilledAdjudicator on first call so importing this module stays free
        even when the user never reaches the local_distilled branch."""
        if not self.distilled_adapter_path:
            return {
                "status": "error",
                "provider": "local_distilled",
                "model": "",
                "risk_label": None,
                "public_status": "not_checked",
                "confidence": 0.0,
                "materiality_reason": "",
                "matched_public_sources": [],
                "unverified_claims": [],
                "review_recommendation": (
                    "provider=local_distilled requires KAYPOH_LLM_DISTILLED_ADAPTER_PATH "
                    "(or settings.llm.distilled_adapter_path) to point at a LoRA adapter dir"
                ),
            }
        if self._distilled_student is None:
            try:
                from training.distillation.student_provider import (
                    build_local_distilled_adjudicator,
                )
                from pathlib import Path as _P

                self._distilled_student = build_local_distilled_adjudicator(
                    adapter_path=_P(self.distilled_adapter_path),
                    base_model=self.distilled_base_model,
                    input_mode=self.llm_input_mode,
                )
            except Exception as exc:
                return {
                    "status": "error",
                    "provider": "local_distilled",
                    "model": self.distilled_base_model,
                    "risk_label": None,
                    "public_status": "not_checked",
                    "confidence": 0.0,
                    "materiality_reason": "",
                    "matched_public_sources": [],
                    "unverified_claims": [],
                    "review_recommendation": f"local_distilled load failed: {exc}",
                }
        return self._distilled_student.adjudicate(
            text=text,
            current_classification=current_classification,
            findings=findings,
            entity_id=entity_id,
        )

    @classmethod
    def load(cls) -> "LocalLLMAdjudicator":
        from kaypoh.configs.runtime import get_runtime_settings

        return cls(get_runtime_settings().llm)
