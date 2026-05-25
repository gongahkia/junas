from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_CLASSIFY_TEXT_LENGTH = 100000

class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"

class ClassifyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
                "entity_id": "Acme Corp",
                "debug": False,
                "include_offending_spans": True,
            }
        }
    )

    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CLASSIFY_TEXT_LENGTH,
        description="Document text to classify for MNPI sensitivity after control-character cleanup.",
    )
    entity_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional entity identifier used by the Mosaic layer to correlate repeated low-risk fragments.",
    )
    debug: bool = Field(
        False,
        description="Include heavyweight debug payloads such as dense embedding vectors in the response.",
    )
    include_offending_spans: bool = Field(
        False,
        description=(
            "Include exact lexicon-derived spans and approximate classifier-window spans when the final "
            "response is LOW_RISK or HIGH_RISK."
        ),
    )

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        # Remove null bytes/control chars while preserving standard whitespace.
        cleaned = value.replace("\x00", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("text must contain non-whitespace printable content")
        if len(cleaned) > MAX_CLASSIFY_TEXT_LENGTH:
            raise ValueError(f"text exceeds max sanitized length of {MAX_CLASSIFY_TEXT_LENGTH}")
        return cleaned

    @field_validator("entity_id")
    @classmethod
    def sanitize_entity_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.replace("\x00", "").strip()
        cleaned = "".join(ch for ch in cleaned if ch.isprintable())
        if not cleaned:
            return None
        if len(cleaned) > 128:
            raise ValueError("entity_id exceeds maximum length 128")
        return cleaned


class BatchClassifyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "text": "Acme Corp is acquiring GlobalTech for $2.5 billion next quarter.",
                        "include_offending_spans": True,
                    },
                    {
                        "text": "Public press release for next week's earnings call.",
                        "debug": False,
                    },
                ]
            }
        }
    )

    items: list[ClassifyRequest] = Field(
        ...,
        min_length=1,
        max_length=32,
        description="List of classify requests processed in one HTTP call with bounded in-process concurrency.",
    )


class ReviewRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Please send the draft deck to Tan S1234567D. Acme Corp has confidential Q1 guidance.",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SG",
                "document_type": "research_note",
                "entity_id": "Acme Corp",
                "include_suggestions": True,
            }
        }
    )

    text: Optional[str] = Field(
        None,
        max_length=MAX_CLASSIFY_TEXT_LENGTH,
        description="Inline document text. Provide either text or document_base64.",
    )
    document_base64: Optional[str] = Field(
        None,
        description="Base64-encoded text, DOCX, or PDF document payload.",
    )
    document_filename: Optional[str] = Field(
        None,
        max_length=256,
        description="Original filename used to infer document type when MIME type is omitted.",
    )
    document_mime_type: Optional[str] = Field(
        None,
        max_length=128,
        description="MIME type for document_base64, such as text/plain, application/pdf, or DOCX MIME.",
    )
    source_jurisdiction: str = Field(
        "SG",
        max_length=32,
        description="Jurisdiction where the document originates.",
    )
    destination_jurisdiction: str = Field(
        "SG",
        max_length=32,
        description="Jurisdiction where the document will be sent.",
    )
    document_type: str = Field(
        "generic",
        max_length=64,
        description="Customer-supplied document type, such as email, research_note, deck, or memo.",
    )
    review_profile: str = Field(
        "strict",
        max_length=64,
        pattern=r"^(?:strict|audit_grade)$",
        description=(
            "Review profile. `strict` (default) runs the deterministic engine only and never "
            "calls a remote LLM or public-evidence retriever. `audit_grade` engages the LLM "
            "tier (MNPI materiality adjudication, public-evidence retrieval, optional LLM-"
            "assisted defined-term extraction) when the deterministic score is in the "
            "ambiguous band — `kaypoh-server` SKU only."
        ),
    )
    entity_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional issuer/entity used for public-source MNPI checks.",
    )
    include_suggestions: bool = Field(
        True,
        description="Include redaction or rewrite suggestions for each finding.",
    )
    session_id: Optional[str] = Field(
        None,
        max_length=128,
        pattern=r"^[A-Za-z0-9_\-]{1,128}$",
        description=(
            "Optional review-session identifier. When provided, defined terms extracted from "
            "this document are merged into a session-scoped suppression set and inherited by "
            "subsequent /review or /anonymize calls with the same session_id. Useful for "
            "paired documents such as SPA + disclosure schedule that share definitions."
        ),
    )

    @field_validator("text")
    @classmethod
    def sanitize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.replace("\x00", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        if len(cleaned) > MAX_CLASSIFY_TEXT_LENGTH:
            raise ValueError(f"text exceeds max sanitized length of {MAX_CLASSIFY_TEXT_LENGTH}")
        return cleaned

    @field_validator("entity_id")
    @classmethod
    def sanitize_review_entity_id(cls, value: Optional[str]) -> Optional[str]:
        return ClassifyRequest.sanitize_entity_id(value)

    @model_validator(mode="after")
    def require_text_or_document(self):
        if not self.text and not self.document_base64:
            raise ValueError("either text or document_base64 is required")
        return self


class AnonymizeRequest(ReviewRequest):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": (
                    "Send Dr Jane Tan S1234567D the confidential draft. "
                    "Acme Corp expects a $2.5 billion acquisition before announcement."
                ),
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "document_type": "email",
                "include_suggestions": True,
                "include_mnpi_scalars": True,
            }
        }
    )

    include_mnpi_scalars: bool = Field(
        True,
        description=(
            "Also replace exact financial amounts, percentages, and large numbers. "
            "Broad MNPI material-event passages remain review findings rather than automatic replacements."
        ),
    )


