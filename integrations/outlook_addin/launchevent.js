const JUNAS_DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
const JUNAS_DEFAULT_SEND_TIMEOUT_MS = 4000;
const JUNAS_ENDPOINT_KEY = "junas.endpoint";
const JUNAS_TOKEN_KEY = "junas.localToken";
const JUNAS_SEND_TIMEOUT_KEY = "junas.sendHookTimeoutMs";
const JUNAS_TELEMETRY_SCHEMA = "junas.outlook.telemetry.v1";
const JUNAS_TELEMETRY_KEYS = new Set([
  "attachment_count",
  "backend_status",
  "decision",
  "degraded_count",
  "error_type",
  "finding_count",
  "mode",
  "observed_user_action",
  "policy_id",
  "policy_version",
  "recipient_count",
  "recipient_domain_count",
  "recommended_actions",
  "request_id",
  "required_actions",
  "review_id",
  "send_allowed",
  "timeout_ms"
]);

function junasStored(key) {
  if (globalThis.OfficeRuntime && OfficeRuntime.storage) {
    return OfficeRuntime.storage.getItem(key).then((value) => value || "");
  }
  try {
    return Promise.resolve(localStorage.getItem(key) || "");
  } catch (error) {
    return Promise.resolve("");
  }
}

function junasStoredTimeout() {
  return junasStored(JUNAS_SEND_TIMEOUT_KEY).then((value) => {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) return JUNAS_DEFAULT_SEND_TIMEOUT_MS;
    return Math.min(8000, Math.max(1000, parsed));
  });
}

function junasTelemetryDetails(details) {
  const sanitized = {};
  for (const key of JUNAS_TELEMETRY_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(details, key)) continue;
    const value = details[key];
    if (Array.isArray(value)) sanitized[key] = value.map((item) => String(item).slice(0, 80)).sort();
    else if (typeof value === "string") sanitized[key] = value.slice(0, 120);
    else if (typeof value === "number" || typeof value === "boolean") sanitized[key] = value;
  }
  return sanitized;
}

function junasTelemetry(eventName, details) {
  const event = {
    schema_version: JUNAS_TELEMETRY_SCHEMA,
    event_name: eventName,
    surface: "outlook",
    workflow: "email_send",
    timestamp: new Date().toISOString(),
    details: junasTelemetryDetails(details || {})
  };
  if (typeof globalThis.junasTelemetrySink === "function") {
    try {
      globalThis.junasTelemetrySink(event);
    } catch (error) {}
  }
  if (typeof globalThis.dispatchEvent === "function" && typeof globalThis.CustomEvent === "function") {
    try {
      globalThis.dispatchEvent(new CustomEvent("junas:telemetry", {detail: event}));
    } catch (error) {}
  }
  return event;
}

function junasBodyText(event) {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item.body.getAsync("text", {asyncContext: event}, (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

function junasGetAsync(accessor, fallback) {
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

function junasSubjectText() {
  return junasGetAsync(Office.context.mailbox.item.subject, "");
}

function junasRecipientDomains(recipients) {
  const domains = [];
  for (const recipient of recipients) {
    const email = String(recipient?.emailAddress || recipient?.email || "").trim().toLowerCase();
    const at = email.lastIndexOf("@");
    if (at > 0 && at < email.length - 1) domains.push(email.slice(at + 1).replace(/\.$/, ""));
  }
  return [...new Set(domains)].sort();
}

function junasTelemetryFromResult(result) {
  const policy = result.policy_decision || {};
  const required = Array.isArray(policy.required_actions) ? policy.required_actions : [];
  const recommended = Array.isArray(policy.recommended_actions) ? policy.recommended_actions : [];
  return {
    decision: policy.decision || "",
    send_allowed: typeof policy.send_allowed === "boolean" ? policy.send_allowed : result.send_allowed !== false,
    review_id: policy.review_id || result.review_id || result.request_id || "",
    request_id: result.request_id || "",
    policy_id: policy.policy_id || "",
    policy_version: policy.policy_version || "",
    finding_count: Array.isArray(result.findings) ? result.findings.length : 0,
    degraded_count: Array.isArray(result.degraded_modes) ? result.degraded_modes.length : 0,
    required_actions: required,
    recommended_actions: recommended
  };
}

function junasAllRecipients() {
  const item = Office.context.mailbox.item;
  return Promise.all([
    junasGetAsync(item.to, []),
    junasGetAsync(item.cc, []),
    junasGetAsync(item.bcc, [])
  ]).then((groups) => [].concat(...groups).filter(Boolean));
}

function junasAttachments() {
  const item = Office.context.mailbox.item;
  if (!item.getAttachmentsAsync) return Promise.resolve([]);
  return new Promise((resolve) => {
    item.getAttachmentsAsync((result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded || !Array.isArray(result.value)) resolve([]);
      else resolve(result.value);
    });
  });
}

function junasMessageContext(event) {
  return Promise.all([junasBodyText(event), junasSubjectText(), junasAllRecipients(), junasAttachments()]).then(
    ([body, subject, recipients, attachments]) => ({
      body,
      subject,
      recipients,
      attachments
    })
  );
}

function junasReviewText(context) {
  const subject = String(context.subject || "").trim();
  const body = String(context.body || "").trim();
  return subject ? `Subject: ${subject}\n\n${body}` : body;
}

function junasFetchWithTimeout(url, options, timeoutMs) {
  if (!globalThis.AbortController) return fetch(url, options);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, {...options, signal: controller.signal}).finally(() => clearTimeout(timer));
}

function junasReview(endpoint, token, context, timeoutMs) {
  const headers = {"Content-Type": "application/json"};
  if (token) headers["X-Junas-Local-Token"] = token;
  const recipients = Array.isArray(context.recipients) ? context.recipients : [];
  const attachments = Array.isArray(context.attachments) ? context.attachments : [];
  return junasFetchWithTimeout(`${endpoint}/review`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text: junasReviewText(context),
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "email",
      review_profile: "strict",
      degraded_policy: "block_send",
      surface: "outlook",
      workflow: "email_send",
      requested_action: "send",
      recipient_domains: junasRecipientDomains(recipients),
      recipient_count: recipients.length,
      attachment_count: attachments.length
    })
  }, timeoutMs).then((response) => {
    if (!response.ok) throw new Error(`junas ${response.status}`);
    return response.json();
  });
}

