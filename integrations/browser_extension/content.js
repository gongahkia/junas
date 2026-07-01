const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  operation: "review",
  interceptPaste: false,
  reviewBeforeSubmit: false,
  token: ""
};
let currentSettings = {...DEFAULTS};
let bypassNextSubmit = false;

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
  const prior = document.getElementById("junas-review-result");
  if (prior) prior.remove();
  const panel = document.createElement("div");
  panel.id = "junas-review-result";
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

function promptTarget(element) {
  const adapter = globalThis.JUNAS_BROWSER_ADAPTERS;
  const resolved = adapter?.resolvePromptTarget ? adapter.resolvePromptTarget(element, window.location) : element;
  return isEditable(resolved) ? resolved : null;
}

function submitTarget(element) {
  const adapter = globalThis.JUNAS_BROWSER_ADAPTERS;
  return adapter?.resolveSubmitTarget ? adapter.resolveSubmitTarget(element, window.location) : null;
}

function findPromptTarget() {
  const adapter = globalThis.JUNAS_BROWSER_ADAPTERS;
  const found = adapter?.findPromptComposer ? adapter.findPromptComposer(document, window.location) : null;
  return isEditable(found) ? found : null;
}

function findSubmitButton() {
  const adapter = globalThis.JUNAS_BROWSER_ADAPTERS;
  return adapter?.findSubmitButton ? adapter.findSubmitButton(document, window.location) : null;
}

function promptText(element) {
  if (!element) return "";
  if (typeof element.value === "string") return element.value;
  return element.textContent || "";
}

function reviewOutcome(result) {
  const policy = result?.policy_decision || {};
  const recommended = Array.isArray(policy.recommended_actions) ? policy.recommended_actions : [];
  const findings = Array.isArray(result?.findings) ? result.findings.length : 0;
  const degraded = Array.isArray(result?.degraded_modes) ? result.degraded_modes.length : 0;
  if (degraded > 0 || policy.send_allowed === false || result?.send_allowed === false) return "block";
  if (policy.decision === "warn" || recommended.includes("proceed_with_warning")) return "warn";
  if (policy.decision && policy.decision !== "allow") return "block";
  if (findings > 0) return "warn";
  return "allow";
}

function reportSelectorFailure(kind) {
  const subject = kind === "submit" ? "submit button" : "prompt composer";
  showPanel(`Junas: ${subject} selector unavailable; submission was not blocked because no review ran.`);
}

async function reviewBeforeSubmit(target) {
  const text = promptText(target).trim();
  if (!text) return true;
  showPanel("Junas: reviewing prompt");
  const response = await chrome.runtime.sendMessage({type: "junas-process-text", text, operation: "review"});
  if (!response?.ok) {
    showPanel(`Junas: ${response?.error || "review unavailable"}`);
    return false;
  }
  const outcome = reviewOutcome(response.result);
  if (outcome === "allow") return true;
  if (outcome === "warn") {
    return window.confirm("Junas found review warnings. Submit anyway only if this matches policy.");
  }
  showPanel("Junas: policy blocked this prompt. Review or rewrite before submitting.");
  return false;
}

async function guardPromptSubmit(event, target, submitButton) {
  const cfg = currentSettings;
  if (!cfg.reviewBeforeSubmit) return;
  if (!target) {
    reportSelectorFailure("prompt");
    return;
  }
  if (!submitButton) {
    reportSelectorFailure("submit");
    return;
  }
  if (bypassNextSubmit) {
    bypassNextSubmit = false;
    return;
  }
  event.preventDefault();
  event.stopImmediatePropagation();
  const allowed = await reviewBeforeSubmit(target);
  if (!allowed) return;
  bypassNextSubmit = true;
  submitButton.click();
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
  if (message.type === "junas-error") {
    showPanel(`Junas: ${message.error}`);
    return;
  }
  if (message.type !== "junas-result") return;
  const findings = Array.isArray(message.result.findings) ? message.result.findings.length : 0;
  const degraded = Array.isArray(message.result.degraded_modes) ? message.result.degraded_modes.length : 0;
  const pii = message.result.pii_score ?? 0;
  const mnpi = message.result.mnpi_score ?? 0;
  const action = message.replacementText ? `${message.operation} applied` : "review complete";
  const send = message.result.send_allowed === false ? "; send blocked" : "";
  const coverage = degraded ? `; ${degraded} degraded${send}` : send;
  showPanel(`Junas: ${action}; ${findings} findings; PII ${pii}; MNPI ${mnpi}${coverage}`);
});

document.addEventListener("paste", async (event) => {
  const target = promptTarget(event.target);
  if (!target) return;
  const cfg = currentSettings;
  if (!cfg.interceptPaste) return;
  const text = event.clipboardData?.getData("text/plain") || "";
  if (!text.trim()) return;
  if (cfg.operation === "review") {
    chrome.runtime.sendMessage({type: "junas-process-text", text});
    return;
  }
  const insertionPoint = captureInsertionPoint(target);
  event.preventDefault();
  const response = await chrome.runtime.sendMessage({type: "junas-process-text", text});
  if (response?.ok && response.replacementText) {
    insertText(target, response.replacementText, insertionPoint);
    return;
  }
  insertText(target, text, insertionPoint);
  showPanel(`Junas: ${response?.error || "rewrite unavailable"}`);
});

document.addEventListener("click", (event) => {
  const submitButton = submitTarget(event.target);
  if (!submitButton) return;
  return guardPromptSubmit(event, findPromptTarget(), submitButton);
}, true);

document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.shiftKey || event.metaKey || event.ctrlKey || event.altKey) return;
  const target = promptTarget(event.target);
  const submitButton = findSubmitButton();
  return guardPromptSubmit(event, target, submitButton);
}, true);
