# Backend Workflow

This folder contains the active MNPI workflow stages that the backend orchestrates.

- `layer0-parser/`: corpus parsing helpers
- `layer1-lexicon/`: rules, restricted list matching, spaCy, and Presidio checks
- `layer2-embeddings/`: sentence-transformer embedding generation and runtime encoding
- `layer3-clustering/`: isolation forest anomaly scoring
- `layer4-classification/`: transformer classifiers for risk and severity
- `layer5-mosaic/`: Redis-backed mosaic aggregation
- `layer6-regression/`: optional aggregate scoring layer
