"""SGLB-15 synthetic constraint-set taxonomy loader."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from api.services.template_service import TEMPLATES
from benchmark.constraints import CONSTRAINTS

TAXONOMY_PATH = Path(__file__).resolve().with_name("sglb_15_constraints.yaml")


@dataclass(frozen=True)
class ConstraintSet:
    id: str
    description: str
    applicable_templates: tuple[str, ...]
    constraints: tuple[dict[str, Any], ...]

    def applies_to(self, template_id: str) -> bool:
        return "*" in self.applicable_templates or template_id in self.applicable_templates

    def constraint_payload(self) -> list[dict[str, Any]]:
        return copy.deepcopy(list(self.constraints))

    def as_prompt_context(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "applicable_templates": list(self.applicable_templates),
            "constraint_kinds": [str(item["kind"]) for item in self.constraints],
        }


@dataclass(frozen=True)
class ConstraintTaxonomy:
    version: str
    sets: tuple[ConstraintSet, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.sets)

    def by_id(self) -> dict[str, ConstraintSet]:
        return {item.id: item for item in self.sets}

    def applicable_sets(self, template_id: str) -> tuple[ConstraintSet, ...]:
        return tuple(item for item in self.sets if item.applies_to(template_id))

    def require_valid_set_for_template(self, set_id: str, template_id: str) -> ConstraintSet:
        by_id = self.by_id()
        if set_id not in by_id:
            raise ValueError(f"SGLB-15 unknown constraint set: {set_id}")
        item = by_id[set_id]
        if not item.applies_to(template_id):
            raise ValueError(f"SGLB-15 constraint set {set_id!r} is not applicable to template {template_id!r}")
        return item


@lru_cache(maxsize=1)
def load_constraint_taxonomy(path: Path = TAXONOMY_PATH) -> ConstraintTaxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sets: list[ConstraintSet] = []
    for item in raw.get("constraint_sets", []):
        sets.append(
            ConstraintSet(
                id=str(item["id"]),
                description=str(item.get("description") or ""),
                applicable_templates=tuple(str(t) for t in item.get("applicable_templates", []) or []),
                constraints=tuple(copy.deepcopy(item.get("constraints", []) or [])),
            )
        )
    taxonomy = ConstraintTaxonomy(version=str(raw.get("version") or ""), sets=tuple(sets))
    _validate_taxonomy(taxonomy)
    return taxonomy


def _validate_taxonomy(taxonomy: ConstraintTaxonomy) -> None:
    if not taxonomy.version:
        raise ValueError("SGLB-15 constraint taxonomy version is required")
    if not taxonomy.sets:
        raise ValueError("SGLB-15 constraint taxonomy must define at least one set")
    duplicates = _duplicates(taxonomy.ids)
    if duplicates:
        raise ValueError(f"SGLB-15 duplicate constraint set ids: {duplicates}")

    template_ids = {template.id for template in TEMPLATES}
    covered_templates: set[str] = set()
    for item in taxonomy.sets:
        if not item.description:
            raise ValueError(f"SGLB-15 constraint set {item.id} must have a description")
        if not item.applicable_templates:
            raise ValueError(f"SGLB-15 constraint set {item.id} must declare applicable templates")
        unknown_templates = sorted(set(item.applicable_templates) - template_ids - {"*"})
        if unknown_templates:
            raise ValueError(f"SGLB-15 constraint set {item.id} references unknown templates: {unknown_templates}")
        if "*" in item.applicable_templates:
            covered_templates.update(template_ids)
        else:
            covered_templates.update(item.applicable_templates)
        for constraint in item.constraints:
            kind = str(constraint.get("kind") or "")
            if kind not in CONSTRAINTS:
                raise ValueError(f"SGLB-15 constraint set {item.id} references unknown constraint kind: {kind}")
            if not str(constraint.get("id") or ""):
                raise ValueError(f"SGLB-15 constraint set {item.id} contains a constraint without id")
            if "params" not in constraint:
                raise ValueError(f"SGLB-15 constraint {constraint.get('id')} in {item.id} is missing params")

    missing_template_coverage = sorted(template_ids - covered_templates)
    if missing_template_coverage:
        raise ValueError(f"SGLB-15 templates lack applicable constraint sets: {missing_template_coverage}")


def _duplicates(items: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)
