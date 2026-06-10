const DEFAULTS = {endpoint: "http://127.0.0.1:8765", token: "", operation: "review"};

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  endpoint.value = cfg.endpoint;
  token.value = cfg.token;
  operation.value = cfg.operation;
}

save.addEventListener("click", async () => {
  await chrome.storage.sync.set({
    endpoint: endpoint.value.trim() || DEFAULTS.endpoint,
    token: token.value.trim(),
    operation: operation.value
  });
});

load();
