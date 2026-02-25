import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_config_val
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dataclasses import dataclass

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints", "best")
MAX_SEQ_LEN = 512
THRESHOLD = get_config_val("thresholds", "model1", "MODEL1_THRESHOLD", 0.5, float)

@dataclass
class Model1Result:
    label: str # "safe" or "risk"
    confidence: float # probability of predicted class
    risk_score: float # probability of risk class specifically

class FinBERTClassifier:
    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(checkpoint_dir).to(self.device)
        self.model.eval()
    def predict(self, text: str) -> Model1Result:
        inputs = self.tokenizer(text, truncation=True, padding=True, max_length=MAX_SEQ_LEN, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze()
        risk_score = probs[1].item() # index 1 = non-public/risk
        label = "risk" if risk_score >= THRESHOLD else "safe"
        confidence = risk_score if label == "risk" else probs[0].item()
        return Model1Result(label=label, confidence=confidence, risk_score=risk_score)
