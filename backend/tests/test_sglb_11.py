"""SGLB-11 — perturbations, dataset builder, evaluator, end-to-end run."""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

import pytest
import yaml

from api.services.sal_citation import validate_citation
from benchmark.dataset_builders.sglb_11 import (
    DEFAULT_POOL_PATH,
    FakeGenerator,
    build_dataset,
    load_real_pool,
)
from benchmark.evaluators import CitationHallucinationF1, EvaluatorContext
from benchmark.perturbations import (
    PERTURBATION_TYPES,
    Citation,
    applicable_perturbations,
    apply,
    case_name_swap,
    composite,
    court_swap,
    page_off,
    parse_citation,
    volume_off,
    wholesale_fabrication,
    year_off,
)
from benchmark.runner import run


REAL_POOL = load_real_pool()


# === Perturbation engine ===


def test_parse_citation_neutral():
    c = parse_citation("[2023] SGCA 5")
    assert c is not None
    assert c.kind == "neutral_case"
    assert c.year == 2023
    assert c.court == "SGCA"
    assert c.case_no == 5


def test_parse_citation_slr_r_with_name():
    c = parse_citation("Spandeck Engineering (S) Pte Ltd v DSTA [2007] 4 SLR(R) 100")
    assert c is not None
    assert c.kind == "slr_r_case"
    assert c.year == 2007
    assert c.volume == 4
    assert c.page == 100


def test_parse_citation_slr_form():
    c = parse_citation("[2015] 1 SLR 1116")
    assert c is not None
    assert c.kind == "slr_case"
    assert c.volume == 1
    assert c.page == 1116


def test_parse_returns_none_on_garbage():
    assert parse_citation("nope") is None


def test_year_off_actually_shifts():
    rng = random.Random(0)
    c = parse_citation("[2023] SGCA 5")
    result = year_off(c, rng)
    assert "[2023]" not in result
    assert "SGCA 5" in result


def test_volume_off_only_on_slr_forms():
    rng = random.Random(0)
    neutral = parse_citation("[2023] SGCA 5")
    with pytest.raises(ValueError):
        volume_off(neutral, rng)


def test_page_off_neutral_changes_case_no():
    rng = random.Random(7)
    c = parse_citation("[2023] SGCA 5")
    out = page_off(c, rng)
    assert "SGCA 5" not in out
    assert out.startswith("[2023]")


def test_court_swap_changes_court_code():
    rng = random.Random(0)
    c = parse_citation("[2023] SGCA 5")
    for _ in range(5):
        out = court_swap(c, rng)
        assert "SGCA" not in out
        assert "[2023]" in out


def test_court_swap_rejects_slr_form():
    rng = random.Random(0)
    c = parse_citation("[2015] 1 SLR 1116")
    with pytest.raises(ValueError):
        court_swap(c, rng)


def test_case_name_swap_changes_name_preserves_body():
    rng = random.Random(3)
    c = parse_citation("Gay Choon Ing v Loh Sze Ti Terence Peter [2009] 2 SLR(R) 332")
    out = case_name_swap(c, rng)
    assert "[2009] 2 SLR(R) 332" in out
    assert "Gay Choon" not in out


def test_wholesale_fabrication_is_grammar_conformant():
    rng = random.Random(42)
    for _ in range(20):
        out = wholesale_fabrication(rng)
        # Should pass the SAL grammar check — the perturbation is
        # grammar-conformant by construction; only the case identity is fake.
        v = validate_citation(out.split(" v ")[-1] if " v " in out else out)
        # The whole-string check may fail because case names aren't
        # validated; the citation body should be.
        body = out
        if " v " in body:
            body = body.split("[")[-1]
            body = "[" + body
        assert validate_citation(body).valid, f"non-conformant fabrication: {out!r}"


def test_composite_applies_two_perturbations():
    rng = random.Random(0)
    c = parse_citation("[2023] SGCA 5")
    out = composite(c, rng)
    # year and (court for neutral) should both have changed.
    assert "[2023]" not in out
    assert "SGCA 5" not in out


def test_applicable_perturbations_excludes_court_swap_for_slr():
    c = parse_citation("[2015] 1 SLR 1116")
    types = applicable_perturbations(c)
    assert "court_swap" not in types
    assert "volume_off" in types


def test_applicable_perturbations_excludes_volume_off_for_neutral():
    c = parse_citation("[2023] SGCA 5")
    types = applicable_perturbations(c)
    assert "volume_off" not in types
    assert "court_swap" in types


def test_apply_dispatch_covers_all_types():
    rng = random.Random(123)
    c = parse_citation("[2023] SGCA 5")
    for ptype in PERTURBATION_TYPES:
        if ptype not in applicable_perturbations(c):
            continue
        out = apply(ptype, c, rng)
        assert isinstance(out, str) and out


# === Real pool + verifier ===


def test_real_pool_loads():
    assert len(REAL_POOL) >= 40
    assert all(rc.citation and rc.domain for rc in REAL_POOL)


def test_real_pool_yaml_path_matches_constant():
    assert DEFAULT_POOL_PATH.exists()


def test_fake_generator_never_collides_with_real_pool():
    rng = random.Random(42)
    gen = FakeGenerator(REAL_POOL, rng)
    real_set = {" ".join(rc.citation.split()).rstrip(".").lower() for rc in REAL_POOL}
    for _ in range(100):
        for ptype in PERTURBATION_TYPES:
            try:
                fake = gen.generate(ptype)
            except RuntimeError:
                # Some perturbations may need many retries; allowed.
                continue
            assert " ".join(fake.citation.split()).rstrip(".").lower() not in real_set, (
                f"perturbation {ptype} collided with real pool: {fake.citation!r}"
            )


