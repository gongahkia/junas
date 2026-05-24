"""Shared prompt templates for the distillation pipeline.

Both the teacher (cloud LLM) and the student (local LoRA-tuned model) must see the
SAME prompt shape for the distillation to be coherent. Anything that drifts between
the two paths breaks the (input -> teacher_output) -> (input -> student_output)
correspondence the trainer relies on.

Two shapes are supported because `LocalLLMAdjudicator` itself supports two input modes:

- raw_text: ships the document body + sanitised runtime context. Used when the tenant
  is comfortable with the model seeing raw text (audit_grade default).
- structured_tokens: ships only abstract tokens + SHA-256 hashes. Used for regulated
  tenants. The student distilled from this mode can serve regulated traffic without
  ever seeing raw text in training or inference.

Pick ONE mode per training run. Mixing modes in a single distilled checkpoint produces
a student that sees inconsistent input distributions and degrades accuracy.
"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT_RAW_TEXT = (
    "You are a local-only compliance adjudicator for MNPI triage. "
    "Classify the document using the local text and public evidence. "
    "Return only compact JSON with keys: risk_label, public_status, confidence, "
    "materiality_reason, matched_public_sources, unverified_claims, review_recommendation. "
    "risk_label must be SAFE, LOW_RISK, or HIGH_RISK. "
    "public_status must be public, not_public, ambiguous, or not_checked."
)

SYSTEM_PROMPT_STRUCTURED_TOKENS = (
    "You are a privacy-hardened compliance adjudicator. You do NOT receive "
    "the document text; you receive only structured tokens describing the "
    "deterministic findings and a SHA-256 hash of the document body. "
    "Reason about materiality and public-status from the token shape alone. "
    "Return only compact JSON with keys: risk_label, public_status, confidence, "
    "materiality_reason, matched_public_sources, unverified_claims, review_recommendation. "
    "risk_label must be SAFE, LOW_RISK, or HIGH_RISK. "
    "public_status must be public, not_public, ambiguous, or not_checked."
)


def build_user_content_raw_text(*, text: str, current_classification: str) -> str:
    """User-turn content for raw_text mode. Symmetric with what
    LocalLLMAdjudicator._build_messages emits at runtime, so the student trains on
    the same shape it will see at inference."""
    return json.dumps(
        {
            "document_text": text,
            "runtime_context": {
                "current_classification": current_classification,
                # other context fields are optional at training time; the runtime path
                # fills these from lexicon/model1/model2 layer outputs which are not
                # available during distillation. defaulting them keeps the shape
                # identical, just with empty payloads.
                "lexicon": {},
                "model1": {},
                "model2": {},
                "public_evidence": {},
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def build_user_content_structured_tokens(structured_query: dict[str, Any]) -> str:
    """User-turn content for structured_tokens mode. The structured query is built
    by `kaypoh.workflow.layer8_llm_adjudicator.structured_query.build_structured_query`
    at runtime; distillation builds the same query and trains the student to emit
    the closed-vocabulary response."""
    return json.dumps(structured_query, ensure_ascii=False, sort_keys=True)


def build_messages(
    *,
    input_mode: str,
    text: str,
    current_classification: str,
    structured_query: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Build a (system, user) message pair for the given input mode. Used by both
    teacher collection and student inference so the wire shape is byte-identical."""
    if input_mode == "raw_text":
        return [
            {"role": "system", "content": SYSTEM_PROMPT_RAW_TEXT},
            {"role": "user", "content": build_user_content_raw_text(
                text=text, current_classification=current_classification,
            )},
        ]
    if input_mode == "structured_tokens":
        if structured_query is None:
            raise ValueError("structured_tokens mode requires a structured_query")
        return [
            {"role": "system", "content": SYSTEM_PROMPT_STRUCTURED_TOKENS},
            {"role": "user", "content": build_user_content_structured_tokens(structured_query)},
        ]
    raise ValueError(f"unknown input_mode: {input_mode!r}")


# Target serialisation for trainer supervision. The teacher's JSON response is the
# target; we sort keys + drop nulls so two runs with the same teacher output produce
# byte-identical training targets.
def build_target(teacher_verdict: dict[str, Any]) -> str:
    canonical = {
        "risk_label": teacher_verdict.get("risk_label") or "SAFE",
        "public_status": teacher_verdict.get("public_status") or "ambiguous",
        "confidence": float(teacher_verdict.get("confidence") or 0.0),
        "materiality_reason": teacher_verdict.get("materiality_reason") or "",
        "matched_public_sources": list(teacher_verdict.get("matched_public_sources") or []),
        "unverified_claims": list(teacher_verdict.get("unverified_claims") or []),
        "review_recommendation": teacher_verdict.get("review_recommendation") or "",
    }
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True)
