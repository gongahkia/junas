#!/usr/bin/env python3
"""Train/validate the full Noupe pipeline in two passes.

Pass 1 (80/20):
- train supervised models (model1/model2) and report train/val F1
- train clustering on train split
- train regression from upstream feature payloads on train split
- compare unique eval configs on validation split end-to-end accuracy

Pass 2 (100%):
- retrain final artifacts for model1/model2/clustering/regression on full corpus
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_ROOT = ROOT / "backend" / "workflow"
sys.path.insert(0, str(ROOT))

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

import numpy as np
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split

from helper.training_corpus import list_batch_files, load_documents_from_batches

DATA_DIR = ROOT / "docs" / "json"
LABELS = ["SAFE", "LOW_RISK", "HIGH_RISK"]
FEATURE_COLUMNS = [
    "lex_score",
    "lex_threshold",
    "lex_score_over_threshold",
    "m1_score",
    "m2_score",
    "clust_score",
    "mosaic_count",
]
UPSTREAM_LAYERS = "lexicon,embedding,clustering,model1,model2,mosaic"
CLASSIFY_TIMEOUT_SECONDS = 30
CLASSIFY_MAX_RETRIES = 3
CLASSIFY_RETRY_BACKOFF_SECONDS = 1.5

_LABEL_MAP = {
    "non": "non",
    "non-sensitive": "non",
    "non sensitivity": "non",
    "low": "low",
    "low sensitivity": "low",
    "low-risk": "low",
    "high": "high",
    "high sensitivity": "high",
    "high-risk": "high",
}
CLASS_MAP = {
    "non": "SAFE",
    "low": "LOW_RISK",
    "high": "HIGH_RISK",
}
REGRESSION_TARGET_MAP = {
    "non": 0.0,
    "low": 0.5,
    "high": 1.0,
}


@dataclass
class BackendHandle:
    process: subprocess.Popen
    log_path: Path
    log_fp: Any


@dataclass
class ConfigEntry:
    path: Path
    digest: str
    aliases: list[str]


class PipelineError(RuntimeError):
    """Raised for hard failures that should end script execution."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train/validate full Noupe pipeline")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for 80/20 split")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split ratio")
    parser.add_argument(
        "--base-config",
        type=Path,
        default=ROOT / "config.toml",
        help="Primary config used for training and feature extraction",
    )
    parser.add_argument(
        "--eval-config-pattern",
        default="configs/eval_*.toml",
        help="Glob pattern for pipeline comparison configs",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=ROOT / "reports",
        help="Directory for Markdown report output",
    )
    parser.add_argument("--base-port", type=int, default=8100, help="Base port for backend eval runs")
    parser.add_argument("--startup-timeout", type=int, default=60, help="Backend startup timeout in seconds")
    parser.add_argument(
        "--resume-state-file",
        type=Path,
        default=ROOT / "reports" / ".train_validate_state.json",
        help="Path to persistent pipeline resume-state JSON",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable stage resume; always rerun all stages",
    )
    parser.add_argument(
        "--reset-resume-state",
        action="store_true",
        help="Delete existing resume-state before starting",
    )
    return parser.parse_args()


def get_python_executable() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    return str(venv_python) if venv_python.exists() else sys.executable


