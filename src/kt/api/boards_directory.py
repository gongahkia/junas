from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from kt.api.deps import get_boards_repo
from kt.boards.loader import ingest_geojson
from kt.repos.boards_repo import BoardsRepo

router = APIRouter(prefix="/boards")


@router.get("")
async def list_boards(
    repo: Annotated[BoardsRepo, Depends(get_boards_repo)],
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float, Query(ge=0.1, le=20000)] = 100.0,
    board_type: Annotated[str | None, Query(max_length=64)] = None,
    country: Annotated[str | None, Query(max_length=2)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    # If geocoding params provided, do a spatial search; else list.
    if lat is not None and lon is not None:
        rows = await repo.search_nearby(lat, lon, radius_km, board_type=board_type, limit=limit)
    else:
        rows = await repo.list_all(board_type=board_type, country=country, limit=limit)
    return {"boards": rows, "count": len(rows)}


@router.get("/types")
async def list_board_types(repo: Annotated[BoardsRepo, Depends(get_boards_repo)]):
    return {"types": await repo.types()}


@router.get("/{bid}")
async def get_board(bid: str, repo: Annotated[BoardsRepo, Depends(get_boards_repo)]):
    row = await repo.get(bid)
    if not row:
        raise HTTPException(404, {"error": "not_found"})
    return row


@router.post("/reload")
async def reload_boards(repo: Annotated[BoardsRepo, Depends(get_boards_repo)]):
    # Load the bundled sample. Operators can replace the data at runtime by
    # seeding the board_locations table from an external GeoJSON via the CLI.
    count = await ingest_geojson()
    return {"loaded": count, "total": await repo.count()}
