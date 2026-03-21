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
    base = get_config_val("thresholds", "model2", "MODEL2_THRESHOLD", 0.5, float)
    if os.getenv("MODEL2_THRESHOLD") is not None:
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
            threshold = float(payload.get("model2_threshold", base))
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
class Model2Result:
    label: str # "low_risk" or "high_risk"
    confidence: float
    high_risk_score: float # probability of high_risk class
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


def _count_window_tokens(offsets: list[list[int]]) -> int:
    return sum(1 for start, end in offsets if end > start)

class BERTSeverityClassifier:
    def __init__(self, checkpoint_dir: str = CHECKPOINT_DIR):
        if not _has_model_weights(checkpoint_dir):
            raise FileNotFoundError(f"model2 checkpoint weights missing at {checkpoint_dir}")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir, local_files_only=True, use_fast=True)
        except Exception:
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
        tokenized.pop("overflow_to_sample_mapping", None)
        inputs = {key: value.to(self.device) for key, value in tokenized.items()}

        with torch.inference_mode():
            logits = self.model(**inputs).logits
        if self.temperature > 0:
            logits = logits / self.temperature

        probs = torch.softmax(logits, dim=-1)
        high_risk_scores = probs[:, 1].tolist()
        windows: list[dict] = []

        for index, high_risk_score in enumerate(high_risk_scores):
            offsets = offset_mapping[index].tolist()
            bounds = _window_bounds(offsets)
            if bounds is None:
                continue

            start_char, end_char = bounds
            windows.append(
                {
                    "start_char": start_char,
                    "end_char": end_char,
                    "text": text[start_char:end_char],
                    "high_risk_score": float(high_risk_score),
                    "window_index": index,
                    "token_count": _count_window_tokens(offsets),
                    "window_stride": WINDOW_STRIDE,
                    "max_seq_len": MAX_SEQ_LEN,
                }
            )

        return ([float(score) for score in high_risk_scores], windows)

    def predict(self, text: str) -> Model2Result:
        high_risk_scores, windows = self._predict_windows(text)
        if not high_risk_scores:
            raise RuntimeError("model2 inference produced no windows")

        high_risk_score = max(high_risk_scores)
        label = "high_risk" if high_risk_score >= THRESHOLD else "low_risk"
        confidence = high_risk_score if label == "high_risk" else (1.0 - high_risk_score)
        top_window = max(windows, key=lambda item: item["high_risk_score"]) if windows else None
        return Model2Result(
            label=label,
            confidence=confidence,
            high_risk_score=high_risk_score,
            top_window=top_window,
            window_count=len(high_risk_scores),
        )
