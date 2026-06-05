"""Contamination probes for labelled SG-LegalBench cases."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from benchmark.evaluators import _rouge_l
from benchmark.registry import TASKS, canonical_task_name
from benchmark.schema import Case, EvalCaseResult

PROBE_PROMPT_VERSION = "contamination-v1"
MEMORISATION_THRESHOLD = 0.5

ProbeGenerator = Callable[[list[dict[str, str]], int], Awaitable[str]]


@dataclass(frozen=True)
class ProbeResult:
    case_name: str
    memorisation_score: float
    memorisation_flag: bool
    output: str
    prompt_version: str
    skipped: bool = False
    reason: str = ""


@dataclass(frozen=True)
class ProbeEndpoint:
    generate: ProbeGenerator
    max_tokens: int
    method: str


def _system_message(content: str) -> dict[str, str]:
    return {"role": "system", "content": content}


def _user_message(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def _probe_system() -> dict[str, str]:
    return _system_message(
        "You are answering a contamination audit probe. Do not infer from facts; "
        "answer only from direct recall of the named public source or dataset row. "
        "If you do not know, say unknown."
    )


def _pdpc_case_ref(case: Case) -> str:
    metadata = case.metadata or {}
    citation = str(metadata.get("citation") or "").strip()
    if citation:
        return citation
    case_name = str(metadata.get("case_name") or "").strip()
    if case_name:
        return case_name
    return case.name


def _sglb_01_probe_prompt(case: Case) -> list[dict[str, str]]:
    case_ref = _pdpc_case_ref(case)
    return [
        _probe_system(),
        _user_message(
            "What was the outcome (obligation breached + penalty band) of "
            f"PDPC case {case_ref}? Reply with JSON only: "
            '{"obligations": [<labels>], "penalty_band": "<none|low|mid|high|unknown>"}.'
        ),
    ]


def _section_number(case: Case) -> str:
    metadata = case.metadata or {}
    section = str(metadata.get("section_number") or "").strip()
    if section:
        return section
    citation = str((case.expected_output or {}).get("citation") or "")
    match = re.search(r"\bs\s+([0-9A-Za-z()]+)", citation)
    return match.group(1) if match else case.name


def _sglb_02_probe_prompt(case: Case) -> list[dict[str, str]]:
    statute = str(case.inputs.get("act_full_name") or case.inputs.get("act_short_name") or "").strip()
    section = _section_number(case)
    return [
        _probe_system(),
        _user_message(
            f"What is the text of {statute} section {section}? "
            "Reply with the statutory text only, or unknown if you cannot recall it."
        ),
    ]


def _clause_id(case: Case) -> str:
    metadata = case.metadata or {}
    explicit = str(metadata.get("clause_id") or "").strip()
    if explicit:
        return explicit
    taxonomy = metadata.get("taxonomy_cell") or {}
    if isinstance(taxonomy, dict):
        params = taxonomy.get("params") or {}
        if isinstance(params, dict):
            clause_id = str(params.get("clause_id") or "").strip()
            if clause_id:
                return clause_id
    digest = hashlib.sha256(case.name.encode("utf-8")).hexdigest()[:12]
    return f"case-{digest}"


def _sglb_08_probe_prompt(case: Case) -> list[dict[str, str]]:
    return [
        _probe_system(),
        _user_message(
            f"What is the tone label of clause {_clause_id(case)}? "
            'Reply with JSON only: ["standard"], ["aggressive"], ["balanced"], '
            '["protective"], or ["unknown"].'
        ),
    ]


def build_probe_prompt(workflow: str, case: Case) -> list[dict[str, str]]:
    task = canonical_task_name(workflow)
    if task == "sglb_01":
        return _sglb_01_probe_prompt(case)
    if task == "sglb_02":
        return _sglb_02_probe_prompt(case)
    if task == "sglb_08":
        return _sglb_08_probe_prompt(case)
    raise ValueError(f"no contamination probe for workflow {workflow!r}")


def probe_max_tokens(workflow: str) -> int:
    task = canonical_task_name(workflow)
    if task == "sglb_01":
        return 96
    if task == "sglb_02":
        return 256
    if task == "sglb_08":
        return 32
    return 1


def probe_status(workflow: str) -> tuple[bool, str]:
    task = canonical_task_name(workflow)
    if task in {"sglb_01", "sglb_02", "sglb_08"}:
        return True, ""
    if task == "sglb_04":
        return False, "SGLB-04 is skipped: citation grammar is deterministic."
    return False, f"no contamination probe defined for {task}"


def _normalise_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _parse_json(output: str) -> Any:
    text = (output or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


_OBLIGATION_ALIASES: dict[str, tuple[str, ...]] = {
    "consent": ("consent", "consent obligation"),
    "notification": ("notification", "notification obligation"),
    "purpose_limitation": ("purpose limitation", "purpose_limitation"),
    "protection": ("protection", "protection obligation"),
    "retention_limitation": ("retention limitation", "retention_limitation"),
    "data_portability": ("data portability", "data_portability"),
    "dpo": ("dpo", "data protection officer"),
    "dnc": ("dnc", "do not call"),
    "data_intermediary": ("data intermediary", "data_intermediary"),
    "transfer_limitation": ("transfer limitation", "transfer_limitation"),
    "accountability": ("accountability", "accountability obligation", "openness"),
    "openness": ("openness", "openness obligation"),
    "accuracy": ("accuracy", "accuracy obligation"),
    "access_correction": ("access correction", "access_correction"),
}


def _labels_from_json(value: Any, key: str) -> set[str]:
    if isinstance(value, dict):
        raw = value.get(key)
    else:
        raw = value
    if isinstance(raw, str):
        return {raw.strip().lower()} if raw.strip() else set()
    if isinstance(raw, list):
        return {str(item).strip().lower() for item in raw if str(item).strip()}
    return set()


def _canonical_obligation(value: str) -> str:
    text = _normalise_text(value).replace("-", " ")
    key = text.replace(" ", "_")
    if key in _OBLIGATION_ALIASES:
        return key
    for label, aliases in _OBLIGATION_ALIASES.items():
        if text == label.replace("_", " ") or text in aliases:
            return label
    return key


def _extract_obligations(output: str) -> set[str]:
    parsed = _parse_json(output)
    labels = _labels_from_json(parsed, "obligations")
    if labels:
        return {_canonical_obligation(label) for label in labels}
    text = _normalise_text(output)
    found: set[str] = set()
    for label, aliases in _OBLIGATION_ALIASES.items():
        if any(alias in text for alias in aliases):
            found.add(label)
    return found


def _f1(expected: set[str], predicted: set[str]) -> float:
    if not expected and not predicted:
        return 1.0
    if not expected or not predicted:
        return 0.0
    tp = len(expected & predicted)
    precision = tp / len(predicted)
    recall = tp / len(expected)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _extract_penalty_band(output: str) -> str:
    parsed = _parse_json(output)
    if isinstance(parsed, dict):
        band = str(parsed.get("penalty_band") or "").strip().lower()
        if band in {"none", "low", "mid", "high"}:
            return band
    text = _normalise_text(output)
    for band in ("none", "low", "mid", "high"):
        if re.search(rf"\b{band}\b", text):
            return band
    if "warning" in text or "no financial penalty" in text:
        return "none"
    return ""


def _score_sglb_01(case: Case, output: str) -> float:
    expected = case.expected_output or {}
    gold_obligations = {
        str(item).strip().lower()
        for item in expected.get("obligations", [])
        if str(item).strip()
    }
    obligation_score = _f1(gold_obligations, _extract_obligations(output))
    gold_band = str(expected.get("penalty_band") or "").strip().lower()
    band_score = 1.0 if gold_band and _extract_penalty_band(output) == gold_band else 0.0
    return (obligation_score + band_score) / 2


def _score_sglb_02(case: Case, output: str) -> float:
    gold = str((case.expected_output or {}).get("answer_span") or "")
    if not gold:
        return 0.0
    return _rouge_l(gold, output)


def _extract_tone_labels(output: str) -> set[str]:
    parsed = _parse_json(output)
    labels = _labels_from_json(parsed, "labels")
    if labels:
        return labels
    text = _normalise_text(output)
    return {
        label
        for label in ("standard", "aggressive", "balanced", "protective")
        if re.search(rf"\b{label}\b", text)
    }


def _score_sglb_08(case: Case, output: str) -> float:
    gold = {
        str(item).strip().lower()
        for item in (case.expected_output or {}).get("labels", [])
        if str(item).strip()
    }
    return _f1(gold, _extract_tone_labels(output))


def score_probe_output(workflow: str, case: Case, output: str) -> float:
    task = canonical_task_name(workflow)
    if task == "sglb_01":
        return _score_sglb_01(case, output)
    if task == "sglb_02":
        return _score_sglb_02(case, output)
    if task == "sglb_08":
        return _score_sglb_08(case, output)
    return 0.0


def _callable_generate(obj: Any) -> Callable[..., Awaitable[str]] | None:
    generate = getattr(obj, "generate", None)
    if generate is None or not callable(generate):
        return None
    return generate


def _extract_endpoint(workflow: str) -> ProbeEndpoint | None:
    runner = TASKS.get(workflow)
    if runner is None:
        return None
    cells = getattr(runner, "__closure__", None) or ()
    generate: Callable[..., Awaitable[str]] | None = None
    max_tokens = probe_max_tokens(workflow)
    for cell in cells:
        try:
            obj = cell.cell_contents
        except ValueError:
            continue
        candidate = _callable_generate(obj)
        if candidate is not None:
            generate = candidate
        if hasattr(obj, "max_tokens"):
            try:
                max_tokens = min(max_tokens, int(getattr(obj, "max_tokens")))
            except (TypeError, ValueError):
                pass
    if generate is None:
        return None

    async def _generate(messages: list[dict[str, str]], tokens: int) -> str:
        output = generate(messages, max_tokens=tokens)
        if inspect.isawaitable(output):
            output = await output
        return output if isinstance(output, str) else str(output)

    return ProbeEndpoint(generate=_generate, max_tokens=max_tokens, method="llm_client")


def _workflow_fallback_endpoint(workflow: str) -> ProbeEndpoint | None:
    runner = TASKS.get(workflow)
    if runner is None:
        return None

    async def _generate(messages: list[dict[str, str]], tokens: int) -> str:
        del messages, tokens
        raise RuntimeError("workflow fallback requires the original case")

    return ProbeEndpoint(generate=_generate, max_tokens=probe_max_tokens(workflow), method="workflow_fallback")


async def _run_probe_case(
    workflow: str,
    case: Case,
    endpoint: ProbeEndpoint,
) -> ProbeResult:
    try:
        if endpoint.method == "workflow_fallback":
            output = await TASKS[workflow](case)
        else:
            output = await endpoint.generate(
                build_probe_prompt(workflow, case),
                endpoint.max_tokens,
            )
        score = max(0.0, min(1.0, score_probe_output(workflow, case, output)))
        return ProbeResult(
            case_name=case.name,
            memorisation_score=score,
            memorisation_flag=score >= MEMORISATION_THRESHOLD,
            output=output,
            prompt_version=PROBE_PROMPT_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            case_name=case.name,
            memorisation_score=0.0,
            memorisation_flag=False,
            output="",
            prompt_version=PROBE_PROMPT_VERSION,
            skipped=True,
            reason=str(exc),
        )


async def run_probe(
    workflow: str,
    cases: list[Case],
    *,
    max_concurrency: int,
) -> tuple[list[ProbeResult], str]:
    supported, reason = probe_status(workflow)
    if not supported:
        return [
            ProbeResult(
                case_name=case.name,
                memorisation_score=0.0,
                memorisation_flag=False,
                output="",
                prompt_version=PROBE_PROMPT_VERSION,
                skipped=True,
                reason=reason,
            )
            for case in cases
        ], "skipped"
    endpoint = _extract_endpoint(workflow) or _workflow_fallback_endpoint(workflow)
    if endpoint is None:
        return [
            ProbeResult(
                case_name=case.name,
                memorisation_score=0.0,
                memorisation_flag=False,
                output="",
                prompt_version=PROBE_PROMPT_VERSION,
                skipped=True,
                reason="workflow not registered",
            )
            for case in cases
        ], "skipped"
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(case: Case) -> ProbeResult:
        async with semaphore:
            return await _run_probe_case(workflow, case, endpoint)

    return list(await asyncio.gather(*[_bounded(case) for case in cases])), endpoint.method


def attach_probe_metadata(results: list[EvalCaseResult], probe_results: list[ProbeResult]) -> None:
    by_case = {result.case_name: result for result in probe_results}
    for result in results:
        probe = by_case.get(result.case_name)
        if probe is None:
            continue
        result.metadata["memorisation_score"] = probe.memorisation_score
        result.metadata["memorisation_flag"] = probe.memorisation_flag
        result.metadata["memorisation_probe_version"] = probe.prompt_version
        if probe.skipped:
            result.metadata["memorisation_probe_skipped"] = True
            result.metadata["memorisation_probe_reason"] = probe.reason


def contamination_summary(
    workflow: str,
    evaluators: list[str],
    results: list[EvalCaseResult],
    probe_results: list[ProbeResult],
    *,
    method: str,
) -> dict[str, Any]:
    if not probe_results:
        return {}
    clean_cases = {
        result.case_name
        for result in probe_results
        if not result.skipped and result.memorisation_score < MEMORISATION_THRESHOLD
    }
    flagged = [
        result
        for result in probe_results
        if not result.skipped and result.memorisation_flag
    ]
    completed = [result for result in probe_results if not result.skipped]
    adjusted: dict[str, float | None] = {}
    for evaluator in evaluators:
        scores = [
            result.score
            for result in results
            if not result.error and result.evaluator == evaluator and result.case_name in clean_cases
        ]
        adjusted[evaluator] = (sum(scores) / len(scores)) if scores else None
    skipped = all(result.skipped for result in probe_results)
    return {
        "workflow": canonical_task_name(workflow),
        "probe_prompt_version": PROBE_PROMPT_VERSION,
        "method": method,
        "status": "skipped" if skipped else "completed",
        "reason": probe_results[0].reason if skipped else "",
        "threshold": MEMORISATION_THRESHOLD,
        "total_cases": len(probe_results),
        "probed_cases": len(completed),
        "flagged_cases": len(flagged),
        "mean_memorisation_rate": (len(flagged) / len(completed)) if completed else 0.0,
        "contamination_adjusted_score": adjusted,
    }
