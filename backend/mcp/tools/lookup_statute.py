"""MCP wrapper for local Singapore statute lookup."""
from __future__ import annotations

import os
from pathlib import Path

from api.services.statute_lookup import load_sso_jsonl, resolve_citation_offline

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _candidate_paths() -> list[Path]:
    env_path = os.environ.get("JUNAS_SSO_JSONL")
    paths = []
    if env_path:
        paths.append(Path(env_path))
    paths.extend(
        [
            BACKEND_ROOT / "vendor-data" / "sso" / "statutes.jsonl",
            BACKEND_ROOT.parent / "vendor-data" / "sso" / "statutes.jsonl",
        ]
    )
    return paths


def lookup_statute(query: str) -> dict:
    raw = str(query or "").strip()
    if not raw:
        return {"error": "query must not be blank"}

    for path in _candidate_paths():
        if not path.exists():
            continue
        try:
            rows = load_sso_jsonl(path)
            result = resolve_citation_offline(raw, rows)
        except Exception as exc:  # noqa: BLE001
            return {"query": raw, "source": str(path), "error": str(exc)}
        if result is None:
            return {"query": raw, "source": str(path), "found": False, "result": None}
        return {"query": raw, "source": str(path), "found": True, "result": result}

    return {
        "query": raw,
        "error": "local SSO JSONL not found; run `make ingest-sso` or set JUNAS_SSO_JSONL",
    }
