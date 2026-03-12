#!/usr/bin/env python3
"""Validate training data batch JSON files against the TrainingBatch schema."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import ValidationError
from backend.schemas import TrainingBatch

def validate_file(path: str) -> bool:
    try:
        raw = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        print(f"[FAIL] {path}: invalid JSON — {e}")
        return False
    try:
        batch = TrainingBatch.model_validate(raw)
        print(f"[OK] {path} ({len(batch.documents)} documents)")
        return True
    except ValidationError as e:
        print(f"[FAIL] {path}:")
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            print(f"  {loc}: {err['msg']}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: validate_training_data.py <file.json> [...]")
        sys.exit(1)
    results = [validate_file(f) for f in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
