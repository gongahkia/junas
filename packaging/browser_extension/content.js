chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== "kaypoh-result") return;
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
  const findings = Array.isArray(message.result.findings) ? message.result.findings.length : 0;
  const pii = message.result.pii_score ?? 0;
  const mnpi = message.result.mnpi_score ?? 0;
  panel.textContent = `Kaypoh: ${findings} findings; PII ${pii}; MNPI ${mnpi}`;
  document.documentElement.appendChild(panel);
  setTimeout(() => panel.remove(), 9000);
});
