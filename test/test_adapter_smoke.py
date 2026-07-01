import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from scripts.render_outlook_manifest import TEMPLATE, render_manifest
from scripts.validate_outlook_manifest import validate_manifest

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None
    PlaywrightError = Exception


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "test" / "fixtures" / "adapter-smoke"
BROWSER = ROOT / "integrations" / "browser_extension"
OUTLOOK = ROOT / "integrations" / "outlook_addin"
WORD = ROOT / "integrations" / "word_addin"


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.testids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-testid"):
            self.testids.add(values["data-testid"])


def html_ids(path: Path) -> IdParser:
    parser = IdParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class AdapterManifestSmokeTests(unittest.TestCase):
    def test_browser_manifest_and_fixture_page_are_local_smokeable(self):
        manifest = json.loads((BROWSER / "manifest.json").read_text(encoding="utf-8"))
        fixture = html_ids(FIXTURES / "browser_genai.html")

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["background"]["service_worker"], "service_worker.js")
        self.assertTrue((BROWSER / manifest["background"]["service_worker"]).is_file())
        self.assertTrue((BROWSER / manifest["options_page"]).is_file())
        self.assertEqual(manifest["host_permissions"], ["http://127.0.0.1:8765/*"])
        self.assertNotIn("<all_urls>", manifest["host_permissions"])
        self.assertIn("prompt-textarea", fixture.testids)
        self.assertIn("send-button", fixture.testids)
        for script in manifest["content_scripts"][0]["js"]:
            self.assertTrue((BROWSER / script).is_file(), script)

    def test_outlook_rendered_manifest_validates_without_saas_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.xml"
            rendered = render_manifest(TEMPLATE, profile="production", origin="https://addin.example.com")
            path.write_text(rendered, encoding="utf-8")

            self.assertEqual(validate_manifest(path, profile="production"), [])

        for name in ("taskpane.html", "commands.html", "launchevent.js"):
            self.assertTrue((OUTLOOK / name).is_file(), name)
        self.assertTrue((FIXTURES / "outlook_message_send.html").is_file())

    def test_word_manifest_and_fixture_page_are_local_smokeable(self):
        root = ET.parse(WORD / "manifest.xml").getroot()
        hosts = [element.attrib.get("Name") for element in root.iter() if local_name(element.tag) == "Host"]
        urls = [element.attrib.get("DefaultValue", "") for element in root.iter() if local_name(element.tag) == "Url"]
        fixture = html_ids(FIXTURES / "word_taskpane.html")

        self.assertIn("Document", hosts)
        self.assertTrue(any(url.endswith("/taskpane.html") for url in urls))
        self.assertTrue((WORD / "taskpane.html").is_file())
        self.assertTrue((WORD / "taskpane.js").is_file())
        expected_ids = {"endpoint", "token", "saveSettings", "reviewSelection", "reviewBody", "output"}
        self.assertLessEqual(expected_ids, fixture.ids)


