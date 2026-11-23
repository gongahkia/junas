import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import fresh_holdout as fresh
from scripts import model_corpus as corpus
from scripts.corpus_partitions import (
    FRESH_HOLDOUT_GROUPS,
    FRESH_HOLDOUT_V3_GROUPS,
    FRESH_HOLDOUT_V5_GROUPS,
    FRESH_HOLDOUT_V6_GROUPS,
    SCENARIO_GROUPS,
    check_exclusions,
    exclusion_registry,
    sampling_slot,
)
from scripts.corpus_report import release_holdout
from test.test_model_corpus import QUADRANT_TEXT, config, quadrant_annotation


def test_new_scenarios_are_disjoint_and_old_reservations_still_validate():
    existing = {g["id"] for groups in SCENARIO_GROUPS.values() for g in groups}
    v2 = {g["id"] for g in FRESH_HOLDOUT_GROUPS}
    v3 = {g["id"] for g in FRESH_HOLDOUT_V3_GROUPS}
    assert not existing & v2 and not existing & v3 and not v2 & v3
    for groups in (SCENARIO_GROUPS["holdout"], FRESH_HOLDOUT_GROUPS, FRESH_HOLDOUT_V3_GROUPS):
        sampling = {"split": "holdout", "groups": groups}
        assert len({sampling_slot(sampling, i)["template_group"] for i in range(16)}) == 4
    cfg = json.loads((fresh.ROOT / "config/model_corpus.holdout-v2.json").read_text())
    corpus.validate_config(cfg)
    assert cfg["documents"] == 40 and set(cfg["quadrant_targets"].values()) == {10}
    assert set(cfg["entity_targets"].values()) == {3}
    assert cfg["spending_limit"]["provider_cap_usd"] == "3"
    v3cfg = json.loads((fresh.ROOT / "config/model_corpus.holdout-v3.json").read_text())
    corpus.validate_config(v3cfg)
    assert v3cfg["sampling"]["groups"] == FRESH_HOLDOUT_V3_GROUPS
    assert v3cfg["documents"] == 40 and set(v3cfg["quadrant_targets"].values()) == {10}
    assert set(v3cfg["entity_targets"].values()) == {3}
    assert v3cfg["spending_limit"]["provider_cap_usd"] == "4"
    assert corpus.validate_spending_limit(v3cfg["spending_limit"])["sgd_scenario_ceiling"] == "36.00"
    v5cfg = json.loads((fresh.ROOT / "config/model_corpus.holdout-v5.json").read_text())
    corpus.validate_config(v5cfg)
    assert v5cfg["sampling"]["groups"] == FRESH_HOLDOUT_V5_GROUPS
    v5 = {g["id"] for g in FRESH_HOLDOUT_V5_GROUPS}
    assert not v5 & (existing | v2 | v3)
    for i in range(16):
        assert sampling_slot(v5cfg["sampling"], i)["template_group"] in v5
    assert v5cfg["documents"] == 40 and set(v5cfg["quadrant_targets"].values()) == {10}
    assert set(v5cfg["entity_targets"].values()) == {3}
    assert v5cfg["spending_limit"]["provider_cap_usd"] == "4"
    assert corpus.validate_spending_limit(v5cfg["spending_limit"])["sgd_scenario_ceiling"] == "39.60"


def test_v6_generalization_plan_preserves_targets_models_and_historical_reservations():
    previous = {
        g["id"]
        for groups in [
            *SCENARIO_GROUPS.values(),
            FRESH_HOLDOUT_GROUPS,
            FRESH_HOLDOUT_V3_GROUPS,
            FRESH_HOLDOUT_V5_GROUPS,
        ]
        for g in groups
    }
    cfg = json.loads((fresh.ROOT / "config/model_corpus.holdout-v6.json").read_text())
    old = json.loads((fresh.ROOT / "config/model_corpus.holdout-v5.json").read_text())
    corpus.validate_config(cfg)
    assert cfg["sampling"]["groups"] == FRESH_HOLDOUT_V6_GROUPS
    assert not previous & {g["id"] for g in FRESH_HOLDOUT_V6_GROUPS}
    assert len({sampling_slot(cfg["sampling"], i)["template_group"] for i in range(16)}) == 4
    for key in (
        "documents",
        "quadrant_targets",
        "entity_targets",
        "generator",
        "judges",
        "judge_mode",
        "max_candidates",
    ):
        assert cfg[key] == old[key]
    assert cfg["spending_limit"]["provider_cap_usd"] == "4"
    assert corpus.validate_spending_limit(cfg["spending_limit"])["sgd_scenario_ceiling"] == "43.20"


