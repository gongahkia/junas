"""Hit a real Aurora-ecosystem board with provided credentials.

Usage:
    KT_AURORA_BOARD=tension \
    KT_AURORA_USERNAME='you@example.com' \
    KT_AURORA_PASSWORD='secret' \
    .venv/bin/python -m scripts.smoke_aurora

Reports what worked, what wire fields were observed, and what assumptions in
the client need adjusting. Does not log credentials or full payload bodies."""

from __future__ import annotations

import asyncio
import json
import os
import sys
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
    for it in items[:10]:
        for k in it.keys():
            keys[k] = keys.get(k, 0) + 1
    return dict(sorted(keys.items()))


async def main() -> int:
    board = os.environ.get("KT_AURORA_BOARD", "tension").lower()
    username = os.environ.get("KT_AURORA_USERNAME")
    password = os.environ.get("KT_AURORA_PASSWORD")
    if not username or not password:
        print("ERROR: set KT_AURORA_USERNAME and KT_AURORA_PASSWORD", file=sys.stderr)
        return 2
    if board not in AURORA_BOARDS:
        print(f"ERROR: KT_AURORA_BOARD must be one of {list(AURORA_BOARDS)}", file=sys.stderr)
        return 2

    print(f"smoke: board={board} host={AURORA_HOSTS[board]}")

    client = AuroraClient(board)
    provider = AuroraProvider(board, AURORA_BOARDS[board], client=client)

    print("step: authenticate")
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
    except Exception as e:
        print(f"  FAIL unexpected: {type(e).__name__}: {e}")
        return 1
    print(f"  OK auth: token={_redact(token.value)}")

    print("step: list_layouts")
    try:
        layouts = await provider.list_layouts(token)
        print(f"  OK list_layouts: {len(layouts)} layouts")
        for l in layouts[:5]:
            print(f"    - id={l.id} name={l.name!r} angles={l.angles}")
    except Exception as e:
        print(f"  WARN list_layouts: {type(e).__name__}: {e}")
        layouts = []

    print("step: search_climbs (limit=20)")
    try:
        climbs = await provider.search_climbs(token, ClimbQuery(limit=20))
    except Exception as e:
        print(f"  FAIL search_climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK search_climbs: {len(climbs)} climbs returned")
    for c in climbs[:5]:
        print(
            f"    - id={c.id!r} name={c.name!r} grade={c.grade} angle={c.angle} ascents={c.ascents}"
        )

    print("step: introspect raw payload (first 5 records, key set)")
    raw = await client.sync_climbs(token.value)
    print(f"  raw_count={len(raw)} sample_keys={_summarize_keys(raw)}")
    if raw:
        print("  sample_record (redacted):")
        sample = {k: ("..." if isinstance(v, (dict, list)) and len(json.dumps(v)) > 80 else v)
                  for k, v in raw[0].items()}
        print(f"    {json.dumps(sample, default=str)[:600]}")

    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
