from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from kt.api.auth import require_user
from kt.api.deps import (
    get_climb_notes_repo,
    get_favorites_repo,
    get_logbook_repo,
)
from kt.grades import parse_to_v
from kt.repos.climb_notes_repo import ClimbNotesRepo
from kt.repos.favorites_repo import FavoritesRepo
from kt.repos.logbook_repo import LogbookRepo
from kt.schemas.logbook import (
    FavoriteOut,
    FavoritesPage,
    FavoriteToggleReq,
    ImportResp,
    LogbookCreate,
    LogbookOut,
    LogbookPage,
    NoteOut,
    NoteReq,
)

router = APIRouter(prefix="/me")


@router.get("/logbook", response_model=LogbookPage)
async def list_logbook(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    before: Annotated[str | None, Query()] = None,
    provider: Annotated[str | None, Query()] = None,
):
    entries = await repo.list_for_user(user["id"], limit=limit, before=before, provider=provider)
    next_before = entries[-1]["climbed_at"] if len(entries) == limit else None
    return LogbookPage(
        entries=[LogbookOut(**e) for e in entries], next_before=next_before
    )


@router.post("/logbook", response_model=LogbookOut)
async def create_logbook_entry(
    req: LogbookCreate,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
):
    try:
        row = await repo.add(
            user_id=user["id"],
            provider=req.provider,
            climb_id=req.climb_id,
            result=req.result,
            name=req.name,
            session_code=req.session_code,
            grade_at_send=req.grade_at_send,
            attempts=req.attempts,
            rpe=req.rpe,
            duration_seconds=req.duration_seconds,
            angle=req.angle,
            notes=req.notes,
            climbed_at=req.climbed_at,
        )
    except ValueError as e:
        raise HTTPException(400, {"error": "bad_entry", "detail": str(e)}) from e
    return LogbookOut(**row)


@router.delete("/logbook/{entry_id}")
async def delete_logbook_entry(
    entry_id: str,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
):
    ok = await repo.delete(user["id"], entry_id)
    if not ok:
        raise HTTPException(404, {"error": "not_found"})
    return {"deleted": True}


@router.get("/logbook/export")
async def export_logbook(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
    format: Annotated[str, Query(pattern=r"^(json|csv)$")] = "json",
):
    entries = await repo.list_for_user(user["id"], limit=10_000)
    if format == "json":
        return {"entries": entries}
    buf = io.StringIO()
    if not entries:
        return PlainTextResponse("", media_type="text/csv")
    cols = list(entries[0].keys())
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for e in entries:
        writer.writerow(e)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


_BOARDLIB_RESULT_MAP = {
    "flash": "flash",
    "onsight": "onsight",
    "send": "sent",
    "redpoint": "sent",
    "repeat": "repeat",
    "project": "project",
    "attempt": "attempted",
    "attempts": "attempted",
}


def _boardlib_provider_for(board: str) -> str:
    b = board.strip().lower()
    aliases = {
        "kilter": "kilter",
        "tension": "tension",
        "grasshopper": "grasshopper",
        "decoy": "decoy",
        "soill": "soill",
        "touchstone": "touchstone",
        "aurora": "aurora",
        "moon": "moonboard",
        "moonboard": "moonboard",
    }
    return aliases.get(b, b)


@router.post("/logbook/import", response_model=ImportResp)
async def import_logbook(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
    file: Annotated[UploadFile, File(description="BoardLib CSV export")],
):
    data = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(data))
    imported = 0
    skipped = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        board = row.get("board") or row.get("Board") or ""
        climb_uuid = row.get("climb_uuid") or row.get("climb_id") or row.get("uuid")
        name = row.get("climb_name") or row.get("name")
        date = row.get("date") or row.get("climbed_at")
        grade = row.get("displayed_grade") or row.get("logged_grade") or row.get("grade")
        is_mirror = str(row.get("is_mirror") or row.get("mirror") or "").lower() in {"1", "true", "yes"}
        tries = row.get("tries") or row.get("attempts")
        comment = row.get("comment") or row.get("notes") or ""
        result_raw = (row.get("logged_ascent_type") or row.get("result") or "send").lower()
        angle = row.get("angle")

        if not climb_uuid:
            skipped += 1
            errors.append(f"row {i}: missing climb_uuid")
            continue
        try:
            await repo.add(
                user_id=user["id"],
                provider=_boardlib_provider_for(board),
                climb_id=str(climb_uuid),
                result=_BOARDLIB_RESULT_MAP.get(result_raw, "sent"),
                name=name,
                grade_at_send=grade,
                attempts=int(tries) if tries and str(tries).isdigit() else None,
                angle=int(angle) if angle and str(angle).lstrip("-").isdigit() else None,
                notes=(comment + (" [mirror]" if is_mirror else "")).strip() or None,
                climbed_at=date,
            )
            imported += 1
        except Exception as e:  # pragma: no cover - boardlib CSV is fuzzy
            skipped += 1
            errors.append(f"row {i}: {e}")
    return ImportResp(imported=imported, skipped=skipped, errors=errors[:50])


