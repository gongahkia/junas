"""
MNPI Anomaly Detector — Isolation Forest

Fits on public/baseline document embeddings (pre-computed by embeddings/).
At inference, scores a single embedding and returns a normalised anomaly score
(0.0 = normal, 1.0 = highly anomalous) plus a binary flag.

Design notes:
- No explicit PCA: max_features handles internal random subsampling of the
  768-dim embedding space, avoiding the curse of dimensionality without the
  p >> n instability of PCA on small datasets.
- contamination: upper bound on expected anomaly fraction in training data.
  Lower = stricter boundary (fewer false positives, more false negatives).
  Raise if synthetic corpus contains known noisy/borderline documents.
- max_features=0.3: each tree sees ~230 of 768 dims; key parameter for
  high-dimensional embedding inputs.
- anomaly_score is sigmoid-inverted from IF's score_samples so that
  higher values = more anomalous, suitable as a regression feature.
"""

import sys
import os
import numpy as np
import joblib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_config_val
from sklearn.ensemble import IsolationForest

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "anomaly_detector.joblib")

CONTAMINATION = get_config_val("isolation_forest", "contamination", "IF_CONTAMINATION", 0.05, float)
MAX_FEATURES = get_config_val("isolation_forest", "max_features", "IF_MAX_FEATURES", 0.3, float)
N_ESTIMATORS = get_config_val("isolation_forest", "n_estimators", "IF_N_ESTIMATORS", 100, int)


class MNPIAnomalyDetector:
    def __init__(
        self,
        contamination: float = CONTAMINATION,
        max_features: float = MAX_FEATURES,
        n_estimators: int = N_ESTIMATORS,
    ):
        self.iso = IsolationForest(
            contamination=contamination,  # proportion of dataset expected to be anomalies; lower means stricter (only extreme outliers are flagged) → less false positives, more false negatives, higher means looser (more data flagged as sensitive) → more false positives, less false negatives
            max_features=max_features,   # fraction of features (embedding dims) each tree randomly samples; replaces PCA for high-dim inputs
            n_estimators=n_estimators,
            random_state=42,
        )

    def fit(self, public_embeddings: np.ndarray) -> "MNPIAnomalyDetector":
        """Fit on public/baseline document embeddings. Shape: (n_docs, embedding_dim)."""
        self.iso.fit(public_embeddings)
        return self

    def score(self, embedding: np.ndarray) -> dict:
        """
        Score a single embedding vector.

        Args:
            embedding: 1-D array of shape (embedding_dim,) — e.g. (768,) for mpnet.

        Returns:
            dict with:
                anomaly_score (float, 0–1): higher = more anomalous. Use as regression feature.
                is_anomaly (bool): True if IF predicts this point as an outlier.
                raw_score (float): raw IF score_samples value (negative = anomalous).
        """
        x = embedding.reshape(1, -1)
        raw = self.iso.score_samples(x)[0]          # lower (more negative) = more anomalous
        is_anomaly = self.iso.predict(x)[0] == -1    # -1 = anomaly, 1 = inlier
        anomaly_score = float(1 / (1 + np.exp(raw))) # sigmoid inversion: high score = anomalous
        return {
            "anomaly_score": anomaly_score,
            "is_anomaly": bool(is_anomaly),
            "raw_score": float(raw),
        }

    def save(self, path: str = CHECKPOINT_PATH) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.iso, path)

    @classmethod
    def load(cls, path: str = CHECKPOINT_PATH) -> "MNPIAnomalyDetector":
        obj = cls.__new__(cls)
        obj.iso = joblib.load(path)
        return obj


def train(embeddings_path: str, save_path: str = CHECKPOINT_PATH) -> MNPIAnomalyDetector:
    """
    Train and save the anomaly detector from a .npy embeddings file.

    Train on all_embeddings.npy (public + violation) so the IF learns the full
    distribution of known data and flags only true unknown unknowns as anomalies.

    Usage:
        python3 clustering/isolation_forest.py all_embeddings.npy
    """
    from tqdm import tqdm
    
    # Fake load progress for consistency in "nice loading indicators"
    print(f"Loading embeddings from {embeddings_path}...")
    embeddings = np.load(embeddings_path)
    print(f"Loaded embeddings: {embeddings.shape}")
    
    detector = MNPIAnomalyDetector()
    
    with tqdm(total=1, desc="Fitting Isolation Forest Model", unit="step") as pbar:
        detector.fit(embeddings)
        pbar.update(1)
        
    detector.save(save_path)
    print(f"Saved anomaly detector to {save_path}")
    print(f"  contamination={CONTAMINATION}, max_features={MAX_FEATURES}, n_estimators={N_ESTIMATORS}")
    return detector


if __name__ == "__main__":
    import sys
    emb_path = sys.argv[1] if len(sys.argv) > 1 else "all_embeddings.npy"
    out_path = sys.argv[2] if len(sys.argv) > 2 else CHECKPOINT_PATH
    train(emb_path, out_path)
