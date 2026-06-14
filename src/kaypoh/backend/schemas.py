from enum import Enum
from typing import Any, Literal, Optional

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
        description="Optional issuer/entity context used by audit-grade public-source MNPI checks.",
    )
    debug: bool = Field(
        False,
        description="Include heavyweight debug payloads such as dense embedding vectors in the response.",
    )
    include_offending_spans: bool = Field(
        False,
        description=(
            "Deprecated compatibility flag. Current clients should read deterministic review `findings` "
            "for span evidence."
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
                "surface": "outlook",
                "workflow": "email_send",
                "actor_role": "end_user",
                "recipient_domains": ["example.com"],
                "recipient_count": 1,
                "attachment_count": 1,
                "sensitivity_label": "confidential",
                "external_destination": True,
                "requested_action": "send",
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
    degraded_policy: Literal["allow", "warn", "block_send"] = Field(
        "warn",
        description=(
            "Caller policy for degraded review coverage. `allow` accepts degraded best-effort responses, "
            "`warn` surfaces degraded_modes while allowing send, and `block_send` sets send_allowed=false "
            "when degraded_modes are present."
        ),
    )
    surface: Optional[
        Literal["api", "outlook", "browser_genai", "dms", "desktop", "word", "slack", "google_workspace", "other"]
    ] = Field(None, description="Surface where the review was triggered.")
    workflow: Optional[
        Literal[
            "api_review",
            "email_send",
            "prompt_submit",
            "document_upload",
            "document_review",
            "desktop_watch",
            "reviewer_override",
            "auditor_export",
            "collaboration_message",
            "other",
        ]
    ] = Field(None, description="Workflow being reviewed within the triggering surface.")
    actor_role: Optional[
        Literal[
            "end_user",
            "legal_reviewer",
            "compliance_admin",
            "security_engineer",
            "platform_integrator",
            "auditor",
            "service_account",
            "other",
        ]
    ] = Field(None, description="Role of the actor requesting review.")
    recipient_domains: Optional[list[str]] = Field(
        None,
        max_length=100,
        description="Destination domains known to the adapter or API caller. Empty lists are allowed.",
    )
    recipient_count: Optional[int] = Field(
        None,
        ge=0,
        le=10000,
        description="Number of intended recipients when known.",
    )
    attachment_count: Optional[int] = Field(
        None,
        ge=0,
        le=1000,
        description="Number of attachments or uploaded files associated with the workflow.",
    )
    sensitivity_label: Optional[str] = Field(
        None,
        max_length=128,
        description="Caller-supplied sensitivity label, such as confidential or restricted.",
    )
    external_destination: Optional[bool] = Field(
        None,
        description="Whether the destination leaves the caller's trusted internal boundary.",
    )
    requested_action: Optional[
        Literal[
            "review",
            "send",
            "submit",
            "upload",
            "safe_rewrite",
            "redact_pii",
            "pseudonymize",
            "anonymize",
            "request_approval",
            "hold_until_public",
            "cite_public_source",
            "proceed_with_warning",
            "other",
        ]
    ] = Field(None, description="Action the caller wants to complete after review.")
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
    matter_id: Optional[str] = Field(
        None,
        max_length=128,
        pattern=r"^[A-Za-z0-9_\-:]{1,128}$",
        description=(
            "Optional matter identifier (item 55). Sits above session_id: defined terms "
            "accumulate at matter level and inherit into every session within that matter. "
            "Closes the M&A real-world case of 30+ documents over weeks across multiple "
            "reviewers. Colon allowed for `{dms_vendor}:{matter_id}` composite keys aligned "
            "with iManage Work / NetDocuments matter IDs."
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

    @field_validator("recipient_domains")
    @classmethod
    def sanitize_recipient_domains(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        cleaned: list[str] = []
        for domain in value:
            normalized = domain.replace("\x00", "").strip().lower().rstrip(".")
            if not normalized:
                continue
            if len(normalized) > 253:
                raise ValueError("recipient domain exceeds maximum length 253")
            if any(ch.isspace() for ch in normalized):
                raise ValueError("recipient domain cannot contain whitespace")
            cleaned.append(normalized)
        return cleaned

    @field_validator("sensitivity_label")
    @classmethod
    def sanitize_sensitivity_label(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.replace("\x00", "").strip()
        cleaned = "".join(ch for ch in cleaned if ch.isprintable())
        return cleaned or None

    @model_validator(mode="after")
    def require_text_or_document(self):
        if not self.text and not self.document_base64:
            raise ValueError("either text or document_base64 is required")
        return self


class PlaceholderOperationRequest(ReviewRequest):
    include_mnpi_scalars: bool = Field(
        True,
        description=(
            "Also replace exact financial amounts, percentages, and large numbers. "
            "Broad MNPI material-event passages remain review findings rather than automatic replacements."
        ),
    )


class PseudonymizeRequest(PlaceholderOperationRequest):
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
                "persist_mapping": True,
            }
        }
    )

    persist_mapping: bool = Field(
        True,
        description=(
            "When KAYPOH_REVIEW_PERSIST=1, persist the local placeholder mapping so "
            "POST /reidentify can restore by document_hash. Ignored when persistence is disabled."
        ),
    )


class AnonymizeRequest(PlaceholderOperationRequest):
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


class RedactRequest(PlaceholderOperationRequest):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Send Dr Jane Tan S1234567D the confidential draft.",
                "source_jurisdiction": "SG",
                "destination_jurisdiction": "SG",
                "document_type": "email",
                "include_suggestions": True,
            }
        }
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
    content_sha256: str = Field(
        "",
        description="SHA-256 of raw content evaluated by the privacy guard, such as image OCR bytes.",
    )
    content_type: str = Field(
        "",
        description="MIME type for raw content evaluated by the privacy guard.",
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
    extraction_method: str = Field(
        description="Extraction path used for review, such as inline_text, docx_container_xml, or pypdf."
    )
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
    source: str = Field(
        "text",
        description="Finding source: text for extracted document text, image_ocr for OCR-derived image text.",
    )
    image_locator: Optional["ImageLocatorResponse"] = Field(
        None,
        description="Image locator for OCR-derived findings, including container_path and image_index.",
    )
    image_ocr_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="OCR provider confidence for the source image span when available.",
    )
    image_ocr_regions: list["ImageTextRegionResponse"] = Field(
        default_factory=list,
        description="OCR text regions and normalized bounding boxes overlapping this finding.",
    )
    source_verification: str = Field(
        "not_checked",
        description=(
            "Public-status proof state for MNPI findings: `not_checked` (strict profile or "
            "no retriever wired), `public_source_matched` (audit_grade retriever returned at "
            "least one source, or the document itself cites an http(s) URL beside the event), "
            "`no_public_source_found` (retriever queried but returned no sources), or "
            "`ambiguous` (retriever returned conflicting / unverified signals). PII findings "
            "always carry `not_checked` — public-status is not meaningful for personal data."
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Detector-specific structured metadata. Layer-2 conjunctive MNPI findings use this "
            "for materiality_state, entity/non-public element booleans, and element rules."
        ),
    )


class ReviewSuggestionResponse(BaseModel):
    id: str = Field(description="Stable suggestion identifier.")
    finding_id: str = Field(description="Finding this suggestion remediates.")
    action: str = Field(description="Suggested action, such as redact, remove_or_hold, or verify_or_rewrite.")
    replacement_text: str = Field(description="Suggested replacement placeholder or rewrite instruction.")
    rationale: str = Field(description="Reason this remediation is appropriate.")


class ImageBoundingBoxResponse(BaseModel):
    x: float = Field(ge=0.0, le=1.0, description="Normalized left coordinate.")
    y: float = Field(ge=0.0, le=1.0, description="Normalized top coordinate.")
    width: float = Field(ge=0.0, le=1.0, description="Normalized box width.")
    height: float = Field(ge=0.0, le=1.0, description="Normalized box height.")


class ImageLocatorResponse(BaseModel):
    container_path: str = Field(description="Path or synthetic name of the image inside the submitted document.")
    image_index: int = Field(description="Zero-based image index within the document.")
    page_number: Optional[int] = Field(None, description="One-based PDF page number when known.")
    source_type: str = Field(
        "embedded_image",
        description="Image source type, such as standalone_image or pdf_page_render.",
    )


class ImageTextRegionResponse(BaseModel):
    text: str = Field(description="OCR text in this region.")
    start_char: int = Field(description="Zero-based inclusive start offset in the reviewed text.")
    end_char: int = Field(description="Zero-based exclusive end offset in the reviewed text.")
    bounding_box: Optional[ImageBoundingBoxResponse] = Field(
        None,
        description="Normalized source-image bounding box for this OCR region.",
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Provider confidence when available.")


class DegradedModeResponse(BaseModel):
    mode: str = Field(description="Subsystem or coverage mode that degraded, such as image_ocr or image_redaction.")
    status: str = Field(description="Degradation status, such as skipped, failed_closed, or unavailable.")
    reason: str = Field(description="Human-readable reason for the degraded mode.")
    detail: Optional[dict[str, Any]] = Field(None, description="Optional structured detail for operators.")


class PolicyDecisionResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "decision": "block",
                "send_allowed": False,
                "required_actions": ["request_approval", "hold_until_public"],
                "recommended_actions": ["redact_pii"],
                "blocking_findings": ["mnpi:deal_codenames:42:55:0"],
                "policy_id": "default",
                "policy_version": "2026-06-14",
                "policy_reasons": [
                    "high-risk MNPI cannot be sent externally before public evidence or reviewer approval"
                ],
                "review_id": "b7f1faad-1d2b-4c35-9f60-6b7f08d6fbfb",
            }
        }
    )

    decision: Literal["allow", "warn", "block", "approval_required", "rewrite_required"] = Field(
        description="Policy outcome after evaluating findings, workflow context, and degradation state.",
    )
    send_allowed: bool = Field(description="Whether the caller may complete the send/share action immediately.")
    required_actions: list[str] = Field(
        default_factory=list,
        description="Actions the caller must complete before the workflow may proceed.",
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Non-blocking actions the caller should offer or display.",
    )
    blocking_findings: list[str] = Field(
        default_factory=list,
        description="Finding ids that contributed to a block, approval_required, or rewrite_required decision.",
    )
    policy_id: str = Field(description="Stable tenant policy profile identifier.")
    policy_version: str = Field(description="Version string for the policy rules used to produce this decision.")
    policy_reasons: list[str] = Field(
        default_factory=list,
        description="Deterministic policy reasons safe to journal and show to adapters.",
    )
    review_id: str = Field(description="Review session identifier associated with this policy decision.")


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
    degraded_policy: Literal["allow", "warn", "block_send"] = Field(
        "warn",
        description="Caller policy applied to degraded review coverage.",
    )
    send_allowed: bool = Field(
        True,
        description="False when degraded_policy=block_send and degraded coverage was observed.",
    )
    document: ReviewDocumentMetadataResponse = Field(description="Extracted document metadata.")
    findings: list[ReviewFindingResponse] = Field(default_factory=list, description="Localized PII and MNPI findings.")
    lane_suppressed_count: int = Field(
        0,
        description="Number of findings hidden from the default surfacing lane for this tenant.",
    )
    lane_suppressed_findings: list[ReviewFindingResponse] = Field(
        default_factory=list,
        description="Lane-suppressed findings. Populated only for audit-privileged callers.",
    )
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
            "Advisory output from deterministic audit-grade coverage checks and the "
            "audit_grade LLM inverse audit ('what did we miss?'). Each warning carries "
            "at least rule_guess and why fields. LLM warnings also produce capped "
            "origin=llm findings for reviewer adjudication. All warnings are journaled "
            "as coverage_warning events."
        ),
    )
    degraded_modes: list[DegradedModeResponse] = Field(
        default_factory=list,
        description="Explicit fail-open, fail-closed, or best-effort coverage limitations surfaced for this response.",
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
            "Mapping entries from a prior /pseudonymize call. Required unless document_hash is provided "
            "and KAYPOH_REVIEW_PERSIST is enabled with a persisted mapping for that hash."
        ),
    )
    document_hash: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description=(
            "Hex SHA-256 of the original document text (returned by /pseudonymize as `document_hash`). "
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
            "Deprecated compatibility field. Production reviewer identity is resolved from "
            "the authenticated JWT/API-key principal; local development may use X-Reviewer-ID "
            "when KAYPOH_DEV_AUTH=1."
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
    reviewer_identity_source: str = Field(
        "none",
        description="Source for reviewer_id: jwt, api_key, dev_header, none, or legacy.",
    )
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
    source: str = Field("text", description="Finding source: text or image_ocr.")
    image_locator: Optional[ImageLocatorResponse] = Field(None, description="Image locator for OCR-derived findings.")
    image_ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="OCR confidence when available.")
    image_ocr_regions: list[ImageTextRegionResponse] = Field(
        default_factory=list,
        description="OCR text regions overlapping this persisted finding.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Persisted detector metadata.")
    decision: Optional[str] = Field(
        None,
        description="Current decision: accept, reject, or rewrite. None when undecided.",
    )
    decision_seq: Optional[int] = Field(None, description="Journal seq for the most recent decision on this finding.")
    decision_ts: Optional[str] = Field(None, description="Timestamp of the most recent decision.")
    decision_reviewer_id: Optional[str] = Field(None, description="Reviewer identifier on the latest decision.")
    decision_reviewer_identity_source: Optional[str] = Field(
        None,
        description="Source for decision_reviewer_id on the latest decision.",
    )


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
    lane_suppressed_count: int = Field(
        0,
        description="Number of persisted findings hidden from the default surfacing lane.",
    )
    lane_suppressed_findings: list[ReviewSessionFindingState] = Field(
        default_factory=list,
        description="Lane-suppressed persisted findings. Populated only for audit-privileged callers.",
    )
    decisions_recorded: int = Field(description="Total number of decision events in this session.")
    audit_exports: list[dict] = Field(
        default_factory=list,
        description="Audit-pack exports recorded against this session.",
    )


