"""Evaluator implementations and registry.

Evaluators are tagged with a ``strength`` tier. Per ``docs/coverage-matrix.md``
§4.2, the strong tier is acceptable for publication; weak evaluators are
permitted for migration and smoke-testing but flagged when used in
publication mode (``--strict`` CLI flag in ``benchmark.cli``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from api.services.sal_citation import validate_citation


class EvaluatorStrength(str, Enum):
    """Tier for the strength of an evaluator's signal.

    - ``strong``: rule-based, deterministic, regex/AST/grammar checks; or
      multi-judge ensemble with disclosed agreement metric.
    - ``weak``: keyword-presence, length thresholds, "any citation marker"
      patterns. Acceptable for smoke tests; flagged in publication mode.
    """

    STRONG = "strong"
    WEAK = "weak"


@dataclass(frozen=True)
class EvaluatorContext:
    """Context passed to an evaluator's ``evaluate`` call."""

    case_name: str
    inputs: dict[str, Any]
    expected_output: dict[str, Any] | None
    metadata: dict[str, Any]
    output: str


@dataclass(frozen=True)
class EvaluationResult:
    score: float
    detail: dict[str, Any] = field(default_factory=dict)


class Evaluator:
    """Base class for evaluators.

    Subclasses set ``name`` and ``strength``, and implement ``evaluate``.
    """

    name: str = ""
    strength: EvaluatorStrength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        raise NotImplementedError


# === Strong evaluators ===


class ExactMatch(Evaluator):
    """Strict equality against ``expected_output["span"]`` after normalisation."""

    name = "exact_match"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        target = (ctx.expected_output or {}).get("span", "")
        score = 1.0 if (ctx.output or "").strip() == str(target).strip() else 0.0
        return EvaluationResult(score=score)


class MultiLabelF1(Evaluator):
    """Multi-label F1 between output labels and expected labels.

    Expects ``expected_output["labels"]`` (list of strings) and an output
    that parses to a list (JSON or comma-separated).
    """

    name = "multi_label_f1"
    strength = EvaluatorStrength.STRONG

    @staticmethod
    def _parse_labels(text: str) -> set[str]:
        text = (text or "").strip()
        if text.startswith("["):
            import json

            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return {str(item).strip().lower() for item in parsed if str(item).strip()}
            except json.JSONDecodeError:
                pass
        return {part.strip().lower() for part in text.split(",") if part.strip()}

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected = {
            str(item).strip().lower()
            for item in (ctx.expected_output or {}).get("labels", [])
            if str(item).strip()
        }
        predicted = self._parse_labels(ctx.output)
        if not expected and not predicted:
            return EvaluationResult(score=1.0, detail={"precision": 1.0, "recall": 1.0})
        tp = len(expected & predicted)
        precision = tp / len(predicted) if predicted else 0.0
        recall = tp / len(expected) if expected else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        return EvaluationResult(
            score=f1,
            detail={"precision": precision, "recall": recall, "tp": tp},
        )


# --- SAL citation evaluators ---

_CITATION_TOKEN_PATTERNS = [
    re.compile(r"\[\d{4}\]\s+SG[A-Z]+\s+\d+"),  # neutral case
    re.compile(r"\[\d{4}\]\s+\d+\s+SLR\(R\)\s+\d+"),  # SLR(R)
    re.compile(r"\[\d{4}\]\s+\d+\s+SLR\s+\d+"),  # SLR
    re.compile(r"[A-Z][^()]*?\(Cap\.\s*\d+[A-Z]?(?:,\s*\d{4}\s+Rev\s+Ed)?\)"),  # statute Cap.
    re.compile(r"\bs\s*\.?\s*\d+[A-Z]?(?:\s+of\s+the\s+[A-Z][^.]*?Act)?"),  # statute section
]


def _extract_citation_strings(text: str) -> list[str]:
    cits: list[str] = []
    for pat in _CITATION_TOKEN_PATTERNS:
        cits.extend(match.group(0) for match in pat.finditer(text or ""))
    return cits


class CitationFormatValid(Evaluator):
    """Fraction of citations in output that pass SAL grammar validation.

    Uses ``api.services.sal_citation.validate_citation``. Returns 1.0 when
    no citations are emitted (vacuously valid; pair with
    ``CitesSgStatute`` if you want to enforce presence).
    """

    name = "citation_format_valid"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        cits = _extract_citation_strings(ctx.output)
        if not cits:
            return EvaluationResult(score=1.0, detail={"total": 0, "valid": 0})
        valid = sum(1 for c in cits if validate_citation(c).valid)
        return EvaluationResult(
            score=valid / len(cits),
            detail={"total": len(cits), "valid": valid},
        )


