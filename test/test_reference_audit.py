import json

import pytest

from scripts.audit_model_references import audit
from test.test_retire_holdout import consumed


def test_audit_preserves_consumed_references_and_rejects_mutation(tmp_path):
    run, _ = consumed(tmp_path)
    originals = {p.name: p.read_bytes() for p in run.iterdir()}
    result = audit(run)
    assert result["candidates"] == 1 and not result["reference_labels_changed"]
    assert result["calibrated_confidence"] is None
    assert {p.name: p.read_bytes() for p in run.iterdir()} == originals
    (run / "holdout-consumed.json").write_text(json.dumps({"status": "reserved"}))
    with pytest.raises(ValueError, match="unconsumed"):
        audit(run)
    (run / "holdout-consumed.json").write_bytes(originals["holdout-consumed.json"])
    (run / "combined-records.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="identity"):
        audit(run)