class LexiconHitResponse(BaseModel):
    rule: str = Field(description="Lexicon rule name that produced the hit.")
    matched_text: str = Field(description="Matched surface text recorded by the lexicon layer.")
    severity: str = Field(description="Lexicon hit severity, typically 'high' or 'info'.")
    detail: str = Field("", description="Rule-specific explanation for the hit.")
    score: float = Field(0.0, description="Rule contribution to the cumulative lexicon score.")

class LexiconResponse(BaseModel):
    flagged: bool = Field(description="Whether the lexicon layer produced any notable hits.")
    high_risk_short_circuit: bool = Field(
        description="Whether the lexicon layer alone deterministically forced HIGH_RISK."
    )
    total_score: float = Field(0.0, description="Cumulative lexicon score across all hits.")
    score_threshold: float = Field(0.0, description="Configured lexicon threshold used for escalation.")
    score_threshold_exceeded: bool = Field(
        False,
        description="Whether the cumulative lexicon score crossed the configured threshold.",
    )
    hits: list[LexiconHitResponse] = Field(default_factory=list, description="Individual lexicon hits.")
    restricted_entities: list[dict] = Field(
        default_factory=list,
        description="Restricted-list entities inferred from the current request text.",
    )

class Model1Response(BaseModel):
    label: str = Field(description="Model-1 output label: 'safe' or 'risk'.")
    confidence: float = Field(description="Confidence of the predicted Model-1 label.")
    risk_score: float = Field(description="Probability assigned to the 'risk' class.")

class Model2Response(BaseModel):
    label: str = Field(description="Model-2 output label: 'low_risk' or 'high_risk'.")
    confidence: float = Field(description="Confidence of the predicted Model-2 label.")
    high_risk_score: float = Field(description="Probability assigned to the 'high_risk' class.")

class RegressionResponse(BaseModel):
    risk_score: float = Field(description="Aggregate regression risk probability.")
    reasoning: str = Field("", description="Human-readable summary of the regression feature inputs.")


class PublicEvidenceQueryResponse(BaseModel):
    query: str = Field("", description="Sanitized query approved for or blocked from external retrieval.")
    blocked: bool = Field(False, description="Whether the privacy guard blocked this query.")
    reason: str = Field("", description="Privacy guard decision reason.")


class PublicEvidenceSourceResponse(BaseModel):
    title: str = Field("", description="Public-source title returned by the retrieval provider.")
    url: str = Field("", description="Public-source URL returned by the retrieval provider.")
    published_date: str = Field("", description="Provider-supplied publication date when available.")
    author: str = Field("", description="Provider-supplied author when available.")
    highlights: list[str] = Field(default_factory=list, description="Provider-supplied source highlights.")
    text: str = Field("", description="Short public-source text excerpt returned by the provider.")
    score: Optional[float] = Field(None, description="Provider relevance score when available.")


class PrivacyLedgerEntryResponse(BaseModel):
    destination: str = Field(description="External destination name, such as exa or tinyfish.")
    operation: str = Field(description="Operation guarded by the privacy policy.")
    allowed: bool = Field(description="Whether the operation was allowed.")
    reason: str = Field(description="Guard decision reason.")
    query: str = Field("", description="Sanitized query if one was allowed or evaluated.")
    redactions: list[str] = Field(default_factory=list, description="Redaction classes applied to the query.")
    input_mode: str = Field(
        "",
        description=(
            "LLM input mode for llm_adjudication ledger events, such as raw_text or "
            "structured_tokens. Empty for non-LLM privacy decisions."
        ),
    )


class PublicEvidenceResponse(BaseModel):
    status: str = Field(description="Retrieval status: disabled, skipped, queried, or error.")
    provider: str = Field(description="Configured public evidence provider.")
    detail: str = Field("", description="Human-readable retrieval outcome.")
    queries: list[PublicEvidenceQueryResponse] = Field(
        default_factory=list,
        description="Sanitized public-source queries considered by the layer.",
    )
    sources: list[PublicEvidenceSourceResponse] = Field(
        default_factory=list,
        description="Public sources retrieved without sending private document text.",
    )
    privacy_ledger: list[PrivacyLedgerEntryResponse] = Field(
        default_factory=list,
        description="Per-query privacy decisions for outbound retrieval.",
    )


