"""
Legacy clustering shim.

Canonical implementation lives in layer3-clustering/isolation_forest.py.
"""

import importlib.util
from pathlib import Path


def _load_canonical():
    path = Path(__file__).resolve().parents[1] / "layer3-clustering" / "isolation_forest.py"
    spec = importlib.util.spec_from_file_location("layer3_isolation_forest", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load canonical clustering module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_canonical()

CHECKPOINT_DIR = _mod.CHECKPOINT_DIR
CHECKPOINT_PATH = _mod.CHECKPOINT_PATH
CONTAMINATION = _mod.CONTAMINATION
MAX_FEATURES = _mod.MAX_FEATURES
N_ESTIMATORS = _mod.N_ESTIMATORS
MNPIAnomalyDetector = _mod.MNPIAnomalyDetector
train = _mod.train


if __name__ == "__main__":
    import sys

    emb_path = sys.argv[1] if len(sys.argv) > 1 else "all_embeddings.npy"
    out_path = sys.argv[2] if len(sys.argv) > 2 else CHECKPOINT_PATH
    train(emb_path, out_path)
