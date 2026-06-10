const ENDPOINT = "http://127.0.0.1:8765";

function bodyText() {
  return new Promise((resolve, reject) => {
    Office.context.mailbox.item.body.getAsync("text", (result) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) reject(result.error);
      else resolve(result.value || "");
    });
  });
}

async function kaypoh(path, text) {
  const response = await fetch(`${ENDPOINT}/${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
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
  review.onclick = () => run("review");
  redact.onclick = () => run("redact");
});
