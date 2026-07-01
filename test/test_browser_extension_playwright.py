import unittest
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover - exercised only when Playwright is installed
    sync_playwright = None
    PlaywrightError = Exception


ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "integrations" / "browser_extension"


class BrowserExtensionPlaywrightSmokeTests(unittest.TestCase):
    @unittest.skipIf(sync_playwright is None, "python playwright package unavailable")
    def test_prompt_submit_handles_known_and_changed_composer_dom(self):
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch()
            except PlaywrightError as exc:
                self.skipTest(f"chromium unavailable: {exc}")
            try:
                page = browser.new_page()
                self._install_fixture(page)

                page.click("[data-testid='send-button']")
                page.wait_for_function("window.__submitted === 1 && window.__messages.length === 1")
                self.assertEqual(page.evaluate("window.__messages[0].text"), "warn before submit")
                self.assertEqual(page.evaluate("window.__messages[0].operation"), "review")
                self.assertIn("Submit anyway", page.evaluate("window.__confirmed"))

                page.evaluate(
                    """
                    document.body.innerHTML = `
                      <div class="renamed-editor">dom changed prompt</div>
                      <button data-testid="send-button" onclick="window.__submitted += 1">Send</button>
                    `;
                    window.__submitted = 0;
                    window.__messages = [];
                    """
                )
                page.click("[data-testid='send-button']")
                page.wait_for_function("window.__submitted === 1")
                self.assertEqual(page.evaluate("window.__messages.length"), 0)
                self.assertIn(
                    "prompt composer selector unavailable",
                    page.locator("#junas-review-result").text_content(),
                )

                page.evaluate(
                    """
                    document.body.innerHTML = `
                      <textarea data-testid="prompt-textarea">renamed submit control</textarea>
                      <button id="renamed-submit" onclick="window.__submitted += 1">Send</button>
                    `;
                    window.__submitted = 0;
                    window.__messages = [];
                    """
                )
                page.locator("[data-testid='prompt-textarea']").press("Enter")
                page.wait_for_selector("#junas-review-result")
                self.assertEqual(page.evaluate("window.__messages.length"), 0)
                self.assertIn(
                    "submit button selector unavailable",
                    page.locator("#junas-review-result").text_content(),
                )
            finally:
                browser.close()

    def _install_fixture(self, page):
        fixture = ROOT / "test" / "fixtures" / "adapter-smoke" / "browser_genai.html"
        page.route(
            "https://chatgpt.com/adapter-smoke",
            lambda route: route.fulfill(
                status=200,
                content_type="text/html",
                body=fixture.read_text(encoding="utf-8"),
            ),
        )
        page.goto("https://chatgpt.com/adapter-smoke")
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
        page.add_script_tag(path=str(EXT / "adapters.js"))
        page.add_script_tag(path=str(EXT / "content.js"))
        page.wait_for_function("window.__storageReads === 1")


if __name__ == "__main__":
    unittest.main()
