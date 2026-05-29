from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
MONEY_RE = re.compile(
    r"(?:S\$|US\$|A\$|HK\$|[\$€£¥]|"
    r"\b(?:SGD|USD|EUR|GBP|JPY|AUD|HKD|KRW|CNY|RMB|MYR|IDR|THB|PHP|VND)\b\s*(?:S\$|US\$|A\$|HK\$|[\$€£¥])?)"
    r"\s*\d(?:[\d,]*\d)?(?:\.\d+)?"
    r"(?:(?:\s*(?:thousand|million|billion|trillion)\b)|(?:\s*[KMBT]\b))?"
    r"(?=$|\s|[.,;:)])"
    r"|\b\d(?:[\d,]*\d)?(?:\.\d+)?"
    r"(?:(?:\s+(?:thousand|million|billion|trillion)\b)|(?:[KMBT]\b))",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*%")
LONG_NUMBER_RE = re.compile(r"\b\d[\d,]{5,}\b")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class PrivacyLedgerEntry:
    destination: str
    operation: str
    allowed: bool
    reason: str
    query: str = ""
    redactions: list[str] = field(default_factory=list)
    input_mode: str = ""
    content_sha256: str = ""
    content_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "destination": self.destination,
            "operation": self.operation,
            "allowed": self.allowed,
            "reason": self.reason,
            "query": self.query,
            "redactions": list(self.redactions),
            "input_mode": self.input_mode,
            "content_sha256": self.content_sha256,
            "content_type": self.content_type,
        }


class PrivacyGuard:
    def __init__(
        self,
        *,
        external_query_policy: str = "sanitized_only",
        max_query_chars: int = 180,
        redact_exact_numbers: bool = True,
    ):
        self.external_query_policy = external_query_policy
        self.max_query_chars = max(32, int(max_query_chars))
        self.redact_exact_numbers = bool(redact_exact_numbers)

    def sanitize_query(self, query: str) -> tuple[str, list[str]]:
        redactions: list[str] = []
        sanitized = query
        replacements = [
            (EMAIL_RE, "[email]", "email"),
            (PHONE_RE, "[phone]", "phone"),
            (MONEY_RE, "[amount]", "amount"),
            (PERCENT_RE, "[percent]", "percent"),
        ]
        if self.redact_exact_numbers:
            replacements.append((LONG_NUMBER_RE, "[number]", "long_number"))

        for pattern, replacement, label in replacements:
            sanitized, count = pattern.subn(replacement, sanitized)
            if count:
                redactions.append(label)

        sanitized = WHITESPACE_RE.sub(" ", sanitized).strip()
        if len(sanitized) > self.max_query_chars:
            sanitized = sanitized[: self.max_query_chars].rsplit(" ", 1)[0].strip()
            redactions.append("truncated")
        return sanitized, redactions

    def check_external_query(
        self,
        query: str,
        *,
        destination: str,
        banned_fragments: list[str] | None = None,
    ) -> PrivacyLedgerEntry:
        if self.external_query_policy == "disabled":
            return PrivacyLedgerEntry(
                destination=destination,
                operation="external_query",
                allowed=False,
                reason="external queries are disabled",
                query="",
            )
        if self.external_query_policy == "derived_hashes_only":
            return PrivacyLedgerEntry(
                destination=destination,
                operation="external_query",
                allowed=False,
                reason="sanitized natural-language queries are disallowed by policy",
                query="",
            )

        sanitized, redactions = self.sanitize_query(query)
        if not sanitized:
            return PrivacyLedgerEntry(
                destination=destination,
                operation="external_query",
                allowed=False,
                reason="query empty after sanitization",
                query="",
                redactions=redactions,
            )
        if EMAIL_RE.search(sanitized) or PHONE_RE.search(sanitized):
            return PrivacyLedgerEntry(
                destination=destination,
                operation="external_query",
                allowed=False,
                reason="query still contains direct personal data after sanitization",
                query=sanitized,
                redactions=redactions,
            )
        if MONEY_RE.search(sanitized) or PERCENT_RE.search(sanitized):
            return PrivacyLedgerEntry(
                destination=destination,
                operation="external_query",
                allowed=False,
                reason="query still contains exact financial values after sanitization",
                query=sanitized,
                redactions=redactions,
            )

        lowered = sanitized.lower()
        for fragment in banned_fragments or []:
            normalized = WHITESPACE_RE.sub(" ", str(fragment).strip()).lower()
            if len(normalized) >= 24 and normalized in lowered:
                return PrivacyLedgerEntry(
                    destination=destination,
                    operation="external_query",
                    allowed=False,
                    reason="query contains a long source-text fragment",
                    query=sanitized,
                    redactions=redactions,
                )

        return PrivacyLedgerEntry(
            destination=destination,
            operation="external_query",
            allowed=True,
            reason="sanitized query approved",
            query=sanitized,
            redactions=redactions,
        )

    def check_external_content(
        self,
        content: bytes,
        *,
        destination: str,
        content_type: str = "",
        tenant_opt_in: bool = False,
        operation: str = "external_content",
    ) -> PrivacyLedgerEntry:
        content_hash = hashlib.sha256(content).hexdigest()
        if self.external_query_policy == "disabled":
            return PrivacyLedgerEntry(
                destination=destination,
                operation=operation,
                allowed=False,
                reason="external content transfer is disabled",
                content_sha256=content_hash,
                content_type=content_type,
            )
        if self.external_query_policy == "derived_hashes_only":
            return PrivacyLedgerEntry(
                destination=destination,
                operation=operation,
                allowed=False,
                reason="raw content transfer is disallowed by policy",
                content_sha256=content_hash,
                content_type=content_type,
            )
        if not tenant_opt_in:
            return PrivacyLedgerEntry(
                destination=destination,
                operation=operation,
                allowed=False,
                reason="tenant has not opted in to this external image OCR provider",
                content_sha256=content_hash,
                content_type=content_type,
            )
        if not content:
            return PrivacyLedgerEntry(
                destination=destination,
                operation=operation,
                allowed=False,
                reason="content is empty",
                content_sha256=content_hash,
                content_type=content_type,
            )
        return PrivacyLedgerEntry(
            destination=destination,
            operation=operation,
            allowed=True,
            reason="external image OCR content transfer approved",
            content_sha256=content_hash,
            content_type=content_type,
        )

    @classmethod
    def load(cls) -> "PrivacyGuard":
        from kaypoh.configs.runtime import get_runtime_settings

        settings = get_runtime_settings().privacy
        return cls(
            external_query_policy=settings.external_query_policy,
            max_query_chars=settings.max_query_chars,
            redact_exact_numbers=settings.redact_exact_numbers,
        )
