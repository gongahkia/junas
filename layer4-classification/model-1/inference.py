import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from configs.runtime import get_config_val
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dataclasses import dataclass
from typing import Optional

CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints", "best")
CALIBRATION_PATH = os.path.join(CHECKPOINT_DIR, "calibration.json")
MAX_SEQ_LEN = 512
WINDOW_STRIDE = 128
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
    top_window: Optional[dict] = None
    window_count: int = 1


def _window_bounds(offsets: list[list[int]]) -> Optional[tuple[int, int]]:
    start_char = None
    end_char = None
    for start, end in offsets:
        if end <= start:
            continue
        if start_char is None:
            start_char = int(start)
        end_char = int(end)

    if start_char is None or end_char is None:
        return None
    return (start_char, end_char)

class FinBERTClassifier:
    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        if not _has_model_weights(checkpoint_dir):
            raise FileNotFoundError(f"model1 checkpoint weights missing at {checkpoint_dir}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir, local_files_only=True, use_fast=True)
        except TypeError:
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

    def _predict_windows(self, text: str) -> tuple[list[float], list[dict]]:
        tokenized = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=MAX_SEQ_LEN,
            stride=WINDOW_STRIDE,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            return_tensors="pt",
        )
        offset_mapping = tokenized.pop("offset_mapping")
        inputs = {key: value.to(self.device) for key, value in tokenized.items()}

        with torch.inference_mode():
            logits = self.model(**inputs).logits
        if self.temperature > 0:
            logits = logits / self.temperature

        probs = torch.softmax(logits, dim=-1)
        risk_scores = probs[:, 1].tolist()
        windows: list[dict] = []

        for index, risk_score in enumerate(risk_scores):
            bounds = _window_bounds(offset_mapping[index].tolist())
            if bounds is None:
                continue

            start_char, end_char = bounds
            windows.append(
                {
                    "start_char": start_char,
                    "end_char": end_char,
                    "text": text[start_char:end_char],
                    "risk_score": float(risk_score),
                    "window_index": index,
                }
            )

        return ([float(score) for score in risk_scores], windows)

    def predict(self, text: str) -> Model1Result:
        risk_scores, windows = self._predict_windows(text)
        if not risk_scores:
            raise RuntimeError("model1 inference produced no windows")

        risk_score = max(risk_scores)
        label = "risk" if risk_score >= THRESHOLD else "safe"
        confidence = risk_score if label == "risk" else (1.0 - risk_score)
        top_window = max(windows, key=lambda item: item["risk_score"]) if windows else None
        return Model1Result(
            label=label,
            confidence=confidence,
            risk_score=risk_score,
            top_window=top_window,
            window_count=len(risk_scores),
        )
