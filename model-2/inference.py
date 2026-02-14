import os
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dataclasses import dataclass

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints", "best")
MAX_SEQ_LEN = 512
THRESHOLD = float(os.getenv("MODEL2_THRESHOLD", "0.5"))

@dataclass
class Model2Result:
    label: str # "low_risk" or "high_risk"
    confidence: float
    high_risk_score: float # probability of high_risk class

class BERTSeverityClassifier:
    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(checkpoint_dir).to(self.device)
        self.model.eval()
    def predict(self, text: str) -> Model2Result:
        inputs = self.tokenizer(text, truncation=True, padding=True, max_length=MAX_SEQ_LEN, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze()
        high_risk_score = probs[1].item() # index 1 = high_risk
        label = "high_risk" if high_risk_score >= THRESHOLD else "low_risk"
        confidence = high_risk_score if label == "high_risk" else probs[0].item()
        return Model2Result(label=label, confidence=confidence, high_risk_score=high_risk_score)
