from datetime import datetime
from enum import Enum
from typing import Optional

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
        description="Review profile. v1 supports strict behavior with strictest jurisdiction wins.",
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
    id: str = Field(description="Stable span identifier for frontend keying and reconciliation.")
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
        description="Privacy guard decisions for any outbound retrieval operations.",
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