class LLMAdjudicationResponse(BaseModel):
    status: str = Field(description="Adjudication status: disabled, adjudicated, or error.")
    provider: str = Field(description="Local LLM provider, such as vllm or ollama.")
    model: str = Field(description="Configured local model name.")
    risk_label: Optional[Classification] = Field(None, description="LLM-adjudicated final risk label.")
    public_status: str = Field("not_checked", description="public, not_public, ambiguous, or not_checked.")
    confidence: float = Field(0.0, description="LLM confidence in the adjudicated label.")
    materiality_reason: str = Field("", description="Short local-only rationale for materiality.")
    matched_public_sources: list[str] = Field(
        default_factory=list,
        description="Public source URLs or identifiers the local LLM considered matching.",
    )
    unverified_claims: list[str] = Field(
        default_factory=list,
        description="Claims the local LLM could not match to public evidence.",
    )
    review_recommendation: str = Field("", description="Suggested reviewer action.")
    input_mode: str = Field(
        "raw_text",
        description=(
            "LLM input mode used for this adjudication. `raw_text` (default) sent the "
            "document text + sanitised context. `structured_tokens` sent only abstract "
            "tokens + SHA-256 hashes; the doc body never left the process boundary."
        ),
    )
    output_clamped: bool = Field(
        False,
        description=(
            "True when the LLM tried to emit a value outside the structured-mode closed "
            "vocabulary and the server clamped its response. Only meaningful in "
            "input_mode=structured_tokens."
        ),
    )


class ReviewDocumentMetadataResponse(BaseModel):
    filename: str = Field(description="Original or inferred document filename.")
    mime_type: str = Field(description="Document MIME type used for extraction.")
    extraction_method: str = Field(description="Extraction path used for review, such as inline_text or docx_xml.")
    page_count: Optional[int] = Field(None, description="Extracted page count when available, such as for PDFs.")
    char_count: int = Field(description="Character count of the normalized extracted text reviewed by the engine.")
    extraction_quality: str = Field("accepted", description="Extraction quality gate result for the reviewed text.")
    extraction_warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking extraction warnings, such as image-bearing PDFs with a valid text layer.",
    )
    metadata_findings: list["DocumentMetadataFindingResponse"] = Field(
        default_factory=list,
        description="Container metadata leakage findings separate from visible-text PII/MNPI findings.",
    )


class DocumentMetadataFindingResponse(BaseModel):
    id: str = Field(description="Stable metadata finding identifier.")
    source: str = Field(description="Metadata source, such as docx_core_properties, pdf_info, or image_exif.")
    field: str = Field(description="Metadata field name.")
    severity: str = Field(description="Metadata leakage severity: low, medium, or high.")
    detail: str = Field(description="Why this metadata can leak information.")
    value_preview: str = Field("", description="Short preview of the metadata value for reviewer inspection.")


class ReviewFindingResponse(BaseModel):
    id: str = Field(description="Stable finding identifier for client-side highlighting.")
    category: str = Field(description="Finding category: PII or MNPI.")
    rule: str = Field(description="Rule or detector that produced the finding.")
    jurisdiction: str = Field(description="Jurisdiction rule pack responsible for the finding.")
    severity: str = Field(description="Finding severity: low, medium, or high.")
    score: float = Field(description="Numeric risk contribution for this finding.")
    matched_text: str = Field(description="Exact reviewed text span or local context that triggered the finding.")
    start_char: int = Field(description="Zero-based inclusive starting character offset.")
    end_char: int = Field(description="Zero-based exclusive ending character offset.")
    reason: str = Field(description="Human-readable reason this finding is risky.")
    legal_basis: str = Field(description="Policy or legal rule family applied to this finding.")


class ReviewSuggestionResponse(BaseModel):
    id: str = Field(description="Stable suggestion identifier.")
    finding_id: str = Field(description="Finding this suggestion remediates.")
    action: str = Field(description="Suggested action, such as redact, remove_or_hold, or verify_or_rewrite.")
    replacement_text: str = Field(description="Suggested replacement placeholder or rewrite instruction.")
    rationale: str = Field(description="Reason this remediation is appropriate.")


class ReviewResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
                "overall_risk": "HIGH_RISK",
                "classification": "HIGH_RISK",
                "document_score": 91.0,
                "pii_score": 85.0,
                "mnpi_score": 91.0,
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "jurisdictions_applied": ["SG", "US"],
                "jurisdiction_policy": "strictest_wins",
                "document_type": "research_note",
                "review_profile": "strict",
                "document": {
                    "filename": "inline.txt",
                    "mime_type": "text/plain",
                    "extraction_method": "inline_text",
                    "page_count": None,
                    "char_count": 112,
                },
                "findings": [
                    {
                        "id": "pii:sg_nric_fin:25:34:0",
                        "category": "PII",
                        "rule": "sg_nric_fin",
                        "jurisdiction": "SG",
                        "severity": "high",
                        "score": 85.0,
                        "matched_text": "S1234567D",
                        "start_char": 25,
                        "end_char": 34,
                        "reason": "Singapore NRIC/FIN-like identifier",
                        "legal_basis": "SG_PDPA_PERSONAL_DATA, SG_PDPA_SENSITIVE_CONTEXT",
                    }
                ],
                "suggestions": [
                    {
                        "id": "suggestion:0",
                        "finding_id": "pii:sg_nric_fin:25:34:0",
                        "action": "redact",
                        "replacement_text": "[REDACTED PERSONAL DATA]",
                        "rationale": (
                            "Remove or mask personal data unless it is necessary for the recipient and purpose."
                        ),
                    }
                ],
                "public_evidence": None,
                "llm_adjudication": None,
                "privacy_ledger": [],
                "timings_ms": {"review": 3.2, "total": 3.2},
            }
        }
    )

    request_id: Optional[str] = Field(None, description="Per-request UUID also returned as the X-Request-ID header.")
    overall_risk: Classification = Field(description="Document-level pre-send risk rating.")
    classification: Classification = Field(description="Alias of overall_risk for existing classifier consumers.")
    document_score: float = Field(description="Overall numeric risk score after strictest-wins aggregation.")
    pii_score: float = Field(description="PII-specific numeric risk score.")
    mnpi_score: float = Field(description="MNPI-specific numeric risk score.")
    source_jurisdiction: str = Field(description="Jurisdiction where the document originates.")
    destination_jurisdiction: str = Field(description="Jurisdiction where the document will be sent.")
    jurisdictions_applied: list[str] = Field(description="Resolved jurisdiction rule packs applied to the review.")
    jurisdiction_policy: str = Field(description="Jurisdiction aggregation policy; v1 uses strictest_wins.")
    document_type: str = Field(description="Customer-supplied document type reviewed by the endpoint.")
    review_profile: str = Field(description="Review profile used by the endpoint.")
    document: ReviewDocumentMetadataResponse = Field(description="Extracted document metadata.")
    findings: list[ReviewFindingResponse] = Field(default_factory=list, description="Localized PII and MNPI findings.")
    suggestions: list[ReviewSuggestionResponse] = Field(
        default_factory=list,
        description="Suggested redactions or rewrite actions for findings.",
    )
    public_evidence: Optional[PublicEvidenceResponse] = Field(
        None,
        description="Sanitized public-source retrieval output when public evidence is enabled.",
    )
    llm_adjudication: Optional[LLMAdjudicationResponse] = Field(
        None,
        description="Local LLM adjudication output when the local adjudicator is enabled.",
    )
    privacy_ledger: list[PrivacyLedgerEntryResponse] = Field(
        default_factory=list,
        description="Privacy guard decisions for outbound retrieval and LLM adjudication operations.",
    )
    coverage_warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Advisory output from the audit_grade LLM inverse audit ('what did we miss?'). "
            "Each warning carries at least rule_guess and why fields. Engine never acts on "
            "these — reviewer attention only. Also journaled as coverage_warning events."
        ),
    )
    timings_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Review timing breakdown in milliseconds plus total request time.",
    )


class AnonymizationMappingEntryResponse(BaseModel):
    placeholder: str = Field(description="Deterministic replacement token assigned to the original text.")
    entity_type: str = Field(description="Normalized anonymization entity type, such as PERSON or NRIC_FIN.")
    original_text: str = Field(description="Original text replaced locally by this placeholder.")
    occurrence_count: int = Field(description="Number of accepted replacements using this mapping entry.")


class ReidentifyMappingEntry(BaseModel):
    placeholder: str = Field(..., min_length=1, max_length=128, description="Placeholder present in anonymized_text.")
    original_text: str = Field(..., max_length=4096, description="Original text to restore.")


class ReidentifyRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anonymized_text": "Send [PERSON_1] [NRIC_FIN_1] the draft.",
                "mapping": [
                    {"placeholder": "[PERSON_1]", "original_text": "Dr Jane Tan"},
                    {"placeholder": "[NRIC_FIN_1]", "original_text": "S1234567D"},
                ],
            }
        }
    )

    anonymized_text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CLASSIFY_TEXT_LENGTH,
        description="Text containing placeholders that should be restored.",
    )
    mapping: Optional[list[ReidentifyMappingEntry]] = Field(
        None,
        max_length=10000,
        description=(
            "Mapping entries from a prior /anonymize call. Required unless document_hash is provided "
            "and KAYPOH_REVIEW_PERSIST is enabled with a persisted mapping for that hash."
        ),
    )
    document_hash: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description=(
            "Hex SHA-256 of the original document text (returned by /anonymize as `document_hash`). "
            "If set and a persisted mapping exists locally, the runtime restores from that. "
            "Either `mapping` or `document_hash` is required."
        ),
    )

    @field_validator("anonymized_text")
    @classmethod
    def sanitize_anonymized_text(cls, value: str) -> str:
        cleaned = value.replace("\x00", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
        if not cleaned.strip():
            raise ValueError("anonymized_text must contain non-whitespace printable content")
        return cleaned

    @model_validator(mode="after")
    def require_mapping_or_hash(self):
        if not self.mapping and not self.document_hash:
            raise ValueError("either `mapping` or `document_hash` is required")
        return self


class ReidentifyResponse(BaseModel):
    request_id: Optional[str] = Field(None, description="Per-request UUID also returned as the X-Request-ID header.")
    text: str = Field(description="Reconstructed text with placeholders replaced by their originals.")
    replacement_count: int = Field(description="Number of placeholder occurrences replaced.")
    timings_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Reidentify timing breakdown in milliseconds.",
    )


