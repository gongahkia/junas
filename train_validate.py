#!/usr/bin/env python3
"""
Train/Val Split & Best Val F1 Score
Simple train/val split and returns best val F1 score.
"""

import json
import csv
import glob
import shutil
import importlib.util
from pathlib import Path
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "docs" / "json"
SEED = 42

def generate_training_data():
    """Generate model1 and model2 training datasets from docs/json."""
    m1_rows = []  # model1: non(0) vs risk(1)
    m2_rows = []  # model2: low(0) vs high(1)

    for fp in sorted(glob.glob(str(DATA_DIR / "*.json"))):
        try:
            with open(fp) as f:
                doc = json.load(f)
        except Exception as e:
            print(f"⚠️  Skipping {fp}: {e}")
            continue

        for s in doc.get("document_sentence_array", []):
            text = s.get("text", "").strip()
            label = s.get("label", "").lower()
            
            if not text or label not in ("non", "low", "high"):
                continue
            
            # Model 1: non=0, (low or high)=1
            m1_label = 0 if label == "non" else 1
            m1_rows.append((text, m1_label))
            
            # Model 2: only for low/high, low=0, high=1
            if label in ("low", "high"):
                m2_label = 0 if label == "low" else 1
                m2_rows.append((text, m2_label))

    return m1_rows, m2_rows

def train_and_get_best_val_f1(model_path, rows, model_name):
    """Split data to train/val, train model, return best val F1 score."""
    if not rows:
        print(f"⚠️  No data for {model_name}")
        return None
    
    texts, labels = zip(*rows)
    
    # 80/20 train/val split
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels
    )
    
    print(f"\n🤖 {model_name}")
    print(f"   Train: {len(train_labels)} samples")
    print(f"   Val:   {len(val_labels)} samples")
    
    # Clean old checkpoints before training
    checkpoints_dir = model_path / "checkpoints"
    best_dir = model_path / "best"
    if checkpoints_dir.exists():
        shutil.rmtree(checkpoints_dir)
    if best_dir.exists():
        shutil.rmtree(best_dir)
    
    # Create temp CSV files
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        train_csv = f.name
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(zip(train_texts, train_labels))
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        val_csv = f.name
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(zip(val_texts, val_labels))
    
    try:
        # Dynamically load and train
        classifier_path = model_path / "classifier.py"
        spec = importlib.util.spec_from_file_location("classifier", classifier_path)
        classifier_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(classifier_mod)
        
        print(f"   Training...")
        trainer = classifier_mod.train(train_csv, val_csv, epochs=3, batch_size=16)
        
        # Get best metric from trainer state
        # The trainer evaluates every epoch and tracks the best
        best_metric = trainer.state.best_metric
        print(f"   Best Val F1: {best_metric:.4f}")
        
        return best_metric
        
    finally:
        # Cleanup temp files
        import os
        os.unlink(train_csv)
        os.unlink(val_csv)

def main():
    print("════════════════════════════════════════════════")
    print("  Train/Val Split & Best Val F1 Score")
    print("════════════════════════════════════════════════\n")
    
    print("📋 Generating training data from docs/json...")
    m1_rows, m2_rows = generate_training_data()
    print(f"  Model 1 (non vs risk): {len(m1_rows)} samples")
    print(f"  Model 2 (low vs high): {len(m2_rows)} samples")
    
    results = {}
    
    # Train Model 1
    try:
        m1_best_f1 = train_and_get_best_val_f1(ROOT / "layer4-classification" / "model-1", m1_rows, "Model 1 (non vs risk)")
        if m1_best_f1 is not None:
            results["Model 1"] = m1_best_f1
    except Exception as e:
        print(f"❌ Model 1 failed: {e}")
    
    # Train Model 2
    try:
        m2_best_f1 = train_and_get_best_val_f1(ROOT / "layer4-classification" / "model-2", m2_rows, "Model 2 (low vs high)")
        if m2_best_f1 is not None:
            results["Model 2"] = m2_best_f1
    except Exception as e:
        print(f"❌ Model 2 failed: {e}")
    
    # Print summary
    print("\n════════════════════════════════════════════════")
    print("  📊 Best Val F1 Scores")
    print("════════════════════════════════════════════════\n")
    
    for model_name, best_f1 in results.items():
        print(f"{model_name}: {best_f1:.4f}")
    
    if not results:
        print("❌ No models trained successfully")

if __name__ == "__main__":
    main()
