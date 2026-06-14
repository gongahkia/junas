"""DOCX export endpoints for benchmark receipts and chat sessions."""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.config import get_settings
from api.routers.benchmarks import _find_receipt, _read_receipt
from api.services.docx_export import (
    build_receipt_docx,
    build_session_docx,
    receipt_filename,
    session_filename,
)
from api.services.session_storage import SessionStorage

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


def _session_storage(request: Request) -> SessionStorage:
    existing = getattr(request.app.state, "session_storage", None)
    if isinstance(existing, SessionStorage):
        return existing
    storage = SessionStorage(get_settings().session_storage_path)
    request.app.state.session_storage = storage
    return storage


def _linear_messages(node_map: dict[str, Any], current_leaf_id: str) -> list[dict[str, Any]]:
    if current_leaf_id and current_leaf_id in node_map:
        lineage: list[dict[str, Any]] = []
        node_id = current_leaf_id
        seen: set[str] = set()
        while node_id and node_id not in seen:
            seen.add(node_id)
            node = node_map.get(node_id)
            if not isinstance(node, dict):
                break
            lineage.append(node)
            node_id = str(node.get("parentId") or node.get("parent_id") or "")
        nodes = list(reversed(lineage))
    else:
        nodes = sorted(
            [node for node in node_map.values() if isinstance(node, dict)],
            key=lambda node: int(node.get("timestamp") or 0),
        )
    return [
        {
            "role": str(node.get("role") or ""),
            "content": str(node.get("content") or ""),
            "timestamp": node.get("timestamp"),
        }
        for node in nodes
        if node.get("role") and node.get("content")
    ]


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
async def export_session(session_id: str, request: Request, body: SessionExportBody | None = None) -> Response:
    if body is not None and body.messages:
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
        title = body.title
    else:
        detail = _session_storage(request).get_session(session_id)
        if detail is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
        session = {
            "title": detail.title,
            "created_at": detail.created_at.isoformat(),
            "messages": _linear_messages(detail.node_map, detail.current_leaf_id),
        }
        title = detail.title
    blob = build_session_docx(session)
    return Response(
        content=blob,
        media_type=DOCX_MIME,
        headers={
            "Content-Disposition": _content_disposition(session_filename(session_id, title))
        },
    )
