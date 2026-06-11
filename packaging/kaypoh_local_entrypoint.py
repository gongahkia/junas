"""PyInstaller entrypoint for the kaypoh-local desktop SKU.

Boots the FastAPI runtime on 127.0.0.1 with the deterministic engine and no
external HTTP. The frozen binary is intended to be launched
by a desktop shell (Tauri / Electron) which talks to it over loopback.
"""

from __future__ import annotations

import os
import sys


def _set_local_defaults() -> None:
    os.environ.setdefault("KAYPOH_HOST", "127.0.0.1")
    os.environ.setdefault("KAYPOH_PORT", "8765")
    os.environ.setdefault("PIPELINE_LAYERS", "")
    os.environ.setdefault("KAYPOH_PUBLIC_EVIDENCE_ENABLED", "0")
    os.environ.setdefault("KAYPOH_LLM_ENABLED", "0")
    os.environ.setdefault("KAYPOH_REVIEW_PERSIST", "1")
    os.environ.setdefault("KAYPOH_LOCAL_DAEMON_ACL_ENABLED", "1")


def main() -> int:
    _set_local_defaults()
    import uvicorn

    from kaypoh.backend.main import app  # noqa: F401  -- ensures app symbol resolves

    host = os.environ["KAYPOH_HOST"]
    port = int(os.environ["KAYPOH_PORT"])
    log_level = os.environ.get("KAYPOH_LOG_LEVEL", "info")
    socket_path = os.environ.get("KAYPOH_LOCAL_SOCKET_PATH", "").strip()

    target = f"unix:{socket_path}" if socket_path else f"http://{host}:{port}"
    sys.stdout.write(f"kaypoh-local listening on {target}\n")
    sys.stdout.flush()
    if socket_path:
        try:
            os.unlink(socket_path)
        except FileNotFoundError:
            pass
        uvicorn.run("kaypoh.backend.main:app", uds=socket_path, log_level=log_level)
    else:
        uvicorn.run("kaypoh.backend.main:app", host=host, port=port, log_level=log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