class AdapterFixturePagePlaywrightSmokeTests(unittest.TestCase):
    @unittest.skipIf(sync_playwright is None, "python playwright package unavailable")
    def test_local_fixture_pages_execute_adapter_paths(self):
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except PlaywrightError as exc:
                self.skipTest(f"chromium unavailable: {exc}")
            try:
                context = browser.new_context(ignore_https_errors=True)
                page = context.new_page()
                self._smoke_browser_prompt(page)
                self._smoke_outlook_send(page)
                self._smoke_word_taskpane(page)
            finally:
                browser.close()

    def _route_fixture(self, page, url: str, path: Path):
        page.route(
            url,
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=path.read_text(encoding="utf-8"),
            ),
        )
        page.goto(url)

    def _smoke_browser_prompt(self, page):
        self._route_fixture(page, "https://chatgpt.com/adapter-smoke", FIXTURES / "browser_genai.html")
        page.evaluate(
            """
            window.__submitted = 0;
            window.__messages = [];
            window.__confirmed = "";
            window.__storageReads = 0;
            window.__reviewResponse = {
              ok: true,
              result: {
                findings: [{rule: "email_address"}],
                degraded_modes: [],
                policy_decision: {
                  decision: "warn",
                  send_allowed: true,
                  recommended_actions: ["proceed_with_warning"]
                }
              }
            };
            window.confirm = (message) => {
              window.__confirmed = message;
              return true;
            };
            window.chrome = {
              storage: {
                sync: {
                  get: async (defaults) => {
                    window.__storageReads += 1;
                    return {...defaults, reviewBeforeSubmit: true};
                  }
                },
                onChanged: {addListener() {}}
              },
              runtime: {
                onMessage: {addListener(fn) { window.__messageListener = fn; }},
                sendMessage: async (message) => {
                  window.__messages.push(message);
                  return window.__reviewResponse;
                }
              }
            };
            """
        )
        page.add_script_tag(path=str(BROWSER / "adapters.js"))
        page.add_script_tag(path=str(BROWSER / "content.js"))
        page.wait_for_function("window.__storageReads === 1")
        page.click("[data-testid='send-button']")
        page.wait_for_function("window.__submitted === 1 && window.__messages.length === 1")
        self.assertEqual(page.evaluate("window.__messages[0].text"), "warn before submit")
        self.assertEqual(page.evaluate("window.__messages[0].operation"), "review")
        self.assertIn("Submit anyway", page.evaluate("window.__confirmed"))

    def _smoke_outlook_send(self, page):
        self._route_fixture(page, "http://adapter-smoke.local/outlook.html", FIXTURES / "outlook_message_send.html")
        page.evaluate(
            """
            window.__fetches = [];
            window.__telemetry = [];
            window.__completion = null;
            localStorage.setItem("junas.endpoint", "http://127.0.0.1:8765");
            localStorage.setItem("junas.localToken", "local-smoke-token");
            localStorage.setItem("junas.sendHookTimeoutMs", "2500");
            window.junasTelemetrySink = (event) => window.__telemetry.push(event);
            window.Office = {
              AsyncResultStatus: {Succeeded: "succeeded"},
              MailboxEnums: {SendModeOverride: {PromptUser: "promptUser"}},
              context: {
                mailbox: {
                  item: {
                    body: {
                      getAsync: (coercion, options, callback) => callback({
                        status: "succeeded",
                        value: "Please send Acme Corp renewal terms."
                      })
                    },
                    subject: {getAsync: (callback) => callback({status: "succeeded", value: "Project Harbor"})},
                    to: {
                      getAsync: (callback) => callback({
                        status: "succeeded",
                        value: [{emailAddress: "client@external.example"}]
                      })
                    },
                    cc: {getAsync: (callback) => callback({status: "succeeded", value: []})},
                    bcc: {getAsync: (callback) => callback({status: "succeeded", value: []})},
                    getAttachmentsAsync: (callback) => callback({status: "succeeded", value: [{name: "pricing.pdf"}]})
                  }
                }
              },
              actions: {associate: (name, fn) => { window.__associated = name; window.__handler = fn; }}
            };
            window.fetch = async (url, options) => {
              window.__fetches.push({url, body: JSON.parse(options.body), headers: options.headers});
              return {
                ok: true,
                json: async () => ({
                  request_id: "req-smoke",
                  findings: [{rule: "restricted_list"}],
                  degraded_modes: [],
                  pii_score: 0,
                  mnpi_score: 0,
                  send_allowed: true,
                  policy_decision: {
                    decision: "warn",
                    send_allowed: true,
                    review_id: "rev-smoke",
                    policy_id: "default",
                    policy_version: "1",
                    recommended_actions: ["proceed_with_warning"],
                    required_actions: []
                  }
                })
              };
            };
            """
        )
        page.add_script_tag(path=str(OUTLOOK / "launchevent.js"))
        page.wait_for_function('window.__associated === "onMessageSendHandler"')
        page.evaluate("window.__handler({completed: (options) => { window.__completion = options; }})")
        page.wait_for_function("window.__completion !== null")
        payload = page.evaluate("window.__fetches[0].body")
        completion = page.evaluate("window.__completion")
        telemetry = page.evaluate("window.__telemetry.map((event) => event.event_name)")
        self.assertEqual(payload["surface"], "outlook")
        self.assertEqual(payload["workflow"], "email_send")
        self.assertEqual(payload["recipient_domains"], ["external.example"])
        self.assertEqual(payload["attachment_count"], 1)
        self.assertIn("Subject: Project Harbor", payload["text"])
        self.assertFalse(completion["allowEvent"])
        self.assertEqual(completion["sendModeOverride"], "promptUser")
        self.assertIn("outlook_review_started", telemetry)
        self.assertIn("outlook_policy_decision_received", telemetry)

    def _smoke_word_taskpane(self, page):
        self._route_fixture(page, "http://adapter-smoke.local/word.html", FIXTURES / "word_taskpane.html")
        page.evaluate(
            """
            window.__fetches = [];
            window.Office = {
              AsyncResultStatus: {Succeeded: "succeeded"},
              CoercionType: {Text: "text"},
              context: {
                document: {
                  getSelectedDataAsync: (coercion, callback) => callback({
                    status: "succeeded",
                    value: "Selected Acme Corp clause"
                  })
                }
              },
              onReady: (callback) => Promise.resolve().then(callback)
            };
            window.Word = {
              run: async (callback) => {
                const context = {
                  document: {body: {text: "Body Acme Corp clause", load() {}}},
                  sync: async () => {}
                };
                return callback(context);
              }
            };
            window.fetch = async (url, options) => {
              window.__fetches.push({url, body: JSON.parse(options.body), headers: options.headers});
              return {
                ok: true,
                json: async () => ({
                  pii_score: 0.8,
                  mnpi_score: 0,
                  findings: [{rule: "restricted_list"}],
                  degraded_modes: [],
                  send_allowed: false
                })
              };
            };
            """
        )
        page.add_script_tag(path=str(WORD / "taskpane.js"))
        page.wait_for_function("typeof window.reviewSelection.onclick === 'function'")
        page.click("#reviewSelection")
        page.wait_for_function(
            "window.__fetches.length === 1 && document.getElementById('output').textContent.includes('findings')"
        )
        payload = page.evaluate("window.__fetches[0].body")
        output = json.loads(page.locator("#output").text_content())
        self.assertEqual(payload["document_type"], "word_document")
        self.assertEqual(payload["text"], "Selected Acme Corp clause")
        self.assertEqual(output["findings"], 1)
        self.assertFalse(output["send_allowed"])


if __name__ == "__main__":
    unittest.main()