class DocumentScrubRequest(BaseModel):
    document_base64: str = Field(..., description="Base64-encoded DOCX, PDF, JPEG, or PNG document payload.")
    document_filename: Optional[str] = Field(
        None,
        max_length=256,
        description="Original filename used to infer document type when MIME type is omitted.",
    )
    document_mime_type: Optional[str] = Field(
        None,
        max_length=128,
        description="MIME type for the scrub target.",
    )


class DocumentScrubActionResponse(BaseModel):
    source: str = Field(description="Metadata source that was scrubbed.")
    field: str = Field(description="Metadata field or container that was scrubbed.")
    action: str = Field(description="Scrub action, usually removed.")


class DocumentScrubResponse(BaseModel):
    request_id: Optional[str] = Field(None, description="Per-request UUID also returned as the X-Request-ID header.")
    document_base64: str = Field(description="Base64-encoded scrubbed document payload.")
    document_filename: str = Field(description="Filename associated with the scrubbed document.")
    document_mime_type: str = Field(description="MIME type of the scrubbed document.")
    scrubbed: bool = Field(description="Whether any metadata container or field was scrubbed.")
    actions: list[DocumentScrubActionResponse] = Field(
        default_factory=list,
        description="Metadata scrub actions applied to the payload.",
    )
    metadata_findings: list[DocumentMetadataFindingResponse] = Field(
        default_factory=list,
        description="Metadata findings detected before scrubbing.",
    )
    remaining_warnings: list[DocumentMetadataFindingResponse] = Field(
        default_factory=list,
        description="Metadata findings still present after best-effort scrubbing.",
    )


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "finding_id": "pii:named_person:5:16:0",
                "action": "reject",
                "replacement_text": "",
                "rationale": "Defined term in contract preamble, not a real party",
                "reviewer_id": "priya.raman@example.bank",
            }
        }
    )

    finding_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Finding identifier from a prior /review response.",
    )
    action: str = Field(..., description="One of: accept, reject, rewrite.")
    replacement_text: str = Field("", max_length=4096, description="Rewrite text when action=rewrite.")
    rationale: str = Field("", max_length=2048, description="Reviewer note recorded in the journal.")
    reviewer_id: str = Field(
        "",
        max_length=256,
        description=(
            "Optional reviewer identifier (email, employee number, SSO subject). "
            "If omitted and the X-Reviewer-ID header is present, the header value is used."
        ),
    )

    @field_validator("action")
    @classmethod
    def normalize_action(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"accept", "reject", "rewrite"}:
            raise ValueError("action must be one of: accept, reject, rewrite")
        return normalized


class ReviewDecisionResponse(BaseModel):
    review_id: str = Field(description="Review session identifier.")
    finding_id: str = Field(description="Finding identifier whose decision was recorded.")
    action: str = Field(description="Recorded action: accept, reject, or rewrite.")
    reviewer_id: str = Field("", description="Reviewer identifier persisted alongside the decision.")
    seq: int = Field(description="Journal sequence number for this decision event.")
    ts: str = Field(description="UTC timestamp of the journal entry.")
    hmac: str = Field(description="HMAC of the journal entry; reference for downstream audit verification.")


class ReviewSessionFindingState(BaseModel):
    id: str = Field(description="Finding identifier.")
    category: str = Field(description="PII or MNPI.")
    rule: str = Field(description="Rule that produced the finding.")
    severity: str = Field(description="low | medium | high.")
    matched_text: str = Field(description="Exact matched text from the original document.")
    start_char: int = Field(description="Zero-based inclusive start offset.")
    end_char: int = Field(description="Zero-based exclusive end offset.")
    decision: Optional[str] = Field(
        None,
        description="Current decision: accept, reject, or rewrite. None when undecided.",
    )
    decision_seq: Optional[int] = Field(None, description="Journal seq for the most recent decision on this finding.")
    decision_ts: Optional[str] = Field(None, description="Timestamp of the most recent decision.")
    decision_reviewer_id: Optional[str] = Field(None, description="Reviewer identifier on the latest decision.")


class ReviewSessionStateResponse(BaseModel):
    review_id: str = Field(description="Review session identifier.")
    text_hash: str = Field(description="SHA-256 of the reviewed document text.")
    document_type: str = Field(description="Document type recorded at session start.")
    source_jurisdiction: str = Field(description="Source jurisdiction recorded at session start.")
    destination_jurisdiction: str = Field(description="Destination jurisdiction recorded at session start.")
    findings: list[ReviewSessionFindingState] = Field(
        default_factory=list,
        description="Findings merged with their latest decision.",
    )
    decisions_recorded: int = Field(description="Total number of decision events in this session.")
    audit_exports: list[dict] = Field(
        default_factory=list,
        description="Audit-pack exports recorded against this session.",
    )


class AnonymizationReplacementResponse(BaseModel):
    finding_id: str = Field(description="Review finding that drove this replacement.")
    placeholder: str = Field(description="Placeholder inserted into anonymized_text.")
    entity_type: str = Field(description="Normalized anonymization entity type.")
    original_text: str = Field(description="Exact original substring replaced.")
    start_char: int = Field(description="Zero-based inclusive starting character offset in the extracted text.")
    end_char: int = Field(description="Zero-based exclusive ending character offset in the extracted text.")


