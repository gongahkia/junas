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
                  endpoint: "http://junas.local",
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
                  {type: "junas-process-text", text: "alice@example.com"},
                  {tab: {id: 7}},
                  resolve
                );
                assert.strictEqual(keepAlive, true);
              });
              assert.strictEqual(requests[0].url, "http://junas.local/redact");
              assert.strictEqual(requests[0].options.headers["X-Junas-Local-Token"], "client-token");
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

    def test_browser_worker_uses_bearer_header_for_hosted_auth_mode(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/service_worker.js", "utf8");
            const requests = [];
            const context = {
              fetch: async (url, options) => {
                requests.push({url, options, body: JSON.parse(options.body)});
                return {ok: true, json: async () => ({
                  findings: [],
                  degraded_modes: [],
                  send_allowed: true
                })};
              },
              chrome: {
                storage: {sync: {get: async (defaults) => ({
                  ...defaults,
                  endpoint: "https://junas.example",
                  backendMode: "hosted_server",
                  authMode: "bearer_token",
                  operation: "redact",
                  token: "tenant-jwt"
                })}},
                runtime: {
                  onInstalled: {addListener() {}},
                  onMessage: {addListener(fn) { context.__messageListener = fn; }}
                },
                contextMenus: {
                  create() {},
                  onClicked: {addListener() {}}
                },
                tabs: {sendMessage: async () => {}}
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "service_worker.js"});
            (async () => {
              await new Promise((resolve) => {
                context.__messageListener(
                  {type: "junas-process-text", text: "safe", operation: "review"},
                  {},
                  resolve
                );
              });
              assert.strictEqual(requests[0].url, "https://junas.example/review");
              assert.strictEqual(requests[0].options.headers.Authorization, "Bearer tenant-jwt");
              assert.ok(!requests[0].options.headers["X-Junas-Local-Token"]);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_browser_worker_does_not_store_or_log_prompt_text(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/service_worker.js", "utf8");
            const secret = "privileged board prompt alice@example.com";
            const requests = [];
            const storageWrites = [];
            const consoleCalls = [];
            const context = {
              fetch: async (url, options) => {
                requests.push({url, body: JSON.parse(options.body)});
                return {ok: true, json: async () => ({findings: [], degraded_modes: [], send_allowed: true})};
              },
              console: {
                log: (...args) => consoleCalls.push(["log", args]),
                warn: (...args) => consoleCalls.push(["warn", args]),
                error: (...args) => consoleCalls.push(["error", args])
              },
              localStorage: {setItem: (key, value) => storageWrites.push(["localStorage", key, value])},
              sessionStorage: {setItem: (key, value) => storageWrites.push(["sessionStorage", key, value])},
              indexedDB: {open: (name) => storageWrites.push(["indexedDB", name])},
              chrome: {
                storage: {
                  sync: {
                    get: async (defaults) => ({...defaults, endpoint: "http://junas.local"}),
                    set: (value) => storageWrites.push(["sync", value])
                  },
                  local: {
                    set: (value) => storageWrites.push(["local", value])
                  }
                },
                runtime: {
                  onInstalled: {addListener() {}},
                  onMessage: {addListener(fn) { context.__messageListener = fn; }}
                },
                contextMenus: {
                  create() {},
                  onClicked: {addListener() {}}
                },
                tabs: {sendMessage: async () => {}}
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "service_worker.js"});
            (async () => {
              const response = await new Promise((resolve) => {
                const keepAlive = context.__messageListener(
                  {type: "junas-process-text", text: secret, operation: "review"},
                  {tab: {id: 1}},
                  resolve
                );
                assert.strictEqual(keepAlive, true);
              });
              assert.strictEqual(response.ok, true);
              assert.strictEqual(requests[0].body.text, secret);
              assert.deepStrictEqual(storageWrites, []);
              assert.deepStrictEqual(consoleCalls, []);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_browser_options_connection_health_classifies_states(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/options.js", "utf8");
            const listeners = {};
            const context = {
              endpoint: {value: "http://127.0.0.1:8765"},
              backendMode: {value: "local_daemon"},
              authMode: {value: "local_token"},
              token: {value: "local-token"},
              operation: {value: "review"},
              interceptPaste: {checked: false},
              reviewBeforeSubmit: {checked: false},
              save: {addEventListener: (name, fn) => { listeners.save = fn; }},
              checkConnection: {addEventListener: (name, fn) => { listeners.checkConnection = fn; }},
              startPairing: {addEventListener: () => {}},
              completePairing: {addEventListener: () => {}},
              healthStatus: {textContent: ""},
              pairingStatus: {textContent: ""},
              chrome: {
                storage: {
                  sync: {
                    get: async (defaults) => defaults,
                    set: async () => {}
                  }
                }
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "options.js"});

            (async () => {
              context.fetch = async () => {
                throw new Error("connect ECONNREFUSED");
              };
              assert.strictEqual(await context.checkConnectionHealth(), "local daemon unavailable");

              context.fetch = async () => ({status: 403, ok: false});
              assert.strictEqual(await context.checkConnectionHealth(), "auth failed: 403");

              context.fetch = async (url) => {
                if (url.endsWith("/ready")) return {status: 200, ok: true};
                return {status: 200, ok: true, json: async () => ({send_allowed: false})};
              };
              assert.strictEqual(await context.checkConnectionHealth(), "policy blocked");

              context.fetch = async (url) => {
                if (url.endsWith("/ready")) return {status: 200, ok: true};
                return {
                  status: 200,
                  ok: true,
                  json: async () => ({send_allowed: true, policy_decision: {send_allowed: true}})
                };
              };
              await listeners.checkConnection();
              assert.strictEqual(context.healthStatus.textContent, "server healthy");
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_browser_content_does_not_store_or_log_prompt_text(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/content.js", "utf8");
            const secret = "paste prompt with client secret alice@example.com";
            const listeners = {};
            const messages = [];
            const storageWrites = [];
            const consoleCalls = [];
            const prompt = {
              tagName: "TEXTAREA",
              value: "",
              type: "",
              isContentEditable: false
            };
            const context = {
              setTimeout: () => 0,
              InputEvent: function InputEvent() {},
              window: {
                location: {hostname: "chatgpt.com"},
                getSelection: () => null
              },
              document: {
                addEventListener(name, fn) {
                  listeners[name] = fn;
                },
                getElementById() {
                  return null;
                },
                createElement() {
                  return {style: {}, remove() {}};
                },
                documentElement: {appendChild() {}},
                execCommand() {}
              },
              console: {
                log: (...args) => consoleCalls.push(["log", args]),
                warn: (...args) => consoleCalls.push(["warn", args]),
                error: (...args) => consoleCalls.push(["error", args])
              },
              localStorage: {setItem: (key, value) => storageWrites.push(["localStorage", key, value])},
              sessionStorage: {setItem: (key, value) => storageWrites.push(["sessionStorage", key, value])},
              indexedDB: {open: (name) => storageWrites.push(["indexedDB", name])},
              chrome: {
                storage: {
                  sync: {
                    get: async (defaults) => ({...defaults, interceptPaste: true, operation: "review"}),
                    set: (value) => storageWrites.push(["sync", value])
                  },
                  local: {
                    set: (value) => storageWrites.push(["local", value])
                  },
                  onChanged: {addListener() {}}
                },
                runtime: {
                  onMessage: {addListener() {}},
                  sendMessage: async (message) => {
                    messages.push(message);
                    return {ok: true, result: {findings: [], degraded_modes: [], send_allowed: true}};
                  }
                }
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "content.js"});

            (async () => {
              await Promise.resolve();
              await listeners.paste({
                target: prompt,
                clipboardData: {getData: () => secret},
                preventDefault() {
                  this.prevented = true;
                }
              });
              assert.strictEqual(messages[0].text, secret);
              assert.strictEqual(messages[0].type, "junas-process-text");
              assert.strictEqual(messages[0].operation, undefined);
              assert.deepStrictEqual(storageWrites, []);
              assert.deepStrictEqual(consoleCalls, []);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_browser_target_adapters_resolve_known_prompt_selectors(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/browser_extension/adapters.js", "utf8");
            const context = {};
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "adapters.js"});
            const adapters = context.JUNAS_BROWSER_ADAPTERS;

            function rootReturning(expectedSelector) {
              return {
                selectors: [],
                querySelector(selector) {
                  this.selectors.push(selector);
                  return selector === expectedSelector ? {selector} : null;
                }
              };
            }

            function elementMatching(expectedSelector) {
              return {
                matches(selector) {
                  return selector === expectedSelector;
                },
                closest() {
                  return null;
                },
                tagName: "DIV",
                isContentEditable: true
              };
            }

            const chatgptLocation = {hostname: "chatgpt.com"};
            const claudeLocation = {hostname: "claude.ai"};
            const geminiLocation = {hostname: "gemini.google.com"};
            const genericLocation = {hostname: "example.test"};

            assert.strictEqual(adapters.adapterForLocation(chatgptLocation).id, "chatgpt");
            assert.strictEqual(adapters.adapterForLocation(claudeLocation).id, "claude");
            assert.strictEqual(adapters.adapterForLocation(geminiLocation).id, "gemini");
            assert.strictEqual(adapters.adapterForLocation(genericLocation).id, "generic");

            assert.strictEqual(
              adapters.findPromptComposer(rootReturning("[data-testid='prompt-textarea']"), chatgptLocation).selector,
              "[data-testid='prompt-textarea']"
            );
            assert.strictEqual(
              adapters.findPromptComposer(rootReturning("div.ProseMirror[contenteditable='true']"), claudeLocation)
                .selector,
              "div.ProseMirror[contenteditable='true']"
            );
            assert.strictEqual(
              adapters.findPromptComposer(rootReturning("rich-textarea textarea"), geminiLocation).selector,
              "rich-textarea textarea"
            );
            assert.strictEqual(
              adapters.findPromptComposer(rootReturning("textarea"), genericLocation).selector,
              "textarea"
            );
            assert.ok(
              adapters.resolvePromptTarget(elementMatching("[data-testid='prompt-textarea']"), chatgptLocation)
            );
            """
        )

    def test_browser_content_warns_before_prompt_submit_and_reclicks_on_confirmation(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const adaptersSource = fs.readFileSync("integrations/browser_extension/adapters.js", "utf8");
            const contentSource = fs.readFileSync("integrations/browser_extension/content.js", "utf8");
            const listeners = {};
            const messages = [];
            let clicked = 0;
            let confirmed = "";
            const prompt = {
              tagName: "TEXTAREA",
              value: "warn before submit",
              matches(selector) {
                return selector === "[data-testid='prompt-textarea']" || selector === "textarea";
              },
              closest() {
                return null;
              }
            };
            const submitButton = {
              matches(selector) {
                return selector === "[data-testid='send-button']";
              },
              closest() {
                return null;
              },
              click() {
                clicked += 1;
              }
            };
            const context = {
              setTimeout: () => 0,
              window: {
                location: {hostname: "chatgpt.com"},
                confirm(message) {
                  confirmed = message;
                  return true;
                }
              },
              document: {
                addEventListener(name, fn) {
                  listeners[name] = fn;
                },
                getElementById() {
                  return null;
                },
                createElement() {
                  return {style: {}, remove() {}};
                },
                documentElement: {appendChild() {}},
                querySelector(selector) {
                  if (selector === "[data-testid='prompt-textarea']") return prompt;
                  if (selector === "[data-testid='send-button']") return submitButton;
                  return null;
                }
              },
              chrome: {
                storage: {
                  sync: {
                    get: async (defaults) => ({...defaults, reviewBeforeSubmit: true}),
                    set: async () => {}
                  },
                  onChanged: {addListener() {}}
                },
                runtime: {
                  onMessage: {addListener() {}},
                  sendMessage: async (message) => {
                    messages.push(message);
                    return {
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
                  }
                }
              }
            };
            vm.createContext(context);
            vm.runInContext(adaptersSource, context, {filename: "adapters.js"});
            vm.runInContext(contentSource, context, {filename: "content.js"});

            (async () => {
              await Promise.resolve();
              const event = {
                target: submitButton,
                preventDefault() {
                  this.prevented = true;
                },
                stopImmediatePropagation() {
                  this.stopped = true;
                }
              };
              await listeners.click(event);
              assert.strictEqual(event.prevented, true);
              assert.strictEqual(event.stopped, true);
              assert.strictEqual(messages[0].type, "junas-process-text");
              assert.strictEqual(messages[0].operation, "review");
              assert.strictEqual(messages[0].text, "warn before submit");
              assert.match(confirmed, /Submit anyway/);
              assert.strictEqual(clicked, 1);
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_browser_content_selector_failures_do_not_block_without_review(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const adaptersSource = fs.readFileSync("integrations/browser_extension/adapters.js", "utf8");
            const contentSource = fs.readFileSync("integrations/browser_extension/content.js", "utf8");
            const listeners = {};
            const panels = [];
            const messages = [];
            const prompt = {
              tagName: "TEXTAREA",
              value: "selector fallback",
              matches(selector) {
                return selector === "[data-testid='prompt-textarea']" || selector === "textarea";
              },
              closest() {
                return null;
              }
            };
            const submitButton = {
              matches(selector) {
                return selector === "[data-testid='send-button']";
              },
              closest() {
                return null;
              },
              click() {}
            };
            const context = {
              setTimeout: () => 0,
              window: {
                location: {hostname: "chatgpt.com"},
                confirm() {
                  throw new Error("confirm should not run");
                }
              },
              document: {
                mode: "missing_prompt",
                addEventListener(name, fn) {
                  listeners[name] = fn;
                },
                getElementById() {
                  return null;
                },
                createElement() {
                  return {style: {}, remove() {}};
                },
                documentElement: {
                  appendChild(panel) {
                    panels.push(panel.textContent);
                  }
                },
                querySelector(selector) {
                  if (this.mode === "missing_prompt" && selector === "[data-testid='send-button']") return submitButton;
                  if (this.mode === "missing_submit" && selector === "[data-testid='prompt-textarea']") return prompt;
                  return null;
                }
              },
              chrome: {
                storage: {
                  sync: {
                    get: async (defaults) => ({...defaults, reviewBeforeSubmit: true}),
                    set: async () => {}
                  },
                  onChanged: {addListener() {}}
                },
                runtime: {
                  onMessage: {addListener() {}},
                  sendMessage: async (message) => {
                    messages.push(message);
                    return {ok: true, result: {findings: [], degraded_modes: [], send_allowed: true}};
                  }
                }
              }
            };
            vm.createContext(context);
            vm.runInContext(adaptersSource, context, {filename: "adapters.js"});
            vm.runInContext(contentSource, context, {filename: "content.js"});

            (async () => {
              await Promise.resolve();
              const clickEvent = {
                target: submitButton,
                preventDefault() {
                  this.prevented = true;
                },
                stopImmediatePropagation() {
                  this.stopped = true;
                }
              };
              await listeners.click(clickEvent);
              assert.strictEqual(clickEvent.prevented, undefined);
              assert.strictEqual(clickEvent.stopped, undefined);
              assert.strictEqual(messages.length, 0);
              assert.match(panels[0], /prompt composer selector unavailable/);
              assert.match(panels[0], /not blocked because no review ran/);

              context.document.mode = "missing_submit";
              const keyEvent = {
                key: "Enter",
                target: prompt,
                preventDefault() {
                  this.prevented = true;
                },
                stopImmediatePropagation() {
                  this.stopped = true;
                }
              };
              await listeners.keydown(keyEvent);
              assert.strictEqual(keyEvent.prevented, undefined);
              assert.strictEqual(keyEvent.stopped, undefined);
              assert.strictEqual(messages.length, 0);
              assert.match(panels[1], /submit button selector unavailable/);
              assert.match(panels[1], /not blocked because no review ran/);
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
            const telemetry = [];
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              junasTelemetrySink: (event) => telemetry.push(event),
              localStorage: {getItem: () => ""},
              OfficeRuntime: {storage: {getItem: async (key) => ({
                "junas.endpoint": "http://junas.local",
                "junas.localToken": "client-token",
                "junas.sendHookTimeoutMs": "2500"
              }[key] || "")}},
              Office: {
                AsyncResultStatus: {Succeeded: "succeeded"},
                actions: {associate(name, fn) { context.__handler = fn; }},
                context: {
                  mailbox: {
                    item: {
                      subject: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: "Board draft"});
                        }
                      },
                      body: {
                        getAsync(format, options, callback) {
                          callback({status: "succeeded", value: "confidential draft"});
                        }
                      },
                      to: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: [{emailAddress: "external@example.com"}]});
                        }
                      },
                      cc: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: [{emailAddress: "Legal@internal.test"}]});
                        }
                      },
                      bcc: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: []});
                        }
                      },
                      getAttachmentsAsync(callback) {
                        callback({status: "succeeded", value: [{name: "draft.docx", attachmentType: "file"}]});
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
              assert.strictEqual(requests[0].url, "http://junas.local/review");
              assert.ok(requests[0].options.signal);
              assert.strictEqual(typeof requests[0].options.signal.aborted, "boolean");
              assert.strictEqual(requests[0].options.headers["X-Junas-Local-Token"], "client-token");
              assert.strictEqual(requests[0].body.degraded_policy, "block_send");
              assert.strictEqual(requests[0].body.surface, "outlook");
              assert.strictEqual(requests[0].body.workflow, "email_send");
              assert.match(requests[0].body.text, /Subject: Board draft/);
              assert.match(requests[0].body.text, /confidential draft/);
              assert.deepStrictEqual(requests[0].body.recipient_domains, ["example.com", "internal.test"]);
              assert.strictEqual(requests[0].body.recipient_count, 2);
              assert.strictEqual(requests[0].body.attachment_count, 1);
              assert.ok(!JSON.stringify(requests[0].body).includes("draft.docx"));
              assert.strictEqual(result.allowEvent, false);
              assert.match(result.errorMessage, /could not fully inspect/);
              assert.deepStrictEqual(telemetry.map((event) => event.event_name), [
                "outlook_review_started",
                "outlook_policy_decision_received",
                "outlook_user_blocked"
              ]);
              assert.strictEqual(telemetry[0].schema_version, "junas.outlook.telemetry.v1");
              assert.strictEqual(telemetry[0].details.timeout_ms, 2500);
              assert.strictEqual(telemetry[0].details.recipient_count, 2);
              assert.strictEqual(telemetry[0].details.recipient_domain_count, 2);
              assert.strictEqual(telemetry[0].details.attachment_count, 1);
              assert.strictEqual(telemetry[1].details.degraded_count, 1);
              assert.strictEqual(telemetry[2].details.mode, "hard_block");
              const serializedTelemetry = JSON.stringify(telemetry);
              assert.ok(!serializedTelemetry.includes("Board draft"));
              assert.ok(!serializedTelemetry.includes("confidential draft"));
              assert.ok(!serializedTelemetry.includes("external@example.com"));
              assert.ok(!serializedTelemetry.includes("Legal@internal.test"));
              assert.ok(!serializedTelemetry.includes("draft.docx"));
              assert.ok(!serializedTelemetry.includes("client-token"));
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

            const allow = context.junasSmartAlertCompletion({
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

            const warn = context.junasSmartAlertCompletion({
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

            const approval = context.junasSmartAlertCompletion({
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

            const block = context.junasSmartAlertCompletion({
              findings: [{rule: "sg_nric_fin"}],
              degraded_modes: [],
              policy_decision: {decision: "block", send_allowed: false}
            });
            assert.strictEqual(block.mode, "hard_block");
            assert.strictEqual(block.options.allowEvent, false);
            assert.ok(!block.options.sendModeOverride);
            """
        )

    def test_outlook_launch_event_emits_backend_failure_and_block_telemetry(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const telemetry = [];
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              junasTelemetrySink: (event) => telemetry.push(event),
              localStorage: {getItem: () => ""},
              OfficeRuntime: {storage: {getItem: async (key) => ({
                "junas.endpoint": "http://junas.local",
                "junas.sendHookTimeoutMs": "1000"
              }[key] || "")}},
              Office: {
                AsyncResultStatus: {Succeeded: "succeeded"},
                actions: {associate(name, fn) { context.__handler = fn; }},
                context: {
                  mailbox: {
                    item: {
                      subject: {getAsync(callback) { callback({status: "succeeded", value: "Secret subject"}); }},
                      body: {
                        getAsync(format, options, callback) {
                          callback({status: "succeeded", value: "Secret body"});
                        }
                      },
                      to: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: [{emailAddress: "person@example.com"}]});
                        }
                      },
                      cc: {getAsync(callback) { callback({status: "succeeded", value: []}); }},
                      bcc: {getAsync(callback) { callback({status: "succeeded", value: []}); }},
                      getAttachmentsAsync(callback) {
                        callback({status: "succeeded", value: []});
                      }
                    }
                  }
                }
              },
              fetch: async () => {
                throw new TypeError("network down");
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "launchevent.js"});
            (async () => {
              const result = await new Promise((resolve) => context.__handler({completed: resolve}));
              assert.strictEqual(result.allowEvent, false);
              assert.match(result.errorMessage, /local review is unavailable/);
              assert.deepStrictEqual(telemetry.map((event) => event.event_name), [
                "outlook_review_started",
                "outlook_backend_failure",
                "outlook_user_blocked"
              ]);
              assert.strictEqual(telemetry[1].details.error_type, "TypeError");
              assert.strictEqual(telemetry[2].details.mode, "hard_block");
              const serializedTelemetry = JSON.stringify(telemetry);
              assert.ok(!serializedTelemetry.includes("Secret subject"));
              assert.ok(!serializedTelemetry.includes("Secret body"));
              assert.ok(!serializedTelemetry.includes("person@example.com"));
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_outlook_launch_event_does_not_store_or_log_message_body(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const secret = "DO_NOT_STORE_BODY_S1234567D";
            const storageWrites = [];
            const logs = [];
            const telemetry = [];
            const requests = [];
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              junasTelemetrySink: (event) => telemetry.push(event),
              console: {
                log: (...args) => logs.push(args),
                info: (...args) => logs.push(args),
                warn: (...args) => logs.push(args),
                error: (...args) => logs.push(args),
                debug: (...args) => logs.push(args)
              },
              localStorage: {
                getItem: () => "",
                setItem: (key, value) => storageWrites.push({store: "localStorage", key, value})
              },
              OfficeRuntime: {
                storage: {
                  getItem: async () => "",
                  setItem: async (key, value) => storageWrites.push({store: "OfficeRuntime", key, value})
                }
              },
              Office: {
                AsyncResultStatus: {Succeeded: "succeeded"},
                actions: {associate(name, fn) { context.__handler = fn; }},
                context: {
                  mailbox: {
                    item: {
                      subject: {getAsync(callback) { callback({status: "succeeded", value: "Private subject"}); }},
                      body: {
                        getAsync(format, options, callback) {
                          callback({status: "succeeded", value: secret});
                        }
                      },
                      to: {
                        getAsync(callback) {
                          callback({status: "succeeded", value: [{emailAddress: "private@example.com"}]});
                        }
                      },
                      cc: {getAsync(callback) { callback({status: "succeeded", value: []}); }},
                      bcc: {getAsync(callback) { callback({status: "succeeded", value: []}); }},
                      getAttachmentsAsync(callback) {
                        callback({status: "succeeded", value: [{name: "private.docx"}]});
                      }
                    }
                  }
                }
              },
              fetch: async (url, options) => {
                requests.push({url, body: JSON.parse(options.body)});
                return {ok: true, json: async () => ({
                  findings: [],
                  pii_score: 0,
                  mnpi_score: 0,
                  degraded_modes: [],
                  send_allowed: true,
                  policy_decision: {decision: "allow", send_allowed: true}
                })};
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "launchevent.js"});
            (async () => {
              const result = await new Promise((resolve) => context.__handler({completed: resolve}));
              assert.strictEqual(result.allowEvent, true);
              assert.ok(requests[0].body.text.includes(secret));
              assert.strictEqual(storageWrites.length, 0);
              assert.strictEqual(logs.length, 0);
              const serializedTelemetry = JSON.stringify(telemetry);
              assert.ok(!serializedTelemetry.includes(secret));
              assert.ok(!serializedTelemetry.includes("Private subject"));
              assert.ok(!serializedTelemetry.includes("private@example.com"));
              assert.ok(!serializedTelemetry.includes("private.docx"));
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )

    def test_outlook_completion_telemetry_maps_warning_approval_and_backend_failure(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const telemetry = [];
            const context = {
              localStorage: {getItem: () => ""},
              OfficeRuntime: {storage: {getItem: async () => ""}},
              junasTelemetrySink: (event) => telemetry.push(event),
              Office: {
                MailboxEnums: {SendModeOverride: {PromptUser: "promptUser"}},
                actions: {associate() {}}
              }
            };
            vm.createContext(context);
            vm.runInContext(source, context, {filename: "launchevent.js"});

            const warnResult = {
              findings: [{rule: "email_address", matched_text: "alice@example.com"}],
              degraded_modes: [],
              request_id: "req-warn",
              policy_decision: {
                decision: "warn",
                send_allowed: true,
                policy_id: "default",
                policy_version: "2026-06-14",
                recommended_actions: ["proceed_with_warning"]
              }
            };
            context.junasCompletionTelemetry(warnResult, context.junasSmartAlertCompletion(warnResult));

            const approvalResult = {
              findings: [{rule: "sg_nric_fin", matched_text: "S1234567D"}],
              degraded_modes: [],
              request_id: "req-approval",
              policy_decision: {
                decision: "approval_required",
                send_allowed: false,
                required_actions: ["request_approval"]
              }
            };
            context.junasCompletionTelemetry(approvalResult, context.junasSmartAlertCompletion(approvalResult));
            context.junasTelemetry("outlook_backend_failure", {
              backend_status: "unavailable_or_context_error",
              error_type: "TypeError",
              text: "confidential raw body"
            });

            assert.deepStrictEqual(telemetry.map((event) => event.event_name), [
              "outlook_user_proceeded_after_warning",
              "outlook_user_requested_approval",
              "outlook_user_blocked",
              "outlook_backend_failure"
            ]);
            assert.strictEqual(telemetry[0].details.decision, "warn");
            assert.strictEqual(telemetry[0].details.observed_user_action, false);
            assert.strictEqual(telemetry[1].details.decision, "approval_required");
            assert.strictEqual(telemetry[1].details.observed_user_action, false);
            assert.strictEqual(telemetry[2].details.mode, "soft_block");
            assert.strictEqual(telemetry[3].details.backend_status, "unavailable_or_context_error");
            const serializedTelemetry = JSON.stringify(telemetry);
            assert.ok(!serializedTelemetry.includes("alice@example.com"));
            assert.ok(!serializedTelemetry.includes("S1234567D"));
            assert.ok(!serializedTelemetry.includes("confidential raw body"));
            """
        )

    def test_outlook_smart_alert_message_fixtures_match_runtime(self):
        self.run_node(
            r"""
            const assert = require("assert");
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("integrations/outlook_addin/launchevent.js", "utf8");
            const fixtures = JSON.parse(fs.readFileSync("test/fixtures/outlook_smart_alert_messages.json", "utf8"));
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
            for (const [name, fixture] of Object.entries(fixtures)) {
              const completion = context.junasSmartAlertCompletion(fixture.input);
              assert.strictEqual(completion.mode, fixture.mode, name);
              assert.strictEqual(completion.options.allowEvent, fixture.allowEvent, name);
              assert.strictEqual(completion.options.errorMessage || "", fixture.errorMessage || "", name);
              assert.strictEqual(completion.options.sendModeOverride || "", fixture.sendModeOverride || "", name);
            }
            """
        )


if __name__ == "__main__":
    unittest.main()
