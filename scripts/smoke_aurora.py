"""Hit a real Aurora-ecosystem board with provided credentials.

Usage:
    KT_AURORA_BOARD=tension \
    KT_AURORA_USERNAME='you@example.com' \
    KT_AURORA_PASSWORD='secret' \
    KT_AURORA_MAX_PAGES=3 \
    .venv/bin/python -u -m scripts.smoke_aurora

Exits non-zero on auth/protocol failure. Never logs full credentials or full
response bodies."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

from kt.providers.aurora.client import AURORA_HOSTS, AuroraClient
from kt.providers.aurora.provider import AURORA_BOARDS, AuroraProvider
from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)


def _redact(s: str | None, keep: int = 4) -> str:
    if not s:
        return ""
    return f"{s[:keep]}…({len(s)} chars)"


def _summarize_keys(items: list[dict[str, Any]]) -> dict[str, int]:
    keys: dict[str, int] = {}
    for it in items[:50]:
        if not isinstance(it, dict):
            continue
        for k in it.keys():
            keys[k] = keys.get(k, 0) + 1
    return dict(sorted(keys.items()))


async def main() -> int:
    board = os.environ.get("KT_AURORA_BOARD", "tension").lower()
    username = os.environ.get("KT_AURORA_USERNAME")
    password = os.environ.get("KT_AURORA_PASSWORD")
    max_pages = int(os.environ.get("KT_AURORA_MAX_PAGES", "3"))
    if not username or not password:
        print("ERROR: set KT_AURORA_USERNAME and KT_AURORA_PASSWORD", file=sys.stderr)
        return 2
    if board not in AURORA_BOARDS:
        print(f"ERROR: KT_AURORA_BOARD must be one of {list(AURORA_BOARDS)}", file=sys.stderr)
        return 2

    print(f"smoke: board={board} host={AURORA_HOSTS[board]} max_pages={max_pages}", flush=True)

    client = AuroraClient(board)
    provider = AuroraProvider(board, AURORA_BOARDS[board], client=client)

    print("step: authenticate", flush=True)
    t0 = time.monotonic()
    try:
        token: AuthToken = await provider.authenticate(
            {"username": username, "password": password}
        )
    except ProviderAuthError as e:
        print(f"  FAIL auth: {e}")
        return 1
    except ProviderUnavailable as e:
        print(f"  FAIL upstream: {e}")
        return 1
    print(f"  OK auth in {time.monotonic()-t0:.2f}s: token={_redact(token.value)}", flush=True)

    print(f"step: fetch_table climbs (max_pages={max_pages})", flush=True)
    t0 = time.monotonic()

    def progress(page: int, total_rows: int) -> None:
        print(f"  page={page} cumulative_rows={total_rows} elapsed={time.monotonic()-t0:.1f}s", flush=True)

    try:
        rows = await client.fetch_table(
            token.value, "climbs", max_pages=max_pages, on_page=progress
        )
    except Exception as e:
        print(f"  FAIL fetch_table climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK climbs: {len(rows)} rows in {time.monotonic()-t0:.2f}s", flush=True)

    if rows:
        print(f"  sample_keys={_summarize_keys(rows)}", flush=True)
        sample = {
            k: ("..." if isinstance(v, (dict, list)) and len(json.dumps(v, default=str)) > 80 else v)
            for k, v in rows[0].items()
        }
        print(f"  sample_record={json.dumps(sample, default=str)[:600]}", flush=True)

    print("step: search_climbs (text='a', limit=10) — exercises full provider path", flush=True)
    try:
        climbs = await provider.search_climbs(token, ClimbQuery(text="a", limit=10))
    except Exception as e:
        print(f"  FAIL search_climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK search_climbs: {len(climbs)} climbs", flush=True)
    for c in climbs[:5]:
        print(f"    - id={c.id!r} name={c.name!r} grade={c.grade} angle={c.angle} ascents={c.ascents}", flush=True)

    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
