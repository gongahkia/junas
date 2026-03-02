import os
import numpy as np
import xgboost as xgb

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
CHECKPOINT_PATH = os.path.join(CHECKPOINT_DIR, "risk_regressor.json")


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

        self.model = xgb.XGBRegressor(objective="reg:squarederror")
        self.model.load_model(self.model_path)

    def predict(self, features: list[float]) -> dict:
        """
        Expects features in order:
        [lex_score, m1_score, m2_score, clust_score, mosaic_count]
        """
        arr = np.array(features, dtype=np.float32).reshape(1, -1)
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

