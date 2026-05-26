import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as main

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class BackendOnlyLayoutTests(unittest.TestCase):
    def test_frontend_routes_are_not_mounted(self):
        with TestClient(main.app) as client:
            for path in ("/legacy/", "/chat/"):
                response = client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_archived_demo_assets_are_pruned(self):
        self.assertFalse((ROOT / "archive" / "frontend-demos").exists())

    def test_latency_corpus_folder_exists(self):
        expected_paths = [
            ROOT / "test" / "fixtures" / "latency-corpus" / "README.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing latency corpus asset: {path}")

    def test_launch_scripts_exist(self):
        expected_paths = [
            ROOT / "scripts" / "benchmark_latency_corpus.sh",
            ROOT / "scripts" / "clean_dev.sh",
            ROOT / "scripts" / "launch" / "common.sh",
            ROOT / "scripts" / "launch" / "run_dev.sh",
            ROOT / "scripts" / "launch" / "run_prod.sh",
            ROOT / "scripts" / "launch" / "run_backend_only.sh",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing launcher: {path}")

    def test_active_workflow_layout_is_under_src_package(self):
        expected_paths = [
            ROOT / "src" / "kaypoh" / "workflow" / "layer0_parser" / "parse_docs.py",
            ROOT / "src" / "kaypoh" / "workflow" / "layer7_public_evidence" / "inference.py",
            ROOT / "src" / "kaypoh" / "workflow" / "layer8_llm_adjudicator" / "inference.py",
            ROOT / "src" / "kaypoh" / "workflow" / "privacy_guard.py",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing workflow file: {path}")

    def test_archived_classifier_surfaces_are_removed(self):
        removed_paths = [
            ROOT / "clustering",
            ROOT / "embeddings",
            ROOT / "helper",
            ROOT / "lexicon",
            ROOT / "model-1",
            ROOT / "model-2",
            ROOT / "backend" / "workflow",
            ROOT / "docs" / "json",
            ROOT / "src" / "kaypoh" / "training",
            ROOT / "configs" / "artifacts.py",
            ROOT / "artifacts" / "manifest.json",
        ]
        for path in removed_paths:
            self.assertFalse(path.exists(), f"archived surface should be removed: {path}")

    def test_folder_readmes_exist(self):
        expected_paths = [
            ROOT / "README.md",
            ROOT / "api" / "README.md",
            ROOT / "archive" / "README.md",
            ROOT / "backend" / "README.md",
            ROOT / "configs" / "README.md",
            ROOT / "docs" / "README.md",
            ROOT / "reports" / "README.md",
            ROOT / "scripts" / "README.md",
            ROOT / "scripts" / "launch" / "README.md",
            ROOT / "src" / "kaypoh" / "helper" / "README.md",
            ROOT / "test" / "README.md",
            ROOT / "training" / "README.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing folder README: {path}")


if __name__ == "__main__":
    unittest.main()
