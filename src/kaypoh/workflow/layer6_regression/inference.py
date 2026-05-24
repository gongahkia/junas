import os
import json
from collections.abc import Mapping, Sequence
import numpy as np
import xgboost as xgb

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "risk_regressor.json")
METADATA_PATH = os.path.join(CHECKPOINT_DIR, "metadata.json")
SCHEMA_VERSION = 2
LEGACY_FEATURE_NAMES = ["lex_score", "m1_score", "m2_score", "clust_score", "mosaic_count"]
CURRENT_FEATURE_NAMES = [
    "lex_score",
    "lex_threshold",
    "lex_score_over_threshold",
    "m1_score",
    "m2_score",
    "clust_score",
    "mosaic_count",
]
SUPPORTED_SCHEMA_VERSIONS = {1, 2}


class XGBoostRegression:
    def __init__(self, model_path: str | None = None, metadata_path: str | None = None):
        """
        Multivariate regression layer.
        Loads only from a trained checkpoint; no random in-memory fallback model.
        """
        self.feature_names = CURRENT_FEATURE_NAMES[:]
        self.model_path = model_path or CHECKPOINT_PATH
        self.metadata_path = metadata_path or METADATA_PATH
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Regression checkpoint not found: {self.model_path}")
        if not os.path.exists(self.metadata_path):
            raise FileNotFoundError(f"Regression metadata not found: {self.metadata_path}")

        self._load_metadata(self.metadata_path)

        self.model = xgb.XGBRegressor(objective="reg:squarederror")
        self.model.load_model(self.model_path)

    def _load_metadata(self, metadata_path: str) -> None:
        payload = json.loads(open(metadata_path, "r", encoding="utf-8").read())

        schema_version = int(payload.get("schema_version", -1))
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"Unsupported regression metadata schema_version={schema_version}")

        feature_order = payload.get("feature_names")
        if not isinstance(feature_order, list) or not all(isinstance(name, str) for name in feature_order):
            raise ValueError("Regression feature_names must be a string list")
        if schema_version == 1 and feature_order != LEGACY_FEATURE_NAMES:
            raise ValueError(
                f"Legacy regression feature order mismatch. expected={LEGACY_FEATURE_NAMES} got={feature_order}"
            )
        if schema_version >= 2 and feature_order != CURRENT_FEATURE_NAMES:
            raise ValueError(
                f"Regression feature order mismatch. expected={CURRENT_FEATURE_NAMES} got={feature_order}"
            )
        self.feature_names = feature_order

        scaler = payload.get("scaler", {})
        mean = scaler.get("mean")
        std = scaler.get("std")
        if not isinstance(mean, list) or not isinstance(std, list):
            raise ValueError("Regression scaler metadata missing mean/std arrays")
        if len(mean) != len(self.feature_names) or len(std) != len(self.feature_names):
            raise ValueError("Regression scaler metadata length mismatch")

        self.scaler_mean = np.array(mean, dtype=np.float32)
        self.scaler_std = np.array(std, dtype=np.float32)
        if np.any(self.scaler_std == 0):
            raise ValueError("Regression scaler std contains zeros")

    def _ordered_features(self, features: Mapping[str, float] | Sequence[float]) -> list[float]:
        if isinstance(features, Mapping):
            missing = [name for name in self.feature_names if name not in features]
            if missing:
                raise ValueError(f"Regression feature payload missing keys: {missing}")
            return [float(features[name]) for name in self.feature_names]

        if isinstance(features, Sequence) and not isinstance(features, (str, bytes, bytearray)):
            if len(features) != len(self.feature_names):
                raise ValueError(
                    f"Expected {len(self.feature_names)} ordered features {self.feature_names}, got {len(features)}"
                )
            return [float(v) for v in features]

        raise TypeError("features must be a mapping or ordered sequence")

    def predict(self, features: Mapping[str, float] | Sequence[float]) -> dict:
        """
        Accepts either:
        - Mapping keyed by feature name
        - Ordered sequence matching metadata feature_names order
        """
        ordered_features = self._ordered_features(features)
        arr = np.array(ordered_features, dtype=np.float32).reshape(1, -1)
        if not np.isfinite(arr).all():
            raise ValueError("Regression input contains non-finite values")
        arr = (arr - self.scaler_mean.reshape(1, -1)) / self.scaler_std.reshape(1, -1)
        risk_score = float(self.model.predict(arr)[0])
        risk_score = max(0.0, min(risk_score, 1.0))

        if risk_score > 0.7:
            label = "high_risk"
        elif risk_score > 0.4:
            label = "low_risk"
        else:
            label = "safe"

        return {
            "risk_score": risk_score,
            "label": label,
            "reasoning": (
                f"XGBoost checkpoint produced probability {risk_score:.3f} "
                f"from features {dict(zip(self.feature_names, ordered_features))}"
            ),
        }
