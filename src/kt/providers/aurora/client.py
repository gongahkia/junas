"""Aurora-ecosystem HTTP client.

Wire format mirrors lemeryfertitta/BoardLib's `boardlib.api.aurora` module
(reverse-engineered from the iOS Kilter app traffic). Subject to upstream
change without notice; if a smoke test starts failing, diff against BoardLib's
latest `aurora.py`.
"""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from kt.providers.base import ProviderAuthError, ProviderUnavailable

HOST_BASES: dict[str, str] = {
    "aurora": "auroraboardapp",
    "decoy": "decoyboardapp",
    "grasshopper": "grasshopperboardapp",
    "kilter": "kilterboardapp",
    "soill": "soillboardapp",
    "tension": "tensionboardapp2",
    "touchstone": "touchstoneboardapp",
}
AURORA_HOSTS: dict[str, str] = {k: f"https://{v}.com" for k, v in HOST_BASES.items()}

_APP_UA = "Kilter%20Board/202 CFNetwork/1568.100.1 Darwin/24.0.0"

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=0.05, max=0.2),
    retry=retry_if_exception_type(ProviderUnavailable),
    reraise=True,
)


class AuroraClient:
    def __init__(self, board_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if board_key not in AURORA_HOSTS:
            raise KeyError(f"unknown aurora board: {board_key}")
        self.board_key = board_key
        self.base_url = AURORA_HOSTS[board_key]
        self._transport = transport

    def _client(self, content_type: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=20.0,
            transport=self._transport,
            headers={
                "Accept": "application/json",
                "Accept-Language": "en-AU,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Content-Type": content_type,
                "User-Agent": _APP_UA,
            },
        )

    @_retry
    async def login(self, username: str, password: str) -> str:
        async with self._client("application/json") as c:
            r = await c.post(
                "/sessions",
                json={
                    "username": username,
                    "password": password,
                    "tou": "accepted",
                    "pp": "accepted",
                    "ua": "app",
                },
            )
            if r.status_code in (401, 403, 422):
                detail = r.text[:300] if r.text else ""
                raise ProviderAuthError(f"upstream rejected ({r.status_code}): {detail}")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            data = r.json()
            session = data.get("session")
            if isinstance(session, dict):
                token = session.get("token")
            elif isinstance(session, str):
                token = session
            else:
                token = None
            if not token:
                raise ProviderAuthError("no token in response")
            return token

    async def sync(
        self,
        token: str | None,
        tables_and_sync_dates: dict[str, str],
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Drive the Aurora sync protocol. Returns concatenated page JSONs."""
        payload_dict = dict(tables_and_sync_dates)
        pages: list[dict[str, Any]] = []
        complete = False
        page_count = 0

        while not complete and page_count < max_pages:
            payload = "&".join(
                f"{quote(table)}={quote(sync_date)}"
                for table, sync_date in payload_dict.items()
            )
            page = await self._sync_page(token, payload)
            complete = page.pop("_complete", False)
            pages.append(page)

            if token:
                for us in page.get("user_syncs", []) or []:
                    tn = us.get("table_name")
                    last = us.get("last_synchronized_at")
                    if tn in payload_dict and last:
                        payload_dict[tn] = last
            for ss in page.get("shared_syncs", []) or []:
                tn = ss.get("table_name")
                last = ss.get("last_synchronized_at")
                if tn in payload_dict and last:
                    payload_dict[tn] = last

            page_count += 1
        return pages

    @_retry
    async def _sync_page(self, token: str | None, payload: str) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if token:
            headers["Cookie"] = f"token={token}"
        async with self._client("application/x-www-form-urlencoded") as c:
            r = await c.post("/sync", content=payload, headers=headers)
            if r.status_code in (401, 403):
                raise ProviderAuthError("token rejected")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            return r.json()

    async def fetch_table(
        self,
        token: str,
        table_name: str,
        max_pages: int = 100,
        on_page: "Callable[[int, int], None] | None" = None,
    ) -> list[dict[str, Any]]:
        """Sync one shared table from epoch and return its rows across pages."""
        rows: list[dict[str, Any]] = []
        pages = await self.sync(
            token,
            {table_name: "1970-01-01 00:00:00.000000"},
            max_pages=max_pages,
        )
        for i, page in enumerate(pages, 1):
            chunk = page.get(table_name)
            if chunk is None:
                put = page.get("PUT") or {}
                chunk = put.get(table_name) or []
            if isinstance(chunk, list):
                rows.extend(chunk)
            if on_page is not None:
                on_page(i, len(rows))
        return rows