class CitesSgStatute(Evaluator):
    """At least one statute citation present in output (Cap. form or section ref)."""

    name = "cites_sg_statute"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        statute_patterns = (
            re.compile(r"[A-Z][^()]*?\(Cap\.\s*\d+[A-Z]?(?:,\s*\d{4}\s+Rev\s+Ed)?\)"),
            re.compile(r"\bs\s*\.?\s*\d+[A-Z]?\s+of\s+the\s+[A-Z][^.]*?Act"),
        )
        has = any(p.search(ctx.output or "") for p in statute_patterns)
        return EvaluationResult(score=1.0 if has else 0.0)


class UsesSalStyle(Evaluator):
    """Sequence-level: does the raw output use Ibid/Id where a SAL-style
    repeat reference would require it?

    Detection:
    1. Extract full neutral-form case citation tokens in order.
    2. Count consecutive duplicates by exact token equality.
    3. Count Ibid / Id short-form tokens in the raw output text.
    4. Score = min(1, short_forms / consecutive_duplicates) when duplicates
       exist; 1.0 when no duplicate triggers exist or fewer than two cites.

    This rewards short-form usage proportional to the number of repeat
    references that ought to have been collapsed.
    """

    name = "uses_sal_style"
    strength = EvaluatorStrength.STRONG

    _IBID_RE = re.compile(r"\bIbid\b")
    _ID_RE = re.compile(r"\bId(?:,|\s+at\b|\.)")

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        text = ctx.output or ""
        matches = list(re.finditer(r"\[\d{4}\]\s+SG[A-Z]+\s+\d+", text))
        if len(matches) < 2:
            return EvaluationResult(score=1.0, detail={"reason": "fewer than 2 case citations"})

        consecutive_duplicates = 0
        for i in range(1, len(matches)):
            if matches[i].group(0) == matches[i - 1].group(0):
                consecutive_duplicates += 1

        if consecutive_duplicates == 0:
            return EvaluationResult(score=1.0, detail={"consecutive_duplicates": 0})

        short_forms = len(self._IBID_RE.findall(text)) + len(self._ID_RE.findall(text))
        score = min(1.0, short_forms / consecutive_duplicates)
        return EvaluationResult(
            score=score,
            detail={
                "consecutive_duplicates": consecutive_duplicates,
                "short_forms_in_text": short_forms,
            },
        )


class CompliancePresent(Evaluator):
    """Detects whether the output references at least one of a required set of
    compliance regimes for the case (PDPA / Employment Act / Rules of Court 2021).

    Expects ``expected_output["required_regimes"]`` as a list of regime tags.
    Returns the fraction of required regimes referenced. Useful for
    multi-source review tasks.
    """

    name = "compliance_present"
    strength = EvaluatorStrength.STRONG

    _PATTERNS: dict[str, re.Pattern[str]] = {
        "pdpa": re.compile(r"\bPDPA\b|Personal Data Protection Act", re.IGNORECASE),
        "employment_act": re.compile(r"Employment Act", re.IGNORECASE),
        "roc_2021": re.compile(r"Rules of Court 2021|ROC 2021|\bO\.\s*\d+,\s*r\.\s*\d+", re.IGNORECASE),
    }

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        required = (ctx.expected_output or {}).get("required_regimes", [])
        if not required:
            return EvaluationResult(score=1.0, detail={"reason": "no regimes required"})
        hits = sum(
            1
            for regime in required
            if (pat := self._PATTERNS.get(regime)) and pat.search(ctx.output or "")
        )
        return EvaluationResult(
            score=hits / len(required),
            detail={"required": list(required), "hits": hits},
        )


