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
        self.assertEqual(example["schema_version"], "junas.retention_manifest.v1")
        for control in controls:
            result = checker._evaluate_control(control, example["controls"][control])
            self.assertEqual(result["status"], "configured", msg=f"{control}: {result}")
        for token in ("retention_days", "delete_after_days", "retain_for_days", "policy", "external_policy_ref"):
            self.assertIn(token, text)
        self.assertIn("docs/security/data-retention.md", text)
        self.assertIn("scripts/check_retention_manifest.py --manifest", text)
        self.assertIn("--json", text)

    def test_data_retention_matrix_covers_required_artifacts(self):
        text = (ROOT / "docs" / "security" / "data-retention.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/data-retention.md", docs_index)
        for token in (
            "`journal`",
            "`mapping_store`",
            "`subject_index`",
            "`review_sessions`",
            "`matter_terms`",
            "`adapter_telemetry`",
            "`siem`",
            "`audit_packs`",
            "`fixtures`",
            "`reports`",
            "scripts/check_retention_manifest.py",
            "scripts/erase_subject.py",
            "scripts/check_fixture_scrub.py",
        ):
            self.assertIn(token, text)

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
            ROOT / "packaging" / "macos" / "com.junas.local.plist.template",
            ROOT / "packaging" / "macos" / "install.sh",
            ROOT / "packaging" / "macos" / "update.sh",
            ROOT / "packaging" / "macos" / "uninstall.sh",
            ROOT / "packaging" / "windows" / "README.md",
            ROOT / "integrations" / "browser_extension" / "manifest.json",
            ROOT / "integrations" / "outlook_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "manifest.xml",
            ROOT / "integrations" / "word_addin" / "taskpane.js",
            ROOT / "integrations" / "desktop" / "watch.py",
            ROOT / "test" / "fixtures" / "outlook_smart_alert_messages.json",
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing {path}")

        macos_packager = (ROOT / "scripts" / "package_macos_desktop.sh").read_text(encoding="utf-8")
        extension_packager = (ROOT / "scripts" / "package_browser_extension.sh").read_text(encoding="utf-8")
        launchd = (ROOT / "packaging" / "macos" / "com.junas.local.plist.template").read_text(encoding="utf-8")
        word_manifest = (ROOT / "integrations" / "word_addin" / "manifest.xml").read_text(encoding="utf-8")
        word_js = (ROOT / "integrations" / "word_addin" / "taskpane.js").read_text(encoding="utf-8")

        self.assertIn("codesign", macos_packager)
        self.assertIn("notarytool", macos_packager)
        self.assertIn("stapler", macos_packager)
        self.assertIn("integrations/browser_extension", extension_packager)
        self.assertIn("--pack-extension", extension_packager)
        self.assertIn("RunAtLoad", launchd)
        outlook_manifest = (ROOT / "integrations" / "outlook_addin" / "manifest.xml").read_text(encoding="utf-8")
        self.assertIn("{{JUNAS_OUTLOOK_ADDIN_ORIGIN}}", outlook_manifest)
        self.assertIn('Host Name="Document"', word_manifest)
        self.assertIn("/review", word_js)
        self.assertIn("X-Junas-Local-Token", word_js)
        self.assertIn('degraded_policy: "warn"', word_js)
        self.assertIn("degraded_modes", word_js)
        self.assertIn("send_allowed", word_js)

    def test_desktop_watcher_is_not_in_readme_quick_start(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        quick_start = re.search(r"## Quick Start(?P<body>.*?)## What Junas Does", readme, re.S)
        fallback = re.search(r"## Experimental Local Fallback(?P<body>.*?)## API Surface", readme, re.S)

        self.assertIsNotNone(quick_start)
        self.assertIsNotNone(fallback)
        self.assertNotIn("junas-watch", quick_start.group("body"))
        self.assertNotIn("--clipboard", quick_start.group("body"))
        self.assertIn("junas-watch", fallback.group("body"))
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

    def test_dependency_scanning_doc_covers_release_surfaces(self):
        text = (ROOT / "docs" / "security" / "dependency-scanning.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/dependency-scanning.md", docs_index)
        for token in (
            "uv export --locked --all-extras",
            "uvx pip-audit -r reports/security/requirements-all.txt",
            "integrations/browser_extension/manifest.json",
            "npm audit --audit-level=high",
            "scripts/render_outlook_manifest.py",
            "scripts/validate_outlook_manifest.py",
            "integrations/word_addin/",
            "uv export --locked --extra packaging",
            "uv run pyinstaller packaging/junas-local.spec",
            "reports/security/junas-local.sha256",
            "GitHub Dependency Review",
            "https://pypa.github.io/pip-audit/",
            "https://docs.npmjs.com/cli/v11/commands/npm-audit",
        ):
            self.assertIn(token, text)

    def test_release_checklist_covers_required_security_gates(self):
        text = (ROOT / "docs" / "security" / "release-checklist.md").read_text(encoding="utf-8")
        docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

        self.assertIn("security/release-checklist.md", docs_index)
        for token in (
            "test/test_openapi_snapshot.py",
            "scripts/export_openapi_examples.py",
            "test/test_api_auth.py",
            "test/test_tenant_isolation.py",
            "test/test_backend_log_privacy.py",
            "test/test_siem_export.py",
            "scripts/check_fixture_scrub.py",
            "test/test_local_daemon_acl.py",
            "scripts/smoke_local_daemon_acl.py",
            "X-Junas-Local-Token",
            "test/test_frontend_integration.py",
            "test/test_browser_extension.py",
            "Office Runtime storage",
            "scripts/generate_sbom.py --target all",
            "docs/security/dependency-scanning.md",
            "docs/security/sbom.md",
            "--require-desktop-artifact",
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

    def test_outlook_doc_covers_smart_alerts_deployment_fallback_and_limits(self):
        text = (ROOT / "docs" / "integrations" / "outlook.md").read_text(encoding="utf-8")
        for token in (
            "Smart Alerts Flow",
            "SendMode=\"SoftBlock\"",
            "surface=\"outlook\"",
            "workflow=\"email_send\"",
            "Admin Deployment",
            "Tenant Deployment Guide",
            "Exchange admin",
            "Application Administrator",
            "Microsoft Entra ID",
            "Settings > Integrated apps",
            "Deploy Add-in",
            "Specific users/groups",
            "Just me",
            "top-level Microsoft Entra groups",
            "dynamic groups",
            "security groups",
            "up to 24 hours",
            "up to 72 hours",
            "Client Compatibility Notes",
            "Outlook on the web",
            "new Outlook on Windows",
            "classic Outlook on Windows",
            "Version 2206 (Build 15330.20196)",
            "Simple MAPI send coverage",
            "Version 2301 (Build 17126.20004)",
            "Outlook on Mac",
            "Version 16.65 (22082700)",
            "Outlook mobile for iOS/Android",
            "Not an enforcement target",
            "QA Checklist",
            "Internal recipient",
            "External recipient",
            "No attachment",
            "Attachment present",
            "PII body",
            "MNPI body",
            "Timeout",
            "Backend unavailable",
            "attachment_count=0",
            "attachment_count>0",
            "Junas local review is unavailable",
            "Telemetry Events",
            "junas.outlook.telemetry.v1",
            "outlook_review_started",
            "outlook_policy_decision_received",
            "outlook_user_proceeded_after_warning",
            "outlook_user_blocked",
            "outlook_user_requested_approval",
            "outlook_backend_failure",
            "globalThis.junasTelemetrySink(event)",
            "There is no backend transport endpoint",
            "must not include raw body",
            "Privacy Check",
            "does not write message body",
            "browser local storage",
            "Office runtime storage",
            "console logs",
            "render_outlook_manifest.py",
            "validate_outlook_manifest.py",
            "Event Runtime Bundle",
            "launchevent.js",
            "Do not add ES module",
            "CORS And Well-Known URI Checklist",
            ".well-known/microsoft-officeaddins-allowed.json",
            "JSRuntime.Url",
            "OPTIONS",
            "X-Junas-Local-Token",
            "Microsoft 365 admin-managed deployment",
            "Fallback Behavior",
            "Failure-Mode Table",
            "Add-in unavailable before event runs",
            "Backend timeout or unavailable",
            "Offline mode / Work Offline",
            "Malformed response",
            "Auth failure",
            "Degraded document extraction",
            "not a fail-closed enforcement path",
            "Known Client Limitations",
            "Mailbox requirement set 1.15",
            "Simple MAPI",
        ):
            self.assertIn(token, text)

    def test_word_doc_marks_taskpane_as_review_not_enforcement(self):
        text = (ROOT / "docs" / "integrations" / "word.md").read_text(encoding="utf-8")
        for token in (
            "Document Review Flow",
            "review selection",
            "review body",
            'document_type="word_document"',
            'degraded_policy="warn"',
            "Enforcement Boundary",
            "not true send-time enforcement",
            "does not block Word save",
            "DMS upload",
            "Failure Behavior",
        ):
            self.assertIn(token, text)

    def test_desktop_watcher_doc_marks_opt_in_local_fallback_not_enforcement(self):
        text = (ROOT / "docs" / "integrations" / "desktop-watcher.md").read_text(encoding="utf-8")
        for token in (
            "Opt-In Local Fallback Flow",
            "junas-watch --watch-folder",
            "junas-watch --clipboard",
            "Clipboard polling is never enabled by default",
            "Folder Watch",
            "Clipboard Watch",
            "not enterprise endpoint enforcement",
            "does not block paste",
            "cannot prove that every local file",
            "JUNAS_LOCAL_DAEMON_TOKEN",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
