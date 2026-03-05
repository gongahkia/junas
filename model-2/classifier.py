"""
Legacy Model-2 training shim.

Canonical implementation lives in layer4-classification/model-2/classifier.py.
"""

import importlib.util
from pathlib import Path


def _load_canonical():
    path = Path(__file__).resolve().parents[1] / "layer4-classification" / "model-2" / "classifier.py"
    spec = importlib.util.spec_from_file_location("layer4_model2_classifier", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load canonical model-2 classifier from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_canonical()
train = _mod.train


if __name__ == "__main__":
    import sys

    train_path = sys.argv[1] if len(sys.argv) > 1 else "data/train.csv"
    val_path = sys.argv[2] if len(sys.argv) > 2 else None
    train(train_path, val_path)
