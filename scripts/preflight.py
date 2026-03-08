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


def is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_layers_list(raw: str | list | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


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


def has_sentence_transformer_cache(model_name: str) -> bool:
    model_name = model_name.strip()
    if not model_name:
        return False

    as_path = Path(model_name).expanduser()
    if as_path.exists():
        return True

    normalized = model_name.strip("/")
    st_home = Path(
        os.environ.get(
            "SENTENCE_TRANSFORMERS_HOME",
            str(Path.home() / ".cache" / "torch" / "sentence_transformers"),
        )
    ).expanduser()
    st_candidates = [
        st_home / normalized,
        st_home / normalized.replace("/", "_"),
        st_home / f"sentence-transformers_{normalized.replace('/', '_')}",
    ]
    for candidate in st_candidates:
        if candidate.exists():
            return True

    hf_home = Path(
        os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
    ).expanduser()
    hub_root = hf_home / "hub"
    hf_ids = [normalized]
    if "/" not in normalized:
        hf_ids.append(f"sentence-transformers/{normalized}")
    for model_id in hf_ids:
        repo_dir = hub_root / f"models--{model_id.replace('/', '--')}"
        snapshots = repo_dir / "snapshots"
        if snapshots.exists() and any(snapshots.iterdir()):
            return True
    return False


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
    optional_layers = set(parse_layers_list(cfg.get("pipeline", {}).get("optional_layers")))
    configured_layers = set(pipeline)
    invalid_layers = [l for l in pipeline if l not in VALID_LAYERS]
    if invalid_layers:
        warnings.append(f"invalid pipeline layers in config: {invalid_layers}")
    else:
        checks.append(f"pipeline layers valid: {pipeline}")

    def record_layer_state(layer: str, ok: bool, success_msg: str, failure_msg: str) -> None:
        if layer not in configured_layers:
            return
        if ok:
            checks.append(success_msg)
            return
        if layer in optional_layers:
            checks.append(f"{failure_msg} (optional layer)")
            return
        warnings.append(failure_msg)

    ok_spacy, msg_spacy = check_spacy_model()
    (checks if ok_spacy else warnings).append(msg_spacy)

    clust_ckpt = root / "layer3-clustering" / "checkpoints" / "anomaly_detector.joblib"
    record_layer_state(
        "clustering",
        clust_ckpt.exists(),
        f"clustering checkpoint present: {clust_ckpt}",
        f"clustering checkpoint missing: {clust_ckpt}",
    )

    m1_dir = root / "layer4-classification" / "model-1" / "checkpoints" / "best"
    record_layer_state(
        "model1",
        has_model_weights(m1_dir),
        f"model1 weights present: {m1_dir}",
        f"model1 weights missing: {m1_dir}",
    )

    m2_dir = root / "layer4-classification" / "model-2" / "checkpoints" / "best"
    record_layer_state(
        "model2",
        has_model_weights(m2_dir),
        f"model2 weights present: {m2_dir}",
        f"model2 weights missing: {m2_dir}",
    )

    reg_model = root / "layer6-regression" / "checkpoints" / "risk_regressor.json"
    reg_meta = root / "layer6-regression" / "checkpoints" / "metadata.json"
    record_layer_state(
        "regression",
        reg_model.exists() and reg_meta.exists(),
        f"regression artifacts present: {reg_model}, {reg_meta}",
        f"regression artifacts missing: {reg_model} and/or {reg_meta}",
    )

    mosaic_cfg = cfg.get("mosaic", {})
    redis_host = os.environ.get("REDIS_HOST", str(mosaic_cfg.get("redis_host", "localhost")))
    redis_port = int(os.environ.get("REDIS_PORT", str(mosaic_cfg.get("redis_port", 6379))))
    if "mosaic" in configured_layers:
        ok_redis, msg_redis = check_redis(redis_host, redis_port)
        record_layer_state("mosaic", ok_redis, msg_redis, msg_redis)

    hf_offline = any(
        [
            is_truthy(os.environ.get("NOUPE_HF_OFFLINE")),
            is_truthy(os.environ.get("TRANSFORMERS_OFFLINE")),
            is_truthy(os.environ.get("HF_HUB_OFFLINE")),
        ]
    )
    embed_model = str(cfg.get("embeddings", {}).get("model_name", "all-mpnet-base-v2"))
    if hf_offline:
        if has_sentence_transformer_cache(embed_model):
            checks.append(
                f"HF offline mode enabled and embedding model cache found for '{embed_model}'"
            )
        else:
            warnings.append(
                f"HF offline mode enabled but embedding model cache missing for '{embed_model}'"
            )
    else:
        checks.append("HF online mode (offline env flags not set)")

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

    artifact_warnings = [
        item for item in warnings
        if any(token in item for token in ("checkpoint missing", "weights missing", "artifacts missing"))
    ]
    if artifact_warnings:
        print("next_steps:")
        print("  - Full pipeline artifacts are not present in this checkout.")
        print("  - Generate them with: python3 train_validate_pipeline.py")
        print("  - Or run a minimal lexicon-only server with: PIPELINE_LAYERS=lexicon uvicorn backend.main:app --reload")

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
