from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
import yaml

from benchmark.constraints import CONSTRAINTS
from benchmark.registry import TASKS
from benchmark.runner import run
from benchmark.synthetic import cli
from benchmark.synthetic.generator import (
    MockLLM,
    SyntheticGenerator,
    case_from_body,
    generate_candidate,
    load_env_file,
    preflight_providers,
)
from benchmark.synthetic.ops import show_fixture, status_for_task, validate_task
from benchmark.synthetic.planner import build_plan, estimate_cost_usd, parse_providers
from benchmark.synthetic.promoter import AUDIT_LOG, AGGREGATE_DATASET, promote_task
from benchmark.synthetic.prompts import render_prompt
from benchmark.synthetic.quality import check_case_quality
from benchmark.synthetic.reviewer import record_decision, resolve_fixture
from benchmark.synthetic.taxonomy import cells_for, supported_tasks


def _read_case(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload["cases"][0]


def test_supported_tasks_are_only_synthetic_three() -> None:
    assert set(supported_tasks()) == {"sglb_08", "sglb_12", "sglb_15"}
    with pytest.raises(ValueError):
        cells_for("sglb_01")


def test_sglb_08_taxonomy_covers_clause_tones_and_variants() -> None:
    cells = cells_for("sglb_08")
    assert len(cells) == 6 * 4 * 3
    tones = {cell.params["tone"] for cell in cells}
    variants = {cell.variant for cell in cells}
    assert tones == {"standard", "aggressive", "balanced", "protective"}
    assert variants == {"default", "adversarial", "negative"}


def test_sglb_12_taxonomy_uses_compound_issue_sets() -> None:
    cells = cells_for("sglb_12")
    assert cells
    for cell in cells:
        labels = cell.label["labels"]
        assert 2 <= len(labels) <= 4
        assert all(label.startswith(("pdpa.", "ea.", "roc.")) for label in labels)


def test_sglb_15_taxonomy_references_registered_constraints() -> None:
    kinds = {
        constraint["kind"]
        for cell in cells_for("sglb_15")
        for constraint in cell.label["constraints"]
    }
    assert kinds <= set(CONSTRAINTS)
    assert {"named_party_present", "governing_law_singapore", "required_section_present"} <= kinds


def test_planner_expands_exact_n_and_candidate_paths(tmp_path: Path) -> None:
    plan = build_plan(task="sglb_08", n=20, providers="mock", seed=7, base_dir=tmp_path)
    assert len(plan) == 20
    assert all(item.candidate_path.parent == tmp_path / "sglb_08_clause_tone_candidates" for item in plan)
    assert len({item.slug for item in plan}) == 20


def test_planner_is_seed_stable(tmp_path: Path) -> None:
    a = build_plan(task="sglb_12", n=10, providers="mock", seed=42, base_dir=tmp_path)
    b = build_plan(task="sglb_12", n=10, providers="mock", seed=42, base_dir=tmp_path)
    assert [item.as_dict() for item in a] == [item.as_dict() for item in b]


def test_planner_seed_changes_matrix_order(tmp_path: Path) -> None:
    a = build_plan(task="sglb_12", n=10, providers="mock", seed=1, base_dir=tmp_path)
    b = build_plan(task="sglb_12", n=10, providers="mock", seed=2, base_dir=tmp_path)
    assert [item.cell.cell_id for item in a] != [item.cell.cell_id for item in b]


def test_planner_rotates_providers_uniformly(tmp_path: Path) -> None:
    plan = build_plan(task="sglb_08", n=6, providers="anthropic,openai,google", seed=0, base_dir=tmp_path)
    assert [item.provider for item in plan] == ["anthropic", "openai", "google", "anthropic", "openai", "google"]


def test_parse_providers_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        parse_providers("openai,nope")


def test_prompt_sglb_08_contains_tone_label() -> None:
    cell = cells_for("sglb_08")[0]
    prompt = render_prompt(cell)
    text = "\n".join(message["content"] for message in prompt.messages)
    assert cell.params["tone"] in text
    assert "Gold label payload" in text


def test_prompt_sglb_12_contains_all_issue_labels() -> None:
    cell = cells_for("sglb_12")[0]
    text = "\n".join(message["content"] for message in render_prompt(cell).messages)
    for label in cell.label["labels"]:
        assert label in text


def test_prompt_sglb_15_contains_constraint_payload() -> None:
    cell = cells_for("sglb_15")[0]
    text = "\n".join(message["content"] for message in render_prompt(cell).messages)
    for constraint in cell.label["constraints"]:
        assert constraint["kind"] in text


def test_generator_shim_counts_calls_per_model(tmp_path: Path) -> None:
    clients = {
        "anthropic": MockLLM("anthropic"),
        "openai": MockLLM("openai"),
        "google": MockLLM("google"),
    }
    generator = SyntheticGenerator(clients=clients)
    plan = build_plan(task="sglb_08", n=3, providers="anthropic,openai,google", seed=0, base_dir=tmp_path)
    for item in plan:
        asyncio.run(generator.generate_body(item))
    assert generator.call_counts == {"anthropic": 1, "openai": 1, "google": 1}
    assert all(client.calls == 1 for client in clients.values())


def test_case_metadata_contains_required_audit_fields(tmp_path: Path) -> None:
    item = build_plan(task="sglb_12", n=1, providers="mock", seed=9, base_dir=tmp_path)[0]
    case = case_from_body(item=item, body="scenario", seed=9)
    metadata = case["metadata"]
    required = {
        "generator_model",
        "generator_version",
        "prompt_version",
        "seed",
        "generation_timestamp",
        "taxonomy_cell",
        "data_tier",
    }
    assert required <= set(metadata)
    assert metadata["data_tier"] == "synthetic"
    assert metadata["review_stage"] == "candidate"
    assert "quality" in metadata


def test_generate_candidate_writes_yaml_candidate(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=3, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=3, generator=SyntheticGenerator()))
    assert path.exists()
    case = _read_case(path)
    assert case["expected_output"]["labels"]
    assert case["metadata"]["_human_review_status"] == "pending"


