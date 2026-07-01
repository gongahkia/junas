#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SbomTarget:
    name: str
    extras: tuple[str, ...]
    output_name: str
    artifact_label: str


TARGETS = {
    "server": SbomTarget(
        name="server",
        extras=("server",),
        output_name="junas-server.cdx.json",
        artifact_label="junas-server FastAPI backend",
    ),
    "desktop": SbomTarget(
        name="desktop",
        extras=("local", "packaging"),
        output_name="junas-local-desktop.cdx.json",
        artifact_label="junas-local PyInstaller bundle",
    ),
}


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _run_uv_export(target: SbomTarget, output: Path) -> None:
    command = ["uv", "export", "--locked"]
    for extra in target.extras:
        command.extend(["--extra", extra])
    command.extend(
        [
            "--format",
            "cyclonedx1.5",
            "--preview-features",
            "sbom-export",
            "--output-file",
            str(output),
        ]
    )
    subprocess.run(command, cwd=ROOT, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def desktop_artifact_components(artifact_dir: Path) -> list[dict[str, Any]]:
    if not artifact_dir.exists():
        return []
    if not artifact_dir.is_dir():
        raise ValueError(f"desktop artifact path is not a directory: {artifact_dir}")
    components: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in artifact_dir.rglob("*") if candidate.is_file()):
        relative = path.relative_to(artifact_dir).as_posix()
        components.append(
            {
                "type": "file",
                "bom-ref": f"junas-local-file:{relative}",
                "name": relative,
                "hashes": [{"alg": "SHA-256", "content": _sha256(path)}],
                "properties": [
                    {"name": "junas:artifact_surface", "value": "pyinstaller"},
                    {"name": "junas:artifact_path", "value": f"dist/junas-local/{relative}"},
                ],
            }
        )
    return components


def _metadata_properties(sbom: dict[str, Any]) -> list[dict[str, str]]:
    metadata = sbom.setdefault("metadata", {})
    properties = metadata.setdefault("properties", [])
    if not isinstance(properties, list):
        raise ValueError("CycloneDX metadata.properties must be a list")
    return properties


def annotate_sbom(
    sbom: dict[str, Any],
    target: SbomTarget,
    *,
    desktop_artifact_dir: Path,
    require_desktop_artifact: bool,
) -> dict[str, Any]:
    if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.5":
        raise ValueError("expected CycloneDX 1.5 JSON from uv export")
    components = sbom.setdefault("components", [])
    if not isinstance(components, list):
        raise ValueError("CycloneDX components must be a list")

    properties = _metadata_properties(sbom)
    properties.extend(
        [
            {"name": "junas:sbom_target", "value": target.name},
            {"name": "junas:artifact", "value": target.artifact_label},
            {"name": "junas:dependency_source", "value": "uv.lock"},
            {"name": "junas:generator", "value": "scripts/generate_sbom.py"},
        ]
    )

    if target.name == "desktop":
        artifact_components = desktop_artifact_components(desktop_artifact_dir)
        if require_desktop_artifact and not artifact_components:
            raise ValueError(f"desktop artifact directory has no files: {desktop_artifact_dir}")
        components.extend(artifact_components)
        status = "included" if artifact_components else "missing"
        properties.extend(
            [
                {"name": "junas:desktop_artifact_dir", "value": str(desktop_artifact_dir)},
                {"name": "junas:desktop_artifact_status", "value": status},
                {"name": "junas:desktop_artifact_file_count", "value": str(len(artifact_components))},
            ]
        )

    return sbom


def generate_target(
    target: SbomTarget,
    *,
    out_dir: Path,
    desktop_artifact_dir: Path,
    require_desktop_artifact: bool,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / target.output_name
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_output = Path(tmp_dir) / target.output_name
        _run_uv_export(target, tmp_output)
        sbom = json.loads(tmp_output.read_text(encoding="utf-8"))
    annotated = annotate_sbom(
        sbom,
        target,
        desktop_artifact_dir=desktop_artifact_dir,
        require_desktop_artifact=require_desktop_artifact,
    )
    output.write_text(json.dumps(annotated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def selected_targets(raw: str) -> list[SbomTarget]:
    if raw == "all":
        return [TARGETS["server"], TARGETS["desktop"]]
    return [TARGETS[raw]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Junas CycloneDX SBOM artifacts")
    parser.add_argument("--target", choices=("all", "server", "desktop"), default="all")
    parser.add_argument("--out-dir", type=Path, default=Path("reports/sbom"))
    parser.add_argument("--desktop-artifact-dir", type=Path, default=Path("dist/junas-local"))
    parser.add_argument("--require-desktop-artifact", action="store_true")
    args = parser.parse_args(argv)

    out_dir = _rooted(args.out_dir)
    desktop_artifact_dir = _rooted(args.desktop_artifact_dir)
    try:
        outputs = [
            generate_target(
                target,
                out_dir=out_dir,
                desktop_artifact_dir=desktop_artifact_dir,
                require_desktop_artifact=args.require_desktop_artifact,
            )
            for target in selected_targets(args.target)
        ]
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"generate_sbom: {exc}", file=sys.stderr)
        return 64
    for output in outputs:
        print(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
