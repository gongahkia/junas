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

    def test_install_admin_threat_and_limitations_docs_cover_lastbit_controls(self):
        install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
        admin = (ROOT / "docs" / "admin-security.md").read_text(encoding="utf-8")
        threat = (ROOT / "docs" / "threat-model.md").read_text(encoding="utf-8")
        limitations = (ROOT / "docs" / "known-limitations.md").read_text(encoding="utf-8")
        combined = "\n".join([install, admin, threat, limitations])

        for token in (
            "codesign",
            "notarytool",
            "auto-start",
            "Update:",
            "Uninstall:",
            "Okta",
            "Microsoft Entra ID",
            "SAML",
            "External KMS",
            "customer-held",
            "SIEM",
            "redacted",
            "not legal advice",
            "procurement-grade",
            "threat",
            "Known Limitations",
        ):
            self.assertIn(token, combined)

    def test_distribution_artifacts_exist_for_packaging_surfaces(self):
        expected = [
            ROOT / "scripts" / "package_macos_desktop.sh",
            ROOT / "scripts" / "package_browser_extension.sh",
            ROOT / "packaging" / "macos" / "com.kaypoh.local.plist.template",
            ROOT / "packaging" / "macos" / "install.sh",
            ROOT / "packaging" / "macos" / "update.sh",
            ROOT / "packaging" / "macos" / "uninstall.sh",
            ROOT / "packaging" / "windows" / "README.md",
            ROOT / "integrations" / "browser_extension" / "manifest.json",
            ROOT / "integrations" / "outlook_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "taskpane.js",
            ROOT / "integrations" / "desktop" / "watch.py",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing {path}")

        macos_packager = (ROOT / "scripts" / "package_macos_desktop.sh").read_text(encoding="utf-8")
        extension_packager = (ROOT / "scripts" / "package_browser_extension.sh").read_text(encoding="utf-8")
        launchd = (ROOT / "packaging" / "macos" / "com.kaypoh.local.plist.template").read_text(encoding="utf-8")
        word_manifest = (ROOT / "integrations" / "word_addin" / "manifest.xml").read_text(encoding="utf-8")
        word_js = (ROOT / "integrations" / "word_addin" / "taskpane.js").read_text(encoding="utf-8")

        self.assertIn("codesign", macos_packager)
        self.assertIn("notarytool", macos_packager)
        self.assertIn("stapler", macos_packager)
        self.assertIn("integrations/browser_extension", extension_packager)
        self.assertIn("--pack-extension", extension_packager)
        self.assertIn("RunAtLoad", launchd)
        self.assertIn('Host Name="Document"', word_manifest)
        self.assertIn("/review", word_js)
        self.assertIn("X-Kaypoh-Local-Token", word_js)
        self.assertIn('degraded_policy: "warn"', word_js)
        self.assertIn("degraded_modes", word_js)
        self.assertIn("send_allowed", word_js)

    def test_desktop_watcher_is_not_in_readme_quick_start(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        quick_start = re.search(r"## Quick Start(?P<body>.*?)## What Kaypoh Does", readme, re.S)
        fallback = re.search(r"## Experimental Local Fallback(?P<body>.*?)## API Surface", readme, re.S)

        self.assertIsNotNone(quick_start)
        self.assertIsNotNone(fallback)
        self.assertNotIn("kaypoh-watch", quick_start.group("body"))
        self.assertNotIn("--clipboard", quick_start.group("body"))
        self.assertIn("kaypoh-watch", fallback.group("body"))
        self.assertIn("desktop-watcher.md", fallback.group("body"))

    def test_root_integrations_index_names_supported_and_future_surfaces(self):
        text = (ROOT / "INTEGRATIONS.md").read_text(encoding="utf-8")
        for token in (
            "Direct API",
            "Outlook Smart Alerts",
            "Browser GenAI extension",
            "Word taskpane",
            "Desktop watcher",
            "DMS hooks",
            "Future Slack",
            "Future Google Workspace",
            "docs/integrations/maturity-matrix.md",
        ):
            self.assertIn(token, text)

    def test_direct_api_integration_doc_covers_baseline_contract(self):
        text = (ROOT / "docs" / "integrations" / "direct-api.md").read_text(encoding="utf-8")
        for token in (
            "Maturity: `core`",
            "POST /review",
            '"surface": "api"',
            '"workflow": "api_review"',
            "policy_decision",
            "Idempotency-Key",
            "/safe-rewrite",
            "/request-approval",
            "docs/policy/decision-contract.md",
        ):
            self.assertIn(token, text)

    def test_dms_integration_doc_covers_upload_metadata_failure_and_audit_fields(self):
        text = (ROOT / "docs" / "integrations" / "dms.md").read_text(encoding="utf-8")
        for token in (
            "Maturity: `experimental`",
            'surface="dms"',
            'workflow="document_upload"',
            "Required Metadata",
            "Failure Behavior",
            "Audit Fields To Store",
            "matter_id",
            "document_id",
            "Idempotency-Key",
            "policy_decision.decision",
            "text_hash",
        ):
            self.assertIn(token, text)

    def test_genai_browser_doc_covers_target_assumptions_without_universal_claim(self):
        text = (ROOT / "docs" / "integrations" / "genai-browser.md").read_text(encoding="utf-8")
        for token in (
            "chatgpt.com",
            "claude.ai",
            "gemini.google.com",
            "Generic textarea",
            "textarea",
            "contenteditable",
            "not universal browser DLP",
            "do not guarantee",
            "Target DOM mismatch",
            'surface="browser_genai"',
            'workflow="prompt_submit"',
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