class AnonymizationReplacementResponse(BaseModel):
    finding_id: str = Field(description="Review finding that drove this replacement.")
    placeholder: str = Field(description="Placeholder inserted into pseudonymized_text.")
    entity_type: str = Field(description="Normalized anonymization entity type.")
    original_text: str = Field(description="Exact original substring replaced.")
    start_char: int = Field(description="Zero-based inclusive starting character offset in the extracted text.")
    end_char: int = Field(description="Zero-based exclusive ending character offset in the extracted text.")


class PlaceholderReplacementResponse(BaseModel):
    finding_id: str = Field(description="Review finding that drove this replacement.")
    placeholder: str = Field(description="Placeholder inserted into the output text.")
    entity_type: str = Field(description="Normalized placeholder type; does not include original text.")
    start_char: int = Field(description="Zero-based inclusive starting character offset in the extracted text.")
    end_char: int = Field(description="Zero-based exclusive ending character offset in the extracted text.")


class OpaqueRedactionResponse(BaseModel):
    finding_id: str = Field(description="Review finding that drove this redaction.")
    marker: str = Field(description="Opaque marker inserted into redacted_text.")
    start_char: int = Field(description="Zero-based inclusive starting character offset in the extracted text.")
    end_char: int = Field(description="Zero-based exclusive ending character offset in the extracted text.")


