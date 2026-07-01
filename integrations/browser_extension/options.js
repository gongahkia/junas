const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  backendMode: "local_daemon",
  authMode: "local_token",
  token: "",
  operation: "review",
  interceptPaste: false,
  reviewBeforeSubmit: false,
  allowedInspectionHosts: "chatgpt.com,claude.ai,gemini.google.com",
  blockedInspectionHosts: ""
};
let pendingPairing = null;

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  endpoint.value = cfg.endpoint;
  backendMode.value = cfg.backendMode;
  authMode.value = cfg.authMode;
  token.value = cfg.token;
  operation.value = cfg.operation;
  interceptPaste.checked = Boolean(cfg.interceptPaste);
  reviewBeforeSubmit.checked = Boolean(cfg.reviewBeforeSubmit);
  allowedInspectionHosts.value = cfg.allowedInspectionHosts || "";
  blockedInspectionHosts.value = cfg.blockedInspectionHosts || "";
}

save.addEventListener("click", async () => {
  await chrome.storage.sync.set({
    endpoint: endpoint.value.trim() || DEFAULTS.endpoint,
    backendMode: backendMode.value,
    authMode: authMode.value,
    token: token.value.trim(),
    operation: operation.value,
    interceptPaste: interceptPaste.checked,
    reviewBeforeSubmit: reviewBeforeSubmit.checked,
    allowedInspectionHosts: allowedInspectionHosts.value.trim(),
    blockedInspectionHosts: blockedInspectionHosts.value.trim()
  });
});

function authHeaders() {
  const headers = {"Content-Type": "application/json"};
  const value = token.value.trim();
  if (value && authMode.value === "bearer_token") headers.Authorization = `Bearer ${value}`;
  else if (value && authMode.value !== "none") headers["X-Junas-Local-Token"] = value;
  return headers;
}

function healthLabel(kind, detail) {
  return detail ? `${kind}: ${detail}` : kind;
}

async function checkConnectionHealth() {
  const base = endpoint.value.trim() || DEFAULTS.endpoint;
  const headers = authHeaders();
  try {
    const ready = await fetch(`${base}/ready`, {headers});
    if (ready.status === 401 || ready.status === 403) return healthLabel("auth failed", `${ready.status}`);
    if (!ready.ok) throw new Error(`ready ${ready.status}`);
    const review = await fetch(`${base}/review`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        text: "Junas browser extension connection check.",
        source_jurisdiction: "SG",
        destination_jurisdiction: "SG",
        document_type: "generic",
        review_profile: "strict",
        degraded_policy: "warn",
        surface: "browser_genai",
        workflow: "connection_check"
      })
    });
    if (review.status === 401 || review.status === 403) return healthLabel("auth failed", `${review.status}`);
    if (!review.ok) throw new Error(`review ${review.status}`);
    const payload = await review.json();
    const policy = payload.policy_decision || {};
    if (policy.send_allowed === false || payload.send_allowed === false) return "policy blocked";
    return "server healthy";
  } catch (error) {
    if (backendMode.value === "local_daemon") return "local daemon unavailable";
    return healthLabel("server unavailable", String(error.message || error));
  }
}

checkConnection.addEventListener("click", async () => {
  healthStatus.textContent = "checking";
  healthStatus.textContent = await checkConnectionHealth();
});

async function pair(path, body) {
  const response = await fetch(`${endpoint.value.trim() || DEFAULTS.endpoint}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `junas ${response.status}`);
  return payload;
}

startPairing.addEventListener("click", async () => {
  try {
    pendingPairing = await pair("/local/pairing/start", {client_name: "Junas browser extension"});
    pairingStatus.textContent = `Pairing code: ${pendingPairing.pairing_code}\nApprove it in Junas desktop, then complete pairing.`;
  } catch (error) {
    pairingStatus.textContent = String(error);
  }
});

completePairing.addEventListener("click", async () => {
  if (!pendingPairing) {
    pairingStatus.textContent = "Start pairing first";
    return;
  }
  try {
    const result = await pair("/local/pairing/claim", {
      pairing_id: pendingPairing.pairing_id,
      pairing_code: pendingPairing.pairing_code
    });
    if (!result.approved) {
      pairingStatus.textContent = "Pairing pending";
      return;
    }
    token.value = result.client_token;
    backendMode.value = "local_daemon";
    authMode.value = "local_token";
    await chrome.storage.sync.set({
      backendMode: "local_daemon",
      authMode: "local_token",
      token: result.client_token
    });
    pendingPairing = null;
    pairingStatus.textContent = `Paired until ${new Date(result.expires_at * 1000).toISOString()}`;
  } catch (error) {
    pairingStatus.textContent = String(error);
  }
});

load();
