import numpy as np

class RegressionStub:
    def __init__(self):
        # A simple linear combination for demonstration (stub)
        self.weights = np.array([0.1, 0.3, 0.3, 0.2, 0.1])
        
    def predict(self, features: list[float]) -> dict:
        """
        features is expected to be [lex_score, m1_score, m2_score, clust_score, mosaic_count]
        """
        arr = np.array(features)
        
        # Sigmoid function for lex_score if it is unbounded, but let's just use it as is for the stub.
        # Ensure it doesn't blow up the combination
        arr[0] = min(arr[0] / 10.0, 1.0) # Normalize lex_score slightly if it's high
        arr[4] = min(arr[4] / 10.0, 1.0) # Normalize mosaic count

        risk_score = float(np.dot(arr, self.weights))
        
        if risk_score > 0.7:
            label = "high_risk"
        elif risk_score > 0.4:
            label = "low_risk"
        else:
            label = "safe"
            
        return {
            "risk_score": risk_score,
            "label": label,
            "reasoning": f"Weighted features {features} resulted in {risk_score:.3f}"
        }