def refresh_artifact_manifest(python_exec: str) -> None:
    cmd = [
        python_exec,
        str(ROOT / "scripts" / "bootstrap_artifacts.py"),
        "--update-manifest",
        "--sync-from-legacy",
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def fingerprint_file(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not path.exists():
        return {
            "path": str(resolved),
            "missing": True,
        }

    try:
        return {
            "path": str(resolved),
            "sha256": file_sha256(path),
        }
    except Exception as exc:
        stat = path.stat()
        return {
            "path": str(resolved),
            "sha256_error": str(exc),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }


def build_run_signature(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    eval_paths = [Path(p) for p in sorted(glob.glob(str(ROOT / args.eval_config_pattern)))]
    data_paths = list_batch_files(DATA_DIR)

    payload = {
        "seed": args.seed,
        "test_size": args.test_size,
        "base_port": args.base_port,
        "startup_timeout": args.startup_timeout,
        "base_config": fingerprint_file(args.base_config),
        "eval_config_pattern": args.eval_config_pattern,
        "eval_configs": [fingerprint_file(path) for path in eval_paths],
        "data_files": [fingerprint_file(path) for path in data_paths],
        "pipeline_script": fingerprint_file(Path(__file__)),
    }

    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return signature, payload


def persist_resume_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_raw = tempfile.mkstemp(
        prefix=f"{state_path.name}.",
        suffix=".tmp",
        dir=str(state_path.parent),
    )
    tmp_path = Path(tmp_raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2, sort_keys=True)
        os.replace(tmp_path, state_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def load_resume_state(
    *,
    state_path: Path,
    run_signature: str,
    signature_payload: dict[str, Any],
    resume_enabled: bool,
    reset_state: bool,
) -> dict[str, Any]:
    if reset_state and state_path.exists():
        print(f"  [resume] Removing existing state file: {state_path}")
        state_path.unlink()

    base_state = {
        "run_signature": run_signature,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "signature_payload": signature_payload,
        "stages": {},
    }

    if not resume_enabled:
        return base_state

    if not state_path.exists():
        persist_resume_state(state_path, base_state)
        print(f"  [resume] Initialized new state file: {state_path}")
        return base_state

    try:
        existing = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [resume] Failed to parse state file ({state_path}); resetting. Reason: {exc}")
        persist_resume_state(state_path, base_state)
        return base_state

    if existing.get("run_signature") != run_signature:
        print("  [resume] State signature mismatch; starting a fresh state for this run.")
        persist_resume_state(state_path, base_state)
        return base_state

    existing.setdefault("stages", {})
    existing["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"  [resume] Loaded existing state: {state_path}")
    return existing


def run_stage(
    *,
    stage_key: str,
    runner: Any,
    resume_enabled: bool,
    state_path: Path,
    resume_state: dict[str, Any],
) -> Any:
    stages = resume_state.setdefault("stages", {})
    if resume_enabled:
        cached = stages.get(stage_key)
        if cached and cached.get("status") == "done":
            print(f"  [resume] Stage already complete, skipping: {stage_key}")
            return cached.get("result")

    started = time.time()
    print(f"  [stage] Running {stage_key}")
    try:
        result = runner()
    except Exception as exc:
        if resume_enabled:
            stages[stage_key] = {
                "status": "failed",
                "error": str(exc),
                "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            resume_state["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            persist_resume_state(state_path, resume_state)
        raise

    elapsed = round(time.time() - started, 3)
    if resume_enabled:
        stages[stage_key] = {
            "status": "done",
            "elapsed_seconds": elapsed,
            "completed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "result": result,
        }
        resume_state["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        persist_resume_state(state_path, resume_state)
    print(f"  [stage] Completed {stage_key} in {elapsed:.3f}s")
    return result


def load_documents(data_dir: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for doc in load_documents_from_batches(data_dir):
        sentences: list[dict[str, Any]] = []
        for sent in doc["sentences"]:
            text = str(sent.get("text", "")).strip()
            raw_label = str(sent.get("label", "")).strip().lower()
            label = _LABEL_MAP.get(raw_label)
            if text and label:
                sentences.append(
                    {
                        "text": text,
                        "label": label,
                        "sentence_index": sent["sentence_index"],
                    }
                )

        if sentences:
            documents.append(
                {
                    "path": doc["path"],
                    "document_name": doc["document_name"],
                    "entity_id": doc["entity_id"],
                    "sentences": sentences,
                }
            )

    return documents


def split_documents(documents: list[dict[str, Any]], test_size: float, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Mirror training/train_validate_classification.py split behavior exactly."""
    if len(documents) < 2:
        raise PipelineError(f"Need at least 2 documents to split, found {len(documents)}")

    indices = list(range(len(documents)))
    train_idx, val_idx = train_test_split(indices, test_size=test_size, random_state=seed)
    train_docs = [documents[i] for i in sorted(train_idx)]
    val_docs = [documents[i] for i in sorted(val_idx)]
    return train_docs, val_docs


def extract_model1_rows(documents: list[dict[str, Any]]) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for doc in documents:
        for sentence in doc["sentences"]:
            rows.append((sentence["text"], 0 if sentence["label"] == "non" else 1))
    return rows


def extract_model2_rows(documents: list[dict[str, Any]]) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for doc in documents:
        for sentence in doc["sentences"]:
            if sentence["label"] in ("low", "high"):
                rows.append((sentence["text"], 0 if sentence["label"] == "low" else 1))
    return rows


def extract_sentence_samples(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for doc in documents:
        for sentence in doc["sentences"]:
            samples.append(
                {
                    "text": sentence["text"],
                    "label": sentence["label"],
                    "expected": CLASS_MAP[sentence["label"]],
                    "entity_id": doc["entity_id"],
                    "document_name": doc["document_name"],
                    "sentence_index": sentence["sentence_index"],
                }
            )
    return samples


def label_distribution(rows: list[tuple[str, int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for _, label in rows:
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def write_temp_csv(rows: list[tuple[str, int]]) -> Path:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["text", "label"])
        writer.writerows(rows)
    return Path(path)


def load_module_from_path(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise PipelineError(f"Unable to load module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_f1(trainer: Any, dataset: Any, target_names: list[str]) -> dict[str, Any]:
    result = trainer.predict(dataset)
    preds = np.argmax(result.predictions, axis=1)
    labels = result.label_ids

    weighted = float(f1_score(labels, preds, average="weighted"))
    macro = float(f1_score(labels, preds, average="macro"))
    report = classification_report(labels, preds, digits=4, target_names=target_names, zero_division=0)

    return {
        "weighted_f1": weighted,
        "macro_f1": macro,
        "report": report,
    }


def train_classification_model(
    *,
    model_path: Path,
    train_rows: list[tuple[str, int]],
    val_rows: list[tuple[str, int]] | None,
    model_name: str,
    target_names: list[str],
    evaluate: bool,
) -> dict[str, Any]:
    if not train_rows:
        raise PipelineError(f"No training rows for {model_name}")

    train_classes = {label for _, label in train_rows}
    if len(train_classes) < 2:
        raise PipelineError(f"Training rows for {model_name} contain only one class: {sorted(train_classes)}")

    if evaluate:
        if not val_rows:
            raise PipelineError(f"Validation rows missing for {model_name}")
        val_classes = {label for _, label in val_rows}
        if len(val_classes) < 2:
            raise PipelineError(f"Validation rows for {model_name} contain only one class: {sorted(val_classes)}")

    checkpoints_dir = model_path / "checkpoints"
    if checkpoints_dir.exists():
        shutil.rmtree(checkpoints_dir)

    train_csv = write_temp_csv(train_rows)
    val_csv = write_temp_csv(val_rows) if val_rows else None

    try:
        classifier_module = load_module_from_path(
            f"{model_path.name}_classifier",
            model_path / "classifier.py",
        )
        trainer = classifier_module.train(str(train_csv), str(val_csv) if val_csv else None)

        metrics: dict[str, Any] = {
            "train_size": len(train_rows),
            "val_size": len(val_rows or []),
            "train_distribution": label_distribution(train_rows),
            "val_distribution": label_distribution(val_rows or []),
        }

        if evaluate and val_rows:
            metrics["train"] = evaluate_f1(trainer, trainer.train_dataset, target_names)
            metrics["val"] = evaluate_f1(trainer, trainer.eval_dataset, target_names)

        return metrics
    finally:
        train_csv.unlink(missing_ok=True)
        if val_csv:
            val_csv.unlink(missing_ok=True)


def read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fp:
            return tomllib.load(fp)
    except Exception:
        return {}


def get_embedding_model_name(config_path: Path) -> str:
    cfg = read_toml(config_path)
    return str(cfg.get("embeddings", {}).get("model_name", "all-mpnet-base-v2"))


def train_clustering(documents: list[dict[str, Any]], embedding_model_name: str, python_exec: str) -> dict[str, Any]:
    from sentence_transformers import SentenceTransformer

    texts = [sentence["text"] for doc in documents for sentence in doc["sentences"]]
    if not texts:
        raise PipelineError("No texts available for clustering training")

    print(f"  [clustering] Encoding {len(texts)} sentence(s) with {embedding_model_name}...")
    model = SentenceTransformer(embedding_model_name)
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=True)

    fd, npy_path_raw = tempfile.mkstemp(suffix=".npy")
    os.close(fd)
    npy_path = Path(npy_path_raw)
    try:
        np.save(str(npy_path), embeddings)
        cmd = [python_exec, str(WORKFLOW_ROOT / "layer3-clustering" / "isolation_forest.py"), str(npy_path)]
        run_checked(cmd, "clustering training")
    finally:
        npy_path.unlink(missing_ok=True)

    return {
        "samples": len(texts),
        "embedding_dim": int(embeddings.shape[1]) if len(embeddings.shape) > 1 else 0,
    }


def run_checked(cmd: list[str], label: str, cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT))
    if proc.returncode != 0:
        raise PipelineError(f"{label} failed with exit code {proc.returncode}: {' '.join(cmd)}")


def wait_for_server(base_url: str, timeout_s: int) -> bool:
    deadline = time.time() + timeout_s
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def wait_for_ready_state(base_url: str, timeout_s: int) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last_payload: dict[str, Any] = {}
    ready_url = f"{base_url}/ready"
    while time.time() < deadline:
        try:
            payload = http_get_json(ready_url, timeout_s=5)
            last_payload = payload
            if bool(payload.get("ready", False)):
                return payload
            if payload.get("missing_required_layers"):
                return payload
            if payload.get("warming_required_layers"):
                time.sleep(1)
                continue
        except Exception:
            pass
        time.sleep(1)
    return last_payload


def http_get_json(url: str, timeout_s: int = 5) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def classify(base_url: str, text: str, entity_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"text": text}
    if entity_id:
        payload["entity_id"] = entity_id

    last_error: Exception | None = None
    for attempt in range(1, CLASSIFY_MAX_RETRIES + 1):
        request = urllib.request.Request(
            f"{base_url}/classify",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=CLASSIFY_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= CLASSIFY_MAX_RETRIES:
                break
            sleep_seconds = CLASSIFY_RETRY_BACKOFF_SECONDS * attempt
            time.sleep(sleep_seconds)

    if last_error is None:
        raise PipelineError("classify request failed without a captured exception")
    raise last_error


def start_backend(config_path: Path, port: int, seed: int, extra_env: dict[str, str] | None = None) -> BackendHandle:
    python_exec = get_python_executable()
    env = {
        **os.environ,
        "NOUPE_CONFIG": str(config_path.resolve()),
        "NOUPE_DETERMINISTIC": "1",
        "NOUPE_SEED": str(seed),
        "PYTHONUNBUFFERED": "1",
    }
    if extra_env:
        env.update(extra_env)

    fd, log_path_raw = tempfile.mkstemp(prefix=f"noupe_backend_{port}_", suffix=".log")
    os.close(fd)
    log_path = Path(log_path_raw)
    log_fp = log_path.open("w", encoding="utf-8")

    cmd = [
        python_exec,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    process = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
    )
    return BackendHandle(process=process, log_path=log_path, log_fp=log_fp)


def stop_backend(handle: BackendHandle) -> None:
    try:
        if handle.process.poll() is None:
            handle.process.send_signal(signal.SIGINT)
            try:
                handle.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                handle.process.kill()
                handle.process.wait(timeout=5)
    finally:
        handle.log_fp.close()


def start_backend_and_wait(
    config_path: Path,
    port: int,
    seed: int,
    timeout_s: int,
    extra_env: dict[str, str] | None = None,
) -> tuple[BackendHandle, str]:
    handle = start_backend(config_path=config_path, port=port, seed=seed, extra_env=extra_env)
    base_url = f"http://127.0.0.1:{port}"
    if wait_for_server(base_url, timeout_s):
        return handle, base_url

    stop_backend(handle)
    log_text = handle.log_path.read_text(encoding="utf-8", errors="ignore")
    raise PipelineError(
        f"Backend failed to start for config {config_path} on port {port}. "
        f"Log: {handle.log_path}\n{log_text[-4000:]}"
    )


def build_regression_rows(
    *,
    samples: list[dict[str, Any]],
    config_path: Path,
    seed: int,
    port: int,
    timeout_s: int,
    entity_prefix: str,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    extra_env = {
        "PIPELINE_LAYERS": UPSTREAM_LAYERS,
        "NOUPE_OPTIONAL_LAYERS": "mosaic,regression",
        "NOUPE_FAIL_ON_LAYER_LOAD_ERROR": "0",
        "NOUPE_LAZY_LOAD_HEAVY": "0",
        "NOUPE_PREWARM_REQUIRED_LAYERS": "0",
    }

    handle, base_url = start_backend_and_wait(
        config_path=config_path,
        port=port,
        seed=seed,
        timeout_s=timeout_s,
        extra_env=extra_env,
    )
    try:
        health = http_get_json(f"{base_url}/health", timeout_s=5)
        ready = wait_for_ready_state(base_url, timeout_s=timeout_s)
        diagnostics = http_get_json(f"{base_url}/diagnostics", timeout_s=5)

        required_layers = {"model1", "model2", "clustering"}
        pipeline_layers = set(diagnostics.get("pipeline", []))
        available_layers = set(diagnostics.get("loaded_layers", [])) | set(diagnostics.get("lazy_layers", []))

        missing_in_pipeline = sorted(required_layers - pipeline_layers)
        if missing_in_pipeline:
            raise PipelineError(
                f"Regression feature extraction config missing required layers in pipeline: {missing_in_pipeline}"
            )

        missing_unavailable = sorted(required_layers - available_layers)
        if missing_unavailable:
            raise PipelineError(
                f"Regression feature extraction missing available layers: {missing_unavailable}"
            )

        if not bool(ready.get("ready", False)):
            missing_required = ready.get("missing_required_layers", [])
            warming_required = ready.get("warming_required_layers", [])
            reasons = ready.get("reasons", [])
            raise PipelineError(
                "Regression feature extraction backend not ready; "
                f"missing required layers: {missing_required}; "
                f"warming required layers: {warming_required}; "
                f"reasons: {reasons}"
            )

        rows: list[dict[str, float]] = []
        request_errors = 0
        total = len(samples)
        for index, sample in enumerate(samples, start=1):
            if index % 50 == 0 or index == total:
                print(f"  [regression] featurizing sample {index}/{total}")

            scoped_entity_id = f"{entity_prefix}:{sample['entity_id']}"
            try:
                response = classify(base_url, sample["text"], entity_id=scoped_entity_id)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                request_errors += 1
                if request_errors <= 5 or request_errors % 25 == 0:
                    print(
                        "  [warn] regression featurization request failed "
                        f"(sample={index}/{total}, errors={request_errors}): {exc}"
                    )
                continue

            lexicon = response.get("lexicon") or {}
            model1 = response.get("model1") or {}
            model2 = response.get("model2") or {}
            clustering = response.get("clustering") or {}
            mosaic = response.get("mosaic") or {}

            lex_score = float(lexicon.get("total_score", 0.0) or 0.0)
            lex_threshold = float(lexicon.get("score_threshold", 0.0) or 0.0)
            row = {
                "lex_score": lex_score,
                "lex_threshold": lex_threshold,
                "lex_score_over_threshold": max(0.0, lex_score - lex_threshold),
                "m1_score": float(model1.get("risk_score", 0.0) or 0.0),
                "m2_score": float(model2.get("high_risk_score", 0.0) or 0.0),
                "clust_score": float(clustering.get("anomaly_score", 0.0) or 0.0),
                "mosaic_count": float(mosaic.get("count", 0.0) or 0.0),
                "target": float(REGRESSION_TARGET_MAP[sample["label"]]),
            }
            rows.append(row)

        if not rows:
            raise PipelineError("No regression feature rows were produced.")
        if request_errors > 0:
            print(
                "  [warn] regression featurization completed with "
                f"{request_errors} request error(s); using {len(rows)} successful row(s)."
            )
            health = dict(health)
            health["regression_request_errors"] = request_errors
            health["regression_rows_built"] = len(rows)

        return rows, health
    finally:
        stop_backend(handle)


def write_regression_csv(rows: list[dict[str, float]]) -> Path:
    fd, path_raw = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(FEATURE_COLUMNS + ["target"])
        for row in rows:
            writer.writerow([row[col] for col in FEATURE_COLUMNS] + [row["target"]])
    return Path(path_raw)


def train_regression(
    *,
    samples: list[dict[str, Any]],
    config_path: Path,
    seed: int,
    port: int,
    timeout_s: int,
    entity_prefix: str,
    python_exec: str,
) -> dict[str, Any]:
    if not samples:
        raise PipelineError("No samples available for regression training")

    rows, health = build_regression_rows(
        samples=samples,
        config_path=config_path,
        seed=seed,
        port=port,
        timeout_s=timeout_s,
        entity_prefix=entity_prefix,
    )

    regression_csv = write_regression_csv(rows)
    try:
        cmd = [python_exec, str(WORKFLOW_ROOT / "layer6-regression" / "train.py"), str(regression_csv)]
        run_checked(cmd, "regression training")
    finally:
        regression_csv.unlink(missing_ok=True)

    return {
        "rows": len(rows),
        "health": health,
    }


def discover_unique_configs(pattern: str) -> list[ConfigEntry]:
    absolute_pattern = str(ROOT / pattern)
    paths = [Path(p) for p in sorted(glob.glob(absolute_pattern))]
    if not paths:
        raise PipelineError(f"No evaluation configs found for pattern: {pattern}")

    by_digest: dict[str, ConfigEntry] = {}
    for path in paths:
        try:
            with path.open("rb") as fp:
                parsed = tomllib.load(fp)
            normalized = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        except Exception:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in by_digest:
            by_digest[digest] = ConfigEntry(path=path, digest=digest[:12], aliases=[path.name])
        else:
            by_digest[digest].aliases.append(path.name)

    return list(by_digest.values())


def compute_metrics(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    confusion = {exp: {pred: 0 for pred in LABELS} for exp in LABELS}

    for predicted, expected in pairs:
        if expected in confusion and predicted in confusion[expected]:
            confusion[expected][predicted] += 1
        if predicted == expected:
            tp[expected] += 1
        else:
            fp[predicted] += 1
            fn[expected] += 1

    per_class: dict[str, dict[str, float]] = {}
    for label in LABELS:
        p_denom = tp[label] + fp[label]
        r_denom = tp[label] + fn[label]
        precision = tp[label] / p_denom if p_denom else 0.0
        recall = tp[label] / r_denom if r_denom else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        support = r_denom
        per_class[label] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "support": int(support),
        }

    macro_precision = sum(item["precision"] for item in per_class.values()) / len(LABELS)
    macro_recall = sum(item["recall"] for item in per_class.values()) / len(LABELS)
    macro_f1 = sum(item["f1"] for item in per_class.values()) / len(LABELS)

    micro_tp = sum(tp.values())
    micro_fp = sum(fp.values())
    micro_fn = sum(fn.values())
    micro_precision = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) else 0.0
    micro_recall = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    accuracy = sum(tp.values()) / len(pairs) if pairs else 0.0

    return {
        "per_class": per_class,
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "micro_precision": float(micro_precision),
        "micro_recall": float(micro_recall),
        "micro_f1": float(micro_f1),
        "accuracy": float(accuracy),
        "confusion": confusion,
    }


def evaluate_configs(
    *,
    config_entries: list[ConfigEntry],
    eval_samples: list[dict[str, Any]],
    seed: int,
    base_port: int,
    timeout_s: int,
) -> list[dict[str, Any]]:
    if not eval_samples:
        raise PipelineError("Validation split has no samples for config evaluation")

    results: list[dict[str, Any]] = []

    for index, entry in enumerate(config_entries):
        port = base_port + index
        print(f"  [eval] Running {entry.aliases[0]} (digest={entry.digest}) on port {port}")

        handle, base_url = start_backend_and_wait(
            config_path=entry.path,
            port=port,
            seed=seed,
            timeout_s=timeout_s,
            extra_env=None,
        )

        try:
            health = http_get_json(f"{base_url}/health", timeout_s=5)
            ready = http_get_json(f"{base_url}/ready", timeout_s=5)

            pairs: list[tuple[str, str]] = []
            request_errors = 0
            for sample in eval_samples:
                scoped_entity_id = f"{entry.digest}:{sample['entity_id']}"
                try:
                    response = classify(base_url, sample["text"], entity_id=scoped_entity_id)
                    predicted = str(response.get("classification", "")).upper().strip()
                    expected = sample["expected"]
                    if predicted in LABELS:
                        pairs.append((predicted, expected))
                    else:
                        request_errors += 1
                except urllib.error.URLError:
                    request_errors += 1
                except Exception:
                    request_errors += 1

            if not pairs:
                raise PipelineError(f"No valid predictions produced for {entry.path}")
            if request_errors > 0:
                raise PipelineError(
                    f"Encountered {request_errors} request error(s) while evaluating {entry.path.name}"
                )

            metrics = compute_metrics(pairs)
            results.append(
                {
                    "config": entry.path.name,
                    "config_path": str(entry.path),
                    "digest": entry.digest,
                    "aliases": entry.aliases,
                    "samples": len(pairs),
                    "request_errors": request_errors,
                    "health": health,
                    "ready": ready,
                    "metrics": metrics,
                }
            )
        finally:
            stop_backend(handle)

    return results


def render_confusion_table(confusion: dict[str, dict[str, int]]) -> str:
    lines = [
        "| expected \\ predicted | SAFE | LOW_RISK | HIGH_RISK |",
        "|---|---:|---:|---:|",
    ]
    for expected in LABELS:
        row = confusion[expected]
        lines.append(
            f"| {expected} | {row['SAFE']} | {row['LOW_RISK']} | {row['HIGH_RISK']} |"
        )
    return "\n".join(lines)


def write_report(
    *,
    report_dir: Path,
    split_stats: dict[str, Any],
    pass1_classification: dict[str, Any],
    config_results: list[dict[str, Any]],
    pass2_stats: dict[str, Any],
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = report_dir / f"train_validate_pipeline_{timestamp}.md"

    lines: list[str] = []
    lines.append("# Train/Validate Pipeline Report")
    lines.append("")
    lines.append(f"- Generated: `{timestamp}`")
    lines.append(f"- Split strategy: document-level random 80/20 (`seed={split_stats['seed']}`)")
    lines.append(f"- Documents: train={split_stats['train_docs']}, val={split_stats['val_docs']}, total={split_stats['total_docs']}")
    lines.append(f"- Sentences: train={split_stats['train_sentences']}, val={split_stats['val_sentences']}, total={split_stats['total_sentences']}")
    lines.append("")

    lines.append("## Pass 1 - Supervised Layer Metrics")
    lines.append("")
    lines.append("| Model | Split | Weighted F1 | Macro F1 |")
    lines.append("|---|---|---:|---:|")
    for model_name, metrics in pass1_classification.items():
        lines.append(
            f"| {model_name} | Train | {metrics['train']['weighted_f1']:.4f} | {metrics['train']['macro_f1']:.4f} |"
        )
        lines.append(
            f"| {model_name} | Val | {metrics['val']['weighted_f1']:.4f} | {metrics['val']['macro_f1']:.4f} |"
        )
    lines.append("")

    lines.append("## Pass 1 - End-to-End Config Comparison (Validation Split)")
    lines.append("")
    lines.append("| Config | Aliases (same content) | Samples | Accuracy | Macro F1 | Micro F1 | Request Errors |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for result in config_results:
        aliases = ", ".join(result["aliases"])
        metrics = result["metrics"]
        lines.append(
            f"| {result['config']} | {aliases} | {result['samples']} | {metrics['accuracy']:.4f} | "
            f"{metrics['macro_f1']:.4f} | {metrics['micro_f1']:.4f} | {result['request_errors']} |"
        )
    lines.append("")

    lines.append("## Non-Supervised Layer Operational Stats")
    lines.append("")
    lines.append("| Config | Ready | Missing Required Layers | Embedding Loaded | Clustering Loaded | Mosaic Loaded | Regression Loaded |")
    lines.append("|---|---|---|---|---|---|---|")
    for result in config_results:
        ready = result["ready"]
        health = result["health"]
        missing = ", ".join(ready.get("missing_required_layers", [])) or "none"
        lines.append(
            f"| {result['config']} | {ready.get('ready')} | {missing} | "
            f"{health.get('embedding_loaded')} | {health.get('clustering_loaded')} | "
            f"{health.get('mosaic_loaded')} | {health.get('regression_loaded')} |"
        )
    lines.append("")

    for result in config_results:
        metrics = result["metrics"]
        lines.append(f"## {result['config']}")
        lines.append("")
        lines.append(f"- Config path: `{result['config_path']}`")
        lines.append(f"- Digest: `{result['digest']}`")
        lines.append(f"- Aliases: `{', '.join(result['aliases'])}`")
        lines.append(f"- Accuracy: `{metrics['accuracy']:.4f}`")
        lines.append("")
        lines.append("### Per-class Metrics")
        lines.append("")
        lines.append("| Label | Precision | Recall | F1 | Support |")
        lines.append("|---|---:|---:|---:|---:|")
        for label in LABELS:
            m = metrics["per_class"][label]
            lines.append(
                f"| {label} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['support']} |"
            )
        lines.append("")
        lines.append("### Confusion Matrix")
        lines.append("")
        lines.append(render_confusion_table(metrics["confusion"]))
        lines.append("")

    lines.append("## Pass 2 - Final 100% Retraining")
    lines.append("")
    lines.append(f"- Model 1 rows: `{pass2_stats['model1_rows']}`")
    lines.append(f"- Model 2 rows: `{pass2_stats['model2_rows']}`")
    lines.append(f"- Clustering rows: `{pass2_stats['clustering_rows']}`")
    lines.append(f"- Regression rows: `{pass2_stats['regression_rows']}`")
    lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def print_supervised_summary(pass1_classification: dict[str, Any]) -> None:
    print("\nPass 1 supervised metrics")
    print("=" * 64)
    header = f"{'Model':<28} {'Split':<7} {'Weighted F1':>12} {'Macro F1':>10}"
    print(header)
    print("-" * len(header))
    for model_name, metrics in pass1_classification.items():
        print(
            f"{model_name:<28} {'Train':<7} {metrics['train']['weighted_f1']:>12.4f} {metrics['train']['macro_f1']:>10.4f}"
        )
        print(
            f"{model_name:<28} {'Val':<7} {metrics['val']['weighted_f1']:>12.4f} {metrics['val']['macro_f1']:>10.4f}"
        )


def print_config_summary(config_results: list[dict[str, Any]]) -> None:
    print("\nPass 1 config comparison (validation split)")
    print("=" * 64)
    for result in config_results:
        metrics = result["metrics"]
        print(
            f"- {result['config']} aliases={result['aliases']} "
            f"accuracy={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f} "
            f"micro_f1={metrics['micro_f1']:.4f} errors={result['request_errors']}"
        )


def run_pass1(
    *,
    train_docs: list[dict[str, Any]],
    val_docs: list[dict[str, Any]],
    args: argparse.Namespace,
    python_exec: str,
    embedding_model_name: str,
    resume_enabled: bool,
    resume_state: dict[str, Any],
    resume_state_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    print("\n[Pass 1] 80/20 training + validation metrics")

    m1_train = extract_model1_rows(train_docs)
    m1_val = extract_model1_rows(val_docs)
    m2_train = extract_model2_rows(train_docs)
    m2_val = extract_model2_rows(val_docs)

    print(f"  model1 rows: train={len(m1_train)} val={len(m1_val)}")
    print(f"  model2 rows: train={len(m2_train)} val={len(m2_val)}")

    model1_metrics = run_stage(
        stage_key="pass1.model1",
        runner=lambda: train_classification_model(
            model_path=WORKFLOW_ROOT / "layer4-classification" / "model-1",
            train_rows=m1_train,
            val_rows=m1_val,
            model_name="Model 1",
            target_names=["safe (0)", "risk (1)"],
            evaluate=True,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )
    model2_metrics = run_stage(
        stage_key="pass1.model2",
        runner=lambda: train_classification_model(
            model_path=WORKFLOW_ROOT / "layer4-classification" / "model-2",
            train_rows=m2_train,
            val_rows=m2_val,
            model_name="Model 2",
            target_names=["low_risk (0)", "high_risk (1)"],
            evaluate=True,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    run_stage(
        stage_key="pass1.clustering",
        runner=lambda: train_clustering(train_docs, embedding_model_name, python_exec),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    regression_samples = extract_sentence_samples(train_docs)
    run_stage(
        stage_key="pass1.regression",
        runner=lambda: train_regression(
            samples=regression_samples,
            config_path=args.base_config,
            seed=args.seed,
            port=args.base_port + 100,
            timeout_s=args.startup_timeout,
            entity_prefix="pass1-reg",
            python_exec=python_exec,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    config_entries = discover_unique_configs(args.eval_config_pattern)
    val_samples = extract_sentence_samples(val_docs)
    config_results = run_stage(
        stage_key="pass1.config_eval",
        runner=lambda: evaluate_configs(
            config_entries=config_entries,
            eval_samples=val_samples,
            seed=args.seed,
            base_port=args.base_port,
            timeout_s=args.startup_timeout,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    pass1_classification = {
        "Model 1": {
            "train": model1_metrics["train"],
            "val": model1_metrics["val"],
        },
        "Model 2": {
            "train": model2_metrics["train"],
            "val": model2_metrics["val"],
        },
    }

    return pass1_classification, config_results


def run_pass2(
    *,
    all_docs: list[dict[str, Any]],
    args: argparse.Namespace,
    python_exec: str,
    embedding_model_name: str,
    resume_enabled: bool,
    resume_state: dict[str, Any],
    resume_state_path: Path,
) -> dict[str, Any]:
    print("\n[Pass 2] 100% retraining for final artifacts")

    m1_rows = extract_model1_rows(all_docs)
    m2_rows = extract_model2_rows(all_docs)

    run_stage(
        stage_key="pass2.model1",
        runner=lambda: train_classification_model(
            model_path=WORKFLOW_ROOT / "layer4-classification" / "model-1",
            train_rows=m1_rows,
            val_rows=None,
            model_name="Model 1",
            target_names=["safe (0)", "risk (1)"],
            evaluate=False,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )
    run_stage(
        stage_key="pass2.model2",
        runner=lambda: train_classification_model(
            model_path=WORKFLOW_ROOT / "layer4-classification" / "model-2",
            train_rows=m2_rows,
            val_rows=None,
            model_name="Model 2",
            target_names=["low_risk (0)", "high_risk (1)"],
            evaluate=False,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    clustering_stats = run_stage(
        stage_key="pass2.clustering",
        runner=lambda: train_clustering(all_docs, embedding_model_name, python_exec),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    full_samples = extract_sentence_samples(all_docs)
    regression_stats = run_stage(
        stage_key="pass2.regression",
        runner=lambda: train_regression(
            samples=full_samples,
            config_path=args.base_config,
            seed=args.seed,
            port=args.base_port + 200,
            timeout_s=args.startup_timeout,
            entity_prefix="pass2-reg",
            python_exec=python_exec,
        ),
        resume_enabled=resume_enabled,
        state_path=resume_state_path,
        resume_state=resume_state,
    )

    return {
        "model1_rows": len(m1_rows),
        "model2_rows": len(m2_rows),
        "clustering_rows": clustering_stats["samples"],
        "regression_rows": regression_stats["rows"],
    }


def main() -> int:
    args = parse_args()
    python_exec = get_python_executable()
    resume_enabled = not args.no_resume
    resume_state_path = args.resume_state_file
    if not resume_state_path.is_absolute():
        resume_state_path = (ROOT / resume_state_path).resolve()
    run_signature, signature_payload = build_run_signature(args)
    resume_state = load_resume_state(
        state_path=resume_state_path,
        run_signature=run_signature,
        signature_payload=signature_payload,
        resume_enabled=resume_enabled,
        reset_state=args.reset_resume_state,
    )
    if resume_enabled:
        persist_resume_state(resume_state_path, resume_state)

    print("=" * 72)
    print("Noupe Train/Validate Pipeline")
    print("=" * 72)
    if resume_enabled:
        print(f"Resume state: {resume_state_path}")
        print(f"Run signature: {run_signature[:12]}")
    else:
        print("Resume state: disabled (--no-resume)")

    documents = load_documents(DATA_DIR)
    if len(documents) < 2:
        raise PipelineError(f"Insufficient documents in {DATA_DIR}: {len(documents)}")

    total_sentences = sum(len(doc["sentences"]) for doc in documents)
    print(f"Loaded {len(documents)} documents with {total_sentences} sentence(s)")

    train_docs, val_docs = split_documents(documents, test_size=args.test_size, seed=args.seed)
    train_sentences = sum(len(doc["sentences"]) for doc in train_docs)
    val_sentences = sum(len(doc["sentences"]) for doc in val_docs)

    print(
        f"Split: train_docs={len(train_docs)} val_docs={len(val_docs)} "
        f"train_sentences={train_sentences} val_sentences={val_sentences}"
    )

    embedding_model_name = get_embedding_model_name(args.base_config)
    print(f"Embedding model: {embedding_model_name}")

    pass1_classification, config_results = run_pass1(
        train_docs=train_docs,
        val_docs=val_docs,
        args=args,
        python_exec=python_exec,
        embedding_model_name=embedding_model_name,
        resume_enabled=resume_enabled,
        resume_state=resume_state,
        resume_state_path=resume_state_path,
    )

    print_supervised_summary(pass1_classification)
    print_config_summary(config_results)

    pass2_stats = run_pass2(
        all_docs=documents,
        args=args,
        python_exec=python_exec,
        embedding_model_name=embedding_model_name,
        resume_enabled=resume_enabled,
        resume_state=resume_state,
        resume_state_path=resume_state_path,
    )

    split_stats = {
        "seed": args.seed,
        "total_docs": len(documents),
        "train_docs": len(train_docs),
        "val_docs": len(val_docs),
        "total_sentences": total_sentences,
        "train_sentences": train_sentences,
        "val_sentences": val_sentences,
    }

    report_path = write_report(
        report_dir=args.report_dir,
        split_stats=split_stats,
        pass1_classification=pass1_classification,
        config_results=config_results,
        pass2_stats=pass2_stats,
    )
    refresh_artifact_manifest(python_exec)

    print("\nFinal 100% retraining complete")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PipelineError as exc:
        print(f"[error] {exc}")
        raise SystemExit(1)
