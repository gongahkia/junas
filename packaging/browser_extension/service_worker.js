const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  operation: "review",
  interceptPaste: false,
  token: ""
};

async function settings() {
  return chrome.storage.sync.get(DEFAULTS);
}

async function callKaypoh(text) {
  const cfg = await settings();
  const op = ["review", "pseudonymize", "anonymize", "redact"].includes(cfg.operation) ? cfg.operation : "review";
  const headers = {"Content-Type": "application/json"};
  if (cfg.token) headers["X-Kaypoh-Local-Token"] = cfg.token;
  const body = {
    text,
    source_jurisdiction: "SG",
    destination_jurisdiction: "SG",
    document_type: "generic",
    review_profile: "strict"
  };
  const response = await fetch(`${cfg.endpoint}/${op}`, {method: "POST", headers, body: JSON.stringify(body)});
  if (!response.ok) throw new Error(`kaypoh ${response.status}`);
  const result = await response.json();
  return {operation: op, result, replacementText: replacementText(op, result)};
}

function replacementText(operation, result) {
  if (operation === "pseudonymize") return result.pseudonymized_text || result.anonymized_text || "";
  if (operation === "anonymize") return result.anonymized_text || "";
  if (operation === "redact") return result.redacted_text || "";
  return "";
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "kaypoh-review-selection",
    title: "Review selection with Kaypoh",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "kaypoh-review-selection" || !info.selectionText || !tab?.id) return;
  const payload = await callKaypoh(info.selectionText);
  await chrome.tabs.sendMessage(tab.id, {type: "kaypoh-result", ...payload});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "kaypoh-process-text") return false;
  callKaypoh(message.text || "")
    .then((payload) => {
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "kaypoh-result", ...payload});
      sendResponse({ok: true, ...payload});
    })
    .catch((error) => {
      if (sender.tab?.id) chrome.tabs.sendMessage(sender.tab.id, {type: "kaypoh-error", error: String(error.message || error)});
      sendResponse({ok: false, error: String(error.message || error)});
    });
  return true;
});
