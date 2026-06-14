from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

from benchmark.schema import Case, Dataset
from benchmark.synthetic.multi_judge import (
    JudgeSpec,
    build_local_ollama_judge_specs,
    build_summary,
    main,
    parse_label_vote,
    run_votes,
)


class _MockJudge:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.messages: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        del max_tokens
        self.messages.append(messages)
        return self.outputs.pop(0)


def _case(name: str, tone: str, clause_type: str = "Confidentiality") -> Case:
    return Case(
        name=name,
        inputs={"clause_text": f"{tone} clause body", "clause_type": clause_type},
        expected_output={"labels": [tone]},
        metadata={
            "generator_provider": "azure",
            "generator_model": "azure:gpt-5-2",
            "taxonomy_cell": {
                "cell_id": f"{clause_type.lower()}_{tone}",
                "params": {"clause_type": clause_type, "tone": tone},
            },
        },
    )


def test_parse_label_vote_accepts_single_element_json_array() -> None:
    parsed = parse_label_vote('["balanced"]')
    assert parsed.json_parse_success is True
    assert parsed.label_valid is True
    assert parsed.parsed_label == "balanced"
    assert parsed.effective_label == "balanced"


def test_parse_label_vote_strips_json_fences() -> None:
    parsed = parse_label_vote('```json\n["protective"]\n```')
    assert parsed.json_parse_success is True
    assert parsed.label_valid is True
    assert parsed.parsed_label == "protective"


def test_parse_label_vote_marks_malformed_output_invalid() -> None:
    parsed = parse_label_vote("balanced")
    assert parsed.json_parse_success is False
    assert parsed.label_valid is False
    assert parsed.parsed_label is None
    assert parsed.effective_label == "__invalid__"


def test_run_votes_writes_two_provider_rows_and_reuses_prompt(tmp_path: Path) -> None:
    dataset = Dataset(cases=[_case("c1", "standard"), _case("c2", "aggressive")])
    anthropic = _MockJudge(['["standard"]', '["aggressive"]'])
    gemini = _MockJudge(['["standard"]', '["standard"]'])
    specs = [
        JudgeSpec(provider="anthropic", model="claude-test", client=anthropic),
        JudgeSpec(provider="gemini", model="gemini-test", client=gemini),
    ]
    output_path = tmp_path / "judges.jsonl"

    rows = asyncio.run(
        run_votes(
            dataset=dataset,
            judge_specs=specs,
            output_path=output_path,
            max_concurrency=1,
            force=True,
        )
    )

    assert len(rows) == 4
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 4
    assert rows[0]["case_id"] == "c1"
    assert rows[0]["provider"] == "anthropic"
    assert rows[1]["provider"] == "gemini"
    assert "experienced Singapore contracts lawyer" in anthropic.messages[0][0]["content"]
    assert "Clause type: Confidentiality" in anthropic.messages[0][1]["content"]


def test_build_summary_computes_pairwise_and_parse_counts(tmp_path: Path) -> None:
    dataset = Dataset(cases=[_case("c1", "standard"), _case("c2", "aggressive")])
    anthropic = _MockJudge(['["standard"]', '["aggressive"]'])
    gemini = _MockJudge(['["standard"]', "not-json"])
    specs = [
        JudgeSpec(provider="anthropic", model="claude-test", client=anthropic),
        JudgeSpec(provider="gemini", model="gemini-test", client=gemini),
    ]
    votes_path = tmp_path / "judges.jsonl"
    summary_path = tmp_path / "judges.summary.json"
    votes = asyncio.run(
        run_votes(
            dataset=dataset,
            judge_specs=specs,
            output_path=votes_path,
            max_concurrency=1,
            force=True,
        )
    )

    summary = build_summary(
        dataset=dataset,
        votes=votes,
        judge_specs=specs,
        dataset_path=tmp_path / "dataset.yaml",
        votes_path=votes_path,
        summary_path=summary_path,
    )

    assert summary["n_cases"] == 2
    assert summary["n_judges"] == 3
    assert summary["pairwise_cohen_kappa"]["azure:gpt-5-2 <-> anthropic:claude-test"]["kappa"] == 1.0
    assert summary["parse_failures"]["gemini:gemini-test"]["json_parse_failures"] == 1
    persisted = json.loads(summary_path.read_text(encoding="utf-8"))
    assert persisted["leaderboard"]["n"] == 2


def test_dry_run_reports_missing_env_keys(tmp_path: Path, capsys) -> None:
    dataset_path = tmp_path / "dataset.yaml"
    dataset_path.write_text(
        yaml.safe_dump({"cases": [_case("c1", "standard").model_dump()]}),
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=anthropic-key\n", encoding="utf-8")

    rc = main(["--dry-run", "--dataset", str(dataset_path), "--env-file", str(env_file)])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["missing"] == ["GEMINI_API_KEY"]
    assert payload["would_run"] is False


def test_build_local_ollama_specs_accepts_comma_separated_models() -> None:
    specs = build_local_ollama_judge_specs(
        models=["qwen2.5vl:7b,llama3.1:8b"],
        base_url="http://127.0.0.1:11434",
        seed=7,
    )

    assert [spec.provider for spec in specs] == ["ollama", "ollama"]
    assert [spec.model for spec in specs] == ["qwen2.5vl:7b", "llama3.1:8b"]
    assert specs[0].label == "ollama:qwen2.5vl:7b"
