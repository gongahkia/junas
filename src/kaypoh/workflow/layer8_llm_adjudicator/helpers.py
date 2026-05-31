from __future__ import annotations

import hashlib
import ipaddress
import json
from typing import Any
from urllib.parse import urlparse

import httpx

ALLOWED_HELPER_PROVIDERS = {"vllm", "ollama", "openai"}


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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RuntimeLLMHelperError(RuntimeError):
    """Raised when a configured audit-grade LLM helper cannot run safely."""


class _RuntimeLLMHelperBase:
    name = "llm_helper"
    enabled_under_profile = "audit_grade"

    def __init__(self, settings: Any):
        self.enabled = bool(getattr(settings, "enabled", False))
        self.provider = str(getattr(settings, "provider", "vllm") or "vllm").lower()
        self.api_key = str(getattr(settings, "api_key", "") or "")
        self.base_url = str(getattr(settings, "base_url", "http://127.0.0.1:8001/v1") or "").rstrip("/")
        self.model = str(getattr(settings, "model", "gpt-oss-20b") or "gpt-oss-20b")
        self.timeout_seconds = max(0.1, float(getattr(settings, "timeout_seconds", 20.0) or 20.0))
        self.allow_remote_base_url = bool(getattr(settings, "allow_remote_base_url", False))
        self.allow_remote_raw_text = bool(getattr(settings, "allow_remote_raw_text", False))
        self.tenant_opt_in_openai = bool(getattr(settings, "tenant_opt_in_openai", False))
        self._privacy_ledger: list[dict[str, Any]] = []

    def pop_privacy_ledger_events(self) -> list[dict[str, Any]]:
        events = list(self._privacy_ledger)
        self._privacy_ledger.clear()
        return events

    def health(self) -> dict[str, Any]:
        if not self.enabled or self.provider == "none":
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": "LLM provider is disabled",
            }
        if self.provider not in ALLOWED_HELPER_PROVIDERS:
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": f"unsupported LLM helper provider: {self.provider}",
            }
        if not self.base_url:
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": "LLM base URL is not configured",
            }
        if self.provider == "openai" and not self.tenant_opt_in_openai:
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": "provider=openai requires tenant_opt_in_openai=true",
            }
        if not self.allow_remote_base_url and not _is_private_or_local_base_url(self.base_url):
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": "remote LLM base URL requires allow_remote_base_url=true",
            }
        return {
            "status": "unknown",
            "configured": True,
            "healthy": None,
            "detail": f"provider={self.provider}; model={self.model}; profile=audit_grade",
        }

    def _ledger_event(
        self,
        *,
        operation: str,
        allowed: bool,
        reason: str,
        input_mode: str,
        content_sha256: str,
    ) -> dict[str, Any]:
        return {
            "destination": self.provider,
            "operation": operation,
            "allowed": allowed,
            "reason": reason,
            "query": "",
            "redactions": [],
            "input_mode": input_mode,
            "content_sha256": content_sha256,
            "content_type": "application/json" if input_mode == "structured_summary" else "text/plain",
        }

    def _refuse(
        self,
        *,
        operation: str,
        reason: str,
        input_mode: str,
        content_sha256: str,
    ) -> None:
        self._privacy_ledger.append(
            self._ledger_event(
                operation=operation,
                allowed=False,
                reason=reason,
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        )
        raise RuntimeLLMHelperError(reason)

    def _approve(
        self,
        *,
        operation: str,
        input_mode: str,
        content_sha256: str,
        sends_raw_text: bool,
    ) -> None:
        if not self.enabled or self.provider == "none":
            self._refuse(
                operation=operation,
                reason="LLM provider is disabled",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        if self.provider not in ALLOWED_HELPER_PROVIDERS:
            self._refuse(
                operation=operation,
                reason=f"unsupported LLM helper provider: {self.provider}",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        if not self.base_url:
            self._refuse(
                operation=operation,
                reason="LLM base URL is not configured",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        base_is_remote = not _is_private_or_local_base_url(self.base_url)
        if base_is_remote and not self.allow_remote_base_url:
            self._refuse(
                operation=operation,
                reason="remote LLM base URL requires allow_remote_base_url=true",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        if base_is_remote and sends_raw_text and not self.allow_remote_raw_text:
            self._refuse(
                operation=operation,
                reason="remote raw-text helper input requires allow_remote_raw_text=true",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        if self.provider == "openai" and not self.tenant_opt_in_openai:
            self._refuse(
                operation=operation,
                reason="provider=openai requires tenant_opt_in_openai=true",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        self._privacy_ledger.append(
            self._ledger_event(
                operation=operation,
                allowed=True,
                reason="LLM helper input approved by runtime privacy gates",
                input_mode=input_mode,
                content_sha256=content_sha256,
            )
        )

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _call_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
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
        parsed = json.loads(str(content))
        if not isinstance(parsed, dict):
            raise RuntimeLLMHelperError("LLM helper returned non-object JSON")
        return parsed


class RuntimeLLMDefinedTermExtractor(_RuntimeLLMHelperBase):
    name = "llm_defined_term_extractor"

    def health(self) -> dict[str, Any]:
        status = super().health()
        if (
            status.get("configured")
            and status.get("healthy") is None
            and not _is_private_or_local_base_url(self.base_url)
            and not self.allow_remote_raw_text
        ):
            return {
                "status": "down",
                "configured": True,
                "healthy": False,
                "detail": "remote defined-term extraction requires allow_remote_raw_text=true",
            }
        return status

    def extract(self, preamble: str) -> list[str]:
        content_hash = _sha256_text(preamble)
        self._approve(
            operation="llm_defined_terms",
            input_mode="raw_preamble",
            content_sha256=content_hash,
            sends_raw_text=True,
        )
        payload = self._call_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract contract defined terms from the supplied preamble. "
                        "Return only JSON with key terms, whose value is an array of strings. "
                        "Include only terms expressly introduced as definitions or aliases. "
                        "Do not include personal names, company names, amounts, dates, statutes, "
                        "or generic nouns unless the text expressly defines them."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"preamble": preamble}, ensure_ascii=False, sort_keys=True),
                },
            ]
        )
        terms = payload.get("terms", [])
        if not isinstance(terms, list):
            raise RuntimeLLMHelperError("defined-term helper returned non-list terms")
        invalid = [type(term).__name__ for term in terms if not isinstance(term, str)]
        if invalid:
            raise RuntimeLLMHelperError("defined-term helper returned non-string terms")
        return [term.strip() for term in terms if term.strip()]


class RuntimeLLMCoverageAuditor(_RuntimeLLMHelperBase):
    name = "llm_coverage_auditor"

    def audit(
        self,
        *,
        findings: list[dict[str, Any]],
        body_hash: str,
        document_type: str,
    ) -> list[dict[str, Any]]:
        self._approve(
            operation="llm_coverage_audit",
            input_mode="structured_summary",
            content_sha256=body_hash,
            sends_raw_text=False,
        )
        payload = self._call_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You audit deterministic PII/MNPI findings without seeing document text. "
                        "Use only the structured finding summary and body hash. Return only JSON "
                        "with key warnings, whose value is an array of objects. Each object must "
                        "have rule_guess, why, and confidence in [0,1]. Warnings are advisory; "
                        "do not repeat existing findings and do not claim certainty."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "body_hash": body_hash,
                            "document_type": document_type,
                            "findings": findings,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ]
        )
        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list):
            raise RuntimeLLMHelperError("coverage-audit helper returned non-list warnings")
        return list(warnings)


def build_llm_defined_term_extractor(settings: Any) -> RuntimeLLMDefinedTermExtractor:
    return RuntimeLLMDefinedTermExtractor(settings)


def build_llm_coverage_auditor(settings: Any) -> RuntimeLLMCoverageAuditor:
    return RuntimeLLMCoverageAuditor(settings)
