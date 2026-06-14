from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

BatchStatus = Literal["queued", "running", "completed", "cancelled", "error"]
DocumentStatus = Literal["pending", "running", "done", "error", "cancelled"]


class BatchDocument(BaseModel):
    id: str
    file_name: str
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("text must not be blank")
        return text


class BatchCreateRequest(BaseModel):
    documents: list[BatchDocument] = Field(..., min_length=1, max_length=50)
    threshold: float = Field(0.5, ge=0.0, le=1.0)
    top_k_types: int = Field(3, ge=1, le=5)


class BatchResult(BaseModel):
    document_id: str
    file_name: str
    status: DocumentStatus
    summary: str = ""
    clauses: list[dict[str, Any]] = Field(default_factory=list)
    flagged_clauses: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BatchJob(BaseModel):
    id: str
    status: BatchStatus
    total: int
    completed: int = 0
    cancelled: bool = False
    created_at: datetime
    updated_at: datetime
    results: list[BatchResult] = Field(default_factory=list)
