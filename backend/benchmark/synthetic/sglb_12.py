"""SGLB-12 synthetic issue taxonomy and composition loaders."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TAXONOMY_PATH = Path(__file__).resolve().with_name("sglb_12_taxonomy.yaml")
COMPOSITIONS_PATH = Path(__file__).resolve().with_name("sglb_12_compositions.yaml")


@dataclass(frozen=True)
class IssueDefinition:
    code: str
    source: str
    source_ref: str
    trigger: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def as_prompt_context(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": self.source,
            "source_ref": self.source_ref,
            "trigger": self.trigger,
        }


@dataclass(frozen=True)
class IssueTaxonomy:
    version: str
    issues: tuple[IssueDefinition, ...]

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    @property
    def code_set(self) -> set[str]:
        return set(self.codes)

    @property
    def alias_map(self) -> dict[str, str]:
        return {alias: issue.code for issue in self.issues for alias in issue.aliases}

    def canonicalize(self, label: str) -> str:
        return self.alias_map.get(label, label)

    def require_valid(self, labels: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        canonical = tuple(self.canonicalize(str(label)) for label in labels)
        invalid = sorted(set(canonical) - self.code_set)
        if invalid:
            raise ValueError(f"SGLB-12 unknown issue labels: {invalid}")
        return canonical

    def by_code(self) -> dict[str, IssueDefinition]:
        return {issue.code: issue for issue in self.issues}


@dataclass(frozen=True)
class IssueComposition:
    id: str
    description: str
    labels: tuple[str, ...]

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(sorted({label.split(".", 1)[0] for label in self.labels}))

    def as_prompt_context(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "labels": list(self.labels),
            "sources": list(self.sources),
            "issues": issue_prompt_context(self.labels),
        }


@dataclass(frozen=True)
class IssueCompositionMatrix:
    version: str
    compositions: tuple[IssueComposition, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.compositions)

    def by_id(self) -> dict[str, IssueComposition]:
        return {item.id: item for item in self.compositions}

    def require_valid(self, composition_id: str) -> IssueComposition:
        by_id = self.by_id()
        if composition_id not in by_id:
            raise ValueError(f"SGLB-12 unknown issue composition: {composition_id}")
        return by_id[composition_id]


@lru_cache(maxsize=1)
def load_issue_taxonomy(path: Path = TAXONOMY_PATH) -> IssueTaxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    issues = []
    for item in raw.get("issues", []):
        issues.append(
            IssueDefinition(
                code=str(item["code"]),
                source=str(item["source"]),
                source_ref=str(item["source_ref"]),
                trigger=str(item["trigger"]),
                aliases=tuple(str(alias) for alias in item.get("aliases", []) or []),
            )
        )
    taxonomy = IssueTaxonomy(version=str(raw.get("version") or ""), issues=tuple(issues))
    _validate_taxonomy(taxonomy)
    return taxonomy


@lru_cache(maxsize=1)
def load_issue_compositions(path: Path = COMPOSITIONS_PATH) -> IssueCompositionMatrix:
    issue_taxonomy = load_issue_taxonomy()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    compositions = []
    for item in raw.get("compositions", []):
        labels = issue_taxonomy.require_valid(tuple(str(label) for label in item.get("labels", []) or []))
        compositions.append(
            IssueComposition(
                id=str(item["id"]),
                description=str(item.get("description") or ""),
                labels=labels,
            )
        )
    matrix = IssueCompositionMatrix(version=str(raw.get("version") or ""), compositions=tuple(compositions))
    _validate_compositions(matrix)
    return matrix


def _validate_taxonomy(taxonomy: IssueTaxonomy) -> None:
    if not taxonomy.version:
        raise ValueError("SGLB-12 taxonomy version is required")
    if len(taxonomy.issues) < 25:
        raise ValueError("SGLB-12 taxonomy must contain at least 25 issues")
    duplicates = _duplicates(taxonomy.codes)
    if duplicates:
        raise ValueError(f"SGLB-12 duplicate issue codes: {duplicates}")
    alias_duplicates = _duplicates(tuple(taxonomy.alias_map))
    if alias_duplicates:
        raise ValueError(f"SGLB-12 duplicate issue aliases: {alias_duplicates}")
    invalid_sources = sorted({issue.source for issue in taxonomy.issues} - {"pdpa", "ea", "roc"})
    if invalid_sources:
        raise ValueError(f"SGLB-12 invalid sources: {invalid_sources}")


def _validate_compositions(matrix: IssueCompositionMatrix) -> None:
    if not matrix.version:
        raise ValueError("SGLB-12 composition matrix version is required")
    if len(matrix.compositions) < 10:
        raise ValueError("SGLB-12 composition matrix must contain at least 10 compositions")
    duplicates = _duplicates(matrix.ids)
    if duplicates:
        raise ValueError(f"SGLB-12 duplicate issue composition ids: {duplicates}")
    covered_sources: set[str] = set()
    for composition in matrix.compositions:
        if not composition.description:
            raise ValueError(f"SGLB-12 composition {composition.id} must have a description")
        if len(composition.labels) < 2:
            raise ValueError(f"SGLB-12 composition {composition.id} must contain at least two labels")
        if len(composition.labels) > 4:
            raise ValueError(f"SGLB-12 composition {composition.id} must not exceed four labels")
        duplicate_labels = _duplicates(composition.labels)
        if duplicate_labels:
            raise ValueError(f"SGLB-12 composition {composition.id} contains duplicate labels: {duplicate_labels}")
        if len(composition.sources) < 2:
            raise ValueError(f"SGLB-12 composition {composition.id} must mix at least two source families")
        covered_sources.update(composition.sources)
    if covered_sources != {"pdpa", "ea", "roc"}:
        raise ValueError(f"SGLB-12 composition matrix must cover pdpa, ea, and roc sources: {sorted(covered_sources)}")


def _duplicates(items: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def issue_prompt_context(labels: list[str] | tuple[str, ...]) -> list[dict[str, Any]]:
    taxonomy = load_issue_taxonomy()
    canonical = taxonomy.require_valid(labels)
    by_code = taxonomy.by_code()
    return [by_code[label].as_prompt_context() for label in canonical]