function junasPromptUserOverride() {
  return globalThis.Office?.MailboxEnums?.SendModeOverride?.PromptUser || "promptUser";
}

function junasCompletion(mode, message) {
  if (mode === "allow") return {mode, options: {allowEvent: true}};
  const options = {
    allowEvent: false,
    errorMessage: message || "Junas review blocked this send. Open Junas Review before sending."
  };
  if (mode === "prompt_user") options.sendModeOverride = junasPromptUserOverride();
  return {mode, options};
}

function junasSmartAlertCompletion(result) {
  const policy = result.policy_decision || {};
  const decision = policy.decision || "";
  const required = Array.isArray(policy.required_actions) ? policy.required_actions : [];
  const recommended = Array.isArray(policy.recommended_actions) ? policy.recommended_actions : [];
  const degraded = Array.isArray(result.degraded_modes) ? result.degraded_modes.length : 0;
  const findings = Array.isArray(result.findings) ? result.findings.length : 0;
  const pii = Number(result.pii_score || 0);
  const mnpi = Number(result.mnpi_score || 0);
  if (degraded > 0) {
    return junasCompletion("hard_block", "Junas could not fully inspect this message. Open Junas Review before sending.");
  }
  if (decision === "allow" || (!decision && result.send_allowed !== false && findings === 0 && pii < 0.5 && mnpi < 0.5)) {
    return junasCompletion("allow");
  }
  if (decision === "warn" || recommended.includes("proceed_with_warning")) {
    return junasCompletion("prompt_user", "Junas found review warnings. Send anyway only if this matches policy.");
  }
  if (decision === "approval_required" || required.includes("request_approval")) {
    return junasCompletion("soft_block", "Junas requires reviewer approval before sending. Open Junas Review.");
  }
  if (decision === "rewrite_required" || required.includes("safe_rewrite") || required.includes("redact_pii")) {
    return junasCompletion("soft_block", "Junas requires safe rewrite or redaction before sending. Open Junas Review.");
  }
  if (decision === "block" || policy.send_allowed === false || result.send_allowed === false) {
    return junasCompletion("hard_block", "Junas policy blocked this send. Open Junas Review.");
  }
  return junasCompletion("soft_block", "Junas found possible PII/MNPI. Open Junas Review before sending.");
}

function junasCompletionTelemetry(result, completion) {
  const summary = {...junasTelemetryFromResult(result), mode: completion.mode};
  const policy = result.policy_decision || {};
  const required = Array.isArray(policy.required_actions) ? policy.required_actions : [];
  if (completion.mode === "prompt_user") {
    junasTelemetry("outlook_user_proceeded_after_warning", {...summary, observed_user_action: false});
    return;
  }
  if (policy.decision === "approval_required" || required.includes("request_approval")) {
    junasTelemetry("outlook_user_requested_approval", {...summary, observed_user_action: false});
  }
  if (completion.options && completion.options.allowEvent === false) {
    junasTelemetry("outlook_user_blocked", summary);
  }
}

function junasComplete(event, completion) {
  event.completed(completion.options);
}

function onMessageSendHandler(event) {
  Promise.all([junasStored(JUNAS_ENDPOINT_KEY), junasStored(JUNAS_TOKEN_KEY), junasStoredTimeout()])
    .then(([endpoint, token, timeoutMs]) => {
      const targetEndpoint = endpoint || JUNAS_DEFAULT_ENDPOINT;
      return junasMessageContext(event).then((context) => {
        const recipients = Array.isArray(context.recipients) ? context.recipients : [];
        const attachments = Array.isArray(context.attachments) ? context.attachments : [];
        junasTelemetry("outlook_review_started", {
          attachment_count: attachments.length,
          recipient_count: recipients.length,
          recipient_domain_count: junasRecipientDomains(recipients).length,
          timeout_ms: timeoutMs
        });
        return junasReview(targetEndpoint, token, context, timeoutMs);
      });
    })
    .then((result) => {
      junasTelemetry("outlook_policy_decision_received", junasTelemetryFromResult(result));
      const completion = junasSmartAlertCompletion(result);
      junasCompletionTelemetry(result, completion);
      junasComplete(event, completion);
    })
    .catch((error) => {
      junasTelemetry("outlook_backend_failure", {
        backend_status: "unavailable_or_context_error",
        error_type: error && error.name ? error.name : "Error"
      });
      const completion = junasCompletion("hard_block", "Junas local review is unavailable. Check pairing before sending.");
      junasTelemetry("outlook_user_blocked", {
        backend_status: "unavailable_or_context_error",
        mode: completion.mode
      });
      junasComplete(event, completion);
    });
}

if (globalThis.Office && Office.actions) {
  Office.actions.associate("onMessageSendHandler", onMessageSendHandler);
}
