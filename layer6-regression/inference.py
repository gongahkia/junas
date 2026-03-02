import os
import json
import numpy as np
import xgboost as xgb

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "risk_regressor.json")
METADATA_PATH = os.path.join(CHECKPOINT_DIR, "metadata.json")
SCHEMA_VERSION = 1


class XGBoostRegression:
    def __init__(self, model_path: str | None = None):
        """
        Multivariate regression layer.
        Loads only from a trained checkpoint; no random in-memory fallback model.
        """
        self.feature_names = ["lex_score", "m1_score", "m2_score", "clust_score", "mosaic_count"]
        self.model_path = model_path or CHECKPOINT_PATH
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Regression checkpoint not found: {self.model_path}")
        if not os.path.exists(METADATA_PATH):
            raise FileNotFoundError(f"Regression metadata not found: {METADATA_PATH}")

        self._load_metadata(METADATA_PATH)

        self.model = xgb.XGBRegressor(objective="reg:squarederror")
        self.model.load_model(self.model_path)

    def _load_metadata(self, metadata_path: str) -> None:
        payload = json.loads(open(metadata_path, "r", encoding="utf-8").read())

        schema_version = int(payload.get("schema_version", -1))
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported regression metadata schema_version={schema_version}")

        feature_order = payload.get("feature_names")
        if feature_order != self.feature_names:
            raise ValueError(
                f"Regression feature order mismatch. expected={self.feature_names} got={feature_order}"
            )

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

    def predict(self, features: list[float]) -> dict:
        """
        Expects features in order:
        [lex_score, m1_score, m2_score, clust_score, mosaic_count]
        """
        if len(features) != len(self.feature_names):
            raise ValueError(
                f"Expected {len(self.feature_names)} features in order {self.feature_names}, got {len(features)}"
            )
        arr = np.array(features, dtype=np.float32).reshape(1, -1)
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
            "reasoning": f"XGBoost checkpoint produced probability {risk_score:.3f} from features {features}",
        }