@router.get("/favorites", response_model=FavoritesPage)
async def list_favorites(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[FavoritesRepo, Depends(get_favorites_repo)],
    list_name: Annotated[str, Query(alias="list", min_length=1, max_length=64)] = "favorites",
):
    entries = await repo.list_for(user["id"], list_name=list_name)
    return FavoritesPage(
        list=list_name, entries=[FavoriteOut(**e) for e in entries]
    )


@router.post("/favorites", response_model=FavoriteOut)
async def add_favorite(
    req: FavoriteToggleReq,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[FavoritesRepo, Depends(get_favorites_repo)],
):
    row = await repo.add(
        user["id"], req.provider, req.climb_id, list_name=req.list_name
    )
    return FavoriteOut(**row)


@router.delete("/favorites")
async def remove_favorite(
    req: FavoriteToggleReq,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[FavoritesRepo, Depends(get_favorites_repo)],
):
    ok = await repo.remove(
        user["id"], req.provider, req.climb_id, list_name=req.list_name
    )
    return {"removed": bool(ok)}


@router.get("/favorites/lists")
async def list_favorite_lists(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[FavoritesRepo, Depends(get_favorites_repo)],
):
    return {"lists": await repo.lists_for(user["id"])}


@router.put("/notes/{provider}/{climb_id}", response_model=NoteOut)
async def put_note(
    provider: str,
    climb_id: str,
    req: NoteReq,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[ClimbNotesRepo, Depends(get_climb_notes_repo)],
):
    row = await repo.put(user["id"], provider, climb_id, req.body, req.tags)
    return NoteOut(**row)


@router.get("/notes/{provider}/{climb_id}", response_model=NoteOut)
async def get_note(
    provider: str,
    climb_id: str,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[ClimbNotesRepo, Depends(get_climb_notes_repo)],
):
    row = await repo.get(user["id"], provider, climb_id)
    if not row:
        raise HTTPException(404, {"error": "not_found"})
    return NoteOut(**row)


@router.delete("/notes/{provider}/{climb_id}")
async def delete_note(
    provider: str,
    climb_id: str,
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[ClimbNotesRepo, Depends(get_climb_notes_repo)],
):
    ok = await repo.delete(user["id"], provider, climb_id)
    if not ok:
        raise HTTPException(404, {"error": "not_found"})
    return {"deleted": True}


@router.get("/notes", response_model=list[NoteOut])
async def list_notes(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[ClimbNotesRepo, Depends(get_climb_notes_repo)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    rows = await repo.list_for_user(user["id"], limit=limit)
    return [NoteOut(**r) for r in rows]


@router.get("/stats")
async def logbook_stats(
    user: Annotated[dict, Depends(require_user)],
    repo: Annotated[LogbookRepo, Depends(get_logbook_repo)],
):
    """Basic analytics: total sends, per-result counts, per-grade histogram, hardest V."""
    entries = await repo.list_for_user(user["id"], limit=10_000)
    results: dict[str, int] = {}
    grade_hist: dict[int, int] = {}
    hardest: int | None = None
    for e in entries:
        results[e["result"]] = results.get(e["result"], 0) + 1
        v = e.get("grade_v_at_send")
        if v is None and e.get("grade_at_send"):
            v = parse_to_v(e["grade_at_send"])
        if v is not None and e["result"] in {"sent", "flash", "onsight"}:
            grade_hist[v] = grade_hist.get(v, 0) + 1
            if hardest is None or v > hardest:
                hardest = v
    return {
        "total_entries": len(entries),
        "by_result": results,
        "by_grade_v": grade_hist,
        "hardest_v": hardest,
    }
