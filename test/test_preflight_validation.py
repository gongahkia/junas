import pytest

pytest.skip(
    "legacy classifier pipeline archived 2026-05-26; "
    "see ARCHITECTURE-PIVOT-24-MAY.md item 63. Rewrite tests for the new "
    "thin-wrapper /classify shape (findings/pii_score/mnpi_score) in a follow-up.",
    allow_module_level=True,
)

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.preflight as preflight
from kaypoh.configs import artifacts as artifact_config


class PreflightValidationTests(unittest.TestCase):
    def _patch_artifact_root(self, root: Path):
        resolved_root = root.resolve()
        return patch.multiple(
            artifact_config,
            PROJECT_ROOT=resolved_root,
            DEFAULT_MANIFEST_PATH=resolved_root / "artifacts" / "manifest.json",
            DEFAULT_CONFIG_PATH=resolved_root / "config.toml",
        )

    def _write_config(self, root: Path, content: str) -> Path:
        path = root / "config.toml"
        path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
        return path

    def _populate_fake_artifacts(self, root: Path) -> tuple[Path, Path]:
        config_path = self._write_config(
            root,
            """
            [pipeline]
            layers = ["model1"]
            optional_layers = []
            """,
        )

        for spec in artifact_config.ARTIFACT_SPECS:
            target = root / spec["path"]
            if spec["kind"] == "file":
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"{spec['name']}-artifact\n", encoding="utf-8")
            else:
                target.mkdir(parents=True, exist_ok=True)
                (target / "weights.bin").write_text(f"{spec['name']}-weights\n", encoding="utf-8")

        manifest_path = artifact_config.write_artifact_manifest(
            training_revision="test-revision",
            manifest_path=root / "artifacts" / "manifest.json",
            prefer_target=True,
            config_path=config_path,
        )
        return config_path, manifest_path

    def test_verify_artifact_manifest_detects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            with self._patch_artifact_root(root):
                _, manifest_path = self._populate_fake_artifacts(root)
                (root / "artifacts" / "layer4_classification" / "model1" / "best" / "weights.bin").write_text(
                    "mutated\n",
                    encoding="utf-8",
                )

                errors = artifact_config.verify_artifact_manifest(manifest_path)

        self.assertTrue(any("hash mismatch" in item for item in errors))

    def test_verify_artifact_manifest_detects_missing_member(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            with self._patch_artifact_root(root):
                _, manifest_path = self._populate_fake_artifacts(root)
                (root / "artifacts" / "layer4_classification" / "model1" / "best" / "weights.bin").unlink()

                errors = artifact_config.verify_artifact_manifest(manifest_path)

        self.assertTrue(any("artifact member missing for model1" in item for item in errors))

    def test_preflight_strict_returns_nonzero_for_invalid_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            config_path = self._write_config(
                root,
                """
                [pipeline
                layers = ["model1"]
                """,
            )

            with patch.object(sys, "argv", ["preflight.py", "--strict", "--config", str(config_path)]):
                exit_code = preflight.main()

        self.assertEqual(exit_code, 1)

    def test_preflight_strict_returns_nonzero_for_manifest_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            with self._patch_artifact_root(root):
                config_path, manifest_path = self._populate_fake_artifacts(root)
                (root / "artifacts" / "layer4_classification" / "model1" / "best" / "weights.bin").write_text(
                    "mutated\n",
                    encoding="utf-8",
                )

                with (
                    patch.object(preflight, "check_spacy_model", return_value=(True, "spaCy model loaded")),
                    patch.object(sys, "argv", ["preflight.py", "--strict", "--config", str(config_path)]),
                    patch.dict("os.environ", {"KAYPOH_ARTIFACT_MANIFEST": str(manifest_path)}, clear=False),
                ):
                    exit_code = preflight.main()

        self.assertEqual(exit_code, 1)

    def test_preflight_strict_ignores_inactive_artifact_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            with self._patch_artifact_root(root):
                config_path, manifest_path = self._populate_fake_artifacts(root)
                (root / "artifacts" / "layer3_clustering" / "anomaly_detector.joblib").write_text(
                    "mutated\n",
                    encoding="utf-8",
                )

                with (
                    patch.object(preflight, "check_spacy_model", return_value=(True, "spaCy model loaded")),
                    patch.object(sys, "argv", ["preflight.py", "--strict", "--config", str(config_path)]),
                    patch.dict("os.environ", {"KAYPOH_ARTIFACT_MANIFEST": str(manifest_path)}, clear=False),
                ):
                    exit_code = preflight.main()

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
