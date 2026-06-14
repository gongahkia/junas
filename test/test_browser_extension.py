import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "integrations" / "browser_extension"


class BrowserExtensionTests(unittest.TestCase):
    def test_manifest_targets_supported_genai_hosts(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["content_scripts"][0]
        self.assertEqual(
            scripts["matches"],
            ["https://chatgpt.com/*", "https://claude.ai/*", "https://gemini.google.com/*"],
        )
        self.assertIn("http://127.0.0.1:8765/*", manifest["host_permissions"])
        self.assertNotIn("scripting", manifest["permissions"])

    def test_options_expose_opt_in_paste_and_irreversible_modes(self):
        html = (EXT / "options.html").read_text(encoding="utf-8")
        js = (EXT / "options.js").read_text(encoding="utf-8")
        self.assertIn('value="anonymize"', html)
        self.assertIn("interceptPaste", html)
        self.assertIn('id="startPairing"', html)
        self.assertIn('id="completePairing"', html)
        self.assertIn("/local/pairing/start", js)
        self.assertIn("/local/pairing/claim", js)
        self.assertIn("client_token", js)
        self.assertIn("interceptPaste: false", js)
        self.assertIn("interceptPaste.checked", js)

    def test_content_script_intercepts_paste_only_when_enabled(self):
        text = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertIn('document.addEventListener("paste"', text)
        self.assertIn("let currentSettings", text)
        self.assertIn("chrome.storage.onChanged.addListener", text)
        self.assertIn("if (!cfg.interceptPaste) return", text)
        self.assertIn('cfg.operation === "review"', text)
        self.assertIn("captureInsertionPoint(target)", text)
        self.assertIn("event.preventDefault()", text)
        self.assertIn("insertText(target, text, insertionPoint)", text)
        self.assertIn("degraded_modes", text)
        self.assertIn("send_allowed", text)

    def test_worker_routes_all_privacy_operations(self):
        text = (EXT / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn('["review", "pseudonymize", "anonymize", "redact"]', text)
        self.assertIn('degraded_policy: "warn"', text)
        self.assertIn("result.pseudonymized_text", text)
        self.assertIn("result.anonymized_text", text)
        self.assertIn("result.redacted_text", text)
        self.assertIn('"kaypoh-process-text"', text)


if __name__ == "__main__":
    unittest.main()
