"""Hit moonboard.com with provided credentials.

Usage:
    KT_MOONBOARD_USERNAME='you' \
    KT_MOONBOARD_PASSWORD='secret' \
    KT_MOONBOARD_LAYOUT=2019 \
    .venv/bin/python -m scripts.smoke_moonboard
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

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

    print(f"smoke: moonboard layout={layout}")
    scraper = MoonboardScraper()
    provider = MoonboardProvider(scraper=scraper)

    print("step: authenticate")
    try:
        token = await provider.authenticate({"username": username, "password": password})
    except ProviderAuthError as e:
        print(f"  FAIL auth: {e}")
        return 1
    except ProviderUnavailable as e:
        print(f"  FAIL upstream: {e}")
        return 1
    print(f"  OK auth: cookie={_redact(token.value)}")

    print(f"step: search_climbs (layout={layout}, limit=20)")
    try:
        climbs = await provider.search_climbs(token, ClimbQuery(layout_id=layout, limit=20))
    except Exception as e:
        print(f"  FAIL search_climbs: {type(e).__name__}: {e}")
        return 1
    print(f"  OK search_climbs: {len(climbs)} climbs returned")
    for c in climbs[:5]:
        print(f"    - id={c.id!r} name={c.name!r} grade={c.grade} ascents={c.ascents}")

    print("step: raw introspection")
    raw = await scraper.list_problems(token.value, layout, None, 20, 0)
    print(f"  raw_count={len(raw)}")
    if raw:
        sample_keys = sorted(raw[0].keys())
        print(f"  sample_keys={sample_keys}")
        print(f"  sample_record={json.dumps(raw[0], default=str)[:600]}")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
