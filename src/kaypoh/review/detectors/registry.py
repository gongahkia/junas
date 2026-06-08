from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DetectorContext:
    text: str
    packs: Sequence[Any]
    jurisdiction: str
    legal_basis: str
    document_type: str = "generic"
    defined_terms: frozenset[str] = frozenset()


DetectorFn = Callable[[DetectorContext, int], list[Any]]


@dataclass(frozen=True)
class RegisteredDetector:
    name: str
    family: str
    detect: DetectorFn


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: list[RegisteredDetector] = []
        self._names: set[str] = set()

    @property
    def detectors(self) -> tuple[RegisteredDetector, ...]:
        return tuple(self._detectors)

    def names(self) -> tuple[str, ...]:
        return tuple(detector.name for detector in self._detectors)

    def register(self, *, name: str, family: str, detect: DetectorFn) -> None:
        if not name:
            raise ValueError("detector name must be non-empty")
        if name in self._names:
            raise ValueError(f"duplicate detector name: {name}")
        self._detectors.append(RegisteredDetector(name=name, family=family, detect=detect))
        self._names.add(name)

    def run(self, context: DetectorContext, *, idx_start: int = 0) -> list[Any]:
        findings: list[Any] = []
        for detector in self._detectors:
            produced = detector.detect(context, idx_start + len(findings))
            if not isinstance(produced, list):
                raise TypeError(f"detector {detector.name} returned {type(produced).__name__}, expected list")
            findings.extend(produced)
        return findings
