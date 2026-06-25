#!/usr/bin/env python3
"""Smoke-test local daemon Origin/CORS and token gates."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


TOKEN = "local-smoke-token"


def _env() -> dict[str, str]:
    return {
        "KAYPOH_API_KEY": "",
        "KAYPOH_LOCAL_DAEMON_ACL_ENABLED": "1",
        "KAYPOH_LOCAL_DAEMON_TOKEN": TOKEN,
        "KAYPOH_LOCAL_DAEMON_ALLOWED_ORIGINS": "https://chatgpt.com,https://claude.ai,https://gemini.google.com,chrome-extension://*",
    }


def _post_classify(client: TestClient, origin: str, token: str = TOKEN):
    headers = {"Origin": origin}
    if token:
        headers["X-Kaypoh-Local-Token"] = token
    return client.post("/classify", json={"text": "public update"}, headers=headers)


def run_smoke() -> tuple[bool, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    with patch.dict(os.environ, _env(), clear=False):
        from kaypoh.backend import main  # noqa: PLC0415

        main._state.clear()
        with TestClient(main.app) as client:
            pairing_start = client.post(
                "/local/pairing/start",
                headers={"Origin": "https://chatgpt.com"},
                json={"client_name": "smoke"},
            )
            signed_token = ""
            if pairing_start.status_code == 200:
                pairing = pairing_start.json()
                client.post(
                    "/local/pairing/approve",
                    headers={"Origin": "https://chatgpt.com", "X-Kaypoh-Local-Token": TOKEN},
                    json={"pairing_id": pairing["pairing_id"], "pairing_code": pairing["pairing_code"]},
                )
                claim = client.post(
                    "/local/pairing/claim",
                    headers={"Origin": "https://chatgpt.com"},
                    json={"pairing_id": pairing["pairing_id"], "pairing_code": pairing["pairing_code"]},
                )
                if claim.status_code == 200:
                    signed_token = claim.json()["client_token"]
            cases = [
                ("disallowed_origin", _post_classify(client, "https://evil.example"), 403),
                ("missing_token", _post_classify(client, "https://chatgpt.com", token=""), 401),
                ("extension_allowed", _post_classify(client, "chrome-extension://abcdef"), 200),
                ("signed_token_allowed", _post_classify(client, "https://chatgpt.com", token=signed_token), 200),
                (
                    "cors_preflight_allowed",
                    client.options(
                        "/classify",
                        headers={
                            "Origin": "https://chatgpt.com",
                            "Access-Control-Request-Method": "POST",
                            "Access-Control-Request-Headers": "content-type,x-kaypoh-local-token",
                        },
                    ),
                    200,
                ),
                (
                    "cors_preflight_disallowed",
                    client.options(
                        "/classify",
                        headers={
                            "Origin": "https://evil.example",
                            "Access-Control-Request-Method": "POST",
                        },
                    ),
                    403,
                ),
                (
                    "pairing_status_open",
                    client.get("/local/pairing/status", headers={"Origin": "https://chatgpt.com"}),
                    200,
                ),
            ]
        main._state.clear()

    for name, response, expected in cases:
        ok = response.status_code == expected and TOKEN not in response.text
        rows.append({"name": name, "status_code": response.status_code, "expected": expected, "ok": ok})
    return all(row["ok"] for row in rows), rows


def main_cli() -> int:
    ok, rows = run_smoke()
    print(json.dumps({"ok": ok, "checks": rows}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
