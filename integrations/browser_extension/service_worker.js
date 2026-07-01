const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  backendMode: "local_daemon",
  authMode: "local_token",
  operation: "review",
  interceptPaste: false,
  allowedInspectionHosts: "chatgpt.com,claude.ai,gemini.google.com",
  blockedInspectionHosts: "",
  token: ""
};
const JUNAS_BACKEND_TIMEOUT_MS = 8000;

async function settings() {
  return chrome.storage.sync.get(DEFAULTS);
}

function hostRules(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim().toLowerCase()).filter(Boolean);
  return String(value || "").split(/[\s,]+/).map((item) => item.trim().toLowerCase()).filter(Boolean);
}

function normalizedHostFromUrl(url) {
  try {
    return new URL(url || "").hostname.toLowerCase();
  } catch (error) {
    return "";
  }
}

function hostMatchesRule(host, rule) {
  const cleanRule = rule.replace(/^[a-z*][a-z0-9+.-]*:\/\//, "").replace(/\/.*$/, "");
  if (!cleanRule) return false;
  if (cleanRule.startsWith("*.")) {
    const suffix = cleanRule.slice(2);
    return host === suffix || host.endsWith(`.${suffix}`);
  }
  return host === cleanRule;
}

function canInspectUrl(url, cfg) {
  const host = normalizedHostFromUrl(url);
  if (!host) return false;
  const blocked = hostRules(cfg?.blockedInspectionHosts);
  if (blocked.some((rule) => hostMatchesRule(host, rule))) return false;
  const allowed = hostRules(cfg?.allowedInspectionHosts);
  if (allowed.length === 0) return true;
  return allowed.some((rule) => hostMatchesRule(host, rule));
}

async function callJunas(text, requestedOperation, cfgOverride) {
  const cfg = cfgOverride || await settings();
  const selectedOperation = requestedOperation || cfg.operation;
  const op = ["review", "pseudonymize", "anonymize", "redact"].includes(selectedOperation) ? selectedOperation : "review";
  const headers = {"Content-Type": "application/json"};
  if (cfg.token && cfg.authMode === "bearer_token") headers.Authorization = `Bearer ${cfg.token}`;
  else if (cfg.token && cfg.authMode !== "none") headers["X-Junas-Local-Token"] = cfg.token;
  const body = {
    text,
    source_jurisdiction: "SG",
    destination_jurisdiction: "SG",
    document_type: "generic",
    review_profile: "strict",
    degraded_policy: "warn"
  };
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let timedOut = false;
  const timer = controller ? setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, JUNAS_BACKEND_TIMEOUT_MS) : null;
  try {
    const options = {method: "POST", headers, body: JSON.stringify(body)};
    if (controller) options.signal = controller.signal;
    const response = await fetch(`${cfg.endpoint}/${op}`, options);
    if (!response.ok) throw new Error(`junas ${response.status}`);
    const result = await response.json();
    return {operation: op, result, replacementText: replacementText(op, result)};
  } catch (error) {
    if (timedOut) throw new Error("backend_timeout");
    throw error;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function replacementText(operation, result) {
  if (operation === "pseudonymize") return result.pseudonymized_text || result.anonymized_text || "";
  if (operation === "anonymize") return result.anonymized_text || "";
  if (operation === "redact") return result.redacted_text || "";
  return "";
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "junas-review-selection",
    title: "Review selection with Junas",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "junas-review-selection" || !info.selectionText || !tab?.id) return;
  const cfg = await settings();
  if (!canInspectUrl(info.pageUrl || tab.url, cfg)) return;
  const payload = await callJunas(info.selectionText, undefined, cfg);
  await chrome.tabs.sendMessage(tab.id, {type: "junas-result", ...payload});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "junas-process-text") return false;
  settings()
    .then((cfg) => {
      if (!canInspectUrl(sender.url || sender.tab?.url, cfg)) {
        return {blocked: true};
      }
      return callJunas(message.text || "", message.operation, cfg);
    })
    .then((payload) => {
      if (payload.blocked) {
        sendResponse({ok: false, error: "inspection_host_blocked"});
        return;
      }
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "junas-result", ...payload});
      sendResponse({ok: true, ...payload});
    })
    .catch((error) => {
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "junas-error", error: String(error.message || error)});
      sendResponse({ok: false, error: String(error.message || error)});
    });
  return true;
});
