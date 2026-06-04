"""Task registry.

A ``task`` is an async callable ``(case) -> str`` that runs the workflow
under evaluation on a case. Tasks register themselves with their string
name; the CLI looks them up.

A *provenance* record (optional) carries the publication-grade metadata
required by `docs/coverage-matrix.md` §4.4 — prompt version, prompt SHA,
provider label, max tokens. The runner copies it onto every JSON
receipt so reviewers can re-run the same eval and get bit-identical
inputs.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from benchmark.schema import Case

TaskRunner = Callable[[Case], Awaitable[str]]

TASKS: dict[str, TaskRunner] = {}
PROVENANCE: dict[str, dict[str, Any]] = {}


def register_task(
    name: str,
    runner: TaskRunner,
    *,
    provenance: dict[str, Any] | None = None,
) -> None:
    """Register a task runner by name. Re-registration overwrites.

    Args:
        name: registered task name.
        runner: async callable ``(case) -> str``.
        provenance: optional dict of publication-grade metadata
            (``prompt_version``, ``prompt_sha``, ``provider_label``,
            ``max_tokens``). Stored alongside the runner and copied onto
            every JSON receipt for runs of this workflow.
    """
    TASKS[name] = runner
    if provenance is not None:
        PROVENANCE[name] = dict(provenance)
    else:
        PROVENANCE.pop(name, None)


def register_provenance(name: str, provenance: dict[str, Any]) -> None:
    """Attach (or replace) provenance metadata for an already-registered task."""
    PROVENANCE[name] = dict(provenance)


def get_provenance(name: str) -> dict[str, Any]:
    """Return provenance metadata for a task, empty dict if none registered."""
    return dict(PROVENANCE.get(name, {}))


async def _echo_task(case: Case) -> str:
    """Trivial smoke task. Returns the ``query`` input verbatim."""
    return str(case.inputs.get("query", ""))


register_task("echo", _echo_task)
