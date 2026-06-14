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
      degraded_policy: "block_send",
      surface: "outlook",
      workflow: "email_send",
      requested_action: "send"
    })
  }).then((response) => {
    if (!response.ok) throw new Error(`kaypoh ${response.status}`);
    return response.json();
  });
}

function kaypohPromptUserOverride() {
  return globalThis.Office?.MailboxEnums?.SendModeOverride?.PromptUser || "promptUser";
}

function kaypohCompletion(mode, message) {
  if (mode === "allow") return {mode, options: {allowEvent: true}};
  const options = {
    allowEvent: false,
    errorMessage: message || "Kaypoh review blocked this send. Open Kaypoh Review before sending."
  };
  if (mode === "prompt_user") options.sendModeOverride = kaypohPromptUserOverride();
  return {mode, options};
}

function kaypohSmartAlertCompletion(result) {
  const policy = result.policy_decision || {};
  const decision = policy.decision || "";
  const required = Array.isArray(policy.required_actions) ? policy.required_actions : [];
  const recommended = Array.isArray(policy.recommended_actions) ? policy.recommended_actions : [];
  const degraded = Array.isArray(result.degraded_modes) ? result.degraded_modes.length : 0;
  const findings = Array.isArray(result.findings) ? result.findings.length : 0;
  const pii = Number(result.pii_score || 0);
  const mnpi = Number(result.mnpi_score || 0);
  if (degraded > 0) {
    return kaypohCompletion("hard_block", "Kaypoh could not fully inspect this message. Open Kaypoh Review before sending.");
  }
  if (decision === "allow" || (!decision && result.send_allowed !== false && findings === 0 && pii < 0.5 && mnpi < 0.5)) {
    return kaypohCompletion("allow");
  }
  if (decision === "warn" || recommended.includes("proceed_with_warning")) {
    return kaypohCompletion("prompt_user", "Kaypoh found review warnings. Send anyway only if this matches policy.");
  }
  if (decision === "approval_required" || required.includes("request_approval")) {
    return kaypohCompletion("soft_block", "Kaypoh requires reviewer approval before sending. Open Kaypoh Review.");
  }
  if (decision === "rewrite_required" || required.includes("safe_rewrite") || required.includes("redact_pii")) {
    return kaypohCompletion("soft_block", "Kaypoh requires safe rewrite or redaction before sending. Open Kaypoh Review.");
  }
  if (decision === "block" || policy.send_allowed === false || result.send_allowed === false) {
    return kaypohCompletion("hard_block", "Kaypoh policy blocked this send. Open Kaypoh Review.");
  }
  return kaypohCompletion("soft_block", "Kaypoh found possible PII/MNPI. Open Kaypoh Review before sending.");
}

function kaypohComplete(event, completion) {
  event.completed(completion.options);
}

function onMessageSendHandler(event) {
  Promise.all([kaypohStored(KAYPOH_ENDPOINT_KEY), kaypohStored(KAYPOH_TOKEN_KEY)])
    .then(([endpoint, token]) => kaypohBodyText(event).then((text) => kaypohReview(endpoint || KAYPOH_DEFAULT_ENDPOINT, token, text)))
    .then((result) => {
      kaypohComplete(event, kaypohSmartAlertCompletion(result));
    })
    .catch(() => {
      kaypohComplete(event, kaypohCompletion("hard_block", "Kaypoh local review is unavailable. Check pairing before sending."));
    });
}

if (globalThis.Office && Office.actions) {
  Office.actions.associate("onMessageSendHandler", onMessageSendHandler);
}