class CitationHallucinationF1(Evaluator):
    """SGLB-11 scorer.

    Inputs:
    - ``case.expected_output["fakes"]``: list of citation strings that
      are the gold fabricated set.
    - ``case.metadata["citation_index"]``: per-citation provenance
      (used to stratify F1 by perturbation type when present).
    - Model output: JSON list of citation strings the model believes
      are fabricated.

    Score (primary): F1 over the citation set (predicted-fake vs
    gold-fake). Detail includes per-perturbation-class P/R/F1 when
    provenance is available.
    """

    name = "citation_hallucination_f1"
    strength = EvaluatorStrength.STRONG

    @staticmethod
    def _parse_predictions(output: str) -> set[str]:
        import json

        text = (output or "").strip()
        if not text:
            return set()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return {str(item).strip() for item in parsed if str(item).strip()}
        except json.JSONDecodeError:
            pass
        return {part.strip() for part in text.split(",") if part.strip()}

    @staticmethod
    def _normalise(s: str) -> str:
        return " ".join(s.split()).rstrip(".").lower()

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected_fakes_raw = (ctx.expected_output or {}).get("fakes", []) or []
        expected_fakes: set[str] = {self._normalise(s) for s in expected_fakes_raw}
        predicted_fakes_raw = self._parse_predictions(ctx.output)
        predicted_fakes: set[str] = {self._normalise(s) for s in predicted_fakes_raw}

        tp = len(expected_fakes & predicted_fakes)
        precision = tp / len(predicted_fakes) if predicted_fakes else 0.0
        recall = tp / len(expected_fakes) if expected_fakes else 0.0
        if not expected_fakes and not predicted_fakes:
            f1 = 1.0
        elif precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)

        # Per-perturbation breakdown via citation_index provenance.
        per_perturbation: dict[str, dict[str, float]] = {}
        index = ctx.metadata.get("citation_index") or []
        if index:
            buckets: dict[str, dict[str, set[str]]] = {}
            for entry in index:
                if not entry.get("is_fake"):
                    continue
                ptype = entry.get("perturbation") or "unknown"
                buckets.setdefault(ptype, {"gold": set(), "predicted": set()})
                buckets[ptype]["gold"].add(self._normalise(entry["citation"]))

            citation_to_ptype = {
                self._normalise(entry["citation"]): (entry.get("perturbation") or "unknown")
                for entry in index
                if entry.get("is_fake")
            }
            real_in_passage = {
                self._normalise(entry["citation"])
                for entry in index
                if not entry.get("is_fake")
            }
            for pred in predicted_fakes:
                if pred in citation_to_ptype:
                    ptype = citation_to_ptype[pred]
                    buckets.setdefault(ptype, {"gold": set(), "predicted": set()})
                    buckets[ptype]["predicted"].add(pred)
                elif pred in real_in_passage:
                    buckets.setdefault("false_positive_on_real", {"gold": set(), "predicted": set()})
                    buckets["false_positive_on_real"]["predicted"].add(pred)

            for ptype, sets in buckets.items():
                gold = sets["gold"]
                pred = sets["predicted"]
                tp_p = len(gold & pred)
                p_p = tp_p / len(pred) if pred else 0.0
                r_p = tp_p / len(gold) if gold else 0.0
                if not gold and not pred:
                    f1_p = 1.0
                elif p_p + r_p == 0:
                    f1_p = 0.0
                else:
                    f1_p = 2 * p_p * r_p / (p_p + r_p)
                per_perturbation[ptype] = {
                    "precision": p_p,
                    "recall": r_p,
                    "f1": f1_p,
                    "tp": float(tp_p),
                    "gold": float(len(gold)),
                    "predicted": float(len(pred)),
                }

        return EvaluationResult(
            score=f1,
            detail={
                "precision": precision,
                "recall": recall,
                "tp": tp,
                "gold_count": len(expected_fakes),
                "predicted_count": len(predicted_fakes),
                "per_perturbation": per_perturbation,
            },
        )


# --- SGLB-06 ROC-2021 ---


def _normalise_order_rule(value: str) -> str:
    """Normalise an Order/Rule reference to ``O. <n>, r. <m>``.

    Accepts: ``O 9 r 1`` / ``O.9, r.1`` / ``Order 9, Rule 1`` /
    ``O. 9, r. 1`` → canonical ``O. 9, r. 1``.
    """
    s = (value or "").strip()
    if not s:
        return ""
    s = re.sub(r"\bOrder\s+", "O ", s, flags=re.IGNORECASE)
    s = re.sub(r"\bRule\s+", "r ", s, flags=re.IGNORECASE)
    s = re.sub(r"\bO\s*\.?\s*", "O ", s, flags=re.IGNORECASE)
    s = re.sub(r"\br\s*\.?\s*", "r ", s, flags=re.IGNORECASE)
    m = re.search(r"O\s*(\d+[A-Z]?)\s*[,;]?\s*r\s*(\d+[A-Z]?)", s, flags=re.IGNORECASE)
    if not m:
        return ""
    return f"O. {m.group(1)}, r. {m.group(2)}"


