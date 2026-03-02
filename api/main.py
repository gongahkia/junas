"""
Legacy API entrypoint shim.

`backend.main:app` is the canonical orchestrator.
This module exists for backward compatibility with older run commands.
"""

from backend.main import app  # re-export canonical FastAPI app

