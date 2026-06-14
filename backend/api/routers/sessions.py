from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.config import get_settings
from api.models.sessions import SessionCreate, SessionDetail, SessionMeta, SessionRename, SessionUpdate
from api.services.session_storage import SessionStorage

router = APIRouter(prefix="/sessions")


def _storage(request: Request) -> SessionStorage:
    existing = getattr(request.app.state, "session_storage", None)
    if isinstance(existing, SessionStorage):
        return existing
    storage = SessionStorage(get_settings().session_storage_path)
    request.app.state.session_storage = storage
    return storage


@router.get("", response_model=list[SessionMeta])
async def list_sessions(request: Request) -> list[SessionMeta]:
    return _storage(request).list_sessions()


@router.post("", response_model=SessionDetail)
async def create_session(payload: SessionCreate, request: Request) -> SessionDetail:
    return _storage(request).create_session(payload)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, request: Request) -> SessionDetail:
    detail = _storage(request).get_session(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="session not found")
    return detail


@router.put("/{session_id}", response_model=SessionDetail)
async def save_session(session_id: str, payload: SessionUpdate, request: Request) -> SessionDetail:
    try:
        return _storage(request).save_session(session_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None


@router.patch("/{session_id}", response_model=SessionDetail)
async def rename_session(session_id: str, payload: SessionRename, request: Request) -> SessionDetail:
    try:
        return _storage(request).rename_session(session_id, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request) -> dict[str, bool | str]:
    deleted = _storage(request).delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": session_id, "deleted": True}
