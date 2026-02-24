const analyzeInput = document.getElementById('analyze-input');
const classifyBtn = document.getElementById('classify-btn');
const resultsDisplay = document.getElementById('results-display');
const debugContent = document.getElementById('debug-content');
const statusDot = document.querySelector('.status-dot');

const API_BASE = 'http://localhost:8000';

async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/health`);
        const data = await resp.json();
        if (data.status === 'ok') {
            statusDot.style.backgroundColor = '#10b981';
            statusDot.style.boxShadow = '0 0 8px #10b981';
        } else {
            statusDot.style.backgroundColor = '#f59e0b';
            statusDot.style.boxShadow = '0 0 8px #f59e0b';
        }
    } catch (err) {
        statusDot.style.backgroundColor = '#ef4444';
        statusDot.style.boxShadow = '0 0 8px #ef4444';
    }
}

setInterval(checkHealth, 10000);
checkHealth();

function updateResults(data) {
    resultsDisplay.classList.remove('hidden');

    const classification = data.classification;
    const badgeClass = `badge-${classification.toLowerCase().replace('_', '-')}`;

    let html = `
        <div class="classification-badge ${badgeClass}">${classification}</div>
        <div style="font-size: 1.1rem; line-height: 1.4;">
            Analysis indicates this content is <strong>${classification.replace('_', ' ')}</strong>.
        </div>
        <div class="details">
    `;

    // Lexicon
    if (data.lexicon && data.lexicon.flagged) {
        html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--high-red); font-weight: 600;">FLAGGED</span></div>`;
        data.lexicon.hits.forEach(hit => {
            html += `<div style="font-size: 0.75rem; color: var(--high-red); margin-left: 12px; margin-top: -8px; margin-bottom: 8px;">&bull; Match: "${hit.matched_text}" (${hit.rule})</div>`;
        });
    } else {
        html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--safe-green);">CLEAN</span></div>`;
    }

    // Model 1
    if (data.model1) {
        html += `<div class="detail-item"><span>NLP Model 1 (Public/Private):</span> <span>${(data.model1.confidence * 100).toFixed(1)}% ${data.model1.label}</span></div>`;
    }

    // Model 2
    if (data.model2) {
        html += `<div class="detail-item"><span>NLP Model 2 (Severity):</span> <span>${(data.model2.confidence * 100).toFixed(1)}% ${data.model2.label.replace('_', ' ')}</span></div>`;
    }

    html += `</div>`;
    resultsDisplay.innerHTML = html;
}

function addDebugLog(text, responseData) {
    const logItem = document.createElement('div');
    logItem.className = 'debug-log-item';

    const curl = `curl -X POST "${API_BASE}/classify" \\
     -H "Content-Type: application/json" \\
     -d '{"text": "${text.replace(/'/g, "'\\''").replace(/"/g, '\\"')}"}'`;

    const jsonResponse = JSON.stringify(responseData, null, 2);

    logItem.innerHTML = `
        <div class="debug-section">
            <h3>cURL Request</h3>
            <pre><code class="language-bash">${curl}</code></pre>
        </div>
        <div class="debug-section">
            <h3>JSON Response</h3>
            <pre><code class="language-json">${jsonResponse}</code></pre>
        </div>
    `;

    debugContent.appendChild(logItem);

    // apply syntax highlighting
    logItem.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });

    debugContent.scrollTop = debugContent.scrollHeight;
}

async function handleClassify() {
    const text = analyzeInput.value.trim();
    if (!text) return;

    classifyBtn.disabled = true;
    classifyBtn.textContent = 'Analyzing...';

    try {
        const response = await fetch(`${API_BASE}/classify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        updateResults(data);
        addDebugLog(text, data);
    } catch (err) {
        resultsDisplay.classList.remove('hidden');
        resultsDisplay.innerHTML = `<div style="color: var(--high-red);">Error: ${err.message}. Check if backend is running.</div>`;
    } finally {
        classifyBtn.disabled = false;
        classifyBtn.textContent = 'Classify Text';
    }
}

classifyBtn.addEventListener('click', handleClassify);
