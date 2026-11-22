import copy

import pytest

from scripts.corpus_partitions import SCENARIO_GROUPS, reservation, sampling_slot, validate_partition_records
from scripts.model_corpus import evaluate_records


def test_reserved_groups_are_disjoint_and_not_collected():
    assert not reservation()["holdout_established"]
    a, b = ({g["id"] for g in groups} for groups in SCENARIO_GROUPS.values())
    assert not a & b
    slot = sampling_slot({"split": "holdout", "groups": SCENARIO_GROUPS["holdout"]}, 7)
    assert slot["template_group"] == "holdout-benefits-v1"


def test_partition_check_rejects_number_substitution_and_group_leakage():
    dev = [{"text": "Account 1234", "template_group": "a"}]
    held = [{"text": "Account 9876", "template_group": "b", "split": "holdout"}]
    with pytest.raises(ValueError, match="contamination"):
        validate_partition_records(dev, held)
    held[0]["text"] = "Unrelated prose"
    validate_partition_records(dev, held)
    held[0]["template_group"] = "a"
    with pytest.raises(ValueError, match="contamination"):
        validate_partition_records(dev, held)


def test_development_evaluation_does_not_open_holdout_labels():
    record = {"split": "holdout", "status": "completed", "accepted": True, "consensus": None}
    assert evaluate_records([record])["pii"]["status"] == "unavailable"
    changed = copy.deepcopy(SCENARIO_GROUPS["holdout"])
    changed[0]["id"] = "dev-intake-v1"
    with pytest.raises(ValueError, match="reserved"):
        sampling_slot({"split": "holdout", "groups": changed}, 0)


def test_near_duplicates_reuse_pilot_contamination_heuristic():
    from scripts.corpus_partitions import check_exclusions, exclusion_registry

    text = (
        "A confidential corporate board memorandum considers a future transaction "
        "with extensive explanatory notes for counsel."
    )
    registry = exclusion_registry([{"text": text}])
    with pytest.raises(ValueError, match="conflicts"):
        check_exclusions(text + " Extra.", "fresh-group", registry)


def test_prepared_holdout_refuses_missing_registry_before_any_network(tmp_path, monkeypatch):
    import json

    from scripts import model_corpus as c
    from test.test_model_corpus import authorization

    config = json.loads((c.ROOT / "config/model_corpus.holdout.json").read_text())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="exclusion registry"):
        c.run(config, authorization(config), tmp_path / "no-registry")
    assert not (tmp_path / "no-registry").exists()


def test_scenario_group_cycle_does_not_assign_one_group_to_each_quadrant():
    sampling = {"split": "holdout", "groups": SCENARIO_GROUPS["holdout"]}
    groups = [sampling_slot(sampling, i)["template_group"] for i in range(16)]
    assert len(set(groups)) == 4
    assert all(len(set(groups[start : start + 4])) == 1 for start in range(0, 16, 4))
