from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from datetime import datetime

class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="text to classify for MNPI sensitivity")
    entity_id: Optional[str] = Field(None, description="Optional entity identifier for Mosaic tracking")
    debug: bool = Field(False, description="Include heavy debug fields in response")

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
    classification: Classification
    lexicon: Optional[LexiconResponse] = None
    model1: Optional[Model1Response] = None # none if lexicon short-circuits
    model2: Optional[Model2Response] = None # none if model1 says safe
    embedding: Optional[list[float]] = None
    clustering: Optional[dict] = None
    mosaic: Optional[MosaicResponse] = None
    regression: Optional[RegressionResponse] = None

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
    load_errors: list[dict] = Field(default_factory=list)
