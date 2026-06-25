import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFICE = ROOT / "integrations" / "outlook_addin"


class OfficeAddinTests(unittest.TestCase):
    def test_taskpane_exposes_token_storage_controls(self):
        html = (OFFICE / "taskpane.html").read_text(encoding="utf-8")
        self.assertIn('id="endpoint"', html)
        self.assertIn('id="token"', html)
        self.assertIn('type="password"', html)
        self.assertIn('id="sendHookTimeoutMs"', html)
        self.assertIn('id="saveSettings"', html)
        self.assertIn('id="checkPairing"', html)
        self.assertIn('id="startPairing"', html)
        self.assertIn('id="completePairing"', html)

    def test_taskpane_persists_token_and_sets_local_header(self):
        js = (OFFICE / "taskpane.js").read_text(encoding="utf-8")
        self.assertIn("OfficeRuntime?.storage", js)
        self.assertIn("localStorage.setItem", js)
        self.assertIn("junas.localToken", js)
        self.assertIn("junas.sendHookTimeoutMs", js)
        self.assertIn('headers["X-Junas-Local-Token"] = currentConfig.token', js)
        self.assertIn("/local/pairing/start", js)
        self.assertIn("/local/pairing/claim", js)
        self.assertIn("client_token", js)
        self.assertIn('degraded_policy: "warn"', js)
        self.assertIn("degraded_modes", js)
        self.assertIn("send_allowed", js)

    def test_taskpane_can_check_pairing_status(self):
        js = (OFFICE / "taskpane.js").read_text(encoding="utf-8")
        self.assertIn("/local/pairing/status", js)
        self.assertIn("token_provisioned", js)
        self.assertIn("acl_enabled", js)

    def test_manifest_declares_on_message_send_launch_event(self):
        xml = (OFFICE / "manifest.xml").read_text(encoding="utf-8")
        self.assertIn("Pre-send policy review and decision support", xml)
        self.assertNotIn("Pre-send review through the local Junas daemon", xml)
        self.assertIn("{{JUNAS_OUTLOOK_ADDIN_ORIGIN}}/taskpane.html", xml)
        self.assertNotIn("https://localhost:3000", xml)
        self.assertIn('DefaultMinVersion="1.15"', xml)
        self.assertIn('xsi:type="LaunchEvent"', xml)
        self.assertIn('Type="OnMessageSend"', xml)
        self.assertIn('FunctionName="onMessageSendHandler"', xml)
        self.assertIn('SendMode="SoftBlock"', xml)
        self.assertIn('id="JSRuntime.Url"', xml)

    def test_event_runtime_associates_handler_and_calls_review(self):
        js = (OFFICE / "launchevent.js").read_text(encoding="utf-8")
        html = (OFFICE / "commands.html").read_text(encoding="utf-8")
        self.assertIn("Office.actions.associate", js)
        self.assertIn("onMessageSendHandler", js)
        self.assertIn("/review", js)
        self.assertIn("allowEvent: false", js)
        self.assertIn("X-Junas-Local-Token", js)
        self.assertIn('degraded_policy: "block_send"', js)
        self.assertIn('surface: "outlook"', js)
        self.assertIn('workflow: "email_send"', js)
        self.assertIn("junasMessageContext", js)
        self.assertIn("junasStoredTimeout", js)
        self.assertIn("JUNAS_DEFAULT_SEND_TIMEOUT_MS", js)
        self.assertIn("AbortController", js)
        self.assertIn("recipient_domains", js)
        self.assertIn("attachment_count", js)
        self.assertIn("junasSmartAlertCompletion", js)
        self.assertIn("sendModeOverride", js)
        self.assertIn("policy_decision", js)
        self.assertIn("could not fully inspect", js)
        self.assertIn("launchevent.js", html)
        self.assertNotRegex(js, re.compile(r"^\s*(import|export)\b", re.M))
        self.assertIn('<script src="launchevent.js"></script>', html)

    def test_adapter_does_not_store_message_body_or_log_to_console(self):
        sources = {
            "launchevent.js": (OFFICE / "launchevent.js").read_text(encoding="utf-8"),
            "taskpane.js": (OFFICE / "taskpane.js").read_text(encoding="utf-8"),
        }
        combined = "\n".join(sources.values())

        self.assertNotIn("console.", combined)
        storage_pattern = re.compile(
            r"(localStorage|OfficeRuntime\.storage)\.setItem\([^)]*(body|text|subject)",
            re.I,
        )
        self.assertNotRegex(combined, storage_pattern)
        self.assertNotRegex(combined, re.compile(r"setStored\([^)]*(body|text|subject|recipient|attachment)", re.I))
        self.assertNotIn("junasMessageContext(event).then((context) => setStored", sources["launchevent.js"])
        self.assertIn("junasTelemetryDetails", sources["launchevent.js"])
        self.assertIn("JUNAS_TELEMETRY_KEYS", sources["launchevent.js"])


if __name__ == "__main__":
    unittest.main()
