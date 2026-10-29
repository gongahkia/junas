"""Local extraction → OCR → detection, without workflow policy or persistence."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from junas.configs.runtime import RuntimeSettings, get_runtime_settings
from junas.external.privacy_guard import PrivacyGuard
from junas.models import DocumentInput
from junas.review.document import ExtractedDocument, extract_review_document
from junas.review.engine import PreSendReviewEngine, ReviewResult
from junas.review.image_scan import (
    ImageScanError,
    append_ocr_text_blocks,
    build_image_scanner,
    image_locator_for_span,
    image_ocr_metadata_for_span,
    scan_image_candidates,
)


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


@dataclass
class AnalysisResult:
    review: ReviewResult
    document: ExtractedDocument

    def to_dict(self) -> dict[str, Any]:
        """Offsets refer to the included extracted text, not to bytes in the source file."""
        result = asdict(self.review)
        result["overall_risk"] = self.review.overall_risk.value
        result["status"] = "degraded" if self.review.degraded_modes else "completed"
        result["document"] = {
            "text": self.document.text,
            "filename": self.document.filename,
            "mime_type": self.document.mime_type,
            "extraction_method": self.document.extraction_method,
            "extraction_quality": self.document.extraction_quality,
            "extraction_warnings": self.document.extraction_warnings or [],
            "metadata_findings": self.document.metadata_findings or [],
            "image_scan_provider": self.document.image_scan_provider,
        }
        return result


class ReviewPipeline:
    def __init__(self, settings: RuntimeSettings | None = None):
        self.settings = settings or get_runtime_settings()
        self._engines: dict[str, PreSendReviewEngine] = {}

    def review_text(self, text: str, **kwargs: Any) -> AnalysisResult:
        return self.review(DocumentInput(text=text), **kwargs)

    def review_file(self, path: str | Path, **kwargs: Any) -> AnalysisResult:
        path = Path(path)
        with path.open("rb") as stream:
            data = stream.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("document exceeds the 10 MiB input limit")
        return self.review(
            DocumentInput(document_base64=base64.b64encode(data).decode("ascii"), document_filename=path.name),
            **kwargs,
        )

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
        settings = self.settings
        document = extract_review_document(
            payload,
            settings.document_ingest,
            image_scan_enabled=settings.image_scan.provider != "none",
            image_scan_settings=settings.image_scan,
        )
        degraded: list[dict[str, Any]] = []
        for warning in document.extraction_warnings or []:
            if "fail-open:" in warning or "reviewed text layer only" in warning:
                degraded.append({"layer": "document_ingest", "mode": "incomplete", "reason": warning})
        privacy_ledger: list[dict[str, Any]] = []
        if settings.image_scan.provider != "none" and document.image_candidates:
            try:
                scanner = build_image_scanner(settings.image_scan, _privacy_guard(settings))
                if scanner is None:
                    raise ImageScanError("configured OCR provider is unavailable")
                results, privacy_ledger = scan_image_candidates(
                    document.image_candidates, scanner=scanner, settings=settings.image_scan
                )
                text, spans = append_ocr_text_blocks(document.text, results)
                if not text.strip():
                    raise ImageScanError("image OCR produced no reviewable text")
                if len(results) != len(document.image_candidates):
                    degraded.append(
                        {"layer": "image_ocr", "mode": "incomplete", "reason": "some images yielded no text"}
                    )
                document = replace(
                    document,
                    text=text,
                    image_text_spans=spans,
                    image_scan_provider=settings.image_scan.provider,
                    extraction_quality="accepted",
                    document_structure=None,
                )
            except ImageScanError as exc:
                if settings.document_ingest.fail_closed:
                    raise
                degraded.append({"layer": "image_ocr", "mode": "failed", "reason": str(exc)})
        engine = self._engines.get(review_profile)
        if engine is None:
            engine = build_review_engine(settings, review_profile=review_profile)
            self._engines[review_profile] = engine
        review = engine.review(
            text=document.text,
            source_jurisdiction=source_jurisdiction,
            destination_jurisdiction=destination_jurisdiction or source_jurisdiction,
            entity_id=entity_id,
            include_suggestions=include_suggestions,
            document_type=document_type,
            context_terms=context_terms,
            review_profile=review_profile,
            document_structure=document.document_structure,
        )
        for finding in review.findings:
            spans = document.image_text_spans or []
            locator = image_locator_for_span(spans, finding.start_char, finding.end_char)
            if locator is not None:
                metadata = image_ocr_metadata_for_span(spans, finding.start_char, finding.end_char) or {}
                finding.source = "image_ocr"
                finding.image_locator = locator
                finding.image_ocr_confidence = metadata.get("confidence")
                finding.image_ocr_regions = metadata.get("regions", [])
        review.privacy_ledger = privacy_ledger + review.privacy_ledger
        review.degraded_modes = degraded + review.degraded_modes
        return AnalysisResult(review=review, document=document)


def classify_text(text: str, **kwargs: Any) -> ReviewResult:
    """Convenience entrypoint returning findings and scores from the local pipeline."""
    return ReviewPipeline().review_text(text, **kwargs).review
