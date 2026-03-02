#!/usr/bin/env python3
"""One-command preflight checks for local runtime readiness."""

import argparse
import json
import os
from pathlib import Path
import socket

try:
    import tomllib
except ImportError:
    import tomli as tomllib

VALID_LAYERS = {"lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"}


def load_config(config_path: Path):
    if not config_path.exists():
        return {}, [f"config file missing: {config_path}"]
    try:
        return tomllib.loads(config_path.read_text()), []
    except Exception as e:
        return {}, [f"config parse failure ({config_path}): {e}"]


def has_model_weights(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    for ext in ("safetensors", "bin", "pt", "ckpt"):
        if list(path.glob(f"*.{ext}")):
            return True
    return False


def check_spacy_model() -> tuple[bool, str]:
    try:
        import spacy

        spacy.load("en_core_web_sm")
        return True, "spaCy model en_core_web_sm loaded"
    except Exception as e:
        return False, f"spaCy model load failed: {e}"


def check_redis(host: str, port: int, timeout: float = 1.0) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True, f"redis reachable at {host}:{port}"
    except Exception as e:
        return False, f"redis unreachable at {host}:{port} ({e})"
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Noupe runtime preflight checks")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on any warning")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    config_path = Path(os.environ.get("NOUPE_CONFIG", str(root / "config.toml")))
    cfg, cfg_errors = load_config(config_path)

    checks = []
    warnings = []

    if cfg_errors:
        warnings.extend(cfg_errors)

    pipeline = cfg.get("pipeline", {}).get(
        "layers",
        ["lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"],
    )
    invalid_layers = [l for l in pipeline if l not in VALID_LAYERS]
    if invalid_layers:
        warnings.append(f"invalid pipeline layers in config: {invalid_layers}")
    else:
        checks.append(f"pipeline layers valid: {pipeline}")

    ok_spacy, msg_spacy = check_spacy_model()
    (checks if ok_spacy else warnings).append(msg_spacy)

    clust_ckpt = root / "layer3-clustering" / "checkpoints" / "anomaly_detector.joblib"
    if clust_ckpt.exists():
        checks.append(f"clustering checkpoint present: {clust_ckpt}")
    else:
        warnings.append(f"clustering checkpoint missing: {clust_ckpt}")

    m1_dir = root / "layer4-classification" / "model-1" / "checkpoints" / "best"
    if has_model_weights(m1_dir):
        checks.append(f"model1 weights present: {m1_dir}")
    else:
        warnings.append(f"model1 weights missing: {m1_dir}")

    m2_dir = root / "layer4-classification" / "model-2" / "checkpoints" / "best"
    if has_model_weights(m2_dir):
        checks.append(f"model2 weights present: {m2_dir}")
    else:
        warnings.append(f"model2 weights missing: {m2_dir}")

    reg_model = root / "layer6-regression" / "checkpoints" / "risk_regressor.json"
    reg_meta = root / "layer6-regression" / "checkpoints" / "metadata.json"
    if reg_model.exists() and reg_meta.exists():
        checks.append(f"regression artifacts present: {reg_model}, {reg_meta}")
    else:
        warnings.append(f"regression artifacts missing: {reg_model} and/or {reg_meta}")

    mosaic_cfg = cfg.get("mosaic", {})
    redis_host = os.environ.get("REDIS_HOST", str(mosaic_cfg.get("redis_host", "localhost")))
    redis_port = int(os.environ.get("REDIS_PORT", str(mosaic_cfg.get("redis_port", 6379))))
    ok_redis, msg_redis = check_redis(redis_host, redis_port)
    (checks if ok_redis else warnings).append(msg_redis)

    print("=== Noupe Preflight ===")
    print(f"config_path: {config_path}")
    print("checks:")
    for item in checks:
        print(f"  - {item}")
    print("warnings:")
    if warnings:
        for item in warnings:
            print(f"  - {item}")
    else:
        print("  - none")

    payload = {"checks": checks, "warnings": warnings}
    print("summary_json:")
    print(json.dumps(payload, indent=2))

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

