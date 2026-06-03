"""SGLB-08 synthetic tone taxonomy loader."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TAXONOMY_PATH = Path(__file__).resolve().with_name("sglb_08_tones.yaml")
REQUIRED_TONES = ("standard", "aggressive", "balanced", "protective")


@dataclass(frozen=True)
class ToneDefinition:
    id: str
    description: str
    generation_guidance: str

    def as_prompt_context(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "generation_guidance": self.generation_guidance,
        }


@dataclass(frozen=True)
class ToneTaxonomy:
    version: str
    tones: tuple[ToneDefinition, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(tone.id for tone in self.tones)

    @property
    def id_set(self) -> set[str]:
        return set(self.ids)

    def by_id(self) -> dict[str, ToneDefinition]:
        return {tone.id: tone for tone in self.tones}

    def require_valid(self, tone_id: str) -> ToneDefinition:
        by_id = self.by_id()
        if tone_id not in by_id:
            raise ValueError(f"SGLB-08 unknown tone: {tone_id}")
        return by_id[tone_id]


@lru_cache(maxsize=1)
def load_tone_taxonomy(path: Path = TAXONOMY_PATH) -> ToneTaxonomy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tones = []
    for item in raw.get("tones", []):
        tones.append(
            ToneDefinition(
                id=str(item["id"]),
                description=str(item.get("description") or ""),
                generation_guidance=str(item.get("generation_guidance") or ""),
            )
        )
    taxonomy = ToneTaxonomy(version=str(raw.get("version") or ""), tones=tuple(tones))
    _validate_taxonomy(taxonomy)
    return taxonomy


def _validate_taxonomy(taxonomy: ToneTaxonomy) -> None:
    if not taxonomy.version:
        raise ValueError("SGLB-08 tone taxonomy version is required")
    duplicates = _duplicates(taxonomy.ids)
    if duplicates:
        raise ValueError(f"SGLB-08 duplicate tone ids: {duplicates}")
    if taxonomy.ids != REQUIRED_TONES:
        raise ValueError(f"SGLB-08 tone taxonomy must define tones in order: {list(REQUIRED_TONES)}")
    for tone in taxonomy.tones:
        if not tone.description:
            raise ValueError(f"SGLB-08 tone {tone.id} must have a description")
        if not tone.generation_guidance:
            raise ValueError(f"SGLB-08 tone {tone.id} must have generation guidance")


def _duplicates(items: tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)
