"""
Legacy Model-2 inference shim.

Canonical implementation lives in layer4-classification/model-2/inference.py.
"""

import importlib.util
from pathlib import Path


def _load_canonical():
    path = Path(__file__).resolve().parents[1] / "layer4-classification" / "model-2" / "inference.py"
    spec = importlib.util.spec_from_file_location("layer4_model2_inference", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load canonical model-2 inference from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_canonical()

CHECKPOINT_DIR = _mod.CHECKPOINT_DIR
MAX_SEQ_LEN = _mod.MAX_SEQ_LEN
THRESHOLD = _mod.THRESHOLD
Model2Result = _mod.Model2Result
BERTSeverityClassifier = _mod.BERTSeverityClassifier
