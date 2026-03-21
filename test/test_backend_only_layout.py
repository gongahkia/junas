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
            for path in ("/chat/", "/email/", "/slack/"):
                response = client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_archived_demo_assets_exist(self):
        expected_paths = [
            ROOT / "archive" / "frontend-demos" / "legacy" / "index.html",
            ROOT / "archive" / "frontend-demos" / "chat" / "index.html",
            ROOT / "archive" / "frontend-demos" / "email" / "index.html",
            ROOT / "archive" / "frontend-demos" / "slack" / "index.html",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing archived demo asset: {path}")

    def test_latency_corpus_folder_exists(self):
        expected_paths = [
            ROOT / "test" / "fixtures" / "latency-corpus" / "README.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing latency corpus asset: {path}")

    def test_launch_scripts_exist(self):
        expected_paths = [
            ROOT / "scripts" / "clean_dev.sh",
            ROOT / "scripts" / "launch" / "common.sh",
            ROOT / "scripts" / "launch" / "run_dev.sh",
            ROOT / "scripts" / "launch" / "run_prod.sh",
            ROOT / "scripts" / "launch" / "run_backend_only.sh",
            ROOT / "scripts" / "train_dev.sh",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing launcher: {path}")

    def test_workflow_layout_is_nested_under_backend(self):
        expected_paths = [
            ROOT / "backend" / "workflow" / "layer0-parser" / "parse_docs.py",
            ROOT / "backend" / "workflow" / "layer1-lexicon" / "filter.py",
            ROOT / "backend" / "workflow" / "layer2-embeddings" / "inference.py",
            ROOT / "backend" / "workflow" / "layer3-clustering" / "isolation_forest.py",
            ROOT / "backend" / "workflow" / "layer4-classification" / "model-1" / "inference.py",
            ROOT / "backend" / "workflow" / "layer4-classification" / "model-2" / "inference.py",
            ROOT / "backend" / "workflow" / "layer5-mosaic" / "inference.py",
            ROOT / "backend" / "workflow" / "layer6-regression" / "inference.py",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing workflow file: {path}")

    def test_duplicate_root_shims_are_removed(self):
        removed_paths = [
            ROOT / "clustering",
            ROOT / "embeddings",
            ROOT / "lexicon",
            ROOT / "model-1",
            ROOT / "model-2",
        ]
        for path in removed_paths:
            self.assertFalse(path.exists(), f"duplicate shim should be removed: {path}")

    def test_folder_readmes_exist(self):
        expected_paths = [
            ROOT / "README.md",
            ROOT / "api" / "README.md",
            ROOT / "archive" / "README.md",
            ROOT / "backend" / "README.md",
            ROOT / "backend" / "workflow" / "README.md",
            ROOT / "configs" / "README.md",
            ROOT / "docs" / "README.md",
            ROOT / "helper" / "README.md",
            ROOT / "reports" / "README.md",
            ROOT / "scripts" / "README.md",
            ROOT / "scripts" / "launch" / "README.md",
            ROOT / "test" / "README.md",
            ROOT / "training" / "README.md",
        ]
        for path in expected_paths:
            self.assertTrue(path.exists(), f"missing folder README: {path}")


if __name__ == "__main__":
    unittest.main()
