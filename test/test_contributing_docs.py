import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ContributingDocTests(unittest.TestCase):
    def test_contributing_doc_has_setup_gates_and_invariants(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for token in (
            "uv sync --extra dev",
            "uv run python -m spacy download en_core_web_sm",
            "uv run python scripts/preflight.py --strict",
            "./scripts/demo.sh",
            "./scripts/launch/run_backend_only.sh",
            "uv run ruff check",
            "git diff --check",
            "./scripts/verify_runtime.sh",
            "uv run pytest",
            "uv run python scripts/recall_gate.py",
            "uv run python scripts/generate_accuracy_doc.py --check",
            "The default local runtime is deterministic and offline",
            "review_profile=strict",
            "The FastAPI backend remains the trust boundary",
            "Deterministic-high findings must stay visible",
            "real secrets, customer text, live personal data",
            "README/product claims need local evidence",
        ):
            self.assertIn(token, contributing)

        for forbidden_dependency in (
            "torch",
            "transformers",
            "sentence-transformers",
            "redis",
            "xgboost",
            "scikit-learn",
            "pandas",
            "accelerate",
        ):
            self.assertIn(forbidden_dependency, contributing)

        self.assertIn("- [Contributing](#contributing)", readme)
        self.assertIn("[`CONTRIBUTING.md`](./CONTRIBUTING.md)", readme)

    def test_contributing_doc_links_scoped_good_first_issues(self):
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for issue in (
            "#77: Add desktop watcher threat model",
            "#78: Add developer FAQ for review and rewrite endpoints",
            "#79: Add deployment comparison table",
            "#80: Add operator FAQ for DLP coexistence",
            "#81: Mark LaunchAgent install optional and admin-controlled",
        ):
            self.assertIn(issue, contributing)
        self.assertEqual(contributing.count("https://github.com/gongahkia/junas/issues/"), 5)
        self.assertIn("documentation-only entry points drawn from the GitHub issue backlog", contributing)


if __name__ == "__main__":
    unittest.main()
