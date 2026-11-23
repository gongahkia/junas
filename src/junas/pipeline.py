"""Text-only classification; optional text advice requires an explicit audit profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from junas.configs.runtime import RuntimeSettings, get_runtime_settings
from junas.external.privacy_guard import PrivacyGuard
from junas.input_limits import read_source
from junas.models import DocumentInput
from junas.review.engine import PreSendReviewEngine, ReviewResult
from junas.review.jurisdictions import normalize_jurisdiction, resolve_rule_packs


def build_review_engine(settings: RuntimeSettings, *, review_profile: str = "strict") -> PreSendReviewEngine:
    """Construct optional providers only for an explicitly selected audit-grade experiment."""
    if review_profile not in {"strict", "audit_grade"}:
        raise ValueError("review_profile must be strict or audit_grade")
    if review_profile == "strict":
        return PreSendReviewEngine()
    public_evidence = llm = defined_terms = coverage_audit = None
    if settings.public_evidence.enabled:
        from junas.external.public_evidence.inference import PublicEvidenceRetriever

        public_evidence = PublicEvidenceRetriever(settings.public_evidence, _privacy_guard(settings))
    if settings.llm.enabled:
        from junas.advisory.llm_adjudicator.helpers import build_llm_coverage_auditor, build_llm_defined_term_extractor
        from junas.advisory.llm_adjudicator.inference import LocalLLMAdjudicator

        llm = LocalLLMAdjudicator(settings.llm)
        if settings.llm_helpers.defined_terms_enabled:
            defined_terms = build_llm_defined_term_extractor(settings.llm)
        if settings.llm_helpers.coverage_audit_enabled:
            coverage_audit = build_llm_coverage_auditor(settings.llm)
    return PreSendReviewEngine(
        public_evidence_retriever=public_evidence,
        llm_adjudicator=llm,
        llm_defined_term_extractor=defined_terms,
        llm_coverage_auditor=coverage_audit,
    )


def _privacy_guard(settings: RuntimeSettings) -> PrivacyGuard:
    return PrivacyGuard(
        external_query_policy=settings.privacy.external_query_policy,
        max_query_chars=settings.privacy.max_query_chars,
        redact_exact_numbers=settings.privacy.redact_exact_numbers,
    )


@dataclass(frozen=True)
class TextDocument:
    text: str
    filename: str = ""
    mime_type: str = "text/plain"
    extraction_method: str = "inline_text"


@dataclass
class AnalysisResult:
    review: ReviewResult
    document: TextDocument

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self.review)
        result["overall_risk"] = self.review.overall_risk.value
        result["status"] = "degraded" if self.review.degraded_modes else "completed"
        result["document"] = asdict(self.document)
        return result


class ReviewPipeline:
    def __init__(self, settings: RuntimeSettings | None = None):
        self.settings = settings or get_runtime_settings()
        self._engines: dict[str, PreSendReviewEngine] = {}

    def review_text(self, text: str, **kwargs: Any) -> AnalysisResult:
        return self.review(DocumentInput(text=text), **kwargs)

    def review_file(self, path: str | Path, **kwargs: Any) -> AnalysisResult:
        path = Path(path)
        if path.suffix.lower() not in {"", ".txt", ".text", ".md", ".csv", ".json", ".log"}:
            raise ValueError("Junas accepts UTF-8 text files only; document/email/archive/OCR input was removed")
        with path.open("rb") as stream:
            data = read_source(stream)
        if data.lstrip().startswith((b"%PDF-", b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"\x89PNG", b"\xff\xd8\xff")):
            raise ValueError("binary document content is not supported; supply canonical UTF-8 text")
        analysis = self.review_text(data.decode("utf-8"), **kwargs)
        analysis.document = replace(analysis.document, filename=path.name, extraction_method="utf8_file")
        return analysis

    def review(
        self,
        payload: DocumentInput,
        *,
        source_jurisdiction: str = "SG",
        destination_jurisdiction: str | None = None,
        document_type: str = "generic",
        entity_id: str | None = None,
        review_profile: str = "strict",
        context_terms: set[str] | None = None,
        include_suggestions: bool = False,
    ) -> AnalysisResult:
        if review_profile not in {"strict", "audit_grade"}:
            raise ValueError("review_profile must be strict or audit_grade")
        if not isinstance(payload, DocumentInput):
            raise ValueError("review requires DocumentInput(text=...)")
        destination_jurisdiction = source_jurisdiction if destination_jurisdiction is None else destination_jurisdiction
        resolve_rule_packs(source_jurisdiction, destination_jurisdiction)
        source_jurisdiction = normalize_jurisdiction(source_jurisdiction)
        destination_jurisdiction = normalize_jurisdiction(destination_jurisdiction)
        if review_profile not in self._engines:
            self._engines[review_profile] = build_review_engine(self.settings, review_profile=review_profile)
        review = self._engines[review_profile].review(
            text=payload.text,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
            document_type=document_type,
            context_terms=context_terms,
            review_profile=review_profile,
        )
        return AnalysisResult(review=review, document=TextDocument(payload.text))


def classify_text(text: str, **kwargs: Any) -> ReviewResult:
    return ReviewPipeline().review_text(text, **kwargs).review
