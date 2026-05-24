"""local_distilled adjudicator backend (item 29 step d).

A small wrapper that loads the LoRA-adapted student and serves verdicts via the
same `adjudicate()` interface `LocalLLMAdjudicator` exposes. The architecture
explicitly says "no runtime contract changes" — so this module satisfies the
contract from outside rather than mutating LocalLLMAdjudicator itself.

To activate at runtime: set `KAYPOH_LLM_PROVIDER=local_distilled` and provide
`KAYPOH_LLM_DISTILLED_ADAPTER_PATH` pointing at the LoRA adapter dir. The
LocalLLMAdjudicator branch in `inference.py` short-circuits to this builder
when those are set.

Heavy ML imports (torch / transformers / peft) are deferred to `_load_model()`
so importing this module alone is free.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from training.distillation.prompts import (
    SYSTEM_PROMPT_RAW_TEXT,
    SYSTEM_PROMPT_STRUCTURED_TOKENS,
    build_user_content_raw_text,
    build_user_content_structured_tokens,
)


_ADJUDICATION_DEFAULT = {
    "status": "disabled",
    "provider": "local_distilled",
    "model": "",
    "risk_label": None,
    "public_status": "not_checked",
    "confidence": 0.0,
    "materiality_reason": "",
    "matched_public_sources": [],
    "unverified_claims": [],
    "review_recommendation": "",
}


def _coerce_json_from_completion(completion_text: str) -> dict[str, Any]:
    """The student may emit prose around the JSON. Find the first {...} blob and
    parse it; fall back to an empty dict so the caller normalises."""
    # find the outermost JSON object via a forgiving heuristic — the model is
    # trained on canonical JSON so this almost always succeeds first try.
    try:
        return json.loads(completion_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", completion_text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


class LocalDistilledAdjudicator:
    """Drop-in replacement for LocalLLMAdjudicator backed by a LoRA-adapted base.

    `model` and `tokenizer` are loaded once on first call and reused across
    invocations. They are NOT shared across instances; one adjudicator instance per
    process is the intended pattern.
    """

    def __init__(
        self,
        *,
        adapter_path: Path,
        base_model: str,
        input_mode: str = "raw_text",
        max_new_tokens: int = 256,
        device: str | None = None,
    ):
        self.adapter_path = adapter_path
        self.base_model = base_model
        self.input_mode = input_mode
        self.max_new_tokens = max_new_tokens
        self.device = device  # None means auto-detect inside _load_model
        self._model = None
        self._tokenizer = None

    # --- lazy model loading ---------------------------------------------------

    def _load_model(self):
        if self._model is not None and self._tokenizer is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import PeftModel
        except ImportError as exc:
            raise RuntimeError(
                "local_distilled requires `torch`, `transformers`, `peft`. "
                f"Install with `pip install kaypoh[server,training]`. (missing: {exc})"
            ) from exc

        device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        tokenizer = AutoTokenizer.from_pretrained(str(self.adapter_path), trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            self.base_model,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, str(self.adapter_path))
        model.eval()
        model.to(device)
        self._model = model
        self._tokenizer = tokenizer
        self._device = device

    # --- prompt formatting (must match training shape) ------------------------

    def _build_messages(
        self,
        *,
        text: str,
        current_classification: str,
        findings: list,
        entity_id: str | None,
    ) -> list[dict[str, str]]:
        if self.input_mode == "raw_text":
            return [
                {"role": "system", "content": SYSTEM_PROMPT_RAW_TEXT},
                {"role": "user", "content": build_user_content_raw_text(
                    text=text, current_classification=current_classification,
                )},
            ]
        if self.input_mode == "structured_tokens":
            from kaypoh.workflow.layer8_llm_adjudicator.structured_query import (
                build_structured_query,
            )
            query = build_structured_query(
                text=text,
                findings=list(findings or []),
                entity_id=entity_id,
                current_classification=current_classification,
                public_evidence=None,
            )
            return [
                {"role": "system", "content": SYSTEM_PROMPT_STRUCTURED_TOKENS},
                {"role": "user", "content": build_user_content_structured_tokens(query)},
            ]
        raise ValueError(f"unknown input_mode: {self.input_mode!r}")

    # --- adjudicate (the public contract) -------------------------------------

    def adjudicate(
        self,
        *,
        text: str,
        current_classification: str,
        findings: list | None = None,
        entity_id: str | None = None,
        public_evidence: Any = None,
        lexicon: Any = None,
        model1: Any = None,
        model2: Any = None,
    ) -> dict[str, Any]:
        try:
            self._load_model()
        except RuntimeError as exc:
            return {**_ADJUDICATION_DEFAULT, "review_recommendation": str(exc)}

        import torch  # safe — _load_model would have failed already

        messages = self._build_messages(
            text=text,
            current_classification=current_classification,
            findings=list(findings or []),
            entity_id=entity_id,
        )

        if hasattr(self._tokenizer, "apply_chat_template") and self._tokenizer.chat_template:
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        else:
            prompt = (
                f"<|system|>\n{messages[0]['content']}\n"
                f"<|user|>\n{messages[1]['content']}\n"
                f"<|assistant|>\n"
            )

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._device)
        with torch.no_grad():
            out = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                pad_token_id=self._tokenizer.pad_token_id,
            )
        completion = self._tokenizer.decode(
            out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True,
        )

        raw = _coerce_json_from_completion(completion)
        if not raw:
            return {**_ADJUDICATION_DEFAULT,
                    "model": str(self.adapter_path.name),
                    "review_recommendation": "student emitted non-JSON output"}

        # mirror LocalLLMAdjudicator._normalize_payload normalisation contract so
        # the response is shape-compatible with the runtime ReviewResponse schema.
        risk_label = str(raw.get("risk_label", "") or "").upper()
        if risk_label not in {"SAFE", "LOW_RISK", "HIGH_RISK"}:
            risk_label = ""
        public_status = str(raw.get("public_status", "ambiguous") or "ambiguous").lower()
        if public_status not in {"public", "not_public", "ambiguous", "not_checked"}:
            public_status = "ambiguous"
        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "status": "adjudicated" if risk_label else "error",
            "provider": "local_distilled",
            "model": str(self.adapter_path.name),
            "risk_label": risk_label or None,
            "public_status": public_status,
            "confidence": confidence,
            "materiality_reason": str(raw.get("materiality_reason", "") or ""),
            "matched_public_sources": [str(item) for item in raw.get("matched_public_sources", []) or []],
            "unverified_claims": [str(item) for item in raw.get("unverified_claims", []) or []],
            "review_recommendation": str(raw.get("review_recommendation", "") or ""),
            "input_mode": self.input_mode,
            "output_clamped": False,
        }


def build_local_distilled_adjudicator(
    *,
    adapter_path: Path,
    base_model: str,
    input_mode: str = "raw_text",
) -> LocalDistilledAdjudicator:
    """Convenience constructor used by `eval_against_corpus.py` and the runtime
    LLM-provider branch."""
    return LocalDistilledAdjudicator(
        adapter_path=adapter_path,
        base_model=base_model,
        input_mode=input_mode,
    )
