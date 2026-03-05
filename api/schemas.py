"""
Legacy schema entrypoint shim.

`backend.schemas` is the canonical location.
This module re-exports it for backward compatibility.
"""

from backend.schemas import *  # noqa: F401,F403