def test_cli_dry_run_produces_no_llm_calls_or_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main([
        "generate",
        "--task",
        "sglb_08",
        "--n",
        "2",
        "--providers",
        "mock",
        "--dry-run",
        "--base-dir",
        str(tmp_path),
    ])
    assert rc == 0
    assert "estimated_cost_usd" in capsys.readouterr().out
    assert not list(tmp_path.glob("**/*.yaml"))


def test_cli_max_cost_cap_aborts_before_generation(tmp_path: Path) -> None:
    rc = cli.main([
        "generate",
        "--task",
        "sglb_08",
        "--n",
        "2",
        "--providers",
        "openai",
        "--max-cost-usd",
        "0.001",
        "--base-dir",
        str(tmp_path),
    ])
    assert rc == 2
    assert not list(tmp_path.glob("**/*.yaml"))


def test_cli_plan_prints_requested_matrix(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["plan", "--task", "sglb_08", "--n", "20", "--dry-run", "--base-dir", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["items"]) == 20


def test_cli_mock_generate_writes_candidates_under_base_dir(tmp_path: Path) -> None:
    rc = cli.main([
        "generate",
        "--task",
        "sglb_08",
        "--n",
        "2",
        "--providers",
        "mock",
        "--no-review-gate",
        "--base-dir",
        str(tmp_path),
    ])
    assert rc == 0
    candidates = sorted((tmp_path / "sglb_08_clause_tone_candidates").glob("*.yaml"))
    assert len(candidates) == 2
    assert all(_read_case(path)["metadata"]["review_status"] == "pending" for path in candidates)


def test_review_approve_records_state_and_reviewer(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    entry = record_decision(fixture_path=path, decision="approve", reviewer="reviewer-a")
    case = _read_case(path)
    assert entry["status"] == "approved"
    assert case["metadata"]["review_status"] == "approved"
    assert case["metadata"]["_human_review"]["reviewer"] == "reviewer-a"


def test_review_reject_and_needs_edit_transitions(tmp_path: Path) -> None:
    item = build_plan(task="sglb_12", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    record_decision(fixture_path=path, decision="reject", reviewer="reviewer-a")
    assert _read_case(path)["metadata"]["review_status"] == "rejected"
    record_decision(fixture_path=path, decision="needs_edit", reviewer="reviewer-a")
    assert _read_case(path)["metadata"]["review_status"] == "needs_edit"


def test_resolve_fixture_by_slug(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    assert resolve_fixture(item.slug, task="sglb_08", base_dir=tmp_path) == path


def test_promoter_refuses_unreviewed_candidates(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    result = promote_task(task="sglb_08", base_dir=tmp_path)
    assert result["promoted"] == []
    assert result["skipped"]
    assert path.exists()


def test_promoter_moves_approved_candidate_and_writes_audit(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    record_decision(fixture_path=path, decision="approve", reviewer="reviewer-a")
    result = promote_task(task="sglb_08", base_dir=tmp_path)
    reviewed_dir = tmp_path / "sglb_08_clause_tone_reviewed"
    target = reviewed_dir / path.name
    assert not path.exists()
    assert target.exists()
    assert result["promoted"]
    audit_path = reviewed_dir / AUDIT_LOG
    audit = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    required = {"generator_model", "generator_version", "prompt_version", "seed", "taxonomy_cell", "reviewer"}
    assert required <= set(audit)
    assert (reviewed_dir / AGGREGATE_DATASET).exists()


def test_synthetic_tasks_are_registered() -> None:
    assert {"sglb_08", "sglb_12", "sglb_15"} <= set(TASKS)


def test_reviewed_sglb_08_dataset_scores_with_harness(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    record_decision(fixture_path=path, decision="approve", reviewer="reviewer-a")
    result = promote_task(task="sglb_08", base_dir=tmp_path)
    summary = asyncio.run(
        run(
            workflow="sglb_08",
            dataset_path=result["aggregate_dataset"],
            evaluators=["multi_label_f1"],
            strict=True,
        )
    )
    assert summary.data_tier == "synthetic"
    assert summary.to_dict()["data_tier"] == "synthetic"
    assert summary.per_evaluator_mean()["multi_label_f1"] == pytest.approx(1.0)


def test_reviewed_sglb_15_dataset_scores_constraints(tmp_path: Path) -> None:
    item = build_plan(task="sglb_15", n=1, providers="mock", seed=4, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=4, generator=SyntheticGenerator()))
    record_decision(fixture_path=path, decision="approve", reviewer="reviewer-a")
    result = promote_task(task="sglb_15", base_dir=tmp_path)
    summary = asyncio.run(
        run(
            workflow="sglb_15",
            dataset_path=result["aggregate_dataset"],
            evaluators=["constraint_sat"],
            strict=True,
        )
    )
    assert summary.data_tier == "synthetic"
    assert summary.per_evaluator_mean()["constraint_sat"] == pytest.approx(1.0)


def test_estimate_cost_counts_mock_as_zero(tmp_path: Path) -> None:
    plan = build_plan(task="sglb_08", n=5, providers="mock", seed=0, base_dir=tmp_path)
    assert estimate_cost_usd(plan) == 0.0


def test_status_reports_candidate_and_reviewed_counts(tmp_path: Path) -> None:
    plan = build_plan(task="sglb_08", n=2, providers="mock", seed=1, base_dir=tmp_path)
    for item in plan:
        asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    record_decision(fixture_path=plan[0].candidate_path, decision="approve", reviewer="reviewer-a")
    promote_task(task="sglb_08", base_dir=tmp_path)
    status = status_for_task(task="sglb_08", base_dir=tmp_path)
    assert status["candidate_counts"] == {"pending": 1}
    assert status["reviewed_total"] == 1
    assert status["aggregate_exists"] is True


def test_show_fixture_exposes_label_body_and_metadata(tmp_path: Path) -> None:
    item = build_plan(task="sglb_12", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    shown = show_fixture(fixture=path.name, task="sglb_12", base_dir=tmp_path)
    assert shown["case_name"] == item.slug
    assert shown["expected_output"]["labels"] == item.cell.label["labels"]
    assert "Mock synthetic body" in shown["body"]
    assert shown["metadata"]["data_tier"] == "synthetic"
    assert "quality" in shown


def test_validate_task_accepts_pending_candidate_and_reviewed_aggregate(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    path = asyncio.run(generate_candidate(item=item, seed=1, generator=SyntheticGenerator()))
    assert validate_task(task="sglb_08", base_dir=tmp_path)["ok"] is True
    record_decision(fixture_path=path, decision="approve", reviewer="reviewer-a")
    promote_task(task="sglb_08", base_dir=tmp_path)
    result = validate_task(task="sglb_08", base_dir=tmp_path)
    assert result["ok"] is True
    assert result["reviewed_count"] == 1


def test_validate_task_rejects_missing_audit_metadata(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "sglb_08_clause_tone_candidates"
    candidate_dir.mkdir()
    bad = candidate_dir / "bad.yaml"
    bad.write_text(
        yaml.safe_dump(
            {
                "cases": [
                    {
                        "name": "bad",
                        "inputs": {"clause_text": "x", "clause_type": "Force Majeure"},
                        "expected_output": {"labels": ["standard"]},
                        "metadata": {"data_tier": "synthetic", "sglb_task": "sglb_08", "review_stage": "candidate"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = validate_task(task="sglb_08", base_dir=tmp_path)
    assert result["ok"] is False
    assert any("missing metadata fields" in error["message"] for error in result["errors"])


def test_quality_detects_prompt_leakage_in_clause(tmp_path: Path) -> None:
    item = build_plan(task="sglb_08", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    case = case_from_body(
        item=item,
        body="Gold label payload: labels standard. Return only the clause text.",
        seed=1,
    )
    report = check_case_quality(case)
    assert report.ok is False
    assert any("prompt leakage" in error for error in report.errors)


def test_quality_detects_sglb_12_machine_label_leakage(tmp_path: Path) -> None:
    item = build_plan(task="sglb_12", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    case = case_from_body(
        item=item,
        body="The scenario triggers pdpa.protection_obligation and ea.notice_period_breach.",
        seed=1,
    )
    report = check_case_quality(case)
    assert report.ok is False
    assert any("machine-readable issue labels" in error for error in report.errors)


def test_quality_detects_sglb_15_constraint_mismatch(tmp_path: Path) -> None:
    item = build_plan(task="sglb_15", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    case = case_from_body(item=item, body="Draft a short agreement brief for Acme.", seed=1)
    case["inputs"]["constraints"] = []
    report = check_case_quality(case)
    assert report.ok is False
    assert any("constraints differ" in error for error in report.errors)


def test_validate_task_rejects_prompt_leaking_candidate(tmp_path: Path) -> None:
    item = build_plan(task="sglb_12", n=1, providers="mock", seed=1, base_dir=tmp_path)[0]
    case = case_from_body(
        item=item,
        body="Gold issue labels: pdpa.protection_obligation should be returned.",
        seed=1,
    )
    item.candidate_path.parent.mkdir(parents=True)
    item.candidate_path.write_text(yaml.safe_dump({"cases": [case]}, sort_keys=False), encoding="utf-8")
    result = validate_task(task="sglb_12", base_dir=tmp_path)
    assert result["ok"] is False
    assert any("quality error" in error["message"] for error in result["errors"])


def test_cli_status_show_and_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["generate", "--task", "sglb_08", "--n", "1", "--providers", "mock", "--base-dir", str(tmp_path)])
    capsys.readouterr()
    rc = cli.main(["status", "--task", "sglb_08", "--base-dir", str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["candidate_total"] == 1
    slug = next((tmp_path / "sglb_08_clause_tone_candidates").glob("*.yaml")).stem
    rc = cli.main(["show", "--task", "sglb_08", "--fixture", slug, "--base-dir", str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["case_name"] == slug
    rc = cli.main(["validate", "--task", "sglb_08", "--base-dir", str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_load_env_file_sets_missing_keys_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "existing")
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY='from-file'\nGEMINI_API_KEY=from-file\n", encoding="utf-8")
    assert load_env_file(env_file) == 1
    assert preflight_providers("openai")["ok"] is True
    assert preflight_providers("google")["configured_models"]["google"] == "gemini-2.0-flash"
    assert os.environ["GEMINI_API_KEY"] == "existing"


def test_preflight_rejects_missing_real_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = preflight_providers("anthropic")
    assert result["ok"] is False
    assert "ANTHROPIC_API_KEY" in result["missing"]


def test_cli_generate_real_provider_missing_key_aborts_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = cli.main([
        "generate",
        "--task",
        "sglb_08",
        "--n",
        "1",
        "--providers",
        "anthropic",
        "--no-env-file",
        "--base-dir",
        str(tmp_path),
    ])
    assert rc == 2
    assert not list(tmp_path.glob("**/*.yaml"))
