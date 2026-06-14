from __future__ import annotations

from collections import Counter
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from starlette.responses import StreamingResponse

from api.models.batch import BatchCreateRequest, BatchJob
from api.services.batch_service import BatchService
from api.services.contract_classifier import ContractClassifier
from api.services.tos_scanner import ToSScanner

router = APIRouter(prefix="/contracts")


class ContractClassifyRequest(BaseModel):
    text: str = Field(..., min_length=1)
    top_k_types: int = Field(3, ge=1, le=5)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("text must not be blank")
        return text


class ToSScanRequest(BaseModel):
    text: str = Field(..., min_length=1)
    threshold: float = Field(0.5, ge=0.0, le=1.0)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("text must not be blank")
        return text


def get_contract_classifier(request: Request) -> ContractClassifier:
    classifier = getattr(request.app.state, "contract_classifier", None)
    if classifier is None:
        raise HTTPException(status_code=503, detail="Contract classifier model is not loaded")
    return classifier


def get_tos_scanner(request: Request) -> ToSScanner:
    scanner = getattr(request.app.state, "tos_scanner", None)
    if scanner is None:
        raise HTTPException(status_code=503, detail="ToS scanner model is not loaded")
    return scanner


def get_batch_service(
    request: Request,
    classifier: ContractClassifier = Depends(get_contract_classifier),
    scanner: ToSScanner = Depends(get_tos_scanner),
) -> BatchService:
    service = getattr(request.app.state, "batch_service", None)
    if not isinstance(service, BatchService) or service.classifier is not classifier or service.tos_scanner is not scanner:
        service = BatchService(classifier, scanner)
        request.app.state.batch_service = service
    return service


@router.post("/classify")
async def classify_contract(
    body: ContractClassifyRequest,
    classifier: ContractClassifier = Depends(get_contract_classifier),
) -> dict[str, Any]:
    clauses = classifier.classify_contract(body.text, top_k_types=body.top_k_types)
    distribution = dict(Counter(clause["clause_type"] for clause in clauses))
    return {
        "total_clauses": len(clauses),
        "clauses": clauses,
        "clause_distribution": distribution,
    }


@router.post("/scan-tos")
async def scan_tos(
    body: ToSScanRequest,
    scanner: ToSScanner = Depends(get_tos_scanner),
) -> dict[str, Any]:
    return scanner.scan_tos(body.text, threshold=body.threshold)


@router.post("/batch", response_model=BatchJob)
async def create_batch(
    body: BatchCreateRequest,
    service: BatchService = Depends(get_batch_service),
) -> BatchJob:
    return service.create_job(body)


@router.get("/batch/{batch_id}", response_model=BatchJob)
async def get_batch(batch_id: str, service: BatchService = Depends(get_batch_service)) -> BatchJob:
    job = service.get_job(batch_id)
    if job is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return job


@router.post("/batch/{batch_id}/cancel", response_model=BatchJob)
async def cancel_batch(batch_id: str, service: BatchService = Depends(get_batch_service)) -> BatchJob:
    job = await service.cancel_job(batch_id)
    if job is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return job


@router.get("/batch/{batch_id}/events")
async def batch_events(batch_id: str, service: BatchService = Depends(get_batch_service)) -> StreamingResponse:
    if service.get_job(batch_id) is None:
        raise HTTPException(status_code=404, detail="batch not found")

    async def stream():
        async for event in service.iter_events(batch_id):
            yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
