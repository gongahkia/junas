"""Compatibility shim for the canonical `kaypoh.backend.main` module."""

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_SRC_ROOT = _Path(__file__).resolve().parent.parent / "src"
if str(_SRC_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_SRC_ROOT))

_module = _import_module("kaypoh.backend.main")
_sys.modules[__name__] = _module
