from pydantic import BaseModel, Field
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
    hits: list[LexiconHitResponse] = []
    restricted_entities: list[dict] = []

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
