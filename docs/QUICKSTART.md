# Quick Reference - Neural Network Integration

## 🚀 Quick Start (5 Minutes)

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

## 📁 Key Files

| File | Purpose |
|------|---------|
| `training/train_tui.py` | **Main training interface** (use this!) |
| `training/download_data.py` | Download Food-101 dataset |
| `backend/src/utils/modelService.js` | ONNX inference engine |
| `backend/src/utils/visionService.js` | Auto NN/heuristic selection |
| `training/TRAINING.md` | Complete training guide |

## 🎯 Features

### Training TUI Features
- ✅ Interactive configuration
- ✅ Live progress tracking
- ✅ Real-time metrics (loss, accuracy)
- ✅ Automatic checkpointing
- ✅ ONNX export built-in
- ✅ Clear next-step instructions

### Backend Features
- ✅ Automatic model detection
- ✅ ONNX Runtime inference
- ✅ Heuristic fallback
- ✅ ~50-100ms per image
- ✅ Drop-in replacement for old system

## 📊 Expected Results

### Training (Full Food-101)
- **Time**: 1-8 hours (CPU), 1-2 hours (GPU)
- **Accuracy**: 70-85% validation
- **Model Size**: ~10-15 MB

### Inference
- **Speed**: 50-100ms/image (CPU)
- **Format**: ONNX (Node.js compatible)
- **Input**: 224×224 RGB images

## 🔍 Verification

### Check if model is loaded:
```bash
cd backend
npm run dev
# Look for:
# ✅ Using NEURAL NETWORK for food recognition
```

### Run integration test:
```bash
cd training
python test_integration.py
```

## 🆘 Common Issues

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Model file not found" in backend
```bash
# Copy from training to backend
cp training/models/caifan_model.onnx backend/models/
cp training/models/classes.json backend/models/
```

### Training too slow
- Reduce batch size (16 or 8)
- Use fewer epochs (5-10)
- Use sample dataset first

## 📖 Documentation

- **Training Guide**: `training/TRAINING.md` (detailed)
- **Main README**: Updated with NN integration info
- **Implementation Summary**: `.copilot/session-state/.../files/IMPLEMENTATION_SUMMARY.md`

## 💡 Pro Tips

1. **Start with sample dataset** to test pipeline
2. **Use the TUI** - it's much easier than CLI
3. **Monitor logs** - they tell you what's happening
4. **Backend auto-falls back** if model missing
5. **Model files are gitignored** - train locally

## 🎉 What's New

**Before**: Heuristic color-based detection (unreliable)
**Now**: Real MobileNetV3 neural network (accurate)

The system automatically uses the neural network when available and falls back to heuristics if not. This means zero breaking changes!