class RedactedFindingResponse(BaseModel):
    id: str = Field(description="Stable finding identifier for client-side reconciliation.")
    category: str = Field(description="Finding category: PII or MNPI.")
    rule: str = Field(description="Rule or detector that produced the finding.")
    jurisdiction: str = Field(description="Jurisdiction rule pack responsible for the finding.")
    severity: str = Field(description="Finding severity: low, medium, or high.")
    score: float = Field(description="Numeric risk contribution for this finding.")
    start_char: int = Field(description="Zero-based inclusive starting character offset.")
    end_char: int = Field(description="Zero-based exclusive ending character offset.")
    reason: str = Field(description="Human-readable reason this finding is risky.")
    legal_basis: str = Field(description="Policy or legal rule family applied to this finding.")
    source: str = Field("text", description="Finding source: text or image_ocr.")
    source_verification: str = Field("not_checked", description="Public-status proof state for MNPI findings.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Detector-specific structured metadata.")


class RedactedImageResponse(BaseModel):
    container_path: str = Field(description="Path or synthetic name of the redacted image source.")
    image_index: int = Field(description="Zero-based image index within the submitted document.")
    page_number: Optional[int] = Field(None, description="One-based PDF page number when known.")
    source_type: str = Field("embedded_image", description="Image source type.")
    mime_type: str = Field(description="MIME type of the returned redacted artifact.")
    document_base64: str = Field(description="Base64-encoded redacted PNG artifact.")
    redaction_count: int = Field(description="Number of OCR bounding boxes redacted in this artifact.")


