import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from configs.runtime import get_config_val
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dataclasses import dataclass

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints", "best")
CALIBRATION_PATH = os.path.join(CHECKPOINT_DIR, "calibration.json")
MAX_SEQ_LEN = 512
MODEL_WEIGHT_EXTS = ("safetensors", "bin", "pt", "ckpt")


def _load_threshold() -> float:
    base = get_config_val("thresholds", "model1", "MODEL1_THRESHOLD", 0.5, float)
    if os.getenv("MODEL1_THRESHOLD") is not None:
        return base
    lock_path = get_config_val(
        "thresholds",
        "lock_path",
        "THRESHOLD_LOCK_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "configs", "thresholds.lock.json"),
        str,
    )
    if os.path.exists(lock_path):
        try:
            payload = json.loads(open(lock_path, "r", encoding="utf-8").read())
            threshold = float(payload.get("model1_threshold", base))
            return threshold
        except Exception:
            return base
    return base


THRESHOLD = _load_threshold()


def _has_model_weights(checkpoint_dir: str) -> bool:
    if not os.path.isdir(checkpoint_dir):
        return False
    for ext in MODEL_WEIGHT_EXTS:
        if any(name.endswith(f".{ext}") for name in os.listdir(checkpoint_dir)):
            return True
    return False

@dataclass
class Model1Result:
    label: str # "safe" or "risk"
    confidence: float # probability of predicted class
    risk_score: float # probability of risk class specifically

class FinBERTClassifier:
    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        if not _has_model_weights(checkpoint_dir):
            raise FileNotFoundError(f"model1 checkpoint weights missing at {checkpoint_dir}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint_dir,
            local_files_only=True,
        ).to(self.device)
        self.model.eval()
        self.temperature = 1.0
        calibration_path = os.path.join(checkpoint_dir, "calibration.json")
        if os.path.exists(calibration_path):
            try:
                payload = json.loads(open(calibration_path, "r", encoding="utf-8").read())
                temp = float(payload.get("temperature", 1.0))
                if temp > 0:
                    self.temperature = temp
            except Exception:
                pass
    def predict(self, text: str) -> Model1Result:
        inputs = self.tokenizer(text, truncation=True, padding=True, max_length=MAX_SEQ_LEN, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            logits = self.model(**inputs).logits
        if self.temperature > 0:
            logits = logits / self.temperature
        probs = torch.softmax(logits, dim=-1).squeeze()
        risk_score = probs[1].item() # index 1 = non-public/risk
        label = "risk" if risk_score >= THRESHOLD else "safe"
        confidence = risk_score if label == "risk" else probs[0].item()
        return Model1Result(label=label, confidence=confidence, risk_score=risk_score)