def test_old_holdout_is_only_fingerprinted_and_all_generated_candidates_are_excluded(tmp_path, monkeypatch):
    fake = tmp_path / "repo"
    (fake / "test").mkdir(parents=True)
    for name in (
        "test_sensitivity.py",
        "test_contextual_identity_scopes.py",
        "test_contextual_mnpi_scopes.py",
        "test_contextual_generalization.py",
        "test_contextual_event_families.py",
        "test_contextual_mnpi_financial_events.py",
    ):
        (fake / "test" / name).write_text('TEXT = "A previous authored source, never a fresh reference."')
    monkeypatch.setattr(fresh, "ROOT", fake)
    monkeypatch.setattr("scripts.check_reliability.cases", lambda: [])
    inherited = exclusion_registry([{"text": "Existing development source 1234"}])
    prior = tmp_path / "prior"
    prior.mkdir()
    old_text = "Previously consumed held source about fictional records 5678"
    corpus.write_new(
        prior / "candidate-1.json",
        {"text": old_text, "split": "holdout", "template_group": "old", "consensus": "never inspect labels"},
    )
    generated = "Rejected generated candidate, still prohibited for reuse 9988"
    raw = {
        "request": {"text": {"format": {"name": "generator"}}},
        "response": {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps({"text": generated})}]}
            ],
        },
    }
    corpus.write_new(prior / "response-1.json", raw)
    with (
        patch("httpx.Client", side_effect=AssertionError("network forbidden")),
        patch.object(corpus, "evaluate_records", side_effect=AssertionError("old sources cannot be evaluated")),
    ):
        registry, audit = fresh.build_exclusions(inherited, [prior])
    assert audit["prior_candidate_sources_fingerprinted"] == 1
    assert audit["prior_generator_responses_fingerprinted"] == 1
    for text in (old_text, generated, "Existing development source 9876"):
        with pytest.raises(ValueError, match="conflicts"):
            check_exclusions(text, "fresh", registry)
    used = exclusion_registry(
        [{"text": "Already generated v3 source", "template_group": FRESH_HOLDOUT_V3_GROUPS[0]["id"]}]
    )
    with pytest.raises(ValueError, match="families already used"):
        fresh.build_exclusions(used, [prior], FRESH_HOLDOUT_V3_GROUPS)
    v2used = exclusion_registry([{"text": "Consumed v2 source", "template_group": FRESH_HOLDOUT_GROUPS[0]["id"]}])
    fresh.build_exclusions(v2used, [prior], FRESH_HOLDOUT_V3_GROUPS)


