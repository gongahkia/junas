const chatHistory = document.getElementById('chat-history');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const statusDot = document.querySelector('.status-dot');

const API_BASE = 'http://localhost:8000'; // Adjust if backend is on a different port

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

// Check health every 10 seconds
setInterval(checkHealth, 10000);
checkHealth();

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

            // Details breakdown
            html += `<div class="details">`;

            if (responseData.lexicon && responseData.lexicon.flagged) {
                html += `<div class="detail-item"><span>Lexicon Check:</span> <span>⚠️ Flagged</span></div>`;
                responseData.lexicon.hits.forEach(hit => {
                    html += `<div class="detail-item" style="font-size: 0.7rem; color: #ef4444;"><span>&bull; ${hit.rule}:</span> <span>"${hit.matched_text}"</span></div>`;
                });
            } else {
                html += `<div class="detail-item"><span>Lexicon Check:</span> <span>✅ Plain Text</span></div>`;
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
    } catch (err) {
        indicator.remove();
        appendMessage(`Error: ${err.message}. Make sure the backend API is running at ${API_BASE}.`, false);
    }
}

sendBtn.addEventListener('click', handleSendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSendMessage();
});
