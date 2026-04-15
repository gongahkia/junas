"""Hit moonboard.com with provided credentials.

Usage:
    KT_MOONBOARD_USERNAME='you' \
    KT_MOONBOARD_PASSWORD='secret' \
    KT_MOONBOARD_LAYOUT=2019 \
    .venv/bin/python -u -m scripts.smoke_moonboard

Reports the host user's logbook (MoonBoard does not expose a public problems
API via web)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from kt.providers.base import ClimbQuery, ProviderAuthError, ProviderUnavailable
from kt.providers.moonboard.provider import MoonboardProvider
from kt.providers.moonboard.scraper import MoonboardScraper


def _redact(s: str | None, keep: int = 4) -> str:
    if not s:
        return ""
    return f"{s[:keep]}…({len(s)} chars)"


async def main() -> int:
    username = os.environ.get("KT_MOONBOARD_USERNAME")
    password = os.environ.get("KT_MOONBOARD_PASSWORD")
    layout = os.environ.get("KT_MOONBOARD_LAYOUT", "2019")
    if not username or not password:
        print("ERROR: set KT_MOONBOARD_USERNAME and KT_MOONBOARD_PASSWORD", file=sys.stderr)
        return 2

    print(f"smoke: moonboard layout={layout}", flush=True)
    scraper = MoonboardScraper()
    provider = MoonboardProvider(scraper=scraper)

    print("step: authenticate", flush=True)
    t0 = time.monotonic()
    try:
        token = await provider.authenticate({"username": username, "password": password})
    except ProviderAuthError as e:
        print(f"  FAIL auth: {e}")
        return 1
    except ProviderUnavailable as e:
        print(f"  FAIL upstream: {e}")
        return 1
    print(f"  OK auth in {time.monotonic()-t0:.2f}s: cookie={_redact(token.value)}", flush=True)

    print("step: list_logbook (page=1, size=20)", flush=True)
    t0 = time.monotonic()
    try:
        data, total = await scraper.list_logbook(token.value, page=1, page_size=20)
    except Exception as e:
        print(f"  FAIL list_logbook: {type(e).__name__}: {e}")
        return 1
    print(f"  OK list_logbook: {len(data)} entries / total={total} in {time.monotonic()-t0:.2f}s", flush=True)
    if data:
        print(f"  sample_keys={sorted(data[0].keys())}", flush=True)
        print(f"  sample={json.dumps(data[0], default=str)[:600]}", flush=True)
    else:
        print("  (this account has no logged entries — wire still confirmed by Total field)", flush=True)

    print("step: provider.search_climbs (limit=10)", flush=True)
    try:
        climbs = await provider.search_climbs(token, ClimbQuery(limit=10))
    except Exception as e:
        print(f"  FAIL search_climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK search_climbs: {len(climbs)} climbs", flush=True)
    for c in climbs[:5]:
        print(f"    - id={c.id!r} name={c.name!r} grade={c.grade} ascents={c.ascents}", flush=True)

    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
