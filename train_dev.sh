#!/bin/bash
set -e

# Noupe Training Pipeline
# Runs all training steps so run_dev.sh boots cleanly.
# Order: prepare CSVs → embeddings → clustering → model1 → model2

ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$ROOT/docs/json"
TMP_DIR="$ROOT/.train_tmp"

mkdir -p "$TMP_DIR"

echo "════════════════════════════════════════════════"
echo "  Noupe Training Pipeline"
echo "════════════════════════════════════════════════"
echo ""

# ── Pre-check: verify critical deps ──
python3 -c "import accelerate" 2>/dev/null || { echo "❌ Missing 'accelerate'. Run: pip install 'accelerate>=0.26.0'"; exit 1; }


# ── Step 0: Validate training data ──
echo "📋 Step 0/5: Validating training JSON files..."
python3 "$ROOT/scripts/validate_training_data.py" "$DATA_DIR"/*.json
echo "✅ All training files valid."
echo ""

# ── Step 1: Prepare CSVs from docs/json ──
echo "📄 Step 1/5: Generating training CSVs from docs/json..."
python3 -c "
import json, csv, os, glob

data_dir = '$DATA_DIR'
tmp_dir = '$TMP_DIR'

m1_rows = [] # model1: public(0) vs risk(1)
m2_rows = [] # model2: low(0) vs high(1), violation-only

for fp in sorted(glob.glob(os.path.join(data_dir, '*.json'))):
    with open(fp) as f:
        doc = json.load(f)
    for s in doc.get('document_sentence_array', []):
        text = s.get('text', '').strip()
        label = s.get('label', '').lower()
        if not text or label not in ('non', 'low', 'high'):
            continue
        m1_label = 0 if label == 'non' else 1
        m1_rows.append((text, m1_label))
        if label in ('low', 'high'):
            m2_label = 0 if label == 'low' else 1
            m2_rows.append((text, m2_label))

for name, rows in [('model1_train.csv', m1_rows), ('model2_train.csv', m2_rows)]:
    path = os.path.join(tmp_dir, name)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['text', 'label'])
        w.writerows(rows)
    print(f'  wrote {path} ({len(rows)} rows)')
"
echo "✅ CSVs ready."
echo ""

# ── Step 2: Generate embeddings ──
echo "🧠 Step 2/5: Generating sentence embeddings..."
cd "$ROOT"
python3 layer2-embeddings/generate_embeddings.py
echo "✅ Embeddings saved."
echo ""

# ── Step 3: Train Isolation Forest (clustering) ──
echo "🌲 Step 3/5: Training Isolation Forest anomaly detector..."
python3 layer3-clustering/isolation_forest.py all_embeddings.npy
echo "✅ Clustering checkpoint saved."
echo ""

# ── Step 4: Train Model 1 (FinBERT binary classifier) ──
echo "🤖 Step 4/5: Training Model 1 (FinBERT — public vs non-public)..."
python3 layer4-classification/model-1/classifier.py "$TMP_DIR/model1_train.csv"
echo "✅ Model 1 checkpoint saved."
echo ""

# ── Step 5: Train Model 2 (BERT severity classifier) ──
echo "🤖 Step 5/5: Training Model 2 (BERT — low vs high risk)..."
python3 layer4-classification/model-2/classifier.py "$TMP_DIR/model2_train.csv"
echo "✅ Model 2 checkpoint saved."
echo ""

# ── Cleanup ──
rm -rf "$TMP_DIR"
rm -f "$ROOT/public_embeddings.npy" "$ROOT/violation_embeddings.npy" # keep only all_embeddings.npy if desired

echo "════════════════════════════════════════════════"
echo "  ✅ All training complete. run_dev.sh is ready."
echo "════════════════════════════════════════════════"
