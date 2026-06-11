import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import kaypoh.backend.main as main

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

    def test_runtime_layout_is_in_canonical_package(self):
        expected_paths = [
            ROOT / "src" / "kaypoh" / "ingest" / "parser_tools" / "parse_docs.py",
            ROOT / "src" / "kaypoh" / "external" / "public_evidence" / "inference.py",
            ROOT / "src" / "kaypoh" / "advisory" / "llm_adjudicator" / "inference.py",
            ROOT / "src" / "kaypoh" / "external" / "privacy_guard.py",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing runtime file: {path}")

    def test_removed_legacy_layout_is_absent(self):
        removed_paths = [
            ROOT / "backend" / "workflow",
            ROOT / "api",
            ROOT / "backend",
            ROOT / "configs",
            ROOT / "clustering",
            ROOT / "embeddings",
            ROOT / "helper",
            ROOT / "lexicon",
            ROOT / "model-1",
            ROOT / "model-2",
            ROOT / "scripts" / "train_dev.sh",
            ROOT / "src" / "kaypoh" / "workflow",
            ROOT / "src" / "kaypoh" / "workflow" / "layer1_lexicon",
            ROOT / "src" / "kaypoh" / "workflow" / "layer2_embeddings",
            ROOT / "src" / "kaypoh" / "workflow" / "layer3_clustering",
            ROOT / "src" / "kaypoh" / "workflow" / "layer4_classification",
            ROOT / "src" / "kaypoh" / "workflow" / "layer5_mosaic",
            ROOT / "src" / "kaypoh" / "workflow" / "layer6_regression",
        ]
        for path in removed_paths:
            self.assertFalse(path.exists(), f"duplicate shim should be removed: {path}")

    def test_folder_readmes_exist(self):
        expected_paths = [
            ROOT / "README.md",
            ROOT / "archive" / "README.md",
            ROOT / "docs" / "README.md",
            ROOT / "reports" / "README.md",
            ROOT / "scripts" / "README.md",
            ROOT / "scripts" / "launch" / "README.md",
            ROOT / "src" / "kaypoh" / "backend" / "README.md",
            ROOT / "src" / "kaypoh" / "configs" / "README.md",
            ROOT / "src" / "kaypoh" / "external" / "README.md",
            ROOT / "src" / "kaypoh" / "helper" / "README.md",
            ROOT / "src" / "kaypoh" / "ingest" / "parser_tools" / "README.md",
            ROOT / "test" / "README.md",
            ROOT / "training" / "README.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing folder README: {path}")


if __name__ == "__main__":
    unittest.main()