class AnonymizeResponse(ReviewResponse):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
                "overall_risk": "HIGH_RISK",
                "classification": "HIGH_RISK",
                "document_score": 91.0,
                "pii_score": 88.0,
                "mnpi_score": 91.0,
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "US",
                "jurisdictions_applied": ["SG", "US"],
                "jurisdiction_policy": "strictest_wins",
                "document_type": "email",
                "review_profile": "strict",
                "document": {
                    "filename": "inline.txt",
                    "mime_type": "text/plain",
                    "extraction_method": "inline_text",
                    "page_count": None,
                    "char_count": 120,
                },
                "findings": [],
                "suggestions": [],
                "anonymized_text": "Send [PERSON_1] [NRIC_FIN_1] the confidential draft.",
                "mapping": [
                    {
                        "placeholder": "[PERSON_1]",
                        "entity_type": "PERSON",
                        "original_text": "Dr Jane Tan",
                        "occurrence_count": 1,
                    }
                ],
                "replacements": [
                    {
                        "finding_id": "pii:named_person:5:16:0",
                        "placeholder": "[PERSON_1]",
                        "entity_type": "PERSON",
                        "original_text": "Dr Jane Tan",
                        "start_char": 5,
                        "end_char": 16,
                    }
                ],
                "public_evidence": None,
                "llm_adjudication": None,
                "privacy_ledger": [],
                "timings_ms": {"extract": 0.1, "review": 0.4, "anonymize": 0.2, "total": 0.7},
            }
        }
    )

    anonymized_text: str = Field(description="Extracted document text with accepted findings replaced by placeholders.")
    document_hash: str = Field(
        "",
        description=(
            "SHA-256 of the extracted document text. Use this as the `document_hash` field on "
            "POST /reidentify to recover the mapping without retaining it client-side. Persisted "
            "locally only when KAYPOH_REVIEW_PERSIST=1."
        ),
    )
    mapping_persisted: bool = Field(
        False,
        description="True when the mapping was written to the local mapping store for later reidentify.",
    )
    mapping: list[AnonymizationMappingEntryResponse] = Field(
        default_factory=list,
        description="Local mapping from placeholders back to original text.",
    )
    replacements: list[AnonymizationReplacementResponse] = Field(
        default_factory=list,
        description="Accepted span-level replacements applied to build anonymized_text.",
    )


class MosaicResponse(BaseModel):
    entity_id: str = Field(description="Normalized entity key used for rolling-window aggregation.")
    escalated: bool = Field(description="Whether Mosaic escalated a low-risk result to high risk.")
    recent_event_count: int = Field(description="Number of recent low-risk events observed inside the active window.")
    unique_fragment_count: int = Field(
        description="Number of unique fragment hashes observed inside the active window."
    )
    window_hours: float = Field(description="Active rolling aggregation window in hours.")
    threshold: int = Field(description="Unique-fragment threshold required for escalation.")
    escalation_reason: str = Field("", description="Human-readable reason for the current escalation outcome.")
    matched_event_ids: list[str] = Field(
        default_factory=list,
        description="Recent mosaic event identifiers contributing to the current aggregate.",
    )


class LayerErrorResponse(BaseModel):
    layer: str = Field(description="Layer name associated with the failure.")
    phase: str = Field(description="Failure phase: startup, lazy_load, or runtime.")
    message: str = Field(description="Error message captured for this layer failure.")


class OffendingSpanResponse(BaseModel):
    id: str = Field(description="Stable span identifier for client keying and reconciliation.")
    layer: str = Field(description="Origin layer for the span: lexicon, model1, or model2.")
    rule: str = Field(description="Rule name or span source label.")
    severity: str = Field(description="Severity associated with the span source.")
    matched_text: str = Field(description="Matched text or approximate classifier window text.")
    detail: str = Field("", description="Additional human-readable context for the span.")
    start_char: int = Field(description="Zero-based inclusive starting character offset.")
    end_char: int = Field(description="Zero-based exclusive ending character offset.")
    start_line: int = Field(description="One-based starting line number.")
    start_column: int = Field(description="One-based starting column number.")
    end_line: int = Field(description="One-based ending line number.")
    end_column: int = Field(description="One-based ending column number.")
    is_exact: bool = Field(description="True for exact lexicon hits, false for approximate classifier windows.")
    char_length: int = Field(description="Span length in characters.")
    line_span: int = Field(description="Number of lines covered by the span.")
    context_before: str = Field("", description="Up to 48 characters of leading local context.")
    context_after: str = Field("", description="Up to 48 characters of trailing local context.")
    score: Optional[float] = Field(None, description="Associated rule score or classifier score, if available.")
    score_type: Optional[str] = Field(
        None,
        description="Metric represented by score, such as rule_score, risk_score, or high_risk_score.",
    )
    window_index: Optional[int] = Field(
        None,
        description="Zero-based classifier window index for approximate model spans.",
    )
    window_count: Optional[int] = Field(
        None,
        description="Total number of classifier windows evaluated for the request.",
    )
    window_token_count: Optional[int] = Field(
        None,
        description="Number of non-padding tokens in the selected classifier window.",
    )
    window_stride: Optional[int] = Field(
        None,
        description="Tokenizer stride used while constructing overlapping classifier windows.",
    )
    window_max_seq_len: Optional[int] = Field(
        None,
        description="Maximum token length used for classifier windows.",
    )


