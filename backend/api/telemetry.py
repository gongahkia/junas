"""Opt-in Logfire instrumentation.

Gated entirely behind the ``LOGFIRE_TOKEN`` env var. When unset, every
hook in this module is a no-op and no network calls are made. See
``docs/contributor-observability.md`` for setup.

Privacy: we never emit API keys, model outputs, or user-provided text.
Only structural metadata (workflow, evaluator, score, duration, error
class). Outputs belong in the harness receipt JSON.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_LOGFIRE: Any = None  # cached module handle when active
_CONFIGURED = False


def is_enabled() -> bool:
    return bool(os.environ.get("LOGFIRE_TOKEN", "").strip())


def configure(service_name: str = "junas") -> Any | None:
    """Configure Logfire if ``LOGFIRE_TOKEN`` is set, else no-op.

    Idempotent: subsequent calls return the cached module.
    """
    global _LOGFIRE, _CONFIGURED
    if _CONFIGURED:
        return _LOGFIRE
    _CONFIGURED = True
    if not is_enabled():
        return None
    try:
        import logfire  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("LOGFIRE_TOKEN set but `logfire` package not installed; telemetry disabled")
        return None
    try:
        logfire.configure(service_name=service_name, send_to_logfire=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("logfire.configure failed: %s; telemetry disabled", type(exc).__name__)
        return None
    _LOGFIRE = logfire
    logger.info("logfire telemetry enabled (service=%s)", service_name)
    return logfire


def instrument_fastapi(app: Any) -> None:
    """Attach Logfire's FastAPI instrumentor when active."""
    lf = configure()
    if lf is None:
        return
    try:
        lf.instrument_fastapi(app)
    except Exception as exc:  # noqa: BLE001
        logger.warning("logfire.instrument_fastapi failed: %s", type(exc).__name__)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Open a Logfire span when active, else a no-op context.

    Caller is responsible for passing only structural metadata — no raw
    user text, no model outputs, no API keys.
    """
    lf = configure()
    if lf is None:
        with nullcontext() as ctx:
            yield ctx
        return
    try:
        with lf.span(name, **attributes) as s:
            yield s
    except Exception as exc:  # noqa: BLE001
        logger.warning("logfire.span(%s) failed: %s", name, type(exc).__name__)
        with nullcontext() as ctx:
            yield ctx


def set_span_attributes(span_obj: Any, **attributes: Any) -> None:
    """Best-effort attribute set on an active span; safe when span is None."""
    if span_obj is None:
        return
    setter = getattr(span_obj, "set_attribute", None)
    if setter is None:
        return
    for k, v in attributes.items():
        try:
            setter(k, v)
        except Exception:  # noqa: BLE001
            pass
