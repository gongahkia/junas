const analyzeInput = document.getElementById('analyze-input');
const entityInput = document.getElementById('entity-input');
const classifyBtn = document.getElementById('classify-btn');
const resultsDisplay = document.getElementById('results-display');
const connectionText = document.getElementById('connection-text');
const statusDot = document.querySelector('.status-dot');

const API_BASE = 'http://localhost:8000';

mermaid.initialize({ startOnLoad: false, theme: 'default' });

async function checkHealth() {
    try {
        const resp = await fetch(`${API_BASE}/ready`);
        const data = await resp.json();
        if (data.ready === true) {
            statusDot.style.backgroundColor = '#10b981';
            statusDot.style.boxShadow = '0 0 8px #10b981';
            if (connectionText) {
                connectionText.textContent = 'Backend at port 8000: READY';
                connectionText.style.color = '#10b981';
            }
        } else {
            statusDot.style.backgroundColor = '#f59e0b';
            statusDot.style.boxShadow = '0 0 8px #f59e0b';
            if (connectionText) {
                const missing = Array.isArray(data.missing_required_layers) && data.missing_required_layers.length
                    ? ` (missing: ${data.missing_required_layers.join(', ')})`
                    : '';
                connectionText.textContent = `Backend at port 8000: DEGRADED${missing}`;
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
    if (data.lexicon && (data.lexicon.flagged || data.lexicon.total_score > 0)) {
        if (data.lexicon.high_risk_short_circuit) {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--high-red); font-weight: 600;">SHORT-CIRCUIT (Score: ${data.lexicon.total_score})</span></div>`;
        } else if (data.lexicon.flagged) {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--high-red); font-weight: 600;">FLAGGED (Score: ${data.lexicon.total_score})</span></div>`;
        } else {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--safe-green); font-weight: 600;">INFO HIT (Score: ${data.lexicon.total_score})</span></div>`;
        }
        data.lexicon.hits.forEach(hit => {
            html += `<div style="font-size: 0.75rem; color: #555; margin-left: 12px; margin-top: -8px; margin-bottom: 8px;">&bull; Match: "${hit.matched_text}" (${hit.rule}) - Score: ${hit.score}</div>`;
        });
    } else {
        html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--safe-green);">CLEAN (Score: 0)</span></div>`;
    }

    // Model 1
    if (data.model1) {
        html += `<div class="detail-item"><span>NLP Model 1 (Public/Private):</span> <span>${(data.model1.confidence * 100).toFixed(1)}% ${data.model1.label}</span></div>`;
    }

    // Model 2
    if (data.model2) {
        html += `<div class="detail-item"><span>NLP Model 2 (Severity):</span> <span>${(data.model2.confidence * 100).toFixed(1)}% ${data.model2.label.replace('_', ' ')}</span></div>`;
    }

    // Mosaic
    if (data.mosaic) {
        if (data.mosaic.escalated) {
            html += `<div class="detail-item"><span>Mosaic Aggregation:</span> <span style="color: var(--high-red); font-weight: 600;">ESCALATED (${data.mosaic.count} recent hits)</span></div>`;
        } else {
            html += `<div class="detail-item"><span>Mosaic Aggregation:</span> <span style="color: var(--low-yellow);">TRACKED (${data.mosaic.count} recent hits)</span></div>`;
        }
    }

    // Regression
    if (data.regression) {
        html += `<div class="detail-item"><span>Regression (Final Score):</span> <span>${data.regression.risk_score.toFixed(3)}</span></div>`;
        if (data.regression.reasoning) {
            html += `<div style="font-size: 0.75rem; color: #555; margin-left: 12px; margin-top: -8px; margin-bottom: 8px;">&bull; ${data.regression.reasoning}</div>`;
        }
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
    classDef yellow fill:#fef08a,stroke:#ca8a04,color:#ca8a04;
    classDef gray fill:#f3f4f6,stroke:#9ca3af,color:#6b7280,stroke-dasharray: 5 5;

    In[Ingestion] --> L1[1. Lexicon Check]
    class In green;
`;

    if (responseData.lexicon && responseData.lexicon.high_risk_short_circuit) {
        mermaidDef += `    class L1 red;\n`;
        mermaidDef += `    L1 -.-> Reg[6. Regression]\n`;
        if (responseData.regression) {
            mermaidDef += `    class Reg red;\n`;
            mermaidDef += `    Reg -.-> Out[Final Output]\n`;
            mermaidDef += `    class Out red;\n`;
        } else {
            mermaidDef += `    class Reg gray;\n`;
            mermaidDef += `    Reg -.-> Out[Final Output]\n`;
            mermaidDef += `    class Out red;\n`;
        }
    } else {
        if (responseData.lexicon && responseData.lexicon.flagged) {
            mermaidDef += `    class L1 red;\n`;
        } else {
            mermaidDef += `    class L1 green;\n`;
        }

        mermaidDef += `    L1 --> L2[2. Embeddings Generation]\n`;
        mermaidDef += `    class L2 green;\n`;

        mermaidDef += `    L2 --> L3[3. Clustering]\n`;
        if (responseData.clustering) {
            mermaidDef += `    class L3 green;\n`;
        } else {
            mermaidDef += `    class L3 gray;\n`;
        }

        mermaidDef += `    L2 --> L4[4. Classification Model 1]\n`;

        let pathFromModel1 = "L4";

        if (responseData.model1) {
            if (responseData.model1.label === "safe") {
                mermaidDef += `    class L4 green;\n`;
            } else {
                mermaidDef += `    class L4 red;\n`;
                mermaidDef += `    L4 --> L4b[4b. Classification Model 2]\n`;
                if (responseData.model2) {
                    if (responseData.model2.label === "high_risk") {
                        mermaidDef += `    class L4b red;\n`;
                    } else {
                        mermaidDef += `    class L4b green;\n`;
                    }
                } else {
                    mermaidDef += `    class L4b gray;\n`;
                }
                pathFromModel1 = "L4b";
            }
        } else {
            mermaidDef += `    class L4 gray;\n`;
        }

        mermaidDef += `    L3 -.-> L5[5. Mosaic Aggregation]\n`;
        mermaidDef += `    ${pathFromModel1} -.-> L5\n`;

        if (responseData.mosaic) {
            mermaidDef += `    class L5 ${responseData.mosaic.escalated ? "red" : "yellow"};\n`;
        } else {
            mermaidDef += `    class L5 gray;\n`;
        }

        mermaidDef += `    L5 -.-> Reg[6. Regression]\n`;

        if (responseData.regression) {
            let regColor = responseData.regression.risk_score > 0.7 ? "red" : (responseData.regression.risk_score > 0.4 ? "yellow" : "green");
            if (responseData.classification === "HIGH_RISK") regColor = "red";

            mermaidDef += `    class Reg ${regColor};\n`;
            mermaidDef += `    Reg -.-> Out[Final Output];\n`;

            let outColor = responseData.classification === "HIGH_RISK" ? "red" : (responseData.classification === "LOW_RISK" ? "yellow" : "green");
            mermaidDef += `    class Out ${outColor};\n`;
        } else {
            mermaidDef += `    class Reg gray;\n`;
            mermaidDef += `    Reg -.-> Out[Final Output];\n`;
            mermaidDef += `    class Out default;\n`;
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

function updateDebugView(reqBody, responseData) {
    const curl = `curl -X POST "${API_BASE}/classify" \\
     -H "Content-Type: application/json" \\
     -d '${JSON.stringify(reqBody).replace(/'/g, "'\\''")}'`;

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

    const entity_id = entityInput ? entityInput.value.trim() : "";

    classifyBtn.disabled = true;
    classifyBtn.textContent = 'Analyzing...';

    const reqBody = { text };
    if (entity_id) {
        reqBody.entity_id = entity_id;
    }

    try {
        const response = await fetch(`${API_BASE}/classify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        updateResults(data);
        updateDebugView(reqBody, data);
    } catch (err) {
        resultsDisplay.classList.remove('hidden');
        resultsDisplay.innerHTML = `<div style="color: var(--high-red);">Error: ${err.message}. Check if backend is running.</div>`;
    } finally {
        classifyBtn.disabled = false;
        classifyBtn.textContent = 'Classify Text';
    }
}

classifyBtn.addEventListener('click', handleClassify);