class ObservabilityResponse(BaseModel):
    degraded: bool = Field(False, description="Whether the response was produced in best-effort degraded mode.")
    cache_status: str = Field("disabled", description="Response cache outcome: hit, miss, or disabled.")
    active_pipeline: list[str] = Field(
        default_factory=list,
        description="Configured pipeline order active for this request.",
    )
    executed_layers: list[str] = Field(
        default_factory=list,
        description="Layers that executed for this specific request.",
    )
    skipped_layers: list[str] = Field(
        default_factory=list,
        description="Configured layers skipped for this specific request path.",
    )
    layer_errors: list[LayerErrorResponse] = Field(
        default_factory=list,
        description="Layer failures associated with this response.",
    )

class ClassifyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
                "classification": "HIGH_RISK",
                "lexicon": {
                    "flagged": True,
                    "high_risk_short_circuit": False,
                    "total_score": 12.5,
                    "score_threshold": 10.0,
                    "score_threshold_exceeded": True,
                    "hits": [
                        {
                            "rule": "money_threshold",
                            "matched_text": "$2.5 billion",
                            "severity": "high",
                            "detail": "parsed=2500000000 >= threshold=1000000",
                            "score": 2.0,
                        }
                    ],
                    "restricted_entities": [{"name": "Acme Corp", "ticker": "ACME", "isin": "US0000000001"}],
                },
                "model1": {"label": "risk", "confidence": 0.82, "risk_score": 0.82},
                "model2": {"label": "high_risk", "confidence": 0.99, "high_risk_score": 0.99},
                "clustering": {"anomaly_score": 0.61, "is_anomaly": False, "raw_score": -0.44},
                "mosaic": {
                    "entity_id": "acme corp",
                    "escalated": True,
                    "recent_event_count": 12,
                    "unique_fragment_count": 10,
                    "window_hours": 24.0,
                    "threshold": 10,
                    "escalation_reason": "10 unique low-risk fragments observed within 24.0 hours",
                    "matched_event_ids": ["req-9", "req-8", "req-7"],
                },
                "regression": {"risk_score": 0.86, "reasoning": "XGBoost checkpoint produced probability 0.856"},
                "observability": {
                    "degraded": False,
                    "cache_status": "disabled",
                    "active_pipeline": [
                        "lexicon",
                        "embedding",
                        "clustering",
                        "model1",
                        "model2",
                        "mosaic",
                        "regression",
                    ],
                    "executed_layers": [
                        "lexicon",
                        "embedding",
                        "clustering",
                        "model1",
                        "model2",
                        "regression",
                    ],
                    "skipped_layers": ["mosaic"],
                    "layer_errors": [],
                },
                "offending_spans": [
                    {
                        "id": "lexicon:money_threshold:38:50:0",
                        "layer": "lexicon",
                        "rule": "money_threshold",
                        "severity": "high",
                        "matched_text": "$2.5 billion",
                        "detail": "parsed=2500000000 >= threshold=1000000",
                        "start_char": 38,
                        "end_char": 50,
                        "start_line": 1,
                        "start_column": 39,
                        "end_line": 1,
                        "end_column": 51,
                        "is_exact": True,
                        "char_length": 12,
                        "line_span": 1,
                        "context_before": "Acme Corp is acquiring GlobalTech for ",
                        "context_after": " next quarter.",
                        "score": 2.0,
                        "score_type": "rule_score",
                        "window_index": None,
                        "window_count": None,
                        "window_token_count": None,
                        "window_stride": None,
                        "window_max_seq_len": None,
                    }
                ],
                "embedding": None,
                "timings_ms": {
                    "lexicon": 11.467,
                    "embedding": 200.766,
                    "clustering": 4.989,
                    "model1": 669.045,
                    "model2": 592.709,
                    "regression": 2.053,
                    "total": 1491.608,
                },
            }
        }
    )

    request_id: Optional[str] = Field(None, description="Per-request UUID also returned as the X-Request-ID header.")
    classification: Classification = Field(description="Final document-level classification.")
    lexicon: Optional[LexiconResponse] = Field(None, description="Lexicon-layer output for this request.")
    model1: Optional[Model1Response] = Field(
        None,
        description=(
            "Model-1 output. Null when the layer is disabled, unavailable, "
            "or skipped after lexicon short-circuit."
        ),
    )
    model2: Optional[Model2Response] = Field(
        None,
        description=(
            "Model-2 output. Null when the layer is disabled, unavailable, "
            "or skipped after a safe Model-1 result."
        ),
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="Dense embedding vector. Included only when debug=true.",
    )
    clustering: Optional[dict] = Field(None, description="Clustering-layer output for this request.")
    mosaic: Optional[MosaicResponse] = Field(None, description="Mosaic aggregation output for this request.")
    regression: Optional[RegressionResponse] = Field(
        None,
        description="Regression-layer output when a trained checkpoint is available and loaded.",
    )
    public_evidence: Optional[PublicEvidenceResponse] = Field(
        None,
        description="Sanitized public-source retrieval output when the public evidence layer is enabled.",
    )
    llm_adjudication: Optional[LLMAdjudicationResponse] = Field(
        None,
        description="Local LLM adjudication output when the local adjudicator layer is enabled.",
    )
    privacy_ledger: list[PrivacyLedgerEntryResponse] = Field(
        default_factory=list,
        description="Privacy guard decisions for outbound retrieval and LLM adjudication operations.",
    )
    observability: ObservabilityResponse = Field(description="Per-request runtime observability metadata.")
    offending_spans: Optional[list[OffendingSpanResponse]] = Field(
        None,
        description="Exact lexicon spans and approximate classifier-window spans when explicitly requested.",
    )
    timings_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Per-layer timing breakdown in milliseconds plus the total request time.",
    )


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResponse] = Field(
        default_factory=list,
        description="Ordered classify responses corresponding to the submitted batch items.",
    )


