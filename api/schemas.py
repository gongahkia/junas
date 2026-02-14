from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

class Classification(str, Enum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    HIGH_RISK = "HIGH_RISK"

class ClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1, description="text to classify for MNPI sensitivity")

class LexiconHitResponse(BaseModel):
    rule: str
    matched_text: str
    severity: str
    detail: str = ""

class LexiconResponse(BaseModel):
    flagged: bool
    high_risk_short_circuit: bool
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

class ClassifyResponse(BaseModel):
    classification: Classification
    lexicon: LexiconResponse
    model1: Optional[Model1Response] = None # none if lexicon short-circuits
    model2: Optional[Model2Response] = None # none if model1 says safe

class HealthResponse(BaseModel):
    status: str
    lexicon_loaded: bool
    model1_loaded: bool
    model2_loaded: bool
