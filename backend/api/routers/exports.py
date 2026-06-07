"""DOCX export endpoints for benchmark receipts and chat sessions.

Sessions persistence (COPILOT-1) is not yet wired; the session export route
accepts an inline session payload so the frontend can post the in-memory
conversation tree. Once /api/v1/sessions/{id} lands, swap the body for a
server-side lookup.
"""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.routers.benchmarks import _find_receipt, _read_receipt
from api.services.docx_export import (
    build_receipt_docx,
    build_session_docx,
    receipt_filename,
    session_filename,
)

router = APIRouter(prefix="/exports")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class SessionMessageBody(BaseModel):
    role: str
    content: str
    timestamp: float | str | None = None


class SessionExportBody(BaseModel):
    session_id: str = Field(..., min_length=1)
    title: str | None = None
    created_at: str | None = None
    messages: list[SessionMessageBody] = Field(default_factory=list)


def _content_disposition(filename: str) -> str:
    safe = filename.replace('"', "")
    return f'attachment; filename="{safe}"'


@router.get("/receipt/{run_id}.docx")
async def export_receipt(run_id: str) -> Response:
    found = _find_receipt(run_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run not found: {run_id}",
        )
    canonical_run_id, receipt_path = found
    payload = _read_receipt(receipt_path)
    blob = build_receipt_docx(payload)
    return Response(
        content=blob,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": _content_disposition(receipt_filename(canonical_run_id))},
    )


@router.post("/session/{session_id}.docx")
async def export_session(session_id: str, body: SessionExportBody | None = None) -> Response:
    # COPILOT-1 sessions persistence has not landed; require inline payload.
    if body is None or not body.messages:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="sessions endpoint not yet wired; POST session payload (messages[]) inline.",
        )
    if body.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id in body does not match URL",
        )
    session: dict[str, Any] = {
        "title": body.title or "Chat session",
        "created_at": body.created_at,
        "messages": [m.model_dump() for m in body.messages],
    }
    blob = build_session_docx(session)
    return Response(
        content=blob,
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": _content_disposition(session_filename(session_id, body.title))
        },
    )