class RedactedDocumentResponse(BaseModel):
    filename: str = Field(description="Filename for the rewritten redacted document.")
    mime_type: str = Field(description="MIME type of the rewritten redacted document.")
    document_base64: str = Field(description="Base64-encoded rewritten redacted document.")
    method: str = Field(
        description="Container rewrite method, such as docx_media_rewrite or pdf_flattened_page_pixels."
    )
    redaction_count: int = Field(description="Number of OCR bounding boxes written back into the document.")
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about fidelity changes in the rewritten document, such as PDF flattening.",
    )


class PseudonymizeResponse(ReviewResponse):
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
                "privacy_operation": "pseudonymize",
                "pseudonymized_text": "Send [PERSON_1] [NRIC_FIN_1] the confidential draft.",
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

    privacy_operation: str = Field("pseudonymize", description="Privacy operation applied by this endpoint.")
    pseudonymized_text: str = Field(
        description="Extracted document text with accepted findings replaced by reversible placeholders."
    )
    anonymized_text: str = Field(
        description="Compatibility alias for pseudonymized_text; use pseudonymized_text for new integrations."
    )
    document_hash: str = Field(
        "",
        description=(
            "SHA-256 of the extracted document text. Use this as the `document_hash` field on "
            "POST /reidentify to recover the mapping without retaining it client-side. Persisted "
            "locally only when KAYPOH_REVIEW_PERSIST=1 and persist_mapping=true."
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
    redacted_images: list[RedactedImageResponse] = Field(
        default_factory=list,
        description=(
            "Best-effort redacted PNG artifacts for image-origin findings. Empty when no image findings "
            "were replaced or the OCR provider returned no bounding boxes."
        ),
    )
    redacted_document: Optional[RedactedDocumentResponse] = Field(
        None,
        description=(
            "Rewritten source container with OCR pixel redactions applied. DOCX rewrites embedded media; "
            "PDF output is a flattened pixel-safe PDF."
        ),
    )


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
                "findings": [],
                "suggestions": [],
                "privacy_operation": "anonymize",
                "anonymization_mode": "placeholder_only",
                "anonymized_text": "Send [PERSON_1] [NRIC_FIN_1] the confidential draft.",
                "document_hash": "4f" * 32,
                "mapping_persisted": False,
                "replacements": [
                    {
                        "finding_id": "pii:named_person:5:16:0",
                        "placeholder": "[PERSON_1]",
                        "entity_type": "PERSON",
                        "start_char": 5,
                        "end_char": 16,
                    }
                ],
                "timings_ms": {"extract": 0.1, "review": 0.4, "anonymize": 0.2, "total": 0.7},
            }
        }
    )

    privacy_operation: str = Field("anonymize", description="Privacy operation applied by this endpoint.")
    anonymization_mode: str = Field(
        "placeholder_only",
        description="Irreversible v2 mode: placeholders are emitted without mapping or original text.",
    )
    anonymized_text: str = Field(description="Extracted document text with accepted findings replaced by placeholders.")
    document_hash: str = Field("", description="SHA-256 of the extracted document text; no mapping is persisted.")
    mapping_persisted: bool = Field(False, description="Always false for irreversible /anonymize v2.")
    replacements: list[PlaceholderReplacementResponse] = Field(
        default_factory=list,
        description="Span-level replacements without original matched text.",
    )
    redacted_images: list[RedactedImageResponse] = Field(
        default_factory=list,
        description="Best-effort redacted PNG artifacts for image-origin findings.",
    )
    redacted_document: Optional[RedactedDocumentResponse] = Field(
        None,
        description="Rewritten source container with OCR pixel redactions applied.",
    )


