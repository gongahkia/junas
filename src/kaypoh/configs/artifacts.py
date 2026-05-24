from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "manifest.json"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"

ARTIFACT_SPECS: tuple[dict[str, str], ...] = (
    {
        "name": "clustering",
        "kind": "file",
        "path": "artifacts/layer3_clustering/anomaly_detector.joblib",
        "legacy_source": "backend/workflow/layer3-clustering/checkpoints/anomaly_detector.joblib",
    },
    {
        "name": "model1",
        "kind": "directory",
        "path": "artifacts/layer4_classification/model1/best",
        "legacy_source": "backend/workflow/layer4-classification/model-1/checkpoints/best",
    },
    {
        "name": "model2",
        "kind": "directory",
        "path": "artifacts/layer4_classification/model2/best",
        "legacy_source": "backend/workflow/layer4-classification/model-2/checkpoints/best",
    },
    {
        "name": "regression",
        "kind": "directory",
        "path": "artifacts/layer6_regression",
        "legacy_source": "backend/workflow/layer6-regression/checkpoints",
    },
)

LAYER_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "clustering": ("clustering",),
    "model1": ("model1",),
    "model2": ("model2",),
    "regression": ("regression",),
}


class ArtifactManifestError(RuntimeError):
    """Raised when the artifact manifest is invalid."""


def artifact_manifest_path(manifest_path: str | os.PathLike[str] | None = None) -> Path:
    raw_path = manifest_path or os.environ.get("KAYPOH_ARTIFACT_MANIFEST") or DEFAULT_MANIFEST_PATH
    return Path(raw_path).expanduser().resolve()


def _project_relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_members(path: Path) -> dict[str, str]:
    members: dict[str, str] = {}
    for child in sorted(path.rglob("*")):
        if child.is_file():
            members[child.relative_to(path).as_posix()] = _sha256_file(child)
    return members


def _source_path_for_spec(spec: dict[str, str], *, prefer_target: bool) -> Path:
    target = PROJECT_ROOT / spec["path"]
    legacy = PROJECT_ROOT / spec["legacy_source"]
    if prefer_target and target.exists():
        return target
    if legacy.exists():
        return legacy
    if target.exists():
        return target
    raise FileNotFoundError(f"artifact source missing for {spec['name']}: {target} or {legacy}")


def build_artifact_manifest(
    *,
    training_revision: str,
    manifest_path: str | os.PathLike[str] | None = None,
    prefer_target: bool = False,
    config_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    config_file = Path(config_path).expanduser().resolve() if config_path is not None else DEFAULT_CONFIG_PATH
    if not config_file.exists():
        raise FileNotFoundError(f"config file missing for manifest generation: {config_file}")

    entries: list[dict[str, Any]] = []
    for spec in ARTIFACT_SPECS:
        source_path = _source_path_for_spec(spec, prefer_target=prefer_target)
        entry: dict[str, Any] = {
            "name": spec["name"],
            "kind": spec["kind"],
            "path": spec["path"],
            "legacy_source": spec["legacy_source"],
        }
        if spec["kind"] == "file":
            entry["sha256"] = _sha256_file(source_path)
        elif spec["kind"] == "directory":
            entry["members"] = _directory_members(source_path)
        else:  # pragma: no cover - protected by static ARTIFACT_SPECS
            raise ArtifactManifestError(f"unsupported artifact kind: {spec['kind']}")
        entries.append(entry)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "training_revision": training_revision,
        "config_digest": {
            "path": _project_relative(config_file),
            "sha256": _sha256_file(config_file),
        },
        "artifacts": entries,
    }


def write_artifact_manifest(
    *,
    training_revision: str,
    manifest_path: str | os.PathLike[str] | None = None,
    prefer_target: bool = False,
    config_path: str | os.PathLike[str] | None = None,
) -> Path:
    target_path = artifact_manifest_path(manifest_path)
    payload = build_artifact_manifest(
        training_revision=training_revision,
        manifest_path=target_path,
        prefer_target=prefer_target,
        config_path=config_path,
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target_path


def load_artifact_manifest(manifest_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = artifact_manifest_path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"artifact manifest missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArtifactManifestError(f"artifact manifest parse failure ({path}): {exc}") from exc
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ArtifactManifestError(f"artifact manifest missing 'artifacts' list: {path}")
    return payload


def artifact_entries(manifest_path: str | os.PathLike[str] | None = None) -> dict[str, dict[str, Any]]:
    payload = load_artifact_manifest(manifest_path)
    entries: dict[str, dict[str, Any]] = {}
    for entry in payload["artifacts"]:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ArtifactManifestError("artifact manifest entry missing a valid name")
        entries[name] = dict(entry)
    return entries


def artifact_names_for_layers(layers: list[str] | tuple[str, ...]) -> set[str]:
    artifact_names: set[str] = set()
    for layer in layers:
        artifact_names.update(LAYER_ARTIFACTS.get(layer, ()))
    return artifact_names


def get_artifact_entry(name: str, manifest_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    entries = artifact_entries(manifest_path)
    if name not in entries:
        raise FileNotFoundError(f"artifact '{name}' not found in manifest {artifact_manifest_path(manifest_path)}")
    return entries[name]


def get_artifact_path(name: str, manifest_path: str | os.PathLike[str] | None = None) -> Path:
    entry = get_artifact_entry(name, manifest_path)
    return (PROJECT_ROOT / entry["path"]).resolve()


def verify_artifact_manifest(manifest_path: str | os.PathLike[str] | None = None) -> list[str]:
    try:
        entries = artifact_entries(manifest_path)
    except (FileNotFoundError, ArtifactManifestError) as exc:
        return [str(exc)]

    errors: list[str] = []
    for name, entry in entries.items():
        target = (PROJECT_ROOT / entry["path"]).resolve()
        kind = entry.get("kind")
        if kind == "file":
            if not target.is_file():
                errors.append(f"artifact missing for {name}: {target}")
                continue
            expected_sha = entry.get("sha256")
            actual_sha = _sha256_file(target)
            if expected_sha != actual_sha:
                errors.append(f"artifact hash mismatch for {name}: {target}")
        elif kind == "directory":
            if not target.is_dir():
                errors.append(f"artifact directory missing for {name}: {target}")
                continue
            members = entry.get("members", {})
            if not isinstance(members, dict):
                errors.append(f"artifact manifest entry for {name} has invalid members payload")
                continue
            for relative_path, expected_sha in members.items():
                member_path = target / relative_path
                if not member_path.is_file():
                    errors.append(f"artifact member missing for {name}: {member_path}")
                    continue
                actual_sha = _sha256_file(member_path)
                if expected_sha != actual_sha:
                    errors.append(f"artifact hash mismatch for {name}: {member_path}")
        else:
            errors.append(f"artifact manifest entry for {name} has unsupported kind={kind!r}")
    return errors


def sync_legacy_artifacts(manifest_path: str | os.PathLike[str] | None = None) -> list[Path]:
    entries = artifact_entries(manifest_path)
    copied: list[Path] = []
    for name, entry in entries.items():
        source = (PROJECT_ROOT / entry["legacy_source"]).resolve()
        target = (PROJECT_ROOT / entry["path"]).resolve()
        if not source.exists():
            continue
        if entry.get("kind") == "file":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif entry.get("kind") == "directory":
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            raise ArtifactManifestError(f"unsupported artifact kind for {name}: {entry.get('kind')!r}")
        copied.append(target)
    return copied
