import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "integrations" / "browser_extension"


class BrowserExtensionTests(unittest.TestCase):
    def test_manifest_targets_supported_genai_hosts(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
        scripts = manifest["content_scripts"][0]
        self.assertEqual(manifest["description"], "Pre-send review for GenAI prompts on managed browser surfaces.")
        self.assertNotIn("DLP", manifest["description"])
        self.assertEqual(
            scripts["matches"],
            ["https://chatgpt.com/*", "https://claude.ai/*", "https://gemini.google.com/*"],
        )
        self.assertEqual(scripts["js"], ["adapters.js", "content.js"])
        self.assertEqual(manifest["permissions"], ["storage", "contextMenus"])
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1:8765/*"])
        self.assertIn("http://127.0.0.1:8765/*", manifest["host_permissions"])
        self.assertNotIn("<all_urls>", manifest["host_permissions"])
        self.assertNotIn("activeTab", manifest["permissions"])
        self.assertNotIn("tabs", manifest["permissions"])
        self.assertNotIn("scripting", manifest["permissions"])

    def test_options_expose_opt_in_paste_and_irreversible_modes(self):
        html = (EXT / "options.html").read_text(encoding="utf-8")
        js = (EXT / "options.js").read_text(encoding="utf-8")
        self.assertIn("Junas GenAI Prompt Review", html)
        self.assertIn("Review pasted GenAI prompts", html)
        self.assertNotIn("universal dlp", html.lower())
        self.assertIn('id="endpoint"', html)
        self.assertIn("Backend URL", html)
        self.assertIn('id="backendMode"', html)
        self.assertIn('value="local_daemon"', html)
        self.assertIn('value="hosted_server"', html)
        self.assertIn('id="authMode"', html)
        self.assertIn('value="local_token"', html)
        self.assertIn('value="bearer_token"', html)
        self.assertIn('value="none"', html)
        self.assertIn('value="anonymize"', html)
        self.assertIn("interceptPaste", html)
        self.assertIn("reviewBeforeSubmit", html)
        self.assertIn('id="startPairing"', html)
        self.assertIn('id="completePairing"', html)
        self.assertIn('id="checkConnection"', html)
        self.assertIn('id="healthStatus"', html)
        self.assertIn("/local/pairing/start", js)
        self.assertIn("/local/pairing/claim", js)
        self.assertIn("client_token", js)
        self.assertIn('backendMode: "local_daemon"', js)
        self.assertIn('authMode: "local_token"', js)
        self.assertIn("backendMode.value", js)
        self.assertIn("authMode.value", js)
        self.assertIn("checkConnectionHealth", js)
        self.assertIn("local daemon unavailable", js)
        self.assertIn("auth failed", js)
        self.assertIn("server healthy", js)
        self.assertIn("policy blocked", js)
        self.assertIn("interceptPaste: false", js)
        self.assertIn("interceptPaste.checked", js)
        self.assertIn("reviewBeforeSubmit: false", js)
        self.assertIn("reviewBeforeSubmit.checked", js)
        self.assertIn('allowedInspectionHosts: "chatgpt.com,claude.ai,gemini.google.com"', js)
        self.assertIn("allowedInspectionHosts.value", js)
        self.assertIn("blockedInspectionHosts.value", js)
        self.assertIn('id="allowedInspectionHosts"', html)
        self.assertIn('id="blockedInspectionHosts"', html)

    def test_content_script_intercepts_paste_only_when_enabled(self):
        text = (EXT / "content.js").read_text(encoding="utf-8")
        self.assertIn('document.addEventListener("paste"', text)
        self.assertIn("let currentSettings", text)
        self.assertIn("chrome.storage.onChanged.addListener", text)
        self.assertIn("promptTarget(event.target)", text)
        self.assertIn("reviewBeforeSubmit", text)
        self.assertIn("guardPromptSubmit", text)
        self.assertIn("reportSelectorFailure", text)
        self.assertIn("submission was not blocked because no review ran", text)
        self.assertIn("reviewOutcome", text)
        self.assertIn("window.confirm", text)
        self.assertIn("JUNAS_BROWSER_ADAPTERS", text)
        self.assertIn("if (!cfg.interceptPaste) return", text)
        self.assertIn('cfg.operation === "review"', text)
        self.assertIn("captureInsertionPoint(target)", text)
        self.assertIn("event.preventDefault()", text)
        self.assertIn("insertText(target, text, insertionPoint)", text)
        self.assertIn("degraded_modes", text)
        self.assertIn("send_allowed", text)
        self.assertIn("browserTelemetry", text)
        self.assertIn("junas.browser.telemetry.v1", text)
        self.assertIn("browser_prompt_review_started", text)
        self.assertIn("browser_policy_decision_received", text)
        self.assertIn("browser_user_canceled", text)
        self.assertIn("browser_user_rewrote", text)
        self.assertIn("browser_user_proceeded_after_warning", text)
        self.assertIn("browser_selector_failure", text)
        self.assertIn("browser_backend_timeout", text)
        self.assertIn("canInspectHost", text)
        self.assertIn("allowedInspectionHosts", text)
        self.assertIn("blockedInspectionHosts", text)

    def test_worker_routes_all_privacy_operations(self):
        text = (EXT / "service_worker.js").read_text(encoding="utf-8")
        self.assertIn('["review", "pseudonymize", "anonymize", "redact"]', text)
        self.assertIn('backendMode: "local_daemon"', text)
        self.assertIn('authMode: "local_token"', text)
        self.assertIn("headers.Authorization", text)
        self.assertIn("callJunas(text, requestedOperation, cfgOverride)", text)
        self.assertIn("message.operation", text)
        self.assertIn('degraded_policy: "warn"', text)
        self.assertIn("result.pseudonymized_text", text)
        self.assertIn("result.anonymized_text", text)
        self.assertIn("result.redacted_text", text)
        self.assertIn('"junas-process-text"', text)
        self.assertIn("JUNAS_BACKEND_TIMEOUT_MS", text)
        self.assertIn('"backend_timeout"', text)
        self.assertIn("canInspectUrl", text)
        self.assertIn("allowedInspectionHosts", text)
        self.assertIn("blockedInspectionHosts", text)
        self.assertIn("inspection_host_blocked", text)

    def test_browser_scripts_do_not_store_or_log_prompt_text(self):
        content = (EXT / "content.js").read_text(encoding="utf-8")
        worker = (EXT / "service_worker.js").read_text(encoding="utf-8")
        combined = "\n".join([content, worker])

        self.assertNotIn("console.", combined)
        self.assertNotIn("localStorage", combined)
        self.assertNotIn("sessionStorage", combined)
        self.assertNotIn("indexedDB", combined)
        self.assertNotIn("chrome.storage.local", combined)
        self.assertNotIn("chrome.storage.sync.set", combined)
        self.assertIn("chrome.storage.sync.get", combined)
        self.assertIn("chrome.runtime.sendMessage", content)
        self.assertIn("fetch(`${cfg.endpoint}/${op}`", worker)

    def test_target_adapter_selectors_are_declared(self):
        text = (EXT / "adapters.js").read_text(encoding="utf-8")
        for token in (
            'id: "chatgpt"',
            'hostnames: ["chatgpt.com"]',
            "[data-testid='prompt-textarea']",
            'id: "claude"',
            'hostnames: ["claude.ai"]',
            "div.ProseMirror[contenteditable='true']",
            'id: "gemini"',
            'hostnames: ["gemini.google.com"]',
            "rich-textarea textarea",
            'id: "generic"',
            "textarea",
            "submitSelectors",
            "findSubmitButton",
            "resolveSubmitTarget",
            "resolvePromptTarget",
            "findPromptComposer",
        ):
            self.assertIn(token, text)

    def test_browser_extension_docs_avoid_universal_dlp_claims(self):
        text = (ROOT / "docs" / "integrations" / "browser-extension.md").read_text(encoding="utf-8")
        self.assertIn("pre-send review for GenAI prompts", text)
        self.assertIn("not universal browser DLP", text)
        self.assertIn("Do not describe this adapter as universal DLP", text)
        self.assertIn("activation-layer coverage only", text)
        self.assertIn("mobile apps", text)
        self.assertIn("native apps", text)
        self.assertIn("unrecognized web UIs", text)

    def test_browser_extension_docs_review_manifest_permissions(self):
        text = (ROOT / "docs" / "integrations" / "browser-extension.md").read_text(encoding="utf-8")

        for token in (
            "## Manifest Permission Review",
            "`permissions` | `storage`",
            "local pairing token",
            "Prompt text must not be stored",
            "`permissions` | `contextMenus`",
            "`host_permissions` | `http://127.0.0.1:8765/*`",
            "`content_scripts.matches`",
            "chatgpt.com",
            "claude.ai",
            "gemini.google.com",
            "`activeTab`",
            "`tabs`",
            "`scripting`",
            "`webRequest`",
            "`cookies`",
            "`history`",
            "`downloads`",
            "`identity`",
            "`<all_urls>`",
            "exact HTTPS backend origin",
            "Do not use `<all_urls>`",
        ):
            self.assertIn(token, text)

    def test_browser_extension_docs_cover_mv3_worker_lifecycle(self):
        text = (ROOT / "docs" / "integrations" / "browser-extension.md").read_text(encoding="utf-8")

        for token in (
            "## MV3 Service Worker Lifecycle",
            "ephemeral",
            "store pending review state",
            "service-worker globals",
            "chrome.storage.sync.get",
            "junas-process-text",
            "one backend request",
            "chrome://extensions",
            "edge://extensions",
            "Stop or let the service worker go inactive",
            "rereads endpoint/auth settings",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