class RedactResponse(ReviewResponse):
    findings: list[RedactedFindingResponse] = Field(
        default_factory=list,
        description="Findings without matched_text; /redact never returns original matched text.",
    )
    privacy_operation: str = Field("redact", description="Privacy operation applied by this endpoint.")
    redaction_style: str = Field(
        "opaque_text_marker",
        description="Opaque text marker style; markers do not expose entity type or original text.",
    )
    redacted_text: str = Field(description="Extracted document text with accepted findings replaced by opaque markers.")
    document_hash: str = Field("", description="SHA-256 of the extracted document text; no mapping is persisted.")
    mapping_persisted: bool = Field(False, description="Always false for /redact.")
    redactions: list[OpaqueRedactionResponse] = Field(
        default_factory=list,
        description="Span-level opaque marker insertions without original matched text.",
    )
    redacted_images: list[RedactedImageResponse] = Field(
        default_factory=list,
        description="Best-effort redacted PNG artifacts for image-origin findings.",
    )
    redacted_document: Optional[RedactedDocumentResponse] = Field(
        None,
        description="Rewritten source container with OCR pixel redactions applied.",
    )


class MosaicResponse(BaseModel):
    entity_id: str = Field(description="Deprecated compatibility field; Mosaic is archived.")
    escalated: bool = Field(description="Deprecated compatibility field; Mosaic is archived.")
    recent_event_count: int = Field(description="Deprecated compatibility field; Mosaic is archived.")
    unique_fragment_count: int = Field(
        description="Deprecated compatibility field; Mosaic is archived."
    )
    window_hours: float = Field(description="Deprecated compatibility field; Mosaic is archived.")
    threshold: int = Field(description="Deprecated compatibility field; Mosaic is archived.")
    escalation_reason: str = Field("", description="Deprecated compatibility field; Mosaic is archived.")
    matched_event_ids: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility field; Mosaic is archived.",
    )


