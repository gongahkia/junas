# Neural Network Training Guide

This guide explains how to train and deploy the real neural network for food recognition, replacing the heuristic approach.

## Overview

The system consists of:
1. **Training Pipeline** (`training/` directory): Python-based with PyTorch
2. **Data Download**: Automated dataset acquisition
3. **Training TUI**: Interactive terminal UI for training
4. **Model Export**: ONNX format for Node.js backend
5. **Backend Integration**: Automatic model loading and inference

## Quick Start

### 1. Install Training Dependencies

```bash
cd training
pip install -r requirements.txt
```

### 2. Download Training Data

Choose one option:

**Option A: Full Food-101 Dataset (Recommended)**
```bash
python download_data.py
```
- Downloads ~5GB of food images
- 101 food categories
- 101,000 images total
- Takes 10-30 minutes depending on connection

**Option B: Sample Dataset (Quick Testing)**
```bash
python download_data.py --sample
```
- Creates empty directory structure
- Add your own images to `data/sample/[class_name]/`
- Good for testing the pipeline

### 3. Train the Model

```bash
python train_tui.py
```

The TUI will guide you through:
- Configuration (data path, epochs, batch size, etc.)
- Dataset validation (corrupt files, duplicates, class distribution)
- Dataset loading and verification
- Model initialization
- Training progress with live metrics
- Validation accuracy tracking
- Detailed evaluation (confusion matrix, per-class P/R/F1)
- Automatic model export to ONNX

### 4. Deploy to Backend

After training completes, copy the model files:

```bash
# Copy ONNX model
cp models/caifan_model.onnx ../backend/models/

# Copy class mappings
cp models/classes.json ../backend/models/
```

### 5. Restart Backend

```bash
cd ../backend
npm install  # Install onnxruntime-node if not already installed
npm run dev  # or npm start
```

The backend will automatically detect and load the neural network model!

## Training Configuration

### Default Parameters

```python
{
  'data_dir': './data/organized',      # Where training images are
  'output_dir': './models',             # Where to save trained models
  'epochs': 10,                         # Training iterations
  'batch_size': 32,                     # Images per batch
  'learning_rate': 0.001,               # Optimizer learning rate
  'train_split': 0.8,                   # 80% train, 20% validation
  'num_workers': 4,                     # Data loading workers
  'device': 'cuda' if available else 'cpu'
}
```

### Recommended Settings

**Quick Test (CPU, small dataset):**
- Epochs: 5
- Batch size: 16
- Learning rate: 0.001

**Production Training (GPU, full dataset):**
- Epochs: 20-50
- Batch size: 64
- Learning rate: 0.0001 (with warmup)

**Fine-tuning (pre-trained model):**
- Epochs: 5-10
- Batch size: 32
- Learning rate: 0.0001

## Model Architecture

**Base Model:** MobileNetV3-Small (PyTorch)
- Efficient mobile-friendly architecture
- Pre-trained on ImageNet
- ~2.5M parameters
- Fast inference (~50ms on CPU)

**Modifications:**
- Final classifier layer replaced with custom output
- Number of classes = number of food categories in dataset
- Input: 224x224 RGB images
- Output: Probability distribution over classes

## Dataset Structure

Organize your images like this:

```
data/
└── organized/
    ├── chicken_rice/
    │   ├── img001.jpg
    │   ├── img002.jpg
    │   └── ...
    ├── char_siew/
    │   ├── img001.jpg
    │   └── ...
    ├── vegetables/
    └── ...
```

Each subdirectory name becomes a class label.

## Output Files

After training, you'll get:

```
models/
├── caifan_model.pth          # PyTorch weights
├── caifan_model.onnx         # ONNX model (for backend)
├── best_model.pth            # Best validation checkpoint
├── classes.json              # Class ID to name mapping
├── config.json               # Training configuration
└── history.json              # Training metrics history
```

**Important:** Only `.onnx` and `classes.json` are needed for backend!

## Monitoring Training

The TUI shows:
- ✅ Real-time loss and accuracy
- ✅ Progress bars for each epoch
- ✅ Validation metrics
- ✅ Best model checkpoints
- ✅ Estimated time remaining

## Backend Integration

### Automatic Detection

The backend automatically:
1. Checks for `backend/models/caifan_model.onnx`
2. Loads the model if found
3. Uses neural network for inference
4. Falls back to heuristics if model missing

### Logs to Watch

```
✅ Neural network model loaded successfully
   Classes: 101
   Model: /path/to/backend/models/caifan_model.onnx
✅ Using NEURAL NETWORK for food recognition
```

Or if model not found:
```
⚠️  Model file not found. Using fallback mode.
   Expected model at: /path/to/backend/models/caifan_model.onnx
   💡 Tip: Train the model first using training/train_tui.py
⚠️  Using HEURISTIC fallback for food recognition
```

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### "Model file not found" in backend
```bash
# Check if model exists
ls -lh backend/models/caifan_model.onnx

# If not, copy from training
cp training/models/caifan_model.onnx backend/models/
cp training/models/classes.json backend/models/
```

### "CUDA out of memory"
Reduce batch size in configuration:
- Try: 16, 8, or even 4
- Or use CPU: The TUI will auto-select

### Poor validation accuracy
- Train for more epochs (20-50)
- Lower learning rate (0.0001)
- Add more training data
- Check dataset quality

### Slow training
- Use GPU if available
- Increase `num_workers` (4-8)
- Increase batch size (if memory allows)

## Advanced Usage

### Resume Training

```python
# Load existing checkpoint
checkpoint = torch.load('models/best_model.pth')
model.load_state_dict(checkpoint)

# Continue training...
```

### Custom Dataset

1. Organize images in class folders
2. Point `data_dir` to your folder
3. Train as normal
4. Classes will be auto-detected

### Transfer Learning

The model uses pre-trained ImageNet weights by default. For fine-tuning:

```python
# In train_tui.py
model = models.mobilenet_v3_small(weights='DEFAULT')  # Use pre-trained
# vs
model = models.mobilenet_v3_small(weights=None)       # Train from scratch
```

## Performance Expectations

### Training Time (CPU)
- Small dataset (5 classes, 500 images): ~5-10 min
- Medium dataset (20 classes, 5k images): ~30-60 min
- Full Food-101 (101 classes, 101k images): ~4-8 hours

### Training Time (GPU)
- Small: ~2-3 min
- Medium: ~10-15 min
- Full: ~1-2 hours

### Inference Speed
- CPU: ~50-100ms per image
- GPU: ~10-20ms per image

### Accuracy Goals
- Training accuracy: 80-95%
- Validation accuracy: 70-85%
- Real-world accuracy: 60-80% (depends on data similarity)

## Next Steps

1. ✅ Train your first model with sample data
2. ✅ Deploy to backend and test
3. ✅ Download full Food-101 dataset
4. ✅ Train production model
5. ✅ Fine-tune based on real usage
6. 🚀 Deploy to production!

## Files Reference

| File | Purpose |
|------|---------|
| `download_data.py` | Downloads Food-101 dataset |
| `train_tui.py` | Interactive training interface |
| `dataset.py` | PyTorch dataset implementation |
| `metrics.py` | Evaluation metrics (confusion matrix, P/R/F1) |
| `validate_data.py` | Dataset validation (corrupt/duplicate detection) |
| `requirements.txt` | Python dependencies |

## Questions?

Check the main README or create an issue on GitHub.
