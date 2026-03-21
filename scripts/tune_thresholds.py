#!/usr/bin/env python3
"""Tune model thresholds from data and persist a versioned lock file."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_ROOT = ROOT / "backend" / "workflow"
MODEL1_DIR = WORKFLOW_ROOT / "layer4-classification" / "model-1" / "checkpoints" / "best"
MODEL2_DIR = WORKFLOW_ROOT / "layer4-classification" / "model-2" / "checkpoints" / "best"
DEFAULT_LOCK = ROOT / "configs" / "thresholds.lock.json"


def f1_for_threshold(scores: np.ndarray, labels: np.ndarray, threshold: float) -> float:
    preds = (scores >= threshold).astype(int)
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0


def load_temperature(model_dir: Path) -> float:
    path = model_dir / "calibration.json"
    if not path.exists():
        return 1.0
    try:
        payload = json.loads(path.read_text())
        temp = float(payload.get("temperature", 1.0))
        return temp if temp > 0 else 1.0
    except Exception:
        return 1.0


def score_dataset(model_dir: Path, csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    if not model_dir.exists():
        raise FileNotFoundError(f"checkpoint not found: {model_dir}")
    if not csv_path.exists():
        raise FileNotFoundError(f"csv not found: {csv_path}")

    df = pd.read_csv(csv_path)
    texts = df["text"].fillna("").astype(str).tolist()
    labels = df["label"].astype(int).to_numpy()

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    temperature = load_temperature(model_dir)

    scores = []
    with torch.no_grad():
        for i in range(0, len(texts), 32):
            batch = texts[i:i + 32]
            enc = tokenizer(batch, truncation=True, padding=True, max_length=512, return_tensors="pt").to(device)
            logits = model(**enc).logits
            logits = logits / temperature
            probs = torch.softmax(logits, dim=-1)[:, 1]
            scores.extend(probs.detach().cpu().numpy().tolist())
    return np.array(scores), labels


def tune_threshold(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    best_t = 0.5
    best_f1 = -1.0
    for t in np.arange(0.05, 0.951, 0.01):
        f1 = f1_for_threshold(scores, labels, float(t))
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return best_t, best_f1


def main() -> int:
    parser = argparse.ArgumentParser(description="Tune thresholds for model-1 and model-2")
    parser.add_argument("--model1-csv", type=Path, required=True, help="Validation CSV for model-1 (text,label)")
    parser.add_argument("--model2-csv", type=Path, required=True, help="Validation CSV for model-2 (text,label)")
    parser.add_argument("--out", type=Path, default=DEFAULT_LOCK, help="Output lock file path")
    args = parser.parse_args()

    m1_scores, m1_labels = score_dataset(MODEL1_DIR, args.model1_csv)
    m2_scores, m2_labels = score_dataset(MODEL2_DIR, args.model2_csv)

    m1_t, m1_f1 = tune_threshold(m1_scores, m1_labels)
    m2_t, m2_f1 = tune_threshold(m2_scores, m2_labels)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model1_threshold": m1_t,
        "model2_threshold": m2_t,
        "metrics": {
            "model1_best_f1": m1_f1,
            "model2_best_f1": m2_f1,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"[OK] Wrote threshold lock file to {args.out}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