def test_fake_generator_emits_correct_perturbation_type():
    rng = random.Random(99)
    gen = FakeGenerator(REAL_POOL, rng)
    for ptype in PERTURBATION_TYPES:
        try:
            fake = gen.generate(ptype)
        except RuntimeError:
            continue
        assert fake.perturbation_type == ptype


# === Dataset builder ===


def test_build_dataset_is_deterministic_for_seed():
    a = build_dataset(seed=42, n_passages=10)
    b = build_dataset(seed=42, n_passages=10)
    assert a == b


def test_build_dataset_covers_every_perturbation_type():
    dataset = build_dataset(seed=42, n_passages=40)
    seen: set[str] = set()
    for case in dataset["cases"]:
        for entry in case["metadata"]["citation_index"]:
            if entry["is_fake"]:
                seen.add(entry["perturbation"])
    assert seen == set(PERTURBATION_TYPES)


def test_build_dataset_passages_have_balanced_real_fake():
    dataset = build_dataset(seed=42, n_passages=20)
    total_real = 0
    total_fake = 0
    for case in dataset["cases"]:
        for entry in case["metadata"]["citation_index"]:
            if entry["is_fake"]:
                total_fake += 1
            else:
                total_real += 1
    # Roughly balanced — not strict 50/50 but within wide bounds.
    assert total_fake > 0 and total_real > 0
    ratio = total_fake / (total_real + total_fake)
    assert 0.2 <= ratio <= 0.7


def test_shipped_smoke_dataset_yaml_loads():
    path = (
        Path(__file__).parent.parent
        / "benchmark"
        / "datasets"
        / "sglb_11_hallucination_smoke.yaml"
    )
    assert path.exists()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert len(raw["cases"]) >= 30
    # Every case carries citation_index provenance.
    for case in raw["cases"]:
        assert "citation_index" in case["metadata"]


# === Evaluator ===


def _ctx(output: str, expected: dict | None = None, metadata: dict | None = None) -> EvaluatorContext:
    return EvaluatorContext(
        case_name="t",
        inputs={},
        expected_output=expected,
        metadata=metadata or {},
        output=output,
    )


def test_citation_hallucination_f1_perfect_match():
    e = CitationHallucinationF1()
    output = '["[2023] SGCA 999"]'
    expected = {"fakes": ["[2023] SGCA 999"]}
    r = asyncio.run(e.evaluate(_ctx(output, expected)))
    assert r.score == pytest.approx(1.0)
    assert r.detail["tp"] == 1


def test_citation_hallucination_f1_zero_when_all_missed():
    e = CitationHallucinationF1()
    expected = {"fakes": ["[2023] SGCA 999", "[2024] SGCA 12345"]}
    r = asyncio.run(e.evaluate(_ctx("[]", expected)))
    assert r.score == 0.0
    assert r.detail["tp"] == 0


def test_citation_hallucination_f1_partial_credit():
    e = CitationHallucinationF1()
    output = '["[2023] SGCA 999"]'
    expected = {"fakes": ["[2023] SGCA 999", "[2024] SGCA 12345"]}
    r = asyncio.run(e.evaluate(_ctx(output, expected)))
    # recall = 0.5, precision = 1.0, f1 = 2/3
    assert r.score == pytest.approx(2 / 3, abs=1e-3)


def test_citation_hallucination_f1_false_positive_on_real():
    e = CitationHallucinationF1()
    output = '["[2023] SGCA 5"]'  # real
    expected = {"fakes": []}
    metadata = {
        "citation_index": [
            {"citation": "[2023] SGCA 5", "is_fake": False, "perturbation": None},
        ]
    }
    r = asyncio.run(e.evaluate(_ctx(output, expected, metadata)))
    assert r.score == 0.0
    assert "false_positive_on_real" in r.detail["per_perturbation"]


def test_citation_hallucination_f1_per_perturbation_breakdown():
    e = CitationHallucinationF1()
    output = '["[2024] SGCA 999"]'
    expected = {"fakes": ["[2024] SGCA 999"]}
    metadata = {
        "citation_index": [
            {"citation": "[2024] SGCA 999", "is_fake": True, "perturbation": "wholesale_fabrication"},
            {"citation": "[2023] SGCA 5", "is_fake": False, "perturbation": None},
        ]
    }
    r = asyncio.run(e.evaluate(_ctx(output, expected, metadata)))
    breakdown = r.detail["per_perturbation"]
    assert "wholesale_fabrication" in breakdown
    assert breakdown["wholesale_fabrication"]["f1"] == pytest.approx(1.0)


def test_citation_hallucination_f1_empty_passage_no_fakes():
    e = CitationHallucinationF1()
    r = asyncio.run(e.evaluate(_ctx("[]", {"fakes": []})))
    # No predictions, no gold = vacuously perfect.
    assert r.score == pytest.approx(1.0)


def test_citation_hallucination_f1_normalises_whitespace_and_trailing_period():
    e = CitationHallucinationF1()
    output = '["[2023] SGCA 999."]'
    expected = {"fakes": ["[2023]  SGCA  999"]}
    r = asyncio.run(e.evaluate(_ctx(output, expected)))
    assert r.score == pytest.approx(1.0)


# === End-to-end harness run ===


def test_oracle_run_against_smoke_dataset_scores_one():
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_11_hallucination_smoke.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_11",
            dataset_path=smoke,
            evaluators=["citation_hallucination_f1"],
            strict=True,
        )
    )
    assert summary.total_cases >= 30
    assert summary.per_evaluator_mean()["citation_hallucination_f1"] == pytest.approx(1.0)
