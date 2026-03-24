"""Compatibility shim for the canonical `noupe.backend.observability` module."""

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("noupe.backend.observability")
_sys.modules[__name__] = _module
