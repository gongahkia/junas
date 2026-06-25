const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  token: "",
  sendHookTimeoutMs: "4000"
};
const STORAGE_KEYS = {
  endpoint: "junas.endpoint",
  token: "junas.localToken",
  sendHookTimeoutMs: "junas.sendHookTimeoutMs"
};
let currentConfig = {...DEFAULTS};
let pendingPairing = null;

async function getStored(key) {
  if (globalThis.OfficeRuntime?.storage) return (await OfficeRuntime.storage.getItem(key)) || "";
  return localStorage.getItem(key) || "";
}

async function setStored(key, value) {
  if (globalThis.OfficeRuntime?.storage) {
    await OfficeRuntime.storage.setItem(key, value);
    return;
  }
  localStorage.setItem(key, value);
}

async function loadConfig() {
  currentConfig = {
    endpoint: (await getStored(STORAGE_KEYS.endpoint)) || DEFAULTS.endpoint,
    token: (await getStored(STORAGE_KEYS.token)) || "",
    sendHookTimeoutMs: (await getStored(STORAGE_KEYS.sendHookTimeoutMs)) || DEFAULTS.sendHookTimeoutMs
  };
  endpoint.value = currentConfig.endpoint;
  token.value = currentConfig.token;
  sendHookTimeoutMs.value = currentConfig.sendHookTimeoutMs;
}

async function saveConfig() {
  const timeoutMs = Number.parseInt(sendHookTimeoutMs.value, 10);
  currentConfig = {
    endpoint: endpoint.value.trim() || DEFAULTS.endpoint,
    token: token.value.trim(),
    sendHookTimeoutMs: String(Math.min(8000, Math.max(1000, Number.isFinite(timeoutMs) ? timeoutMs : 4000)))
  };
  await setStored(STORAGE_KEYS.endpoint, currentConfig.endpoint);
  await setStored(STORAGE_KEYS.token, currentConfig.token);
  await setStored(STORAGE_KEYS.sendHookTimeoutMs, currentConfig.sendHookTimeoutMs);
  sendHookTimeoutMs.value = currentConfig.sendHookTimeoutMs;
  output.textContent = "settings saved";
}

function bodyText() {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item.body.getAsync("text", (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

async function junas(path, text) {
  const headers = {"Content-Type": "application/json"};
  if (currentConfig.token) headers["X-Junas-Local-Token"] = currentConfig.token;
  const response = await fetch(`${currentConfig.endpoint}/${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "email",
      review_profile: "strict",
      degraded_policy: "warn"
    })
  });
  if (!response.ok) throw new Error(`junas ${response.status}`);
  return response.json();
}

async function pairingStatus() {
  output.textContent = "checking";
  try {
    currentConfig.endpoint = endpoint.value.trim() || DEFAULTS.endpoint;
    const response = await fetch(`${currentConfig.endpoint}/local/pairing/status`);
    if (!response.ok) throw new Error(`junas ${response.status}`);
    const result = await response.json();
    output.textContent = JSON.stringify({
      acl_enabled: result.acl_enabled,
      token_provisioned: result.token_provisioned,
      socket_enabled: result.socket_enabled,
      token_error: result.token_error || ""
    }, null, 2);
  } catch (error) {
    output.textContent = String(error);
  }
}

async function pairingCall(path, body) {
  currentConfig.endpoint = endpoint.value.trim() || DEFAULTS.endpoint;
  const response = await fetch(`${currentConfig.endpoint}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `junas ${response.status}`);
  return payload;
}

async function startLocalPairing() {
  output.textContent = "starting pairing";
  try {
    pendingPairing = await pairingCall("/local/pairing/start", {client_name: "Junas Outlook add-in"});
    output.textContent = `Pairing code: ${pendingPairing.pairing_code}\nApprove it in Junas desktop, then complete pairing.`;
  } catch (error) {
    output.textContent = String(error);
  }
}

async function completeLocalPairing() {
  if (!pendingPairing) {
    output.textContent = "Start pairing first";
    return;
  }
  try {
    const result = await pairingCall("/local/pairing/claim", {
      pairing_id: pendingPairing.pairing_id,
      pairing_code: pendingPairing.pairing_code
    });
    if (!result.approved) {
      output.textContent = "Pairing pending";
      return;
    }
    token.value = result.client_token;
    currentConfig.token = result.client_token;
    await setStored(STORAGE_KEYS.token, result.client_token);
    pendingPairing = null;
    output.textContent = `Paired until ${new Date(result.expires_at * 1000).toISOString()}`;
  } catch (error) {
    output.textContent = String(error);
  }
}

async function run(path) {
  output.textContent = "reviewing";
  try {
    const result = await junas(path, await bodyText());
    output.textContent = JSON.stringify({
      pii_score: result.pii_score,
      mnpi_score: result.mnpi_score,
      findings: Array.isArray(result.findings) ? result.findings.length : 0,
      degraded_modes: Array.isArray(result.degraded_modes) ? result.degraded_modes.length : 0,
      send_allowed: result.send_allowed !== false,
      privacy_operation: result.privacy_operation || ""
    }, null, 2);
  } catch (error) {
    output.textContent = String(error);
  }
}

Office.onReady(() => {
  loadConfig();
  saveSettings.onclick = () => saveConfig();
  checkPairing.onclick = () => pairingStatus();
  startPairing.onclick = () => startLocalPairing();
  completePairing.onclick = () => completeLocalPairing();
  review.onclick = () => run("review");
  redact.onclick = () => run("redact");
});
