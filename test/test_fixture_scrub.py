import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_fixture_scrub_module():
    path = ROOT / "scripts" / "check_fixture_scrub.py"
    spec = importlib.util.spec_from_file_location("test_fixture_scrub_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load fixture scrub module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FixtureScrubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_fixture_scrub_module()

    def test_required_patterns_are_detected_in_fixture_scope(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp_dir:
            tmp_root = Path(tmp_dir)
            target = tmp_root / "test" / "fixtures" / "bad.labels.json"
            target.parent.mkdir(parents=True)
            target.write_text(
                "\n".join(
                    [
                        "junas-default-dev-key",
                        '{"storage_format": "plaintext-v1"}',
                        '{"original_text": "Dr Jane Tan"}',
                    ]
                ),
                encoding="utf-8",
            )
            rel = target.relative_to(ROOT)

            findings = self.mod.scan_paths([rel])

        rules = {finding.rule for finding in findings}
        self.assertIn("deleted journal default key", rules)
        self.assertIn("plaintext mapping store marker", rules)
        self.assertIn("reversible mapping value", rules)

    def test_current_committed_fixture_scope_is_clean(self):
        result = self.mod.main([])

        self.assertEqual(result, 0)

    def test_ci_workflow_runs_fixture_scrub_in_security_job(self):
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("name: Security checks", workflow)
        self.assertIn("python scripts/check_fixture_scrub.py", workflow)


if __name__ == "__main__":
    unittest.main()
