from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from datetime import datetime

class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000, description="text to classify for MNPI sensitivity")

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, value: str) -> str:
        cleaned = value.replace("\x00", "")
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in ("\n", "\r", "\t"))
        cleaned = cleaned.strip()
        if not cleaned:
            raise ValueError("text must contain non-whitespace printable content")
        if len(cleaned) > 12000:
            raise ValueError("text exceeds max sanitized length of 12000")
        return cleaned

class LexiconHitResponse(BaseModel):
    rule: str
    matched_text: str
    severity: str
    detail: str = ""

class LexiconResponse(BaseModel):
    flagged: bool
    high_risk_short_circuit: bool
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

class ClassifyResponse(BaseModel):
    classification: Classification
    lexicon: LexiconResponse
    model1: Optional[Model1Response] = None # none if lexicon short-circuits
    model2: Optional[Model2Response] = None # none if model1 says safe

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