@pytest.fixture(scope="module")
def prepared_master(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("fresh-master")
    # a private four-document transport fixture; production config remains forty documents.
    fake = tmp_path / "repo"
    fresh.snapshot(fresh.ROOT, fake)
    cfg = config(documents=4)
    cfg["sampling"] = {"split": "holdout", "groups": FRESH_HOLDOUT_GROUPS}
    cfg["exclusion_registry_sha256"] = "0" * 64
    cfg["spending_limit"] = json.loads((fresh.ROOT / "config/model_corpus.holdout-v2.json").read_text())[
        "spending_limit"
    ]
    (fake / "config/model_corpus.holdout-v2.json").write_text(json.dumps(cfg))
    baseline = tmp_path / "old"
    fresh.snapshot(fake, baseline)
    with (baseline / "src/junas/review/sensitivity.py").open("a") as stream:
        stream.write("\n# distinct frozen baseline fixture\n")
    registry = exclusion_registry(
        [{"text": "Entirely different prior sample and reserved family", "template_group": "old"}]
    )
    inherited = tmp_path / "inherited.json"
    inherited.write_text(json.dumps(registry))
    target = tmp_path / "bundle"
    with (
        patch.object(fresh, "ROOT", fake),
        patch.object(fresh, "build_exclusions", return_value=(registry, {"test_fixture": True})),
        patch("httpx.Client", side_effect=AssertionError("preparation cannot use network")),
    ):
        proposal = fresh.prepare(target, baseline, inherited, [])
    assert proposal["paid_calls_made"] == 0 and not proposal["live_calls_authorized"]
    assert not (target / "authorization.json").exists() and not (target / "run").exists()
    fresh.verify_bundle(target)
    return target


@pytest.fixture
def bundle(tmp_path, prepared_master):
    # only immutable fixture data is shared; drift tests receive private code/config copies.
    def copy(source, target):
        if Path(source).suffix == ".csv":
            return os.link(source, target)
        return shutil.copyfile(source, target)

    target = tmp_path / "bundle"
    shutil.copytree(prepared_master, target, copy_function=copy)
    return target


@pytest.mark.parametrize(
    "name",
    [
        "config.json",
        "targets.json",
        "exclusions.json",
        "source/scripts/model_corpus.py",
        "baseline/src/junas/review/sensitivity.py",
    ],
)
def test_bundle_refuses_any_frozen_input_drift_before_network(bundle, name):
    with (bundle / name).open("a") as stream:
        stream.write(" ")
    with patch("httpx.Client", side_effect=AssertionError("network forbidden")):
        with pytest.raises(ValueError, match="drift"):
            fresh.verify_bundle(bundle)


def staged_records(bundle):
    cfg = json.loads((bundle / "config.json").read_text())
    run = bundle / "run"
    run.mkdir()
    records = []
    for i, (q, text) in enumerate(QUADRANT_TEXT.items()):
        raw = quadrant_annotation(q, text)
        records.append(
            {
                "document_id": f"held-{i}",
                "text": text,
                "text_sha256": corpus.input_identity(text),
                "split": "holdout",
                "template_group": FRESH_HOLDOUT_GROUPS[i]["id"],
                "accepted": True,
                "status": "completed",
                "annotations": [{"output": raw}] * 3,
                "consensus": corpus.consensus([raw] * 3),
            }
        )
    corpus.write_new(
        run / "manifest.json",
        {
            "sampling": cfg["sampling"],
            "config": cfg,
            "config_sha256": corpus.identity(cfg),
            "reproducibility": {"classifier_sha256": fresh.runtime_hash(bundle / "source")},
        },
    )
    (run / "combined-records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return records


def test_paired_release_uses_same_records_and_consumes_before_any_metric(bundle):
    records = staged_records(bundle)
    original = corpus.evaluate_records

    def evaluate(rows):
        assert (bundle / "run/holdout-consumed.json").exists()
        assert [r["text_sha256"] for r in rows] == [r["text_sha256"] for r in records]
        return original(rows)

    with patch("scripts.corpus_report.evaluate_records", side_effect=evaluate):
        result = fresh.evaluate(bundle)
    assert result["documents"] == 4
    assert result["records_sha256"] == corpus.identity(records)
    assert all(delta == 0 for delta in result["delta"].values())
    with pytest.raises((FileExistsError, ValueError)):
        fresh.evaluate(bundle)


def test_recovered_segment_can_be_released_once_but_not_outside_the_bundle(bundle):
    staged_records(bundle)
    resumed = bundle / "run-002"
    (bundle / "run").rename(resumed)
    with pytest.raises(ValueError, match="remain in the frozen bundle"):
        fresh.evaluate(bundle, bundle.parent / "other-run")
    assert not (resumed / "holdout-consumed.json").exists()
    result = fresh.evaluate(bundle, resumed)
    assert result["documents"] == 4 and (resumed / "holdout-consumed.json").exists()
    with pytest.raises((FileExistsError, ValueError)):
        fresh.evaluate(bundle, resumed)


@pytest.mark.parametrize("groups", [FRESH_HOLDOUT_V3_GROUPS, FRESH_HOLDOUT_V6_GROUPS])
def test_custom_reserved_config_is_bound_before_snapshotting(tmp_path, prepared_master, groups):
    config_path = tmp_path / "reserved-config.json"
    cfg = json.loads((prepared_master / "config.json").read_text())
    cfg["sampling"]["groups"] = groups
    cfg["spending_limit"].update(provider_cap_usd="4", prior_cost_reserve_usd="16")
    config_path.write_text(json.dumps(cfg))
    registry = json.loads((prepared_master / "exclusions.json").read_text())
    output = tmp_path / "reserved-bundle"
    with (
        patch.object(fresh, "ROOT", prepared_master / "source"),
        patch.object(fresh, "build_exclusions", return_value=(registry, {})) as exclusions,
        patch("httpx.Client", side_effect=AssertionError("offline preparation")),
    ):
        result = fresh.prepare(
            output, prepared_master / "baseline", prepared_master / "exclusions.json", [], config_path
        )
    assert exclusions.call_args.args[2] == groups
    assert result["proposed_cap_usd"] == "4"
    bound = json.loads((output / "config.json").read_text())
    assert bound["sampling"]["groups"] == groups
    assert "all frozen engineering targets pass" in result["predeclared_evaluation_policy"]["success_condition"]
    assert json.loads((output / "frozen.json").read_text())["config_sha256"] == corpus.identity(bound)
    assert not (output / "authorization.json").exists() and not (output / "run").exists()


def test_release_rechecks_config_bound_fingerprints_before_consuming(bundle):
    staged_records(bundle)
    with pytest.raises(ValueError, match="registry mismatch"):
        release_holdout(
            bundle / "run", [], bundle / "result.json", exclusions=exclusion_registry([{"text": "Wrong registry"}])
        )
    assert not (bundle / "run/holdout-consumed.json").exists()


def test_bad_authorization_refuses_before_loading_key_or_constructing_client(bundle):
    bad = bundle / "not-authorized.json"
    bad.write_text("{}")
    with (
        patch.object(corpus, "load_api_key", side_effect=AssertionError("must not load key")),
        patch("httpx.Client", side_effect=AssertionError("must not construct client")),
    ):
        with pytest.raises(ValueError):
            fresh.execute(bundle, bad, Path("unused.env"))


def test_detector_environment_change_refuses_before_spending(bundle, monkeypatch):
    monkeypatch.setenv("JUNAS_SEMANTIC_ENABLED", "changed-after-freezing")
    with pytest.raises(ValueError, match="environment drift"):
        fresh.verify_bundle(bundle)


def test_budget_stop_keeps_holdout_unreleased(bundle):
    from test.test_model_corpus import authorization

    cfg = json.loads((bundle / "config.json").read_text())
    auth = bundle / "test-authorization.json"
    auth.write_text(json.dumps(authorization(cfg)))
    result = {
        "status": "stopped",
        "stop_reason": "BudgetExhausted",
        "accepted_documents": 0,
        "charged_or_reserved_ceiling_usd": "0.99",
    }
    with (
        patch.object(corpus, "load_api_key"),
        patch.object(corpus, "run", return_value=result),
        patch.object(fresh, "evaluate", side_effect=AssertionError("incomplete holdout cannot be evaluated")),
    ):
        assert fresh.execute(bundle, auth, Path("unused.env"))["validation_passed"] is None
    assert not (bundle / "paired-evaluation.json").exists()


def test_automated_execution_continues_uncertain_candidates_with_the_same_authorization(bundle):
    from test.test_model_corpus import authorization

    cfg = json.loads((bundle / "config.json").read_text())
    auth = bundle / "test-authorization.json"
    auth.write_text(json.dumps(authorization(cfg)))
    stopped = {
        "status": "stopped",
        "stop_reason": "UncertainRequest",
        "attempted_candidates": 1,
        "accepted_documents": 0,
        "charged_or_reserved_ceiling_usd": "0.08",
    }
    done = {**stopped, "status": "completed", "stop_reason": None, "accepted_documents": 4}
    with (
        patch.object(corpus, "load_api_key"),
        patch.object(corpus, "run", side_effect=[stopped, done]) as run,
        patch.object(fresh, "evaluate", return_value={"passed": True}) as evaluate,
    ):
        result = fresh.execute(bundle, auth, Path("unused.env"))
    assert result["validation_passed"] is True and result["final_segment"] == "run-002"
    assert run.call_count == 2 and run.call_args.kwargs["resume_from"] == bundle / "run"
    assert run.call_args_list[0].args[:2] == run.call_args_list[1].args[:2]
    evaluate.assert_called_once_with(bundle, bundle / "run-002")


def test_automated_execution_stops_after_three_consecutive_uncertain_candidates(bundle):
    from test.test_model_corpus import authorization

    cfg = json.loads((bundle / "config.json").read_text())
    auth = bundle / "test-authorization.json"
    auth.write_text(json.dumps(authorization(cfg)))
    reports = [
        {
            "status": "stopped",
            "stop_reason": "UncertainRequest",
            "attempted_candidates": i,
            "accepted_documents": 0,
            "charged_or_reserved_ceiling_usd": str(i / 10),
        }
        for i in range(1, 4)
    ]
    with (
        patch.object(corpus, "load_api_key"),
        patch.object(corpus, "run", side_effect=reports) as run,
        patch.object(fresh, "evaluate", side_effect=AssertionError("incomplete holdout")),
    ):
        result = fresh.execute(bundle, auth, Path("unused.env"))
    assert result["controller_stop_reason"] == "three_consecutive_uncertain_candidates"
    assert result["validation_passed"] is None and run.call_count == 3
