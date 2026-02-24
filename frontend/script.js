const analyzeInput = document.getElementById('analyze-input');
const classifyBtn = document.getElementById('classify-btn');
const resultsDisplay = document.getElementById('results-display');
const connectionText = document.getElementById('connection-text');
const statusDot = document.querySelector('.status-dot');

const API_BASE = 'http://localhost:8000';

mermaid.initialize({ startOnLoad: false, theme: 'default' });

async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/health`);
        const data = await resp.json();
        if (data.status === 'ok') {
            statusDot.style.backgroundColor = '#10b981';
            statusDot.style.boxShadow = '0 0 8px #10b981';
            if (connectionText) {
                connectionText.textContent = 'Backend at port 8000: UP';
                connectionText.style.color = '#10b981';
            }
        } else {
            statusDot.style.backgroundColor = '#f59e0b';
            statusDot.style.boxShadow = '0 0 8px #f59e0b';
            if (connectionText) {
                connectionText.textContent = 'Backend at port 8000: DEGRADED';
                connectionText.style.color = '#f59e0b';
            }
        }
    } catch (err) {
        statusDot.style.backgroundColor = '#ef4444';
        statusDot.style.boxShadow = '0 0 8px #ef4444';
        if (connectionText) {
            connectionText.textContent = 'Backend at port 8000: DOWN';
            connectionText.style.color = '#ef4444';
        }
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

async function renderArchitectureDiagram(responseData) {
    let mermaidDef = `
flowchart TD
    classDef default fill:#fff,stroke:#333,stroke-width:1px,color:#000;
    classDef green fill:#dcfce7,stroke:#16a34a,color:#16a34a;
    classDef red fill:#fee2e2,stroke:#dc2626,color:#dc2626;

    In[Ingestion] --> L1[1. Lexicon Check]
    L1 --> L2[2. Embeddings Generation]
    L2 --> L3[3. Clustering]
    L2 --> L4[4. Classification Model 1]
    L4 --> L5[5. Classification Model 2]
    L3 --> Reg[6. Regression]
    L5 --> Reg
    Reg --> Out[Final Output]

    class In green;
`;

    if (responseData.lexicon && responseData.lexicon.high_risk_short_circuit) {
        mermaidDef += `    class L1 red;\n`;
        mermaidDef += `    L1 -.-> Out;\n`;
        mermaidDef += `    class Out red;\n`;
    } else if (responseData.lexicon && responseData.lexicon.flagged && !responseData.model1) {
        mermaidDef += `    class L1 red;\n`;
        mermaidDef += `    L1 -.-> Out;\n`;
        mermaidDef += `    class Out red;\n`;
    } else {
        mermaidDef += `    class L1 green;\n`;
        mermaidDef += `    class L2 green;\n`;

        if (responseData.model1) {
            if (responseData.model1.label === "safe") {
                mermaidDef += `    class L4 green;\n`;
                mermaidDef += `    L4 -.-> Out;\n`;
                mermaidDef += `    class Out green;\n`;
            } else {
                mermaidDef += `    class L4 red;\n`;
                if (responseData.model2) {
                    if (responseData.model2.label === "high_risk") {
                        mermaidDef += `    class L5 red;\n`;
                        mermaidDef += `    L5 -.-> Out;\n`;
                        mermaidDef += `    class Out red;\n`;
                    } else {
                        mermaidDef += `    class L5 green;\n`;
                        mermaidDef += `    L5 -.-> Out;\n`;
                        mermaidDef += `    class Out green;\n`;
                    }
                } else {
                    mermaidDef += `    L4 -.-> Out;\n`;
                    mermaidDef += `    class Out red;\n`;
                }
            }
        }
    }

    const container = document.getElementById('architecture-diagram');
    try {
        const { svg } = await mermaid.render('mermaid-chart-' + Date.now().toString(), mermaidDef);
        container.innerHTML = svg;
    } catch (e) {
        console.error(e);
        container.innerHTML = `<span style="color:var(--high-red)">Failed to map diagram.</span>`;
    }
}

function updateDebugView(text, responseData) {
    const curl = `curl -X POST "${API_BASE}/classify" \\
     -H "Content-Type: application/json" \\
     -d '{"text": "${text.replace(/'/g, "'\\''").replace(/"/g, '\\"')}"}'`;

    const jsonResponse = JSON.stringify(responseData, null, 2);

    const curlCode = document.getElementById('curl-code');
    const jsonCode = document.getElementById('json-code');

    if (curlCode && jsonCode) {
        curlCode.textContent = curl;
        jsonCode.textContent = jsonResponse;

        // Remove existing highlighting traces
        curlCode.removeAttribute('data-highlighted');
        jsonCode.removeAttribute('data-highlighted');

        hljs.highlightElement(curlCode);
        hljs.highlightElement(jsonCode);
    }

    renderArchitectureDiagram(responseData);
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
        updateDebugView(text, data);
    } catch (err) {
        resultsDisplay.classList.remove('hidden');
        resultsDisplay.innerHTML = `<div style="color: var(--high-red);">Error: ${err.message}. Check if backend is running.</div>`;
    } finally {
        classifyBtn.disabled = false;
        classifyBtn.textContent = 'Classify Text';
    }
}

classifyBtn.addEventListener('click', handleClassify);
