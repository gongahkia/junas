const KAYPOH_DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
const KAYPOH_DEFAULT_SEND_TIMEOUT_MS = 4000;
const KAYPOH_ENDPOINT_KEY = "kaypoh.endpoint";
const KAYPOH_TOKEN_KEY = "kaypoh.localToken";
const KAYPOH_SEND_TIMEOUT_KEY = "kaypoh.sendHookTimeoutMs";

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

function kaypohStoredTimeout() {
  return kaypohStored(KAYPOH_SEND_TIMEOUT_KEY).then((value) => {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) return KAYPOH_DEFAULT_SEND_TIMEOUT_MS;
    return Math.min(8000, Math.max(1000, parsed));
  });
}

function kaypohBodyText(event) {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item.body.getAsync("text", {asyncContext: event}, (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

function kaypohGetAsync(accessor, fallback) {
  return new Promise((resolve) => {
    if (!accessor || typeof accessor.getAsync !== "function") {
      resolve(fallback);
      return;
    }
    accessor.getAsync((result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) resolve(fallback);
      else resolve(result.value || fallback);
    });
  });
}

function kaypohSubjectText() {
  return kaypohGetAsync(Office.context.mailbox.item.subject, "");
}

function kaypohRecipientDomains(recipients) {
  const domains = [];
  for (const recipient of recipients) {
    const email = String(recipient?.emailAddress || recipient?.email || "").trim().toLowerCase();
    const at = email.lastIndexOf("@");
    if (at > 0 && at < email.length - 1) domains.push(email.slice(at + 1).replace(/\.$/, ""));
  }
  return [...new Set(domains)].sort();
}

function kaypohAllRecipients() {
  const item = Office.context.mailbox.item;
  return Promise.all([
    kaypohGetAsync(item.to, []),
    kaypohGetAsync(item.cc, []),
    kaypohGetAsync(item.bcc, [])
  ]).then((groups) => [].concat(...groups).filter(Boolean));
}

function kaypohAttachments() {
  const item = Office.context.mailbox.item;
  if (!item.getAttachmentsAsync) return Promise.resolve([]);
  return new Promise((resolve) => {
    item.getAttachmentsAsync((result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded || !Array.isArray(result.value)) resolve([]);
      else resolve(result.value);
    });
  });
}

function kaypohMessageContext(event) {
  return Promise.all([kaypohBodyText(event), kaypohSubjectText(), kaypohAllRecipients(), kaypohAttachments()]).then(
    ([body, subject, recipients, attachments]) => ({
      body,
      subject,
      recipients,
      attachments
    })
  );
}

function kaypohReviewText(context) {
  const subject = String(context.subject || "").trim();
  const body = String(context.body || "").trim();
  return subject ? `Subject: ${subject}\n\n${body}` : body;
}

function kaypohFetchWithTimeout(url, options, timeoutMs) {
  if (!globalThis.AbortController) return fetch(url, options);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, {...options, signal: controller.signal}).finally(() => clearTimeout(timer));
}

function kaypohReview(endpoint, token, context, timeoutMs) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers["X-Kaypoh-Local-Token"] = token;
  const recipients = Array.isArray(context.recipients) ? context.recipients : [];
  const attachments = Array.isArray(context.attachments) ? context.attachments : [];
  return kaypohFetchWithTimeout(`${endpoint}/review`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text: kaypohReviewText(context),
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "email",
      review_profile: "strict",
      degraded_policy: "block_send",
      surface: "outlook",
      workflow: "email_send",
      requested_action: "send",
      recipient_domains: kaypohRecipientDomains(recipients),
      recipient_count: recipients.length,
      attachment_count: attachments.length
    })
  }, timeoutMs).then((response) => {
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
  Promise.all([kaypohStored(KAYPOH_ENDPOINT_KEY), kaypohStored(KAYPOH_TOKEN_KEY), kaypohStoredTimeout()])
    .then(([endpoint, token, timeoutMs]) =>
      kaypohMessageContext(event).then((context) =>
        kaypohReview(endpoint || KAYPOH_DEFAULT_ENDPOINT, token, context, timeoutMs)
      )
    )
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
