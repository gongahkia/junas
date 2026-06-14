"""Run the SGLB-08 multi-judge label audit."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Protocol

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.config import Settings  # noqa: E402
from api.services.llm_client import get_llm_client  # noqa: E402
from benchmark.llm_runner import (  # noqa: E402
    SGLB_08_PROMPT_VERSION,
    prompt_sha,
    sglb_08_prompt_builder,
)
from benchmark.runner import load_dataset  # noqa: E402
from benchmark.schema import Case, Dataset  # noqa: E402
from benchmark.synthetic.agreement import INVALID_LABEL, cohen_kappa, fleiss_kappa  # noqa: E402
from benchmark.synthetic.sglb_08 import REQUIRED_TONES  # noqa: E402


DEFAULT_DATASET = (
    BACKEND_ROOT
    / "benchmark"
    / "datasets"
    / "sglb_08_clause_tone_reviewed"
    / "dataset.yaml"
)
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
AGREEMENT_FLOOR = 0.4
MAX_TOKENS = 64
AGREEMENT_LABELS = (*REQUIRED_TONES, INVALID_LABEL)
DEFAULT_LOCAL_OLLAMA_MODELS = ("qwen2.5vl:7b", "llama3.1:8b")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


class LLMLike(Protocol):
    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        ...


@dataclass(frozen=True)
class JudgeSpec:
    provider: str
    model: str
    client: LLMLike

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


class OllamaJudgeClient:
    def __init__(self, *, model: str, base_url: str, seed: int = 0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.seed = seed

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
                "seed": self.seed,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return str(message.get("content") or "")


@dataclass(frozen=True)
class ParsedVote:
    json_parse_success: bool
    parsed_label: str | None
    label_valid: bool
    effective_label: str


def parse_label_vote(raw_output: str) -> ParsedVote:
    try:
        parsed = json.loads(_json_payload(raw_output))
    except json.JSONDecodeError:
        return ParsedVote(
            json_parse_success=False,
            parsed_label=None,
            label_valid=False,
            effective_label=INVALID_LABEL,
        )

    label: str | None = None
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], str):
        label = parsed[0].strip().lower()
    label_valid = label in REQUIRED_TONES
    return ParsedVote(
        json_parse_success=True,
        parsed_label=label,
        label_valid=label_valid,
        effective_label=label if label_valid else INVALID_LABEL,
    )


async def run_votes(
    *,
    dataset: Dataset,
    judge_specs: Sequence[JudgeSpec],
    output_path: Path,
    max_concurrency: int = 3,
    force: bool = False,
    group_by_spec: bool = False,
) -> list[dict[str, Any]]:
    existing = [] if force else _read_vote_rows(output_path)
    expected_cases = {case.name for case in dataset.cases}
    expected_specs = {(spec.provider, spec.model) for spec in judge_specs}
    rows_by_key = {
        _vote_key(row): row
        for row in existing
        if row.get("case_id") in expected_cases
        and (str(row.get("provider", "")), str(row.get("model", ""))) in expected_specs
    }
    if group_by_spec:
        pending = [
            (case, spec)
            for spec in judge_specs
            for case in dataset.cases
            if (case.name, spec.provider, spec.model) not in rows_by_key
        ]
    else:
        pending = [
            (case, spec)
            for case in dataset.cases
            for spec in judge_specs
            if (case.name, spec.provider, spec.model) not in rows_by_key
        ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if force and output_path.exists():
        output_path.unlink()

    append_lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _run_one(case: Case, spec: JudgeSpec) -> dict[str, Any]:
        async with semaphore:
            messages = sglb_08_prompt_builder(case)
            try:
                raw = await spec.client.generate(messages, max_tokens=MAX_TOKENS)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"{spec.label} failed on {case.name}: {exc}") from exc
            row = vote_row(case=case, spec=spec, raw_output=str(raw))
            async with append_lock:
                with output_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, sort_keys=True) + "\n")
            return row

    if pending:
        new_rows = await asyncio.gather(*[_run_one(case, spec) for case, spec in pending])
        for row in new_rows:
            rows_by_key[_vote_key(row)] = row

    ordered = _ordered_rows(dataset.cases, judge_specs, rows_by_key)
    if len(ordered) != len(dataset.cases) * len(judge_specs):
        raise RuntimeError("multi-judge run did not produce a complete vote matrix")
    _write_vote_rows(output_path, ordered)
    return ordered


def vote_row(*, case: Case, spec: JudgeSpec, raw_output: str) -> dict[str, Any]:
    parsed = parse_label_vote(raw_output)
    gold = gold_label(case)
    taxonomy_cell = _taxonomy_cell(case)
    return {
        "case_id": case.name,
        "provider": spec.provider,
        "model": spec.model,
        "judge": spec.label,
        "raw_output": raw_output,
        "parsed_label": parsed.parsed_label,
        "json_parse_success": parsed.json_parse_success,
        "label_valid": parsed.label_valid,
        "effective_label": parsed.effective_label,
        "gold_label": gold,
        "clause_type": clause_type(case),
        "taxonomy_cell_id": str(taxonomy_cell.get("cell_id", "")),
        "prompt_builder": "benchmark.llm_runner.sglb_08_prompt_builder",
        "prompt_version": SGLB_08_PROMPT_VERSION,
        "prompt_sha": prompt_sha(sglb_08_prompt_builder, case),
        "voted_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def build_summary(
    *,
    dataset: Dataset,
    votes: Sequence[dict[str, Any]],
    judge_specs: Sequence[JudgeSpec],
    dataset_path: Path,
    votes_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    row_by_key = {_vote_key(row): row for row in votes}
    generator = generator_judge(dataset)
    judge_names = [generator["label"], *[spec.label for spec in judge_specs]]
    ratings_by_judge: dict[str, list[str]] = {name: [] for name in judge_names}
    ratings_by_case: list[list[str]] = []
    cell_indexes: dict[tuple[str, str], list[int]] = defaultdict(list)

    for index, case in enumerate(dataset.cases):
        gold = gold_label(case)
        ratings_by_judge[generator["label"]].append(gold)
        per_case = [gold]
        for spec in judge_specs:
            row = row_by_key.get((case.name, spec.provider, spec.model))
            if row is None:
                raise RuntimeError(f"missing vote row for {case.name} / {spec.label}")
            label = _effective_label(row)
            ratings_by_judge[spec.label].append(label)
            per_case.append(label)
        ratings_by_case.append(per_case)
        cell_indexes[(gold, clause_type(case))].append(index)

    pairwise = _pairwise_summary(judge_names, ratings_by_judge)
    all_judge_fleiss = fleiss_kappa(ratings_by_case, labels=AGREEMENT_LABELS)
    cells = _cell_summary(judge_names, ratings_by_judge, ratings_by_case, cell_indexes)
    low_cells = [
        cell
        for cell in cells
        if cell["below_floor_pairs"] or cell["fleiss_kappa"]["kappa"] is not None
        and float(cell["fleiss_kappa"]["kappa"]) < AGREEMENT_FLOOR
    ]
    low_global_pairs = {
        pair: result
        for pair, result in pairwise.items()
        if result["kappa"] is not None and float(result["kappa"]) < AGREEMENT_FLOOR
    }
    parse_failures = _parse_failure_summary(votes, judge_specs)
    leaderboard_kappa = all_judge_fleiss.kappa
    summary = {
        "task": "SGLB-08",
        "dataset": str(dataset_path),
        "votes": str(votes_path),
        "summary": str(summary_path),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "n_cases": len(dataset.cases),
        "n_judges": len(judge_names),
        "judges": [
            {
                "label": generator["label"],
                "provider": generator["provider"],
                "model": generator["model"],
                "source": "dataset.expected_output.labels",
            },
            *[
                {
                    "label": spec.label,
                    "provider": spec.provider,
                    "model": spec.model,
                    "source": "judges.jsonl",
                }
                for spec in judge_specs
            ],
        ],
        "prompt": {
            "builder": "benchmark.llm_runner.sglb_08_prompt_builder",
            "version": SGLB_08_PROMPT_VERSION,
            "max_tokens": MAX_TOKENS,
        },
        "agreement_floor": AGREEMENT_FLOOR,
        "agreement_labels": list(AGREEMENT_LABELS),
        "pairwise_cohen_kappa": pairwise,
        "fleiss_kappa": all_judge_fleiss.as_dict(),
        "parse_failures": parse_failures,
        "per_cell": cells,
        "dangerously_low_cells": [
            {
                "tone": cell["tone"],
                "clause_type": cell["clause_type"],
                "n": cell["n"],
                "below_floor_pairs": cell["below_floor_pairs"],
                "fleiss_kappa": cell["fleiss_kappa"]["kappa"],
            }
            for cell in low_cells
        ],
        "all_global_pairwise_kappa_at_or_above_floor": not low_global_pairs,
        "global_pairs_below_floor": low_global_pairs,
        "leaderboard": {
            "metric": "fleiss_kappa",
            "kappa": leaderboard_kappa,
            "display": _leaderboard_display(leaderboard_kappa, len(dataset.cases), len(judge_names)),
            "n": len(dataset.cases),
            "judges": len(judge_names),
            "pairwise_floor_pass": not low_global_pairs,
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def gold_label(case: Case) -> str:
    expected = case.expected_output or {}
    labels = expected.get("labels")
    if not isinstance(labels, list) or len(labels) != 1:
        raise ValueError(f"SGLB-08 case {case.name} must have one gold label")
    label = str(labels[0]).strip().lower()
    if label not in REQUIRED_TONES:
        raise ValueError(f"SGLB-08 case {case.name} has invalid gold label {label!r}")
    return label


def clause_type(case: Case) -> str:
    value = str(case.inputs.get("clause_type", "")).strip()
    if value:
        return value
    params = _taxonomy_cell(case).get("params", {})
    if isinstance(params, dict):
        return str(params.get("clause_type", "")).strip()
    return ""


def generator_judge(dataset: Dataset) -> dict[str, str]:
    providers = Counter(str(case.metadata.get("generator_provider", "")).strip() for case in dataset.cases)
    models = Counter(str(case.metadata.get("generator_model", "")).strip() for case in dataset.cases)
    provider = _most_common_nonblank(providers) or "azure"
    model = _most_common_nonblank(models) or "gpt-5"
    label = model if ":" in model else f"{provider}:{model}"
    return {"provider": provider, "model": model, "label": label}


def build_judge_specs(
    *,
    env_file: Path,
    anthropic_model: str = "",
    gemini_model: str = "",
) -> list[JudgeSpec]:
    anthropic_key = _read_dotenv_value(env_file, "ANTHROPIC_API_KEY")
    gemini_key = _read_dotenv_value(env_file, "GEMINI_API_KEY")
    missing = [name for name, value in (("ANTHROPIC_API_KEY", anthropic_key), ("GEMINI_API_KEY", gemini_key)) if not value]
    if missing:
        raise RuntimeError(f"missing provider keys in {env_file}: {', '.join(missing)}")

    resolved_anthropic_model = _model_value(
        env_file=env_file,
        explicit=anthropic_model,
        env_keys=("JUNAS_SYNTH_ANTHROPIC_MODEL", "ANTHROPIC_MODEL"),
        default=DEFAULT_ANTHROPIC_MODEL,
    )
    resolved_gemini_model = _model_value(
        env_file=env_file,
        explicit=gemini_model,
        env_keys=("JUNAS_SYNTH_GOOGLE_MODEL", "GEMINI_MODEL"),
        default=DEFAULT_GEMINI_MODEL,
    )
    anthropic_settings = Settings(
        _env_file=env_file if env_file.exists() else None,
        llm_provider="anthropic",
        anthropic_api_key=anthropic_key,
        anthropic_model=resolved_anthropic_model,
    )
    gemini_settings = Settings(
        _env_file=env_file if env_file.exists() else None,
        llm_provider="gemini",
        gemini_api_key=gemini_key,
        gemini_model=resolved_gemini_model,
    )
    return [
        JudgeSpec(
            provider="anthropic",
            model=resolved_anthropic_model,
            client=get_llm_client(anthropic_settings),
        ),
        JudgeSpec(
            provider="gemini",
            model=resolved_gemini_model,
            client=get_llm_client(gemini_settings),
        ),
    ]


def _split_models(raw_models: Sequence[str]) -> list[str]:
    models: list[str] = []
    for raw in raw_models:
        for part in str(raw).split(","):
            model = part.strip()
            if model:
                models.append(model)
    return models


def build_local_ollama_judge_specs(
    *,
    models: Sequence[str],
    base_url: str,
    seed: int = 0,
) -> list[JudgeSpec]:
    resolved = _split_models(models) or list(DEFAULT_LOCAL_OLLAMA_MODELS)
    return [
        JudgeSpec(
            provider="ollama",
            model=model,
            client=OllamaJudgeClient(model=model, base_url=base_url, seed=seed),
        )
        for model in resolved
    ]


async def _ollama_tags(base_url: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        response = await client.get(f"{base_url.rstrip('/')}/api/tags")
        response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def local_ollama_preflight_payload(
    *,
    dataset_path: Path,
    output_path: Path,
    summary_path: Path,
    models: Sequence[str],
    base_url: str,
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    requested = _split_models(models) or list(DEFAULT_LOCAL_OLLAMA_MODELS)
    missing: list[str] = []
    available: list[str] = []
    api_error = ""
    try:
        tags = await _ollama_tags(base_url)
        available = [
            str(item.get("name") or item.get("model") or "")
            for item in tags.get("models", [])
            if isinstance(item, dict)
        ]
        missing = [model for model in requested if model not in available]
    except Exception as exc:  # noqa: BLE001
        api_error = str(exc)
        missing = list(requested)
    return {
        "dry_run": True,
        "mode": "local_ollama",
        "dataset": str(dataset_path),
        "n_cases": len(dataset.cases),
        "providers": [
            {"provider": "ollama", "model": model, "available": model in available}
            for model in requested
        ],
        "missing": missing,
        "api_error": api_error,
        "would_call": 0 if missing else len(dataset.cases) * len(requested),
        "estimated_cost_usd": 0.0,
        "output": str(output_path),
        "summary": str(summary_path),
        "would_run": not missing,
    }


def preflight_payload(
    *,
    env_file: Path,
    dataset_path: Path,
    output_path: Path,
    summary_path: Path,
    anthropic_model: str = "",
    gemini_model: str = "",
) -> dict[str, Any]:
    dataset = load_dataset(dataset_path)
    missing = [
        name
        for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")
        if not _read_dotenv_value(env_file, name)
    ]
    resolved_anthropic_model = _model_value(
        env_file=env_file,
        explicit=anthropic_model,
        env_keys=("JUNAS_SYNTH_ANTHROPIC_MODEL", "ANTHROPIC_MODEL"),
        default=DEFAULT_ANTHROPIC_MODEL,
    )
    resolved_gemini_model = _model_value(
        env_file=env_file,
        explicit=gemini_model,
        env_keys=("JUNAS_SYNTH_GOOGLE_MODEL", "GEMINI_MODEL"),
        default=DEFAULT_GEMINI_MODEL,
    )
    return {
        "dry_run": True,
        "dataset": str(dataset_path),
        "n_cases": len(dataset.cases),
        "providers": [
            {
                "provider": "anthropic",
                "model": resolved_anthropic_model,
                "api_key": "missing in .env" if "ANTHROPIC_API_KEY" in missing else "present in .env",
            },
            {
                "provider": "gemini",
                "model": resolved_gemini_model,
                "api_key": "missing in .env" if "GEMINI_API_KEY" in missing else "present in .env",
            },
        ],
        "missing": missing,
        "would_call": 0 if missing else len(dataset.cases) * 2,
        "estimated_cost_usd": 2.4,
        "output": str(output_path),
        "summary": str(summary_path),
        "would_run": not missing,
    }


def _pairwise_summary(
    judge_names: Sequence[str],
    ratings_by_judge: dict[str, list[str]],
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for left, right in combinations(judge_names, 2):
        metric = cohen_kappa(
            ratings_by_judge[left],
            ratings_by_judge[right],
            labels=AGREEMENT_LABELS,
        )
        result[f"{left} <-> {right}"] = metric.as_dict()
    return result


def _cell_summary(
    judge_names: Sequence[str],
    ratings_by_judge: dict[str, list[str]],
    ratings_by_case: Sequence[Sequence[str]],
    cell_indexes: dict[tuple[str, str], list[int]],
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for (tone, clause), indexes in sorted(cell_indexes.items()):
        cell_ratings_by_judge = {
            judge: [ratings_by_judge[judge][index] for index in indexes]
            for judge in judge_names
        }
        pairwise = _pairwise_summary(judge_names, cell_ratings_by_judge)
        fleiss = fleiss_kappa(
            [[ratings_by_case[index][judge_index] for judge_index in range(len(judge_names))] for index in indexes],
            labels=AGREEMENT_LABELS,
        )
        below_floor_pairs = [
            pair
            for pair, metric in pairwise.items()
            if metric["kappa"] is not None and float(metric["kappa"]) < AGREEMENT_FLOOR
        ]
        cells.append(
            {
                "tone": tone,
                "clause_type": clause,
                "n": len(indexes),
                "pairwise_cohen_kappa": pairwise,
                "fleiss_kappa": fleiss.as_dict(),
                "below_floor_pairs": below_floor_pairs,
            }
        )
    return cells


def _parse_failure_summary(
    votes: Sequence[dict[str, Any]],
    judge_specs: Sequence[JudgeSpec],
) -> dict[str, dict[str, int]]:
    rows_by_judge: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in votes:
        rows_by_judge[str(row.get("judge", ""))].append(row)
    summary: dict[str, dict[str, int]] = {}
    for spec in judge_specs:
        rows = rows_by_judge.get(spec.label, [])
        summary[spec.label] = {
            "total": len(rows),
            "json_parse_success": sum(1 for row in rows if row.get("json_parse_success") is True),
            "json_parse_failures": sum(1 for row in rows if row.get("json_parse_success") is not True),
            "valid_labels": sum(1 for row in rows if row.get("label_valid") is True),
            "invalid_or_missing_labels": sum(1 for row in rows if row.get("label_valid") is not True),
        }
    return summary


def _json_payload(raw_output: str) -> str:
    text = raw_output.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _effective_label(row: dict[str, Any]) -> str:
    label = str(row.get("effective_label") or "").strip().lower()
    if label in AGREEMENT_LABELS:
        return label
    parsed = str(row.get("parsed_label") or "").strip().lower()
    return parsed if parsed in REQUIRED_TONES and row.get("label_valid") is True else INVALID_LABEL


def _taxonomy_cell(case: Case) -> dict[str, Any]:
    cell = case.metadata.get("taxonomy_cell", {})
    return cell if isinstance(cell, dict) else {}


def _vote_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("case_id", "")),
        str(row.get("provider", "")),
        str(row.get("model", "")),
    )


def _ordered_rows(
    cases: Sequence[Case],
    specs: Sequence[JudgeSpec],
    rows_by_key: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        for spec in specs:
            row = rows_by_key.get((case.name, spec.provider, spec.model))
            if row is not None:
                rows.append(row)
    return rows


def _read_vote_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_vote_rows(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


def _read_dotenv_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    prefix = f"{key}="
    export_prefix = f"export {key}="
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(export_prefix):
            value = line[len(export_prefix) :].strip()
        elif line.startswith(prefix):
            value = line[len(prefix) :].strip()
        else:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value.strip()
    return ""


def _model_value(
    *,
    env_file: Path,
    explicit: str,
    env_keys: Sequence[str],
    default: str,
) -> str:
    if explicit.strip():
        return explicit.strip()
    for key in env_keys:
        value = _read_dotenv_value(env_file, key)
        if value:
            return value
    for key in env_keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


def _most_common_nonblank(counter: Counter[str]) -> str:
    for value, _count in counter.most_common():
        if value:
            return value
    return ""


def _leaderboard_display(kappa: float | None, n_cases: int, n_judges: int) -> str:
    if kappa is None:
        return f"\u03ba = n/a (n={n_cases}, {n_judges} judges)"
    return f"\u03ba = {kappa:.2f} (n={n_cases}, {n_judges} judges)"


def _compact_stdout(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "leaderboard": summary["leaderboard"],
        "pairwise_cohen_kappa": {
            pair: metric["kappa"]
            for pair, metric in summary["pairwise_cohen_kappa"].items()
        },
        "fleiss_kappa": summary["fleiss_kappa"]["kappa"],
        "parse_failures": summary["parse_failures"],
        "dangerously_low_cells": summary["dangerously_low_cells"],
        "summary": summary["summary"],
        "votes": summary["votes"],
    }


async def _run_all(args: argparse.Namespace) -> dict[str, Any]:
    dataset_path = Path(args.dataset).resolve()
    default_output = "judges.local.jsonl" if args.local_ollama else "judges.jsonl"
    default_summary = "judges.local.summary.json" if args.local_ollama else "judges.summary.json"
    output_path = Path(args.output or dataset_path.parent / default_output).resolve()
    summary_path = Path(args.summary or dataset_path.parent / default_summary).resolve()
    env_file = Path(args.env_file).resolve()
    dataset = load_dataset(dataset_path)
    if args.local_ollama:
        specs = build_local_ollama_judge_specs(
            models=args.ollama_model,
            base_url=args.ollama_base_url,
            seed=args.seed,
        )
    else:
        specs = build_judge_specs(
            env_file=env_file,
            anthropic_model=args.anthropic_model,
            gemini_model=args.gemini_model,
        )
    votes = await run_votes(
        dataset=dataset,
        judge_specs=specs,
        output_path=output_path,
        max_concurrency=args.max_concurrency,
        force=args.force,
        group_by_spec=args.local_ollama,
    )
    summary = build_summary(
        dataset=dataset,
        votes=votes,
        judge_specs=specs,
        dataset_path=dataset_path,
        votes_path=output_path,
        summary_path=summary_path,
    )
    print(json.dumps(_compact_stdout(summary), indent=2, sort_keys=True))
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Reviewed SGLB-08 dataset YAML.")
    parser.add_argument("--output", default="", help="Vote JSONL path. Defaults to judges.jsonl next to dataset.")
    parser.add_argument("--summary", default="", help="Summary JSON path. Defaults to judges.summary.json next to dataset.")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"), help="Path to .env with ANTHROPIC_API_KEY and GEMINI_API_KEY.")
    parser.add_argument("--anthropic-model", default="", help=f"Anthropic model override. Defaults to {DEFAULT_ANTHROPIC_MODEL}.")
    parser.add_argument("--gemini-model", default="", help=f"Gemini model override. Defaults to {DEFAULT_GEMINI_MODEL}.")
    parser.add_argument(
        "--local-ollama",
        action="store_true",
        help="Use local Ollama judges and write judges.local.* outputs.",
    )
    parser.add_argument(
        "--ollama-model",
        action="append",
        default=[],
        help="Ollama model to use; repeatable or comma-separated.",
    )
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--seed", type=int, default=0, help="Seed passed to local Ollama.")
    parser.add_argument("--max-concurrency", type=int, default=3, help="Maximum concurrent judge calls.")
    parser.add_argument("--force", action="store_true", help="Discard existing rows for this output and rerun all votes.")
    parser.add_argument("--dry-run", action="store_true", help="Report resolved providers and missing keys without calling LLMs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dataset_path = Path(args.dataset).resolve()
    default_output = "judges.local.jsonl" if args.local_ollama else "judges.jsonl"
    default_summary = "judges.local.summary.json" if args.local_ollama else "judges.summary.json"
    output_path = Path(args.output or dataset_path.parent / default_output).resolve()
    summary_path = Path(args.summary or dataset_path.parent / default_summary).resolve()
    env_file = Path(args.env_file).resolve()
    if args.dry_run:
        if args.local_ollama:
            payload = asyncio.run(
                local_ollama_preflight_payload(
                    dataset_path=dataset_path,
                    output_path=output_path,
                    summary_path=summary_path,
                    models=args.ollama_model,
                    base_url=args.ollama_base_url,
                )
            )
        else:
            payload = preflight_payload(
                env_file=env_file,
                dataset_path=dataset_path,
                output_path=output_path,
                summary_path=summary_path,
                anthropic_model=args.anthropic_model,
                gemini_model=args.gemini_model,
            )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if payload["missing"] else 0

    if not args.local_ollama:
        missing = [
            name
            for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY")
            if not _read_dotenv_value(env_file, name)
        ]
        if missing:
            print(f"error: missing provider keys in {env_file}: {', '.join(missing)}", file=sys.stderr)
            return 1
    try:
        asyncio.run(_run_all(args))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
