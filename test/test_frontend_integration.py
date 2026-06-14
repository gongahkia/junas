import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class FrontendIntegrationTests(unittest.TestCase):
    def run_node(self, script: str) -> None:
        if not shutil.which("node"):
            self.skipTest("node unavailable")
        result = subprocess.run(
            ["node"],
            input=textwrap.dedent(script),
            text=True,
            cwd=ROOT,
            capture_output=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")

    def test_browser_worker_posts_warn_policy_and_returns_redaction(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/service_worker.js", "utf8");
            const requests = [];
            const messages = [];
            const context = {
              fetch: async (url, options) => {
                requests.push({url, options, body: JSON.parse(options.body)});
                return {ok: true, json: async () => ({
                  redacted_text: "[redacted]",
                  degraded_modes: [{mode: "document_unsupported"}],
                  send_allowed: true
                })};
              },
              chrome: {
                storage: {sync: {get: async (defaults) => ({
                  ...defaults,
                  endpoint: "http://kaypoh.local",
                  operation: "redact",
                  token: "client-token"
                })}},
                runtime: {
                  onInstalled: {addListener() {}},
                  onMessage: {addListener(fn) { context.__messageListener = fn; }}
                },
                contextMenus: {
                  create() {},
                  onClicked: {addListener() {}}
                },
                tabs: {sendMessage: async (tabId, payload) => messages.push({tabId, payload})}
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "service_worker.js"});
            (async () => {
              const response = await new Promise((resolve) => {
                const keepAlive = context.__messageListener(
                  {type: "kaypoh-process-text", text: "alice@example.com"},
                  {tab: {id: 7}},
                  resolve
                );
                assert.strictEqual(keepAlive, true);
              });
              assert.strictEqual(requests[0].url, "http://kaypoh.local/redact");
              assert.strictEqual(requests[0].options.headers["X-Kaypoh-Local-Token"], "client-token");
              assert.strictEqual(requests[0].body.degraded_policy, "warn");
              assert.strictEqual(response.ok, true);
              assert.strictEqual(response.replacementText, "[redacted]");
              assert.strictEqual(messages[0].payload.result.degraded_modes.length, 1);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_outlook_launch_event_blocks_degraded_review(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const requests = [];
            const context = {
              localStorage: {getItem: () => ""},
              OfficeRuntime: {storage: {getItem: async (key) => ({
                "kaypoh.endpoint": "http://kaypoh.local",
                "kaypoh.localToken": "client-token"
              }[key] || "")}},
              Office: {
                AsyncResultStatus: {Succeeded: "succeeded"},
                actions: {associate(name, fn) { context.__handler = fn; }},
                context: {
                  mailbox: {
                    item: {
                      body: {
                        getAsync(format, options, callback) {
                          callback({status: "succeeded", value: "confidential draft"});
                        }
                      }
                    }
                  }
                }
              },
              fetch: async (url, options) => {
                requests.push({url, options, body: JSON.parse(options.body)});
                return {ok: true, json: async () => ({
                  findings: [],
                  pii_score: 0,
                  mnpi_score: 0,
                  degraded_modes: [{mode: "document_ocr_unavailable"}],
                  send_allowed: false
                })};
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "launchevent.js"});
            (async () => {
              const completed = new Promise((resolve) => context.__handler({completed: resolve}));
              const result = await completed;
              assert.strictEqual(requests[0].url, "http://kaypoh.local/review");
              assert.strictEqual(requests[0].options.headers["X-Kaypoh-Local-Token"], "client-token");
              assert.strictEqual(requests[0].body.degraded_policy, "block_send");
              assert.strictEqual(requests[0].body.surface, "outlook");
              assert.strictEqual(requests[0].body.workflow, "email_send");
              assert.strictEqual(result.allowEvent, false);
              assert.match(result.errorMessage, /could not fully inspect/);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_outlook_policy_decisions_map_to_smart_alert_completion_modes(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const context = {
              localStorage: {getItem: () => ""},
              OfficeRuntime: {storage: {getItem: async () => ""}},
              Office: {
                MailboxEnums: {SendModeOverride: {PromptUser: "promptUser"}},
                actions: {associate() {}}
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "launchevent.js"});

            const allow = context.kaypohSmartAlertCompletion({
              findings: [],
              pii_score: 0,
              mnpi_score: 0,
              degraded_modes: [],
              send_allowed: true,
              policy_decision: {decision: "allow", send_allowed: true}
            });
            assert.strictEqual(allow.mode, "allow");
            assert.strictEqual(allow.options.allowEvent, true);
            assert.deepStrictEqual(Object.keys(allow.options), ["allowEvent"]);

            const warn = context.kaypohSmartAlertCompletion({
              findings: [{rule: "email_address"}],
              degraded_modes: [],
              policy_decision: {
                decision: "warn",
                send_allowed: true,
                recommended_actions: ["proceed_with_warning"]
              }
            });
            assert.strictEqual(warn.mode, "prompt_user");
            assert.strictEqual(warn.options.allowEvent, false);
            assert.strictEqual(warn.options.sendModeOverride, "promptUser");

            const approval = context.kaypohSmartAlertCompletion({
              findings: [{rule: "sg_nric_fin"}],
              degraded_modes: [],
              policy_decision: {
                decision: "approval_required",
                send_allowed: false,
                required_actions: ["request_approval"]
              }
            });
            assert.strictEqual(approval.mode, "soft_block");
            assert.strictEqual(approval.options.allowEvent, false);
            assert.ok(!approval.options.sendModeOverride);

            const block = context.kaypohSmartAlertCompletion({
              findings: [{rule: "sg_nric_fin"}],
              degraded_modes: [],
              policy_decision: {decision: "block", send_allowed: false}
            });
            assert.strictEqual(block.mode, "hard_block");
            assert.strictEqual(block.options.allowEvent, false);
            assert.ok(!block.options.sendModeOverride);
            """
        )


if __name__ == "__main__":
    unittest.main()
