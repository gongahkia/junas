#!/usr/bin/env python3
"""One-command preflight checks for local runtime readiness."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from noupe.configs.artifacts import (
    artifact_manifest_path,
    get_artifact_path,
    verify_artifact_manifest,
)
from noupe.configs.runtime import ConfigError, VALID_LAYERS, load_runtime_settings


def is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    except Exception as exc:
        return False, f"spaCy model load failed: {exc}"


def check_redis(host: str, port: int, timeout: float = 1.0) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True, f"redis reachable at {host}:{port}"
    except Exception as exc:
        return False, f"redis unreachable at {host}:{port} ({exc})"
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
    parser.add_argument("--config", type=str, help="override config.toml path for this run")
    parser.add_argument("--layers", type=str, help="override active pipeline layers for this run")
    args = parser.parse_args()

    cli_overrides: dict[str, object] = {}
    if args.config:
        cli_overrides["config_path"] = args.config
    if args.layers:
        cli_overrides["pipeline.layers"] = [layer.strip() for layer in args.layers.split(",") if layer.strip()]

    checks: list[str] = []
    warnings: list[str] = []

    try:
        settings = load_runtime_settings(cli_overrides=cli_overrides)
    except ConfigError as exc:
        settings = None
        warnings.append(str(exc))
    else:
        checks.append(f"settings validated: {settings.config_path}")

    if settings is not None:
        pipeline = list(settings.pipeline.layers)
        optional_layers = set(settings.pipeline.optional_layers)
        configured_layers = set(pipeline)
        invalid_layers = [layer for layer in pipeline if layer not in VALID_LAYERS]
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

        manifest_path = artifact_manifest_path()
        manifest_errors = verify_artifact_manifest(manifest_path)
        if manifest_errors:
            warnings.extend(manifest_errors)
        else:
            checks.append(f"artifact manifest verified: {manifest_path}")

        try:
            clust_ckpt = get_artifact_path("clustering")
        except FileNotFoundError as exc:
            record_layer_state("clustering", False, "", str(exc))
        else:
            record_layer_state(
                "clustering",
                clust_ckpt.exists(),
                f"clustering checkpoint present: {clust_ckpt}",
                f"clustering checkpoint missing: {clust_ckpt}",
            )

        try:
            m1_dir = get_artifact_path("model1")
        except FileNotFoundError as exc:
            record_layer_state("model1", False, "", str(exc))
        else:
            record_layer_state(
                "model1",
                has_model_weights(m1_dir),
                f"model1 weights present: {m1_dir}",
                f"model1 weights missing: {m1_dir}",
            )

        try:
            m2_dir = get_artifact_path("model2")
        except FileNotFoundError as exc:
            record_layer_state("model2", False, "", str(exc))
        else:
            record_layer_state(
                "model2",
                has_model_weights(m2_dir),
                f"model2 weights present: {m2_dir}",
                f"model2 weights missing: {m2_dir}",
            )

        try:
            reg_dir = get_artifact_path("regression")
        except FileNotFoundError as exc:
            record_layer_state("regression", False, "", str(exc))
        else:
            reg_model = reg_dir / "risk_regressor.json"
            reg_meta = reg_dir / "metadata.json"
            record_layer_state(
                "regression",
                reg_model.exists() and reg_meta.exists(),
                f"regression artifacts present: {reg_model}, {reg_meta}",
                f"regression artifacts missing: {reg_model} and/or {reg_meta}",
            )

        if "mosaic" in configured_layers:
            ok_redis, msg_redis = check_redis(
                settings.mosaic.redis_host,
                settings.mosaic.redis_port,
                timeout=max(0.1, settings.mosaic.connect_timeout_seconds),
            )
            record_layer_state("mosaic", ok_redis, msg_redis, msg_redis)

        hf_offline = any(
            [
                is_truthy(os.environ.get("NOUPE_HF_OFFLINE")),
                is_truthy(os.environ.get("TRANSFORMERS_OFFLINE")),
                is_truthy(os.environ.get("HF_HUB_OFFLINE")),
            ]
        )
        embed_model = settings.embeddings.model_name
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
    print(f"config_path: {settings.config_path if settings is not None else (Path(args.config).expanduser().resolve() if args.config else ROOT / 'config.toml')}")
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
        print("  - Hydrate or verify them with: python3 scripts/bootstrap_artifacts.py --sync-from-legacy")
        print("  - Regenerate them with: python3 scripts/bootstrap_artifacts.py --regenerate")
        print("  - Or run a minimal lexicon-only server with: PIPELINE_LAYERS=lexicon uvicorn backend.main:app --reload")

    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
