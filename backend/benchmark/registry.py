"""Task registry.

A ``task`` is an async callable ``(case) -> str`` that runs the workflow
under evaluation on a case. Tasks register themselves with their string
name; the CLI looks them up.

For SG-LegalBench v0.2, tasks are stubs until #31 wires the eval CLI.
The registry shape is here so issues #50–#57 can register their tasks
in-place when they ship.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from benchmark.schema import Case

TaskRunner = Callable[[Case], Awaitable[str]]

TASKS: dict[str, TaskRunner] = {}


def register_task(name: str, runner: TaskRunner) -> None:
    """Register a task runner by name. Re-registration overwrites."""
    TASKS[name] = runner


async def _echo_task(case: Case) -> str:
    """Trivial smoke task. Returns the ``query`` input verbatim."""
    return str(case.inputs.get("query", ""))


register_task("echo", _echo_task)
