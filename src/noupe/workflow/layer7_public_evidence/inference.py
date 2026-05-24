from __future__ import annotations

import json
import re
from typing import Any

import httpx

from noupe.workflow.privacy_guard import PrivacyGuard


YEAR_RE = re.compile(r"\b20\d{2}\b")

EVENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "acquisition merger takeover": ("acquisition", "acquire", "merger", "takeover", "buyout"),
    "earnings guidance outlook": ("earnings", "guidance", "outlook", "forecast", "eps", "revenue"),
    "cybersecurity incident breach": ("cyber", "breach", "ransomware", "incident", "data leak"),
    "litigation investigation regulatory": ("lawsuit", "litigation", "investigation", "regulator", "subpoena"),
    "bankruptcy restructuring": ("bankruptcy", "insolvent", "chapter 11", "restructuring"),
    "dividend buyback capital return": ("dividend", "buyback", "repurchase", "capital return"),
    "management change resignation": ("resign", "resignation", "ceo", "cfo", "management"),
    "financing debt equity offering": ("financing", "debt", "equity offering", "convertible", "bond"),
}


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(str(item).strip().split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            out.append(cleaned)
            seen.add(key)
    return out


class PublicEvidenceRetriever:
    def __init__(self, settings: Any, guard: PrivacyGuard | None = None):
        self.enabled = bool(getattr(settings, "enabled", False))
        self.provider = str(getattr(settings, "provider", "exa") or "exa").lower()
        self.api_key = str(getattr(settings, "api_key", "") or "")
        self.endpoint = str(getattr(settings, "endpoint", "https://api.exa.ai/search") or "")
        self.max_results = max(1, int(getattr(settings, "max_results", 5) or 5))
        self.timeout_seconds = max(0.1, float(getattr(settings, "timeout_seconds", 8.0) or 8.0))
        self.guard = guard or PrivacyGuard.load()

    def _entity_candidates(self, *, text: str, entity_id: str | None, lexicon: Any) -> list[str]:
        candidates: list[str] = []
        if entity_id:
            candidates.append(entity_id)

        lex_payload = _as_dict(lexicon)
        for item in lex_payload.get("restricted_entities", []) or []:
            if isinstance(item, dict):
                candidates.extend([str(item.get("name", "") or ""), str(item.get("ticker", "") or "")])

        return _dedupe(candidates)[:3]

    def _event_terms(self, text: str) -> list[str]:
        lowered = text.lower()
        terms = [
            label
            for label, keywords in EVENT_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        ]
        return _dedupe(terms or ["company disclosure news"])[:3]

    def _years(self, text: str) -> list[str]:
        return _dedupe(YEAR_RE.findall(text))[:2]

    def build_queries(self, *, text: str, entity_id: str | None, lexicon: Any = None) -> list[str]:
        entities = self._entity_candidates(text=text, entity_id=entity_id, lexicon=lexicon)
        if not entities:
            return []

        years = self._years(text)
        suffix = " ".join(years + ["press release SEC filing news"])
        queries: list[str] = []
        for entity in entities:
            for terms in self._event_terms(text):
                queries.append(" ".join(part for part in [entity, terms, suffix] if part).strip())
        return _dedupe(queries)[: self.max_results]

    def _search_exa(self, query: str) -> list[dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {
            "query": query,
            "numResults": self.max_results,
            "useAutoprompt": True,
            "type": "neural",
            "contents": {"text": {"maxCharacters": 800}, "highlights": {"numSentences": 2}},
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results", []) if isinstance(payload, dict) else []
        sources: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            sources.append(
                {
                    "title": str(item.get("title", "") or ""),
                    "url": str(item.get("url", "") or ""),
                    "published_date": str(item.get("publishedDate", item.get("published_date", "")) or ""),
                    "author": str(item.get("author", "") or ""),
                    "highlights": [str(v) for v in item.get("highlights", []) or []],
                    "text": str(item.get("text", "") or "")[:800],
                    "score": item.get("score"),
                }
            )
        return sources

    def retrieve(self, *, text: str, entity_id: str | None = None, lexicon: Any = None) -> dict[str, Any]:
        queries = self.build_queries(text=text, entity_id=entity_id, lexicon=lexicon)
        query_records: list[dict[str, Any]] = []
        ledger: list[dict[str, Any]] = []
        approved_queries: list[str] = []

        for raw_query in queries:
            entry = self.guard.check_external_query(
                raw_query,
                destination=self.provider,
                banned_fragments=[text],
            )
            ledger.append(entry.to_dict())
            query_records.append(
                {
                    "query": entry.query,
                    "blocked": not entry.allowed,
                    "reason": entry.reason,
                }
            )
            if entry.allowed:
                approved_queries.append(entry.query)

        if not self.enabled or self.provider == "none":
            return {
                "status": "disabled",
                "provider": self.provider,
                "detail": "public evidence retrieval is disabled",
                "queries": query_records,
                "sources": [],
                "privacy_ledger": ledger,
            }
        if not approved_queries:
            return {
                "status": "skipped",
                "provider": self.provider,
                "detail": "no privacy-approved public evidence queries were available",
                "queries": query_records,
                "sources": [],
                "privacy_ledger": ledger,
            }
        if self.provider == "tinyfish":
            return {
                "status": "skipped",
                "provider": self.provider,
                "detail": "tinyfish retrieval adapter is configured but not implemented in this runtime",
                "queries": query_records,
                "sources": [],
                "privacy_ledger": ledger,
            }
        if self.provider != "exa":
            return {
                "status": "error",
                "provider": self.provider,
                "detail": f"unsupported public evidence provider: {self.provider}",
                "queries": query_records,
                "sources": [],
                "privacy_ledger": ledger,
            }
        if not self.api_key:
            return {
                "status": "skipped",
                "provider": self.provider,
                "detail": "EXA_API_KEY is not configured",
                "queries": query_records,
                "sources": [],
                "privacy_ledger": ledger,
            }

        sources: list[dict[str, Any]] = []
        try:
            for query in approved_queries:
                sources.extend(self._search_exa(query))
        except Exception as exc:
            return {
                "status": "error",
                "provider": self.provider,
                "detail": str(exc),
                "queries": query_records,
                "sources": sources,
                "privacy_ledger": ledger,
            }

        # Keep stable URL-level uniqueness across multi-query retrieval.
        deduped_sources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for source in sources:
            key = source.get("url") or json.dumps(source, sort_keys=True)
            if key in seen_urls:
                continue
            seen_urls.add(str(key))
            deduped_sources.append(source)

        return {
            "status": "queried",
            "provider": self.provider,
            "detail": f"retrieved {len(deduped_sources)} public sources",
            "queries": query_records,
            "sources": deduped_sources[: self.max_results],
            "privacy_ledger": ledger,
        }

    @classmethod
    def load(cls) -> "PublicEvidenceRetriever":
        from noupe.configs.runtime import get_runtime_settings

        settings = get_runtime_settings()
        return cls(settings.public_evidence, PrivacyGuard(
            external_query_policy=settings.privacy.external_query_policy,
            max_query_chars=settings.privacy.max_query_chars,
            redact_exact_numbers=settings.privacy.redact_exact_numbers,
        ))
