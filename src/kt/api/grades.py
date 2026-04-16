from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from kt.grades import SYSTEMS, convert, parse_to_v, system_value

router = APIRouter(prefix="/grades")


@router.get("/systems")
async def list_systems():
    return {"systems": list(SYSTEMS)}


@router.get("/convert")
async def convert_grade(
    value: Annotated[str, Query(min_length=1, max_length=16)],
    from_system: Annotated[str, Query(alias="from", min_length=1, max_length=8)],
    to_system: Annotated[str, Query(alias="to", min_length=1, max_length=8)],
):
    try:
        converted = convert(value, from_system, to_system)
    except ValueError as e:
        raise HTTPException(400, {"error": "bad_system", "detail": str(e)}) from e
    v = parse_to_v(value) if from_system.lower() != "v" else None
    if converted is None:
        raise HTTPException(400, {"error": "unrecognized_grade", "detail": value})
    return {
        "from": {"system": from_system.lower(), "value": value},
        "to": {"system": to_system.lower(), "value": converted},
        "v": v if v is not None else parse_to_v(converted),
        "all": {sys: system_value(parse_to_v(converted) or -1, sys) for sys in SYSTEMS},
    }
