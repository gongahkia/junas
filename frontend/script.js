const chatHistory = document.getElementById('chat-history');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');
const statusDot = document.querySelector('.status-dot');
const debugToggle = document.getElementById('debug-toggle');
const debugSidebar = document.getElementById('debug-sidebar');
const debugContent = document.getElementById('debug-content');

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

// Sidebar Toggle
debugToggle.addEventListener('click', () => {
    debugSidebar.classList.toggle('hidden');
});

function appendMessage(text, isUser = false, responseData = null, isFile = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    if (isUser) {
        if (isFile) {
            msgDiv.innerHTML = `<div style="display: flex; align-items: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>
                <span>${text}</span>
            </div>`;
        } else {
            msgDiv.textContent = text;
        }
    } else {
        if (responseData) {
            const classification = responseData.classification;
            const badgeClass = `badge-${classification.toLowerCase().replace('_', '-')}`;

            let html = `<div class="classification-badge ${badgeClass}">${classification}</div>`;
            html += `<div>Analysis complete. The input is flagged as <strong>${classification}</strong>.</div>`;

            html += `<div class="details">`;

            if (responseData.lexicon && responseData.lexicon.flagged) {
                html += `<div class="detail-item"><span>Lexicon Check:</span> <span>Flagged</span></div>`;
                responseData.lexicon.hits.forEach(hit => {
                    html += `<div class="detail-item" style="font-size: 0.7rem; color: var(--high-red);"><span>&bull; ${hit.rule}:</span> <span>"${hit.matched_text}"</span></div>`;
                });
            } else {
                html += `<div class="detail-item"><span>Lexicon Check:</span> <span>Clean</span></div>`;
            }

            if (responseData.model1) {
                html += `<div class="detail-item"><span>FinBERT (Public/Private):</span> <span>${(responseData.model1.confidence * 100).toFixed(1)}% ${responseData.model1.label}</span></div>`;
            }

            if (responseData.model2) {
                html += `<div class="detail-item"><span>Severity Classifier:</span> <span>${(responseData.model2.confidence * 100).toFixed(1)}% ${responseData.model2.label}</span></div>`;
            }

            html += `</div>`;
            msgDiv.innerHTML = html;
        } else {
            msgDiv.textContent = text;
        }
    }

    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
    chatHistory.appendChild(indicator);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return indicator;
}

function addDebugLog(text, responseData, isFile = false) {
    const logItem = document.createElement('div');
    logItem.className = 'debug-log-item';

    let curl = "";
    if (isFile) {
        curl = `curl -X POST "${API_BASE}/classify-file" \\
     -F "file=@${text}"`;
    } else {
        curl = `curl -X POST "${API_BASE}/classify" \\
     -H "Content-Type: application/json" \\
     -d '{"text": "${text.replace(/'/g, "'\\''")}"}'`;
    }

    logItem.innerHTML = `
        <div class="debug-section">
            <h3>cURL Request</h3>
            <pre>${curl}</pre>
        </div>
        <div class="debug-section">
            <h3>JSON Response</h3>
            <pre>${JSON.stringify(responseData, null, 2)}</pre>
        </div>
        <hr style="border: 0; border-top: 1px solid var(--glass-border); margin: 20px 0;">
    `;

    debugContent.appendChild(logItem);
    debugContent.scrollTop = debugContent.scrollHeight;
}

async function handleSendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    messageInput.value = '';
    appendMessage(text, true);

    const indicator = showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/classify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!response.ok) throw new Error('API request failed');

        const data = await response.json();
        indicator.remove();
        appendMessage('', false, data);
        addDebugLog(text, data);
    } catch (err) {
        indicator.remove();
        appendMessage(`Error: ${err.message}. Make sure the backend API is running at ${API_BASE}.`, false);
    }
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    appendMessage(file.name, true, null, true);
    const indicator = showTypingIndicator();

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/classify-file`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('File upload/processing failed');

        const data = await response.json();
        indicator.remove();
        appendMessage('', false, data);
        addDebugLog(file.name, data, true);
    } catch (err) {
        indicator.remove();
        appendMessage(`Error: ${err.message}.`, false);
    }

    // Reset file input
    fileInput.value = '';
}

uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileUpload);
sendBtn.addEventListener('click', handleSendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSendMessage();
});
