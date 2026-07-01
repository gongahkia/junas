const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  backendMode: "local_daemon",
  authMode: "local_token",
  operation: "review",
  interceptPaste: false,
  token: ""
};
const JUNAS_BACKEND_TIMEOUT_MS = 8000;

async function settings() {
  return chrome.storage.sync.get(DEFAULTS);
}

async function callJunas(text, requestedOperation) {
  const cfg = await settings();
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
  const payload = await callJunas(info.selectionText);
  await chrome.tabs.sendMessage(tab.id, {type: "junas-result", ...payload});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "junas-process-text") return false;
  callJunas(message.text || "", message.operation)
    .then((payload) => {
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "junas-result", ...payload});
      sendResponse({ok: true, ...payload});
    })
    .catch((error) => {
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "junas-error", error: String(error.message || error)});
      sendResponse({ok: false, error: String(error.message || error)});
    });
  return true;
});
