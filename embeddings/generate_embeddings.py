"""
Legacy embeddings generation shim.

Canonical implementation lives in layer2-embeddings/generate_embeddings.py.
"""

from pathlib import Path
import runpy

CANONICAL_PATH = Path(__file__).resolve().parents[1] / "layer2-embeddings" / "generate_embeddings.py"

if __name__ == "__main__":
    runpy.run_path(str(CANONICAL_PATH), run_name="__main__")