class OrderRuleLabelF1(Evaluator):
    """SGLB-06 multi-label F1 over normalised ``O. N, r. M`` labels.

    Output may be a JSON list of label strings or a comma-separated list;
    each label is normalised before comparison.
    """

    name = "order_rule_label_f1"
    strength = EvaluatorStrength.STRONG

    @staticmethod
    def _parse(output: str) -> set[str]:
        text = (output or "").strip()
        if not text:
            return set()
        import json

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                raw = [str(item) for item in parsed if str(item).strip()]
            else:
                raw = [text]
        except json.JSONDecodeError:
            raw = [part.strip() for part in text.split(",") if part.strip()]
        normalised = {_normalise_order_rule(item) for item in raw}
        return {item for item in normalised if item}

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected = {
            _normalise_order_rule(str(item))
            for item in (ctx.expected_output or {}).get("labels", [])
        }
        expected.discard("")
        predicted = self._parse(ctx.output)
        if not expected and not predicted:
            return EvaluationResult(score=1.0, detail={"precision": 1.0, "recall": 1.0})
        tp = len(expected & predicted)
        precision = tp / len(predicted) if predicted else 0.0
        recall = tp / len(expected) if expected else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        return EvaluationResult(
            score=f1,
            detail={"precision": precision, "recall": recall, "tp": tp},
        )


class OrderRuleTop3(Evaluator):
    """SGLB-06 top-3 accuracy: any gold label appears in the model's
    first 3 emitted labels (preserves order). For multi-gold cases, score
    is the fraction of gold labels found in the top-3 predictions.
    """

    name = "order_rule_top3"
    strength = EvaluatorStrength.STRONG

    @staticmethod
    def _parse_ordered(output: str) -> list[str]:
        text = (output or "").strip()
        if not text:
            return []
        import json

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                raw = [str(item) for item in parsed if str(item).strip()]
            else:
                raw = [text]
        except json.JSONDecodeError:
            raw = [part.strip() for part in text.split(",") if part.strip()]
        seen: list[str] = []
        for item in raw:
            norm = _normalise_order_rule(item)
            if norm and norm not in seen:
                seen.append(norm)
        return seen

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected = {
            _normalise_order_rule(str(item))
            for item in (ctx.expected_output or {}).get("labels", [])
        }
        expected.discard("")
        predicted_top3 = set(self._parse_ordered(ctx.output)[:3])
        if not expected:
            return EvaluationResult(score=1.0, detail={"reason": "no gold labels"})
        hits = len(expected & predicted_top3)
        return EvaluationResult(
            score=hits / len(expected),
            detail={"top3": list(predicted_top3), "gold": list(expected), "hits": hits},
        )


# --- SGLB-02 Statute-QA ---


