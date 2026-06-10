const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  operation: "review",
  interceptPaste: false,
  token: ""
};
let currentSettings = {...DEFAULTS};

chrome.storage.sync.get(DEFAULTS).then((cfg) => {
  currentSettings = cfg;
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "sync") return;
  for (const [key, change] of Object.entries(changes)) {
    currentSettings[key] = change.newValue;
  }
});

function showPanel(text) {
  const prior = document.getElementById("kaypoh-review-result");
  if (prior) prior.remove();
  const panel = document.createElement("div");
  panel.id = "kaypoh-review-result";
  panel.style.cssText = [
    "position:fixed",
    "right:16px",
    "bottom:16px",
    "z-index:2147483647",
    "max-width:360px",
    "padding:12px",
    "border:1px solid #222",
    "background:#fff",
    "color:#111",
    "font:13px system-ui,sans-serif",
    "box-shadow:0 8px 24px rgba(0,0,0,.2)"
  ].join(";");
  panel.textContent = text;
  document.documentElement.appendChild(panel);
  setTimeout(() => panel.remove(), 9000);
}

function isEditable(element) {
  if (!element) return false;
  const tag = element.tagName ? element.tagName.toLowerCase() : "";
  if (tag === "textarea") return true;
  if (tag === "input") return ["", "text", "search", "url", "email"].includes((element.type || "").toLowerCase());
  return element.isContentEditable === true;
}

function captureInsertionPoint(element) {
  if (element && typeof element.setRangeText === "function") {
    const start = element.selectionStart ?? element.value.length;
    const end = element.selectionEnd ?? start;
    return {start, end};
  }
  const selection = window.getSelection();
  if (selection && selection.rangeCount > 0) return {range: selection.getRangeAt(0).cloneRange()};
  return {};
}

function insertText(element, text, insertionPoint) {
  if (element && typeof element.setRangeText === "function") {
    const start = insertionPoint?.start ?? element.selectionStart ?? element.value.length;
    const end = insertionPoint?.end ?? element.selectionEnd ?? start;
    element.setRangeText(text, start, end, "end");
    element.dispatchEvent(new InputEvent("input", {bubbles: true, inputType: "insertText", data: text}));
    return;
  }
  if (insertionPoint?.range) {
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(insertionPoint.range);
  }
  document.execCommand("insertText", false, text);
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "kaypoh-error") {
    showPanel(`Kaypoh: ${message.error}`);
    return;
  }
  if (message.type !== "kaypoh-result") return;
  const findings = Array.isArray(message.result.findings) ? message.result.findings.length : 0;
  const pii = message.result.pii_score ?? 0;
  const mnpi = message.result.mnpi_score ?? 0;
  const action = message.replacementText ? `${message.operation} applied` : "review complete";
  showPanel(`Kaypoh: ${action}; ${findings} findings; PII ${pii}; MNPI ${mnpi}`);
});

document.addEventListener("paste", async (event) => {
  const target = event.target;
  if (!isEditable(target)) return;
  const cfg = currentSettings;
  if (!cfg.interceptPaste) return;
  const text = event.clipboardData?.getData("text/plain") || "";
  if (!text.trim()) return;
  if (cfg.operation === "review") {
    chrome.runtime.sendMessage({type: "kaypoh-process-text", text});
    return;
  }
  const insertionPoint = captureInsertionPoint(target);
  event.preventDefault();
  const response = await chrome.runtime.sendMessage({type: "kaypoh-process-text", text});
  if (response?.ok && response.replacementText) {
    insertText(target, response.replacementText, insertionPoint);
    return;
  }
  insertText(target, text, insertionPoint);
  showPanel(`Kaypoh: ${response?.error || "rewrite unavailable"}`);
});
