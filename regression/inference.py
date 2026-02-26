import numpy as np

import os
import numpy as np
import xgboost as xgb

class XGBoostRegression:
    def __init__(self, model_path: str = None):
        """
        Multivariate Regression (Supervised ML) using XGBoost.
        Inputs: lexicon score, finBERT score, BERT severity score, anomaly score, mosaic count.
        """
        self.feature_names = ["lex_score", "m1_score", "m2_score", "clust_score", "mosaic_count"]
        # Since we don't have a pre-trained model yet, we initialize a dummy one
        # that roughly mimics the previous logic.
        self.model = xgb.XGBRegressor(
            n_estimators=10, 
            max_depth=3, 
            learning_rate=0.1,
            objective='reg:squarederror'
        )
        # Train a quick dummy model in memory so it can predict
        # This mirrors a simple linear combination just to have a working XGB model natively
        X_dummy = np.random.rand(100, len(self.feature_names))
        # Simulated labels based on a weighted sum
        weights = np.array([0.1, 0.3, 0.3, 0.2, 0.1])
        y_dummy = np.dot(X_dummy, weights)
        
        self.model.fit(X_dummy, y_dummy)
        
    def predict(self, features: list[float]) -> dict:
        """
        Expects features to be [lex_score, m1_score, m2_score, clust_score, mosaic_count]
        Produces a single MNPI risk probability.
        """
        # Ensure dimensions match (1 sample, n features)
        arr = np.array(features, dtype=np.float32).reshape(1, -1)
        
        # Predict uses the XGBoost regressor
        risk_score = float(self.model.predict(arr)[0])
        # Bound between 0 and 1
        risk_score = max(0.0, min(risk_score, 1.0))
        
        # Determine classification label
        if risk_score > 0.7:
            label = "high_risk"
        elif risk_score > 0.4:
            label = "low_risk"
        else:
            label = "safe"
            
        return {
            "risk_score": risk_score,
            "label": label,
            "reasoning": f"XGBoost regressor produced probability {risk_score:.3f} from features {features}"
        }
