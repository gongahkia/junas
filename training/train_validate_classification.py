#!/usr/bin/env python3
"""
Train/Val Split & F1 Evaluation

- Document-level 80/20 train/val split (no sentence leakage across splits)
- Trains Model 1 (FinBERT: non vs risk) and Model 2 (BERT: low vs high)
- Post-training F1 evaluation on both train and validation sets
- Reports weighted F1 and macro F1 with full classification reports
"""

import json
import csv
import glob
import os
import shutil
import tempfile
import importlib.util
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, classification_report

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "json"
SEED = 42
TEST_SIZE = 0.2

# ---------------------------------------------------------------------------
# Label normalisation: canonical labels are "non", "low", "high"
# Legacy labels from older corpora are mapped here.
# ---------------------------------------------------------------------------
_LABEL_MAP = {
    "non": "non",
    "non-sensitive": "non",
    "low": "low",
    "low sensitivity": "low",
    "high": "high",
    "high sensitivity": "high",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_documents():
    """Load JSON documents from docs/json.

    Returns a list of dicts with keys 'path' and 'sentences'.
    Each sentence dict has 'text' (str) and 'label' (str, canonical).
    """
    documents = []
    for fp in sorted(glob.glob(str(DATA_DIR / "*.json"))):
        try:
            with open(fp) as f:
                doc = json.load(f)
        except Exception as e:
            print(f"  [warn] Skipping {fp}: {e}")
            continue

        sentences = []
        for s in doc.get("document_sentence_array", []):
            text = s.get("text", "").strip()
            raw = s.get("label", "").strip().lower()
            label = _LABEL_MAP.get(raw)
            if text and label:
                sentences.append({"text": text, "label": label})

        if sentences:
            documents.append({"path": fp, "sentences": sentences})

    return documents


# ---------------------------------------------------------------------------
# Document-level split
# ---------------------------------------------------------------------------

def split_documents(documents, test_size=TEST_SIZE, seed=SEED):
    """80/20 train/val split at the document level.

    All sentences from a given JSON file stay together in the same split
    to avoid data leakage from correlated sentences.
    """
    if len(documents) < 2:
        raise ValueError(
            f"Need at least 2 documents to split, found {len(documents)}"
        )

    indices = list(range(len(documents)))
    train_idx, val_idx = train_test_split(
        indices, test_size=test_size, random_state=seed
    )
    train_docs = [documents[i] for i in sorted(train_idx)]
    val_docs = [documents[i] for i in sorted(val_idx)]
    return train_docs, val_docs


# ---------------------------------------------------------------------------
# Row extraction per model
# ---------------------------------------------------------------------------

def extract_model1_rows(documents):
    """Model 1 (FinBERT): non -> 0, (low | high) -> 1."""
    rows = []
    for doc in documents:
        for s in doc["sentences"]:
            rows.append((s["text"], 0 if s["label"] == "non" else 1))
    return rows


def extract_model2_rows(documents):
    """Model 2 (BERT severity): low -> 0, high -> 1.  Violation corpus only."""
    rows = []
    for doc in documents:
        for s in doc["sentences"]:
            if s["label"] in ("low", "high"):
                rows.append((s["text"], 0 if s["label"] == "low" else 1))
    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _label_distribution(rows):
    dist = {}
    for _, lbl in rows:
        dist[lbl] = dist.get(lbl, 0) + 1
    return dict(sorted(dist.items()))


def _write_temp_csv(rows):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(rows)
    return path


def evaluate_f1(trainer, dataset, split_name, target_names):
    """Run predictions on *dataset* and print weighted + macro F1."""
    result = trainer.predict(dataset)
    preds = np.argmax(result.predictions, axis=1)
    labels = result.label_ids

    w_f1 = f1_score(labels, preds, average="weighted")
    m_f1 = f1_score(labels, preds, average="macro")

    print(f"\n    {split_name}:")
    print(f"      Weighted F1 : {w_f1:.4f}")
    print(f"      Macro F1    : {m_f1:.4f}")
    print(
        classification_report(
            labels, preds, digits=4, target_names=target_names, zero_division=0
        )
    )
    return {"weighted_f1": w_f1, "macro_f1": m_f1}


# ---------------------------------------------------------------------------
# Per-model train + evaluate
# ---------------------------------------------------------------------------

def train_and_evaluate(
    model_path,
    train_rows,
    val_rows,
    model_name,
    target_names,
    epochs=3,
    batch_size=16,
):
    """Train a model from its classifier.py, then compute train/val F1."""
    if not train_rows:
        print(f"  No training data for {model_name} -- skipping.")
        return None
    if not val_rows:
        print(f"  No validation data for {model_name} -- skipping.")
        return None

    # Check that both classes are present in each split
    train_labels_set = set(lbl for _, lbl in train_rows)
    val_labels_set = set(lbl for _, lbl in val_rows)
    if len(train_labels_set) < 2:
        print(f"  Train split has only class(es) {train_labels_set} for {model_name} -- skipping.")
        return None
    if len(val_labels_set) < 2:
        print(f"  Val split has only class(es) {val_labels_set} for {model_name} -- skipping.")
        return None

    print(f"\n{'=' * 60}")
    print(f"  {model_name}")
    print(f"{'=' * 60}")
    print(f"  Train : {len(train_rows)} samples  {_label_distribution(train_rows)}")
    print(f"  Val   : {len(val_rows)} samples  {_label_distribution(val_rows)}")

    # Clean old checkpoints
    checkpoints_dir = model_path / "checkpoints"
    if checkpoints_dir.exists():
        shutil.rmtree(checkpoints_dir)

    # Write temp CSVs
    train_csv = _write_temp_csv(train_rows)
    val_csv = _write_temp_csv(val_rows)

    try:
        # Dynamically load the classifier module
        classifier_path = model_path / "classifier.py"
        spec = importlib.util.spec_from_file_location("classifier", classifier_path)
        classifier_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(classifier_mod)

        print("  Training ...")
        trainer = classifier_mod.train(
            train_csv, val_csv, epochs=epochs, batch_size=batch_size
        )

        # -- Post-training evaluation --
        # The Trainer already holds train_dataset and eval_dataset
        # populated by the classifier's train() function.
        print(f"\n  Post-training evaluation for {model_name}")

        train_metrics = evaluate_f1(
            trainer, trainer.train_dataset, "Train", target_names
        )
        val_metrics = evaluate_f1(
            trainer, trainer.eval_dataset, "Validation", target_names
        )

        return {"train": train_metrics, "val": val_metrics}

    finally:
        os.unlink(train_csv)
        os.unlink(val_csv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Train / Val Split  &  F1 Evaluation")
    print("=" * 60)
    print()

    # 1. Load documents
    print("Loading documents from docs/json ...")
    documents = load_documents()
    total_sentences = sum(len(d["sentences"]) for d in documents)
    print(f"  Loaded {len(documents)} documents ({total_sentences} sentences)")

    # 2. Document-level split
    print(f"\nSplitting documents {int((1 - TEST_SIZE) * 100)}/{int(TEST_SIZE * 100)} "
          f"at the document level (seed={SEED}) ...")
    train_docs, val_docs = split_documents(documents)
    print(f"  Train documents : {len(train_docs)}")
    print(f"  Val documents   : {len(val_docs)}")

    # 3. Extract per-model rows
    m1_train = extract_model1_rows(train_docs)
    m1_val = extract_model1_rows(val_docs)
    m2_train = extract_model2_rows(train_docs)
    m2_val = extract_model2_rows(val_docs)

    print(f"\n  Model 1 (non vs risk)  -- train {len(m1_train)}, val {len(m1_val)}")
    print(f"  Model 2 (low vs high)  -- train {len(m2_train)}, val {len(m2_val)}")

    results = {}

    # 4. Train & evaluate Model 1 (FinBERT: safe / risk)
    try:
        m1_result = train_and_evaluate(
            model_path=ROOT / "layer4-classification" / "model-1",
            train_rows=m1_train,
            val_rows=m1_val,
            model_name="Model 1  (FinBERT -- non vs risk)",
            target_names=["safe (0)", "risk (1)"],
        )
        if m1_result is not None:
            results["Model 1"] = m1_result
    except Exception as e:
        print(f"  [error] Model 1 failed: {e}")

    # 5. Train & evaluate Model 2 (BERT severity: low / high)
    try:
        m2_result = train_and_evaluate(
            model_path=ROOT / "layer4-classification" / "model-2",
            train_rows=m2_train,
            val_rows=m2_val,
            model_name="Model 2  (BERT -- low vs high)",
            target_names=["low_risk (0)", "high_risk (1)"],
        )
        if m2_result is not None:
            results["Model 2"] = m2_result
    except Exception as e:
        print(f"  [error] Model 2 failed: {e}")

    # 6. Summary
    print()
    print("=" * 60)
    print("  Summary")
    print("=" * 60)

    if not results:
        print("  No models were trained successfully.")
        return

    header = f"  {'Model':<28} {'Split':<7} {'Weighted F1':>12} {'Macro F1':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for model_name, metrics in results.items():
        for split_name, m in [("Train", metrics["train"]), ("Val", metrics["val"])]:
            print(
                f"  {model_name:<28} {split_name:<7} "
                f"{m['weighted_f1']:>12.4f} {m['macro_f1']:>10.4f}"
            )
        print()


if __name__ == "__main__":
    main()
