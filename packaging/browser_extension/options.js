const DEFAULTS = {endpoint: "http://127.0.0.1:8765", token: "", operation: "review", interceptPaste: false};
let pendingPairing = null;

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  endpoint.value = cfg.endpoint;
  token.value = cfg.token;
  operation.value = cfg.operation;
  interceptPaste.checked = Boolean(cfg.interceptPaste);
}

save.addEventListener("click", async () => {
  await chrome.storage.sync.set({
    endpoint: endpoint.value.trim() || DEFAULTS.endpoint,
    token: token.value.trim(),
    operation: operation.value,
    interceptPaste: interceptPaste.checked
  });
});

async function pair(path, body) {
  const response = await fetch(`${endpoint.value.trim() || DEFAULTS.endpoint}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `kaypoh ${response.status}`);
  return payload;
}

startPairing.addEventListener("click", async () => {
  try {
    pendingPairing = await pair("/local/pairing/start", {client_name: "Kaypoh browser extension"});
    pairingStatus.textContent = `Pairing code: ${pendingPairing.pairing_code}\nApprove it in Kaypoh desktop, then complete pairing.`;
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
    await chrome.storage.sync.set({token: result.client_token});
    pendingPairing = null;
    pairingStatus.textContent = `Paired until ${new Date(result.expires_at * 1000).toISOString()}`;
  } catch (error) {
    pairingStatus.textContent = String(error);
  }
});

load();
