"""
Legacy lexicon shim.

Canonical implementation lives in layer1-lexicon/filter.py.
"""

import importlib.util
from pathlib import Path


def _load_canonical():
    path = Path(__file__).resolve().parents[1] / "layer1-lexicon" / "filter.py"
    spec = importlib.util.spec_from_file_location("layer1_lexicon_filter", str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load canonical lexicon filter from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_canonical()

RESTRICTED_LIST_PATH = _mod.RESTRICTED_LIST_PATH
ABS_THRESHOLD = _mod.ABS_THRESHOLD
PCT_THRESHOLD = _mod.PCT_THRESHOLD
LEXICON_SCORE_THRESHOLD = _mod.LEXICON_SCORE_THRESHOLD
LEXICON_WEIGHTS = _mod.LEXICON_WEIGHTS
DEFAULT_HIGH_WEIGHT = _mod.DEFAULT_HIGH_WEIGHT
DEFAULT_INFO_WEIGHT = _mod.DEFAULT_INFO_WEIGHT
LexiconHit = _mod.LexiconHit
LexiconResult = _mod.LexiconResult
LexiconFilter = _mod.LexiconFilter
