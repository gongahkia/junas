# cAI-png Training Pipeline

This directory contains the training logic for the Cai Fan dish classifier.

## Prerequisites

1.  Python 3.8+
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Data Preparation

Organize your dataset in the following structure:

```
data/
    chicken_curry/
        img1.jpg
        img2.jpg
    broccoli/
        img1.jpg
        ...
    rice/
        ...
```

The script automatically detects class names from the folder names.

## Usage

Run the training script:

```bash
python train.py --data_dir /path/to/your/dataset --output_dir ./models --epochs 20
```

## Output

The script will generate:
1.  `models/caifan_model.pth`: PyTorch model checkpoint.
2.  `models/caifan_model.onnx`: ONNX model for deployment (can be used in Node.js with `onnxruntime-node`).
3.  `models/classes.json`: Mapping of class indices to names.