class LayerErrorResponse(BaseModel):
    layer: str = Field(description="Layer name associated with the failure.")
    phase: str = Field(description="Failure phase: startup, lazy_load, or runtime.")
    message: str = Field(description="Error message captured for this layer failure.")


class OffendingSpanResponse(BaseModel):
    id: str = Field(description="Stable span identifier for client keying and reconciliation.")
    layer: str = Field(description="Origin layer for the span. Deprecated; use ReviewFindingResponse.")
    rule: str = Field(description="Rule name or span source label.")
    severity: str = Field(description="Severity associated with the span source.")
    matched_text: str = Field(description="Matched text for the span. Deprecated; use ReviewFindingResponse.")
    detail: str = Field("", description="Additional human-readable context for the span.")
    start_char: int = Field(description="Zero-based inclusive starting character offset.")
    end_char: int = Field(description="Zero-based exclusive ending character offset.")
    start_line: int = Field(description="One-based starting line number.")
    start_column: int = Field(description="One-based starting column number.")
    end_line: int = Field(description="One-based ending line number.")
    end_column: int = Field(description="One-based ending column number.")
    is_exact: bool = Field(description="Deprecated; use ReviewFindingResponse offsets.")
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
                "lexicon": None,
                "model1": None,
                "model2": None,
                "embedding": None,
                "clustering": None,
                "mosaic": None,
                "regression": None,
                "public_evidence": None,
                "llm_adjudication": None,
                "privacy_ledger": [],
                "observability": {
                    "degraded": False,
                    "cache_status": "disabled",
                    "active_pipeline": ["engine.review"],
                    "executed_layers": ["engine.review"],
                    "skipped_layers": [],
                    "layer_errors": [],
                },
                "offending_spans": None,
                "timings_ms": {"total": 4.2},
                "pii_score": 0.0,
                "mnpi_score": 91.0,
                "findings": [
                    {
                        "id": "mnpi:material_event:0:56:0",
                        "category": "MNPI",
                        "rule": "material_event",
                        "jurisdiction": "SG",
                        "severity": "high",
                        "score": 91.0,
                        "matched_text": "Acme Corp will acquire GlobalTech before announcement.",
                        "start_char": 0,
                        "end_char": 56,
                        "reason": "Material corporate event before public disclosure",
                        "legal_basis": "SG_SFA_MARKET_MISCONDUCT",
                        "source_verification": "not_checked",
                    }
                ],
                "coverage_warnings": [],
            }
        }
    )

    request_id: Optional[str] = Field(None, description="Per-request UUID also returned as the X-Request-ID header.")
    classification: Classification = Field(description="Final document-level classification from engine.review().")
    lexicon: Optional[LexiconResponse] = Field(None, description="Deprecated compatibility field; always null.")
    model1: Optional[Model1Response] = Field(
        None,
        description="Deprecated compatibility field; always null.",
    )
    model2: Optional[Model2Response] = Field(
        None,
        description="Deprecated compatibility field; always null.",
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="Deprecated compatibility field; always null.",
    )
    clustering: Optional[dict] = Field(None, description="Deprecated compatibility field; always null.")
    mosaic: Optional[MosaicResponse] = Field(None, description="Deprecated compatibility field; always null.")
    regression: Optional[RegressionResponse] = Field(
        None,
        description="Deprecated compatibility field; always null.",
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
        description="Deprecated compatibility field; use `findings` for current span evidence.",
    )
    timings_ms: dict[str, float] = Field(
        default_factory=dict,
        description="Review timing breakdown in milliseconds plus the total request time.",
    )
    pii_score: Optional[float] = Field(
        None,
        description="PII risk score from engine.review() (0-100). Populated under the item-63 thin-wrapper flow.",
    )
    mnpi_score: Optional[float] = Field(
        None,
        description="MNPI risk score from engine.review() (0-100). Populated under the item-63 thin-wrapper flow.",
    )
    findings: list[ReviewFindingResponse] = Field(
        default_factory=list,
        description="Deterministic review findings from engine.review().",
    )
    coverage_warnings: list[dict] = Field(
        default_factory=list,
        description=(
            "Coverage_warning events. LLM warnings also produce capped origin=llm findings "
            "under audit_grade."
        ),
    )
    degraded_modes: list[DegradedModeResponse] = Field(
        default_factory=list,
        description="Explicit fail-open, fail-closed, or best-effort coverage limitations surfaced for this response.",
    )


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResponse] = Field(
        default_factory=list,
        description="Ordered classify responses corresponding to the submitted batch items.",
    )


