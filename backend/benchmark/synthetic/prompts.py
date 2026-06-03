"""Prompt templates for synthetic SGLB generation."""
from __future__ import annotations

import json
from dataclasses import dataclass

from benchmark.synthetic.taxonomy import PROMPT_VERSION, TaxonomyCell


@dataclass(frozen=True)
class RenderedPrompt:
    messages: list[dict[str, str]]
    max_tokens: int
    prompt_version: str = PROMPT_VERSION


def _variant_instruction(variant: str) -> str:
    if variant == "adversarial":
        return (
            "Include realistic ambiguity, drafting friction, OCR-like spacing, or legalese that makes the "
            "case harder, while preserving the exact target label."
        )
    if variant == "negative":
        return (
            "Include false-positive bait and nearby benign facts, but do not introduce labels beyond the "
            "explicit target label payload."
        )
    return "Use clear, realistic Singapore legal drafting."


def render_prompt(cell: TaxonomyCell) -> RenderedPrompt:
    label_payload = json.dumps(cell.label, sort_keys=True)
    params_payload = json.dumps(cell.params, sort_keys=True)
    system = (
        "You generate fictional Singapore legal benchmark inputs. All names, entities, facts, "
        "identifiers, and transactions must be fictional. Return only the requested body text; "
        "do not include labels, analysis, markdown fences, or commentary."
    )

    if cell.task == "sglb_08":
        user = (
            "Generate one contract clause for SGLB-08 Clause-Tone.\n"
            f"Gold label payload, fixed by instruction: {label_payload}\n"
            f"Prompt parameters: {params_payload}\n"
            f"Variant instruction: {_variant_instruction(cell.variant)}\n"
            "Return only the clause text, 120-220 words."
        )
        return RenderedPrompt(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=700)

    if cell.task == "sglb_12":
        user = (
            "Generate one compound Singapore legal fact pattern for SGLB-12 Multi-Issue-Spotting.\n"
            f"Gold issue labels, fixed by instruction: {label_payload}\n"
            f"Prompt parameters: {params_payload}\n"
            f"Variant instruction: {_variant_instruction(cell.variant)}\n"
            "Return only the scenario text, 400-800 tokens. Every listed issue must be triggered once; "
            "no additional legal issue labels should be triggered."
        )
        return RenderedPrompt(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=1400)

    if cell.task == "sglb_15":
        user = (
            "Generate one Singapore drafting brief for SGLB-15 Draft-Constraint-Sat.\n"
            f"Gold constraint payload, fixed by instruction: {label_payload}\n"
            f"Prompt parameters: {params_payload}\n"
            f"Variant instruction: {_variant_instruction(cell.variant)}\n"
            "Return only the drafting brief given to the evaluated model, 120-240 words. "
            "Do not draft the final document."
        )
        return RenderedPrompt(messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=700)

    raise ValueError(f"unsupported synthetic task: {cell.task}")
