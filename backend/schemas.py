from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from datetime import datetime

class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"

class ClassifyRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=12000,
        description="text to classify for MNPI sensitivity",
    )
    entity_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional entity identifier for Mosaic tracking",
    )
    debug: bool = Field(False, description="Include heavy debug fields in response")

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        # Remove null bytes/control chars while preserving standard whitespace.
        cleaned = value.replace("\x00", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("text must contain non-whitespace printable content")
        if len(cleaned) > 12000:
            raise ValueError("text exceeds max sanitized length of 12000")
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
    items: list[ClassifyRequest] = Field(
        ...,
        min_length=1,
        max_length=32,
        description="List of classify requests processed sequentially in one HTTP call",
    )


class LexiconHitResponse(BaseModel):
    rule: str
    matched_text: str
    severity: str
    detail: str = ""
    score: float = 0.0

class LexiconResponse(BaseModel):
    flagged: bool
    high_risk_short_circuit: bool
    total_score: float = 0.0
    score_threshold: float = 0.0
    score_threshold_exceeded: bool = False
    hits: list[LexiconHitResponse] = Field(default_factory=list)
    restricted_entities: list[dict] = Field(default_factory=list)

class Model1Response(BaseModel):
    label: str
    confidence: float
    risk_score: float

class Model2Response(BaseModel):
    label: str
    confidence: float
    high_risk_score: float

class RegressionResponse(BaseModel):
    risk_score: float
    reasoning: str = ""

class MosaicResponse(BaseModel):
    escalated: bool
    count: int

class ClassifyResponse(BaseModel):
    request_id: Optional[str] = None
    classification: Classification
    lexicon: Optional[LexiconResponse] = None
    model1: Optional[Model1Response] = None # none if lexicon short-circuits
    model2: Optional[Model2Response] = None # none if model1 says safe
    embedding: Optional[list[float]] = None
    clustering: Optional[dict] = None
    mosaic: Optional[MosaicResponse] = None
    regression: Optional[RegressionResponse] = None
    timings_ms: dict[str, float] = Field(default_factory=dict)


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResponse] = Field(default_factory=list)


class TrainingSentence(BaseModel):
    text: str
    label: str

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
    document_creation: datetime
    document_name: str
    document_sentence_array: list[TrainingSentence] = Field(..., min_length=1)

class HealthResponse(BaseModel):
    status: str
    lexicon_loaded: bool
    model1_loaded: bool
    model2_loaded: bool
    embedding_loaded: bool = False
    clustering_loaded: bool = False
    mosaic_loaded: bool = False
    regression_loaded: bool = False


class ReadyResponse(BaseModel):
    status: str
    ready: bool
    pipeline: list[str] = Field(default_factory=list)
    missing_required_layers: list[str] = Field(default_factory=list)


class DiagnosticsResponse(BaseModel):
    status: str
    pipeline: list[str] = Field(default_factory=list)
    loaded_layers: list[str] = Field(default_factory=list)
    lazy_layers: list[str] = Field(default_factory=list)
    load_errors: list[dict] = Field(default_factory=list)
    startup_timings_ms: dict[str, float] = Field(default_factory=dict)
