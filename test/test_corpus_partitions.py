import copy

import pytest

from scripts.corpus_partitions import SCENARIO_GROUPS, reservation, sampling_slot, validate_partition_records
from scripts.model_corpus import evaluate_records


def test_reserved_groups_are_disjoint_and_not_collected():
    assert not reservation()["holdout_established"]
    a, b = ({g["id"] for g in groups} for groups in SCENARIO_GROUPS.values())
    assert not a & b
    slot = sampling_slot({"split": "holdout", "groups": SCENARIO_GROUPS["holdout"]}, 7)
    assert slot["template_group"] == "holdout-research-v1"


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