class LocalPairingStartRequest(BaseModel):
    client_name: str = Field(
        "kaypoh-local-client",
        max_length=120,
        description="Human-readable browser, Office, or desktop client name shown during local approval.",
    )


class LocalPairingCodeRequest(BaseModel):
    pairing_id: str = Field(..., min_length=1, max_length=128, description="Pairing request id from start.")
    pairing_code: str = Field(..., min_length=1, max_length=32, description="Short code shown to the user.")


class LocalPairingStartResponse(BaseModel):
    pairing_id: str
    pairing_code: str
    expires_at: int
    token_ttl_seconds: int


class LocalPairingApproveResponse(BaseModel):
    approved: bool
    pairing_id: str
    client_id: str
    expires_at: int


class LocalPairingClaimResponse(BaseModel):
    approved: bool
    client_id: str = ""
    client_token: str = ""
    expires_at: int
    token_type: str = ""


class HealthResponse(BaseModel):
    status: str = Field(description="Health endpoint status.")
    lexicon_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    model1_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    model2_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    embedding_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    clustering_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    mosaic_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    regression_loaded: bool = Field(False, description="Deprecated compatibility field; legacy layer archived.")
    public_evidence_loaded: bool = Field(False, description="Whether the public evidence retriever is loaded.")
    llm_adjudicator_loaded: bool = Field(False, description="Whether the LLM adjudicator is loaded.")
    llm_defined_term_extractor_loaded: bool = Field(
        False,
        description="Whether the audit-grade LLM defined-term extractor is loaded.",
    )
    llm_coverage_auditor_loaded: bool = Field(
        False,
        description="Whether the audit-grade LLM inverse coverage auditor is loaded.",
    )


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
        description="Dependency-level health information for optional retrieval and adjudication helpers.",
    )
    runtime_layer_errors: dict[str, RuntimeLayerErrorSummaryResponse] = Field(
        default_factory=dict,
        description="Accumulated runtime failures observed after startup.",
    )