def _rouge_l(reference: str, candidate: str) -> float:
    """Sentence-level ROUGE-L F1 over whitespace tokens.

    Avoids the ``rouge-score`` dep — the LCS-based F1 here matches that
    library's behaviour on whitespace-tokenised English to within
    rounding for the inputs we care about (SG statute prose).
    """
    ref_tokens = (reference or "").lower().split()
    cand_tokens = (candidate or "").lower().split()
    if not ref_tokens or not cand_tokens:
        return 0.0
    # LCS length via DP.
    rows = len(ref_tokens) + 1
    cols = len(cand_tokens) + 1
    table = [[0] * cols for _ in range(rows)]
    for i, r in enumerate(ref_tokens, start=1):
        for j, c in enumerate(cand_tokens, start=1):
            if r == c:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    lcs = table[-1][-1]
    if lcs == 0:
        return 0.0
    precision = lcs / len(cand_tokens)
    recall = lcs / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def _normalise_section_citation(value: str) -> str:
    """Normalise a section citation to a canonical comparison string.

    Tolerates the common surface variations:
    - "s 13", "s.13", "section 13", "section 13(2)" → "s 13"
    - "Act 2012" vs "Act, 2012" → ", 2012"
    - "Personal Data Protection Act" trailing whitespace
    """
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\b[Ss]ection\b", "s", text)
    text = re.sub(r"\bs\.\s*", "s ", text)
    text = re.sub(r"\bs\s+", "s ", text)
    text = re.sub(r"\bAct,\s+", "Act ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text.lower()


class Sglb02CitationMatch(Evaluator):
    """SGLB-02 citation scorer.

    Parses the model output as JSON ``{"citation": "...", "answer": "..."}``
    (also accepts a bare citation string), normalises both sides, and
    scores 1.0 on exact match after normalisation.
    """

    name = "sglb_02_citation_match"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected = _normalise_section_citation(
            (ctx.expected_output or {}).get("citation", "")
        )
        if not expected:
            return EvaluationResult(score=0.0, detail={"error": "no expected citation"})
        parsed = _parse_json_object(ctx.output)
        predicted_raw = parsed.get("citation") if parsed else (ctx.output or "")
        predicted = _normalise_section_citation(str(predicted_raw or ""))
        score = 1.0 if expected == predicted else 0.0
        return EvaluationResult(
            score=score,
            detail={"expected": expected, "predicted": predicted},
        )


class RougeLAnswer(Evaluator):
    """ROUGE-L F1 over the model's answer against the gold span.

    Looks for ``answer`` in a JSON object output; falls back to scoring
    the whole output text against the gold span.
    """

    name = "rouge_l_answer"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        gold = str((ctx.expected_output or {}).get("answer_span", "") or "")
        if not gold:
            return EvaluationResult(score=0.0, detail={"error": "no gold answer_span"})
        parsed = _parse_json_object(ctx.output)
        if parsed and "answer" in parsed:
            candidate = str(parsed.get("answer") or "")
        else:
            candidate = ctx.output or ""
        score = _rouge_l(gold, candidate)
        return EvaluationResult(
            score=score,
            detail={"gold_tokens": len(gold.split()), "cand_tokens": len(candidate.split())},
        )


# --- SGLB-01 PDPA-Outcome ---


def _parse_json_object(output: str) -> dict[str, Any]:
    text = (output or "").strip()
    if not text:
        return {}
    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class Sglb01ObligationsF1(Evaluator):
    """SGLB-01 obligation scorer.

    Parses model output as a JSON object with key ``obligations`` (list of
    strings). Compares against ``expected_output["obligations"]``. Returns
    macro-style F1 over the obligation label set (case-insensitive,
    whitespace-collapsed).
    """

    name = "sglb_01_obligations_f1"
    strength = EvaluatorStrength.STRONG

    @staticmethod
    def _normalise(labels: Any) -> set[str]:
        if not isinstance(labels, list):
            return set()
        return {str(item).strip().lower() for item in labels if str(item).strip()}

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected = self._normalise((ctx.expected_output or {}).get("obligations", []))
        parsed = _parse_json_object(ctx.output)
        predicted = self._normalise(parsed.get("obligations", []))
        if not expected and not predicted:
            return EvaluationResult(score=1.0, detail={"precision": 1.0, "recall": 1.0})
        tp = len(expected & predicted)
        precision = tp / len(predicted) if predicted else 0.0
        recall = tp / len(expected) if expected else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        return EvaluationResult(
            score=f1,
            detail={"precision": precision, "recall": recall, "tp": tp},
        )


class PenaltyBandMae(Evaluator):
    """SGLB-01 penalty-band scorer.

    Parses model output as a JSON object with key ``penalty_band`` (one of
    ``none|low|mid|high``). Maps both expected and predicted onto an
    ordinal scale 0..3 and reports score = ``1 - mae/3`` so higher is
    better; raw MAE is in ``detail``.

    Bands and boundaries are documented in
    ``docs/sglb_specs/SGLB-01.md`` and
    ``backend/data/ingestion/pdpc.py``.
    """

    name = "penalty_band_mae"
    strength = EvaluatorStrength.STRONG

    _BAND_TO_IDX: dict[str, int] = {"none": 0, "low": 1, "mid": 2, "high": 3}

    @classmethod
    def _to_idx(cls, value: Any) -> int | None:
        if not isinstance(value, str):
            return None
        return cls._BAND_TO_IDX.get(value.strip().lower())

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        expected_idx = self._to_idx((ctx.expected_output or {}).get("penalty_band"))
        parsed = _parse_json_object(ctx.output)
        predicted_idx = self._to_idx(parsed.get("penalty_band"))
        if expected_idx is None:
            return EvaluationResult(score=0.0, detail={"error": "expected band missing or invalid"})
        if predicted_idx is None:
            # No parseable prediction → max ordinal distance.
            return EvaluationResult(score=0.0, detail={"mae": 3.0, "predicted": None})
        diff = abs(predicted_idx - expected_idx)
        return EvaluationResult(
            score=1.0 - (diff / 3.0),
            detail={"mae": float(diff), "predicted_idx": predicted_idx, "expected_idx": expected_idx},
        )


class ConstraintSatisfaction(Evaluator):
    """Runs a list of constraint functions (IFEval-style).

    Expects ``expected_output["constraints"]`` as a list of constraint
    descriptors, each ``{"id": str, "kind": str, "params": dict}``. The
    constraint runners are resolved against
    ``benchmark.constraints.CONSTRAINTS`` (registered separately).
    """

    name = "constraint_sat"
    strength = EvaluatorStrength.STRONG

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        from benchmark.constraints import CONSTRAINTS

        constraints = (ctx.expected_output or {}).get("constraints", [])
        if not constraints:
            return EvaluationResult(score=1.0, detail={"total": 0, "passed": 0})
        passed = 0
        per_constraint: list[dict[str, Any]] = []
        for c in constraints:
            kind = c.get("kind", "")
            params = c.get("params", {}) or {}
            runner = CONSTRAINTS.get(kind)
            if runner is None:
                per_constraint.append({"id": c.get("id"), "kind": kind, "pass": False, "error": "unknown constraint kind"})
                continue
            result = runner(ctx.output or "", params)
            per_constraint.append({"id": c.get("id"), "kind": kind, "pass": result})
            if result:
                passed += 1
        return EvaluationResult(
            score=passed / len(constraints),
            detail={"total": len(constraints), "passed": passed, "per_constraint": per_constraint},
        )


# === Weak evaluators (back-compat; flagged in --strict mode) ===


class ContainsKeyword(Evaluator):
    """Fraction of expected keywords present in output. Weak — passes on
    hallucinated outputs that happen to mention the keyword."""

    name = "contains"
    strength = EvaluatorStrength.WEAK

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        terms = (ctx.expected_output or {}).get("contains", []) or []
        if not terms:
            return EvaluationResult(score=1.0)
        text = (ctx.output or "").lower()
        hits = sum(1 for t in terms if str(t).lower() in text)
        return EvaluationResult(score=hits / len(terms), detail={"hits": hits, "total": len(terms)})


class HasCitationMarker(Evaluator):
    """Any of the common citation surface markers appear. Weak — trivially
    passes for plausible-looking but invalid citations."""

    name = "has_citation_marker"
    strength = EvaluatorStrength.WEAK

    _MARKERS = ("Act", "Section", "[", "]", "SGHC", "SGCA", "Cap.", "s.")

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        out = ctx.output or ""
        return EvaluationResult(score=1.0 if any(m in out for m in self._MARKERS) else 0.0)


class MinLength(Evaluator):
    """Output length ≥ min_chars. Weak — non-evaluative."""

    name = "min_length"
    strength = EvaluatorStrength.WEAK

    def __init__(self, min_chars: int = 50) -> None:
        self.min_chars = min_chars

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluationResult:
        return EvaluationResult(score=1.0 if len(ctx.output or "") >= self.min_chars else 0.0)


# === Registry ===


EVALUATORS: dict[str, Evaluator] = {
    # strong
    ExactMatch.name: ExactMatch(),
    MultiLabelF1.name: MultiLabelF1(),
    CitationFormatValid.name: CitationFormatValid(),
    CitesSgStatute.name: CitesSgStatute(),
    UsesSalStyle.name: UsesSalStyle(),
    CompliancePresent.name: CompliancePresent(),
    CitationHallucinationF1.name: CitationHallucinationF1(),
    Sglb01ObligationsF1.name: Sglb01ObligationsF1(),
    PenaltyBandMae.name: PenaltyBandMae(),
    Sglb02CitationMatch.name: Sglb02CitationMatch(),
    RougeLAnswer.name: RougeLAnswer(),
    OrderRuleLabelF1.name: OrderRuleLabelF1(),
    OrderRuleTop3.name: OrderRuleTop3(),
    ConstraintSatisfaction.name: ConstraintSatisfaction(),
    # weak (back-compat)
    ContainsKeyword.name: ContainsKeyword(),
    HasCitationMarker.name: HasCitationMarker(),
    MinLength.name: MinLength(),
}


def register_evaluator(evaluator: Evaluator) -> None:
    EVALUATORS[evaluator.name] = evaluator


# === Constraint runner type alias ===

ConstraintRunner = Callable[[str, dict[str, Any]], bool]
