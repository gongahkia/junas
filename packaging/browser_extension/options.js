const DEFAULTS = {endpoint: "http://127.0.0.1:8765", token: "", operation: "review", interceptPaste: false};

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

load();
