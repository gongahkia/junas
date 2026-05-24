"""PyInstaller entrypoint for the kaypoh-local desktop SKU.

Boots the FastAPI runtime on 127.0.0.1 with the lexicon-only pipeline (no server-side
classifier layers) and no external HTTP. The frozen binary is intended to be launched
by a desktop shell (Tauri / Electron) which talks to it over loopback.
"""

from __future__ import annotations

import os
import sys


def _set_local_defaults() -> None:
    os.environ.setdefault("KAYPOH_HOST", "127.0.0.1")
    os.environ.setdefault("KAYPOH_PORT", "8765")
    os.environ.setdefault("KAYPOH_PIPELINE_LAYERS", "lexicon")
    os.environ.setdefault("KAYPOH_PUBLIC_EVIDENCE_ENABLED", "0")
    os.environ.setdefault("KAYPOH_LLM_ENABLED", "0")
    os.environ.setdefault("KAYPOH_REVIEW_PERSIST", "1")


def main() -> int:
    _set_local_defaults()
    import uvicorn
    from backend.main import app  # noqa: F401  -- ensures app symbol resolves

    host = os.environ["KAYPOH_HOST"]
    port = int(os.environ["KAYPOH_PORT"])
    log_level = os.environ.get("KAYPOH_LOG_LEVEL", "info")

    sys.stdout.write(f"kaypoh-local listening on http://{host}:{port}\n")
    sys.stdout.flush()
    uvicorn.run("backend.main:app", host=host, port=port, log_level=log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
