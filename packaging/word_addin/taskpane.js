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

function selectedText() {
  return new Promise((resolve, reject) => {
    Office.context.document.getSelectedDataAsync(Office.CoercionType.Text, (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

function bodyText() {
  return Word.run(async (context) => {
    const body = context.document.body;
    body.load("text");
    await context.sync();
    return body.text || "";
  });
}

async function kaypohReview(text) {
  const headers = {"Content-Type": "application/json"};
  if (currentConfig.token) headers["X-Kaypoh-Local-Token"] = currentConfig.token;
  const response = await fetch(`${currentConfig.endpoint}/review`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      source_jurisdiction: "SG",
      destination_jurisdiction: "SG",
      document_type: "word_document",
      review_profile: "strict"
    })
  });
  if (!response.ok) throw new Error(`kaypoh ${response.status}`);
  return response.json();
}

async function run(source) {
  output.textContent = "reviewing";
  try {
    currentConfig.endpoint = endpoint.value.trim() || DEFAULTS.endpoint;
    currentConfig.token = token.value.trim();
    const text = source === "selection" ? await selectedText() : await bodyText();
    const result = await kaypohReview(text);
    output.textContent = JSON.stringify({
      pii_score: result.pii_score,
      mnpi_score: result.mnpi_score,
      findings: Array.isArray(result.findings) ? result.findings.length : 0
    }, null, 2);
  } catch (error) {
    output.textContent = String(error);
  }
}

Office.onReady(() => {
  loadConfig();
  saveSettings.onclick = () => saveConfig();
  reviewSelection.onclick = () => run("selection");
  reviewBody.onclick = () => run("body");
});
