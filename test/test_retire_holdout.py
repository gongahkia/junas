import copy
import json

import pytest

from scripts.model_corpus import identity
from scripts.retire_holdout import retire
from test.test_sensitivity_development import records


def consumed(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    data = [dict(records()[0], split="holdout")]
    (run / "combined-records.jsonl").write_text(json.dumps(data[0]) + "\n")
    (run / "holdout-consumed.json").write_text(
        json.dumps({"status": "consumed_for_evaluation", "records_sha256": identity(data)})
    )
    return run, data


def test_retirement_is_lossless_and_explicitly_development_only(tmp_path):
    run, data = consumed(tmp_path)
    originals = {p.name: p.read_bytes() for p in run.iterdir()}
    output = tmp_path / "development.jsonl"
    report = retire(run, output)
    exported = json.loads(output.read_text())
    assert exported.pop("development_provenance")["fresh_validation_eligible"] is False
    assert exported.pop("split") == "development"
    expected = copy.deepcopy(data[0])
    expected.pop("split")
    assert exported == expected
    assert report["documents"] == 1 and not report["fresh_validation_eligible"]
    assert {p.name: p.read_bytes() for p in run.iterdir()} == originals
    with pytest.raises(ValueError, match="already exists"):
        retire(run, output)


def test_retirement_refuses_unconsumed_or_modified_references(tmp_path):
    run, data = consumed(tmp_path)
    marker = run / "holdout-consumed.json"
    marker.write_text(json.dumps({"status": "reserved"}))
    with pytest.raises(ValueError, match="unconsumed"):
        retire(run, tmp_path / "not-exported.jsonl")
    marker.write_text(json.dumps({"status": "consumed_for_evaluation", "records_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="identity mismatch"):
        retire(run, tmp_path / "not-exported.jsonl")
    data[0]["consensus"]["quadrant"] = "both"
    (run / "combined-records.jsonl").write_text(json.dumps(data[0]) + "\n")
    marker.write_text(json.dumps({"status": "consumed_for_evaluation", "records_sha256": identity(data)}))
    with pytest.raises(ValueError, match="consensus changed"):
        retire(run, tmp_path / "not-exported.jsonl")
