const KAYPOH_DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
const KAYPOH_ENDPOINT_KEY = "kaypoh.endpoint";
const KAYPOH_TOKEN_KEY = "kaypoh.localToken";

function kaypohStored(key) {
  if (globalThis.OfficeRuntime && OfficeRuntime.storage) {
    return OfficeRuntime.storage.getItem(key).then((value) => value || "");
  }
  try {
    return Promise.resolve(localStorage.getItem(key) || "");
  } catch (error) {
    return Promise.resolve("");
  }
}

function kaypohBodyText(event) {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item.body.getAsync("text", {asyncContext: event}, (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

function kaypohReview(endpoint, token, text) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers["X-Kaypoh-Local-Token"] = token;
  return fetch(`${endpoint}/review`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "email",
      review_profile: "strict",
      degraded_policy: "block_send"
    })
  }).then((response) => {
    if (!response.ok) throw new Error(`kaypoh ${response.status}`);
    return response.json();
  });
}

function kaypohComplete(event, allowed, message) {
  if (allowed) {
    event.completed({allowEvent: true});
    return;
  }
  event.completed({
    allowEvent: false,
    errorMessage: message || "Kaypoh review blocked this send. Open Kaypoh Review before sending."
  });
}

function onMessageSendHandler(event) {
  Promise.all([kaypohStored(KAYPOH_ENDPOINT_KEY), kaypohStored(KAYPOH_TOKEN_KEY)])
    .then(([endpoint, token]) => kaypohBodyText(event).then((text) => kaypohReview(endpoint || KAYPOH_DEFAULT_ENDPOINT, token, text)))
    .then((result) => {
      const findings = Array.isArray(result.findings) ? result.findings.length : 0;
      const degraded = Array.isArray(result.degraded_modes) ? result.degraded_modes.length : 0;
      const pii = Number(result.pii_score || 0);
      const mnpi = Number(result.mnpi_score || 0);
      if (result.send_allowed === false || degraded > 0) {
        kaypohComplete(event, false, "Kaypoh could not fully inspect this message. Open Kaypoh Review before sending.");
        return;
      }
      if (findings > 0 || pii >= 0.5 || mnpi >= 0.5) {
        kaypohComplete(event, false, "Kaypoh found possible PII/MNPI. Open Kaypoh Review to redact or approve before sending.");
      } else {
        kaypohComplete(event, true);
      }
    })
    .catch(() => {
      kaypohComplete(event, false, "Kaypoh local review is unavailable. Check pairing before sending.");
    });
}

if (globalThis.Office && Office.actions) {
  Office.actions.associate("onMessageSendHandler", onMessageSendHandler);
}
