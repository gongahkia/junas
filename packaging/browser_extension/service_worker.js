const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  operation: "review",
  token: ""
};

async function settings() {
  return chrome.storage.sync.get(DEFAULTS);
}

async function callKaypoh(text) {
  const cfg = await settings();
  const op = cfg.operation === "pseudonymize" ? "pseudonymize" : cfg.operation === "redact" ? "redact" : "review";
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
  return response.json();
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
  const result = await callKaypoh(info.selectionText);
  await chrome.tabs.sendMessage(tab.id, {type: "kaypoh-result", result});
});
