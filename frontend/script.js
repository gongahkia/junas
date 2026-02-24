const chatHistory = document.getElementById('chat-history');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
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

function appendMessage(text, isUser = false, responseData = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;

    if (isUser) {
        msgDiv.textContent = text;
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

function addDebugLog(text, responseData) {
    const logItem = document.createElement('div');
    logItem.className = 'debug-log-item';

    const curl = `curl -X POST "${API_BASE}/classify" \\
     -H "Content-Type: application/json" \\
     -d '{"text": "${text.replace(/'/g, "'\\''")}"}'`;

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

sendBtn.addEventListener('click', handleSendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSendMessage();
});
