import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_retention_module():
    path = ROOT / "scripts" / "check_retention_manifest.py"
    spec = importlib.util.spec_from_file_location("test_retention_manifest_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load retention checker from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RetentionManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_retention_module()

    def test_missing_manifest_reports_all_required_controls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = self.mod.check_manifest(Path(tmp_dir) / "missing.json")

        self.assertFalse(payload["ok"])
        self.assertEqual(
            [item["control"] for item in payload["controls"]],
            ["journal", "mapping_store", "logs", "siem", "backups"],
        )
        self.assertTrue(all(item["status"] == "missing" for item in payload["controls"]))

    def test_valid_manifest_accepts_days_and_policy_refs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "retention.json"
            path.write_text(
                """
{
  "controls": {
    "journal": {"retention_days": 2555},
    "mapping_store": {"delete_after_days": 90},
    "logs": {"policy": "log-platform-policy-123"},
    "siem": {"external_policy_ref": "splunk-index-retention"},
    "backups": {"retain_for_days": "365"}
  }
}
""".strip(),
                encoding="utf-8",
            )
            payload = self.mod.check_manifest(path)

        self.assertTrue(payload["ok"])
        self.assertTrue(all(item["status"] == "configured" for item in payload["controls"]))

    def test_invalid_manifest_fails_strict_main(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "retention.json"
            path.write_text('{"journal": {"retention_days": 30}}', encoding="utf-8")
            exit_code = self.mod.main(["--manifest", str(path), "--strict"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
