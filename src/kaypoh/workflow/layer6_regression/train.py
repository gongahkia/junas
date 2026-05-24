#!/usr/bin/env python3
"""Train regression checkpoint with strict feature schema and persisted scaler."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

FEATURE_NAMES = [
    "lex_score",
    "lex_threshold",
    "lex_score_over_threshold",
    "m1_score",
    "m2_score",
    "clust_score",
    "mosaic_count",
]
TARGET_NAME = "target"
SCHEMA_VERSION = 2
DEFAULT_LEX_THRESHOLD = 10.0


def parse_args():
    parser = argparse.ArgumentParser(description="Train Kaypoh regression model")
    parser.add_argument("csv", type=Path, help="CSV path with feature columns + target")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "checkpoints",
        help="Output checkpoint directory",
    )
    return parser.parse_args()


def validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in FEATURE_NAMES + [TARGET_NAME] if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def ensure_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "lex_threshold" not in out.columns:
        out["lex_threshold"] = DEFAULT_LEX_THRESHOLD
    if "lex_score_over_threshold" not in out.columns:
        if "lex_score" not in out.columns:
            raise ValueError("Cannot derive lex_score_over_threshold without lex_score column")
        out["lex_score_over_threshold"] = (out["lex_score"] - out["lex_threshold"]).clip(lower=0.0)
    return out


def main() -> int:
    args = parse_args()
    if not args.csv.exists():
        raise FileNotFoundError(f"Training CSV not found: {args.csv}")

    df = pd.read_csv(args.csv)
    df = ensure_derived_features(df)
    validate_columns(df)

    X = df[FEATURE_NAMES].astype(np.float32).to_numpy()
    y = df[TARGET_NAME].astype(np.float32).to_numpy()
    y = np.clip(y, 0.0, 1.0)

    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    X_scaled = (X - mean) / std

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        objective="reg:squarederror",
    )
    model.fit(X_scaled, y)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.out_dir / "risk_regressor.json"
    metadata_path = args.out_dir / "metadata.json"

    model.save_model(str(model_path))
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "feature_names": FEATURE_NAMES,
        "scaler": {
            "mean": mean.tolist(),
            "std": std.tolist(),
        },
        "target": TARGET_NAME,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    print(f"[OK] Saved regression model: {model_path}")
    print(f"[OK] Saved regression metadata: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
