import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_retention_checker():
    path = ROOT / "scripts" / "check_retention_manifest.py"
    spec = importlib.util.spec_from_file_location("test_check_retention_manifest", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load retention checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DeploymentDocsTests(unittest.TestCase):
    def test_subject_erasure_runbook_names_backfill_and_retention_limits(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")

        self.assertIn("Subject Erasure Runbook", text)
        self.assertIn("--backfill", text)
        self.assertIn("--dry-run", text)
        self.assertIn("subject_erasure_recorded", text)
        self.assertIn("SIEM exports", text)
        self.assertIn("backups", text)
        self.assertIn("retention", text)

    def test_retention_manifest_doc_example_matches_checker_schema(self):
        text = (ROOT / "docs" / "deployment-hardening.md").read_text(encoding="utf-8")
        match = re.search(r"## Retention Manifest.*?```json\n(?P<body>.*?)\n```", text, re.S)
        self.assertIsNotNone(match)
        example = json.loads(match.group("body"))
        checker = load_retention_checker()
        controls = set(example["controls"])

        self.assertEqual(controls, set(checker.REQUIRED_CONTROLS))
        self.assertEqual(example["schema_version"], "kaypoh.retention_manifest.v1")
        for control in controls:
            result = checker._evaluate_control(control, example["controls"][control])
            self.assertEqual(result["status"], "configured", msg=f"{control}: {result}")
        for token in ("retention_days", "delete_after_days", "retain_for_days", "policy", "external_policy_ref"):
            self.assertIn(token, text)
        self.assertIn("scripts/check_retention_manifest.py --manifest", text)
        self.assertIn("--json", text)


if __name__ == "__main__":
    unittest.main()
