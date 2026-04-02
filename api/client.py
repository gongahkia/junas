"""
Legacy API client shim.

`noupe.client` is the canonical Python integration surface.
This module exists for backward compatibility with older repo-local imports.
"""

from backend.client import *  # noqa: F401,F403