class TrainingSentence(BaseModel):
    text: str = Field(description="Sentence text used for training.")
    label: str = Field(description="Canonical or legacy label for the sentence.")

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        raw = value.strip().lower().replace("_", " ").replace("-", " ")
        mapping = {
            "non": "non",
            "non sensitive": "non",
            "nonsensitive": "non",
            "low": "low",
            "low risk": "low",
            "low sensitivity": "low",
            "high": "high",
            "high risk": "high",
            "high sensitivity": "high",
        }
        if raw not in mapping:
            raise ValueError("label must be one of: non, low, high (or supported aliases)")
        return mapping[raw]

class TrainingDocument(BaseModel):
    document_creation: datetime = Field(description="Document creation timestamp.")
    document_name: str = Field(description="Document name or identifier.")
    document_sentence_array: list[TrainingSentence] = Field(
        ...,
        min_length=1,
        description="Ordered sentence payloads for the document.",
    )


class TrainingBatch(BaseModel):
    batch_name: str = Field(description="Batch identifier.")
    batch_creation: datetime = Field(description="Batch creation timestamp.")
    documents: list[TrainingDocument] = Field(
        ...,
        min_length=1,
        description="Training documents included in the batch.",
    )

class HealthResponse(BaseModel):
    status: str = Field(description="Health endpoint status.")
    lexicon_loaded: bool = Field(description="Whether the lexicon layer is currently loaded.")
    model1_loaded: bool = Field(description="Whether Model-1 is currently loaded.")
    model2_loaded: bool = Field(description="Whether Model-2 is currently loaded.")
    embedding_loaded: bool = Field(False, description="Whether the embedding layer is currently loaded.")
    clustering_loaded: bool = Field(False, description="Whether the clustering layer is currently loaded.")
    mosaic_loaded: bool = Field(False, description="Whether the Mosaic layer is currently loaded.")
    regression_loaded: bool = Field(False, description="Whether the regression layer is currently loaded.")


class ReadyResponse(BaseModel):
    status: str = Field(description="Readiness status: ok or degraded.")
    ready: bool = Field(description="True when all required layers are available and warmed.")
    pipeline: list[str] = Field(default_factory=list, description="Configured active pipeline order.")
    missing_required_layers: list[str] = Field(
        default_factory=list,
        description="Required layers missing from the current runtime.",
    )
    warming_required_layers: list[str] = Field(
        default_factory=list,
        description="Required lazy layers still warming in the background.",
    )
    reasons: list[str] = Field(default_factory=list, description="Human-readable readiness blockers.")


class DependencyStatusResponse(BaseModel):
    status: str = Field(description="Dependency health label, such as up, down, disabled, or unknown.")
    configured: bool = Field(description="Whether the dependency is configured for this runtime.")
    healthy: Optional[bool] = Field(None, description="Boolean health signal when available.")
    detail: str = Field("", description="Additional dependency detail text.")


class RuntimeLayerErrorSummaryResponse(BaseModel):
    count: int = Field(0, description="Number of runtime failures observed for the layer.")
    last_seen: Optional[str] = Field(None, description="UTC timestamp of the most recent runtime failure.")
    last_message: str = Field("", description="Message from the most recent runtime failure.")


class DiagnosticsResponse(BaseModel):
    status: str = Field(description="Diagnostics endpoint status.")
    pipeline: list[str] = Field(default_factory=list, description="Configured active pipeline order.")
    loaded_layers: list[str] = Field(default_factory=list, description="Layers currently loaded in memory.")
    lazy_layers: list[str] = Field(default_factory=list, description="Layers configured for lazy loading.")
    warming_required_layers: list[str] = Field(
        default_factory=list,
        description="Required lazy layers still warming in the background.",
    )
    load_errors: list[dict] = Field(default_factory=list, description="Layer startup and lazy-load failures.")
    startup_timings_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Startup timing breakdown in milliseconds.",
    )
    metrics_mode: str = Field("singleprocess", description="Prometheus export mode: singleprocess or multiprocess.")
    dependency_status: dict[str, DependencyStatusResponse] = Field(
        default_factory=dict,
        description="Dependency-level health information such as Redis connectivity.",
    )
    runtime_layer_errors: dict[str, RuntimeLayerErrorSummaryResponse] = Field(
        default_factory=dict,
        description="Accumulated runtime failures observed after startup.",
    )
