const DEFAULTS = {
  endpoint: "http://127.0.0.1:8765",
  token: ""
};
const STORAGE_KEYS = {
  endpoint: "kaypoh.endpoint",
  token: "kaypoh.localToken"
};
let currentConfig = {...DEFAULTS};

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
    token: (await getStored(STORAGE_KEYS.token)) || ""
  };
  endpoint.value = currentConfig.endpoint;
  token.value = currentConfig.token;
}

async function saveConfig() {
  currentConfig = {
    endpoint: endpoint.value.trim() || DEFAULTS.endpoint,
    token: token.value.trim()
  };
  await setStored(STORAGE_KEYS.endpoint, currentConfig.endpoint);
  await setStored(STORAGE_KEYS.token, currentConfig.token);
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

async function kaypoh(path, text) {
  const headers = {"Content-Type": "application/json"};
  if (currentConfig.token) headers["X-Kaypoh-Local-Token"] = currentConfig.token;
  const response = await fetch(`${currentConfig.endpoint}/${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "email",
      review_profile: "strict"
    })
  });
  if (!response.ok) throw new Error(`kaypoh ${response.status}`);
  return response.json();
}

async function pairingStatus() {
  output.textContent = "checking";
  try {
    currentConfig.endpoint = endpoint.value.trim() || DEFAULTS.endpoint;
    const response = await fetch(`${currentConfig.endpoint}/local/pairing/status`);
    if (!response.ok) throw new Error(`kaypoh ${response.status}`);
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

async function run(path) {
  output.textContent = "reviewing";
  try {
    const result = await kaypoh(path, await bodyText());
    output.textContent = JSON.stringify({
      pii_score: result.pii_score,
      mnpi_score: result.mnpi_score,
      findings: Array.isArray(result.findings) ? result.findings.length : 0,
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
  review.onclick = () => run("review");
  redact.onclick = () => run("redact");
});
