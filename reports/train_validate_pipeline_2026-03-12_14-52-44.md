# Train/Validate Pipeline Report

- Generated: `2026-03-12_14-52-44`
- Split strategy: document-level random 80/20 (`seed=42`)
- Documents: train=50, val=13, total=63
- Sentences: train=986, val=260, total=1246

## Pass 1 - Supervised Layer Metrics

| Model | Split | Weighted F1 | Macro F1 |
|---|---|---:|---:|
| Model 1 | Train | 0.9317 | 0.9253 |
| Model 1 | Val | 0.9020 | 0.8868 |
| Model 2 | Train | 1.0000 | 1.0000 |
| Model 2 | Val | 1.0000 | 1.0000 |

## Pass 1 - End-to-End Config Comparison (Validation Split)

| Config | Aliases (same content) | Samples | Accuracy | Macro F1 | Micro F1 | Request Errors |
|---|---|---:|---:|---:|---:|---:|
| eval_1.toml | eval_1.toml, eval_3.toml | 260 | 0.5231 | 0.5568 | 0.5231 | 0 |
| eval_2.toml | eval_2.toml, eval_4.toml | 260 | 0.5231 | 0.5568 | 0.5231 | 0 |
| eval_5.toml | eval_5.toml | 260 | 0.9000 | 0.8216 | 0.9000 | 0 |
| eval_6.toml | eval_6.toml | 260 | 0.3577 | 0.3838 | 0.3577 | 0 |
| eval_7.toml | eval_7.toml | 260 | 0.9038 | 0.8550 | 0.9038 | 0 |

## Non-Supervised Layer Operational Stats

| Config | Ready | Missing Required Layers | Embedding Loaded | Clustering Loaded | Mosaic Loaded | Regression Loaded |
|---|---|---|---|---|---|---|
| eval_1.toml | False | none | False | True | False | True |
| eval_2.toml | False | none | False | True | False | True |
| eval_5.toml | False | none | False | True | False | True |
| eval_6.toml | False | none | False | False | False | True |
| eval_7.toml | False | none | False | False | False | False |

## eval_1.toml

- Config path: `/Users/gongahkia/Desktop/coding/smu/Noupe/configs/eval_1.toml`
- Digest: `28d211be3805`
- Aliases: `eval_1.toml, eval_3.toml`
- Accuracy: `0.5231`

### Per-class Metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SAFE | 0.9118 | 0.3543 | 0.5103 | 175 |
| LOW_RISK | 0.2231 | 0.8056 | 0.3494 | 36 |
| HIGH_RISK | 0.7258 | 0.9184 | 0.8108 | 49 |

### Confusion Matrix

| expected \ predicted | SAFE | LOW_RISK | HIGH_RISK |
|---|---:|---:|---:|
| SAFE | 62 | 98 | 15 |
| LOW_RISK | 5 | 29 | 2 |
| HIGH_RISK | 1 | 3 | 45 |

## eval_2.toml

- Config path: `/Users/gongahkia/Desktop/coding/smu/Noupe/configs/eval_2.toml`
- Digest: `293070a28210`
- Aliases: `eval_2.toml, eval_4.toml`
- Accuracy: `0.5231`

### Per-class Metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SAFE | 0.9118 | 0.3543 | 0.5103 | 175 |
| LOW_RISK | 0.2231 | 0.8056 | 0.3494 | 36 |
| HIGH_RISK | 0.7258 | 0.9184 | 0.8108 | 49 |

### Confusion Matrix

| expected \ predicted | SAFE | LOW_RISK | HIGH_RISK |
|---|---:|---:|---:|
| SAFE | 62 | 98 | 15 |
| LOW_RISK | 5 | 29 | 2 |
| HIGH_RISK | 1 | 3 | 45 |

## eval_5.toml

- Config path: `/Users/gongahkia/Desktop/coding/smu/Noupe/configs/eval_5.toml`
- Digest: `7acf9863f908`
- Aliases: `eval_5.toml`
- Accuracy: `0.9000`

### Per-class Metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SAFE | 0.8744 | 0.9943 | 0.9305 | 175 |
| LOW_RISK | 0.9375 | 0.4167 | 0.5769 | 36 |
| HIGH_RISK | 1.0000 | 0.9184 | 0.9574 | 49 |

### Confusion Matrix

| expected \ predicted | SAFE | LOW_RISK | HIGH_RISK |
|---|---:|---:|---:|
| SAFE | 174 | 1 | 0 |
| LOW_RISK | 21 | 15 | 0 |
| HIGH_RISK | 4 | 0 | 45 |

## eval_6.toml

- Config path: `/Users/gongahkia/Desktop/coding/smu/Noupe/configs/eval_6.toml`
- Digest: `f13194bcdc95`
- Aliases: `eval_6.toml`
- Accuracy: `0.3577`

### Per-class Metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SAFE | 0.9524 | 0.1143 | 0.2041 | 175 |
| LOW_RISK | 0.1892 | 0.7778 | 0.3043 | 36 |
| HIGH_RISK | 0.4945 | 0.9184 | 0.6429 | 49 |

### Confusion Matrix

| expected \ predicted | SAFE | LOW_RISK | HIGH_RISK |
|---|---:|---:|---:|
| SAFE | 20 | 116 | 39 |
| LOW_RISK | 1 | 28 | 7 |
| HIGH_RISK | 0 | 4 | 45 |

## eval_7.toml

- Config path: `/Users/gongahkia/Desktop/coding/smu/Noupe/configs/eval_7.toml`
- Digest: `145a2171312a`
- Aliases: `eval_7.toml`
- Accuracy: `0.9038`

### Per-class Metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| SAFE | 0.9032 | 0.9600 | 0.9307 | 175 |
| LOW_RISK | 0.7586 | 0.6111 | 0.6769 | 36 |
| HIGH_RISK | 1.0000 | 0.9184 | 0.9574 | 49 |

### Confusion Matrix

| expected \ predicted | SAFE | LOW_RISK | HIGH_RISK |
|---|---:|---:|---:|
| SAFE | 168 | 7 | 0 |
| LOW_RISK | 14 | 22 | 0 |
| HIGH_RISK | 4 | 0 | 45 |

## Pass 2 - Final 100% Retraining

- Model 1 rows: `1246`
- Model 2 rows: `446`
- Clustering rows: `1246`
- Regression rows: `1246`

