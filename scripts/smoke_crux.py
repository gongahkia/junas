"""Hit cruxapp.ca with provided credentials.

Usage:
    KT_CRUX_TOKEN='bearer-token-from-app' \
    KT_CRUX_GYM_SLUG='your-gym-slug' \
    .venv/bin/python -u -m scripts.smoke_crux

Token: in the Crux mobile app, settings → API Authentication.
Gym slug: visible in cruxapp.ca URLs for your home gym.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from kt.providers.base import ClimbQuery, ProviderAuthError, ProviderUnavailable
from kt.providers.crux.provider import CruxProvider


def _redact(s: str | None, keep: int = 4) -> str:
    if not s:
        return ""
    return f"{s[:keep]}…({len(s)} chars)"


async def main() -> int:
    token = os.environ.get("KT_CRUX_TOKEN")
    gym_slug = os.environ.get("KT_CRUX_GYM_SLUG")
    if not token or not gym_slug:
        print("ERROR: set KT_CRUX_TOKEN and KT_CRUX_GYM_SLUG", file=sys.stderr)
        return 2

    print(f"smoke: crux gym_slug={gym_slug} token={_redact(token)}", flush=True)
    provider = CruxProvider()

    print("step: authenticate (also validates gym_slug)", flush=True)
    t0 = time.monotonic()
    try:
        auth_token = await provider.authenticate({"token": token, "gym_slug": gym_slug})
    except ProviderAuthError as e:
        print(f"  FAIL auth: {e}")
        return 1
    except ProviderUnavailable as e:
        print(f"  FAIL upstream: {e}")
        return 1
    print(f"  OK auth in {time.monotonic()-t0:.2f}s", flush=True)

    print("step: list_layouts (gym walls)", flush=True)
    t0 = time.monotonic()
    try:
        layouts = await provider.list_layouts(auth_token)
    except Exception as e:
        print(f"  FAIL list_layouts: {type(e).__name__}: {e}")
        return 1
    print(f"  OK list_layouts: {len(layouts)} walls in {time.monotonic()-t0:.2f}s", flush=True)
    for l in layouts[:5]:
        print(f"    - id={l.id!r} name={l.name!r} angles={l.angles}", flush=True)

    print("step: search_climbs (limit=10)", flush=True)
    t0 = time.monotonic()
    try:
        climbs = await provider.search_climbs(auth_token, ClimbQuery(limit=10))
    except Exception as e:
        print(f"  FAIL search_climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK search_climbs: {len(climbs)} climbs in {time.monotonic()-t0:.2f}s", flush=True)
    for c in climbs[:5]:
        print(
            f"    - id={c.id!r} name={c.name!r} grade={c.grade} angle={c.angle} sends={c.ascents}",
            flush=True,
        )

    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
