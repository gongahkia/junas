# Quick Reference - Neural Network Integration

## Quick Start (5 Minutes)

```bash
# 1. Install Python dependencies
cd training
pip install -r requirements.txt

# 2. Download sample dataset (or use Food-101)
python download_data.py --sample
# OR for full dataset:
# python download_data.py

# 3. Train the model (Interactive TUI)
python train_tui.py

# 4. Deploy to backend
cp models/caifan_model.onnx ../backend/models/
cp models/classes.json ../backend/models/

# 5. Install and run backend
cd ../backend
npm install
npm run dev
```

## Key Files

| File | Purpose |
|------|---------|
| `training/train_tui.py` | Training interface |
| `training/metrics.py` | Evaluation metrics (confusion matrix, P/R/F1) |
| `training/validate_data.py` | Dataset validation |
| `training/download_data.py` | Download Food-101 dataset |
| `backend/src/utils/modelService.js` | ONNX inference engine (with cache + abstention) |
| `backend/src/utils/visionService.js` | Vision service (requires trained model) |

## Features

### Training TUI
- Interactive configuration
- Dataset validation (corrupt/duplicate detection)
- Live progress tracking
- Real-time metrics (loss, accuracy)
- Automatic checkpointing
- Detailed evaluation (confusion matrix, per-class P/R/F1)
- ONNX export built-in

### Backend
- Automatic model detection
- ONNX Runtime inference
- SHA256-keyed inference cache (30s TTL)
- Abstention logic (rejects low-confidence / ambiguous predictions)
- ~50-100ms per image

## Expected Results

### Training (Full Food-101)
- **Time**: 1-8 hours (CPU), 1-2 hours (GPU)
- **Accuracy**: 70-85% validation
- **Model Size**: ~10-15 MB

### Inference
- **Speed**: 50-100ms/image (CPU), cached frames near-instant
- **Format**: ONNX (Node.js compatible)
- **Input**: 224x224 RGB images

## Verification

### Check if model is loaded:
```bash
cd backend
npm run dev
# Look for:
# ✅ Neural network model loaded successfully
```

### Run integration test:
```bash
cd training
python test_integration.py
```

## Common Issues

### "Module not found"
```bash
pip install -r requirements.txt
```

### "No trained model available" in backend
```bash
cp training/models/caifan_model.onnx backend/models/
cp training/models/classes.json backend/models/
```

### Training too slow
- Reduce batch size (16 or 8)
- Use fewer epochs (5-10)
- Use sample dataset first
