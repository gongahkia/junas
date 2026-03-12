const transcriptEl = document.getElementById("chat-transcript");
const chatInputEl = document.getElementById("chat-input");
const sendButtonEl = document.getElementById("send-button");
const uploadButtonEl = document.getElementById("upload-button");
const uploadInputEl = document.getElementById("upload-input");
const errorBannerEl = document.getElementById("error-banner");
const backendStatusTextEl = document.getElementById("backend-status-text");
const backendStatusEl = document.getElementById("backend-status");
const guardPopupEl = document.getElementById("guard-popup");
const guardTitleEl = document.getElementById("guard-title");
const guardSummaryEl = document.getElementById("guard-summary");
const guardClassificationEl = document.getElementById("guard-classification");
const guardDetailsEl = document.getElementById("guard-details");
const guardDismissEl = document.getElementById("guard-dismiss");
const guardActionsEl = document.getElementById("guard-actions");
const guardConfirmEl = document.getElementById("guard-confirm");

const assistantReplies = {
    message: [
        "Draft received. If this were a real assistant workflow, I would continue only because the guardrail allowed it through.",
        "Screening passed. The chat response is hardcoded here, but the approval path is the real feature being demonstrated.",
        "Message accepted. This shows how Noupe can sit in front of a normal conversational interface as a preventive check."
    ],
    upload: [
        "Document accepted. The upload itself is not the point here; the screening gate is.",
        "File cleared the guardrail. In a production flow, the document could now move into downstream review or drafting.",
        "Upload approved. This demo keeps the assistant response simple and puts the emphasis on the classifier decision."
    ]
};

const modalState = {
    resolve: null
};

let replyCursor = 0;
let busy = false;
let guardPopupVisible = false;
let draftBlocked = false;
let blockedDraftText = "";
const MAX_SCREENING_TEXT_LENGTH = 20000;
const SCREENING_CONTROL_CHAR_PATTERN = /[\u0000-\u001f\u007f-\u009f]/;

function refreshActionState(sendLabel = "Send") {
    sendButtonEl.classList.remove("is-blocked", "is-guarded");

    if (busy) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Screening...";
    } else if (draftBlocked) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Cannot send";
        sendButtonEl.classList.add("is-blocked");
    } else if (guardPopupVisible) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Send";
        sendButtonEl.classList.add("is-guarded");
    } else {
        sendButtonEl.disabled = false;
        sendButtonEl.textContent = sendLabel;
    }

    uploadButtonEl.disabled = busy || guardPopupVisible;
    chatInputEl.disabled = busy;
}

function setBusy(nextBusy, sendLabel = "Send") {
    busy = nextBusy;
    refreshActionState(sendLabel);
}

function setGuardPopupVisible(nextVisible) {
    guardPopupVisible = nextVisible;
    guardPopupEl.classList.toggle("hidden", !nextVisible);
    refreshActionState();
}

function setDraftBlocked(nextBlocked, text = "") {
    draftBlocked = nextBlocked;
    blockedDraftText = nextBlocked ? text.trim() : "";
    refreshActionState();
}

function showError(message) {
    errorBannerEl.textContent = message;
    errorBannerEl.classList.remove("hidden");
}

function clearError() {
    errorBannerEl.textContent = "";
    errorBannerEl.classList.add("hidden");
}

function summarizeText(text, maxLength = 180) {
    const normalized = text.replace(/\s+/g, " ").trim();
    if (normalized.length <= maxLength) {
        return normalized;
    }
    return `${normalized.slice(0, maxLength - 1)}...`;
}

function escapeHtml(value) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function sanitizeScreeningText(value) {
    return Array.from(String(value || ""))
        .filter((ch) => ch === "\n" || ch === "\r" || ch === "\t" || !SCREENING_CONTROL_CHAR_PATTERN.test(ch))
        .join("")
        .trim();
}

function validateScreeningText(text, sourceLabel) {
    const cleaned = sanitizeScreeningText(text);
    if (!cleaned) {
        throw new Error(`${sourceLabel} must contain non-whitespace printable content.`);
    }
    if (cleaned.length > MAX_SCREENING_TEXT_LENGTH) {
        throw new Error(`${sourceLabel} exceeds the screening limit of ${MAX_SCREENING_TEXT_LENGTH} characters after cleanup.`);
    }
    return cleaned;
}

function extractApiErrorDetail(payload) {
    if (!payload) {
        return "";
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
        return payload.detail.trim();
    }
    if (Array.isArray(payload.detail)) {
        const messages = payload.detail.map((item) => {
            if (typeof item === "string") {
                return item.trim();
            }
            if (!item || typeof item !== "object") {
                return "";
            }
            const location = Array.isArray(item.loc)
                ? item.loc.filter((part) => part !== "body").join(".")
                : "";
            const message = typeof item.msg === "string" ? item.msg.trim() : "";
            if (!message) {
                return "";
            }
            return location ? `${location}: ${message}` : message;
        }).filter(Boolean);
        if (messages.length) {
            return messages.join(" | ");
        }
    }
    if (payload.detail && typeof payload.detail === "object") {
        try {
            return JSON.stringify(payload.detail);
        } catch (error) {
            return "";
        }
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
        return payload.message.trim();
    }
    return "";
}

function createMessageElement({ role, body, tagLabel, tagClass, kind = "text", filename = "", excerpt = "" }) {
    const article = document.createElement("article");
    article.className = `message ${role === "assistant" ? "assistant-message" : "user-message"}`;

    const meta = document.createElement("div");
    meta.className = "message-meta";

    const roleSpan = document.createElement("span");
    roleSpan.className = "message-role";
    roleSpan.textContent = role === "assistant" ? "Noupe Assistant" : "User";
    meta.appendChild(roleSpan);

    if (tagLabel) {
        const chip = document.createElement("span");
        chip.className = `screening-chip ${tagClass || ""}`.trim();
        chip.textContent = tagLabel;
        meta.appendChild(chip);
    }

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (kind === "upload") {
        bubble.innerHTML = `
            <div class="upload-preview">
                <div class="upload-name">${escapeHtml(filename)}</div>
                <div>${escapeHtml(body)}</div>
                <div class="upload-excerpt">${escapeHtml(excerpt)}</div>
            </div>
        `;
    } else {
        bubble.textContent = body;
    }

    article.appendChild(meta);
    article.appendChild(bubble);
    transcriptEl.appendChild(article);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
}

function nextAssistantReply(kind) {
    const bank = assistantReplies[kind] || assistantReplies.message;
    const reply = bank[replyCursor % bank.length];
    replyCursor += 1;
    return reply;
}

function delay(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function appendAssistantReply(kind) {
    await delay(240);
    createMessageElement({
        role: "assistant",
        body: nextAssistantReply(kind),
        tagLabel: "Stub response",
        tagClass: "safe-tag"
    });
}

function buildRiskDetails(result) {
    const details = [];

    if (result.lexicon && Array.isArray(result.lexicon.hits) && result.lexicon.hits.length > 0) {
        const topHits = result.lexicon.hits.slice(0, 3).map((hit) => {
            const detail = hit.detail ? `: ${hit.detail}` : "";
            return `${hit.rule} matched "${hit.matched_text}"${detail}`;
        });
        details.push(`Lexicon signals: ${topHits.join(" | ")}`);
    }

    if (result.model1) {
        details.push(`Model 1 classified the text as ${result.model1.label} at ${(result.model1.confidence * 100).toFixed(1)}% confidence.`);
    }

    if (result.model2) {
        details.push(`Model 2 severity label: ${result.model2.label} at ${(result.model2.confidence * 100).toFixed(1)}% confidence.`);
    }

    if (result.mosaic && typeof result.mosaic.count === "number") {
        const mosaicState = result.mosaic.escalated ? "escalated" : "tracked";
        details.push(`Mosaic layer ${mosaicState} this entity with ${result.mosaic.count} recent hit(s).`);
    }

    if (result.observability && result.observability.degraded) {
        details.push("The classifier responded in a degraded state. Treat the screening result conservatively.");
    }

    if (details.length === 0) {
        details.push("The classifier flagged the content without a richer debug trail in the response payload.");
    }

    return details;
}

function buildModalContext(result, sourceLabel) {
    const classification = result.classification || "SAFE";
    const shared = {
        classification,
        details: buildRiskDetails(result)
    };

    if (classification === "HIGH_RISK") {
        return {
            ...shared,
            canProceed: false,
            title: "High-risk content blocked",
            summary: `Noupe classified this ${sourceLabel} as HIGH_RISK. It cannot be added to the chat transcript.`,
            classificationClass: "screening-high",
            confirmLabel: "Blocked"
        };
    }

    if (classification === "LOW_RISK") {
        return {
            ...shared,
            canProceed: true,
            title: "Low-risk content needs review",
            summary: `Noupe classified this ${sourceLabel} as LOW_RISK. You can override the warning, but the action is intentionally interrupted first.`,
            classificationClass: "screening-low",
            confirmLabel: "Proceed anyway"
        };
    }

    return {
        ...shared,
        canProceed: true,
        title: "Content cleared",
        summary: `Noupe classified this ${sourceLabel} as SAFE.`,
        classificationClass: "screening-safe",
        confirmLabel: "Continue"
    };
}

function closeGuardPopup(decision) {
    setGuardPopupVisible(false);
    if (typeof modalState.resolve === "function") {
        const resolve = modalState.resolve;
        modalState.resolve = null;
        resolve(decision);
    }
}

function openGuardPopup(context) {
    guardTitleEl.textContent = context.title;
    guardSummaryEl.textContent = context.summary;
    guardClassificationEl.className = `modal-classification ${context.classificationClass}`.trim();
    guardClassificationEl.textContent = context.classification;
    guardDetailsEl.innerHTML = context.details
        .map((detail) => `<div class="modal-detail">${escapeHtml(detail)}</div>`)
        .join("");
    guardConfirmEl.textContent = context.confirmLabel;
    guardActionsEl.classList.toggle("hidden", !context.canProceed);
    guardConfirmEl.classList.toggle("hidden", !context.canProceed);
    setGuardPopupVisible(true);

    return new Promise((resolve) => {
        modalState.resolve = resolve;
    });
}

async function classifyContent(text, sourceLabel = "Content") {
    const screeningText = validateScreeningText(text, sourceLabel);
    const response = await fetch("/classify", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ text: screeningText })
    });

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const payload = await response.json();
            const parsedDetail = extractApiErrorDetail(payload);
            if (parsedDetail) {
                detail = `${parsedDetail} (HTTP ${response.status})`;
            }
        } catch (error) {
            // Keep generic detail.
        }
        throw new Error(detail);
    }

    return response.json();
}

async function guardAndHandle({ text, sourceLabel, kind, filename = "", busyAlreadySet = false }) {
    clearError();
    if (!busyAlreadySet) {
        setBusy(true);
    }

    try {
        const result = await classifyContent(text, sourceLabel === "message" ? "Message" : "Document upload");
        const context = buildModalContext(result, sourceLabel);
        const classification = context.classification;

        if (classification === "HIGH_RISK") {
            if (kind === "message") {
                setDraftBlocked(true, text);
            }
            setBusy(false);
            await openGuardPopup(context);
            return false;
        }

        let allowed = true;
        let tagLabel = "SAFE screened";
        let tagClass = "screening-safe";

        if (kind === "message") {
            setDraftBlocked(false);
        }

        if (classification === "LOW_RISK") {
            setBusy(false);
            allowed = await openGuardPopup(context);
            tagLabel = "LOW_RISK override";
            tagClass = "screening-low";
        }

        if (!allowed) {
            return false;
        }

        if (kind === "upload") {
            createMessageElement({
                role: "user",
                kind: "upload",
                filename,
                body: "DOCX upload accepted after screening.",
                excerpt: summarizeText(text),
                tagLabel,
                tagClass
            });
        } else {
            createMessageElement({
                role: "user",
                body: text,
                tagLabel,
                tagClass
            });
        }

        await appendAssistantReply(kind);
        return true;
    } catch (error) {
        showError(`Unable to screen content through Noupe. The action was stopped. ${error.message}`);
        return false;
    } finally {
        setBusy(false);
    }
}

async function handleSend() {
    const text = chatInputEl.value.trim();
    if (!text || busy || guardPopupVisible) {
        return;
    }

    const accepted = await guardAndHandle({
        text,
        sourceLabel: "message",
        kind: "message"
    });

    if (accepted) {
        chatInputEl.value = "";
    }
}

async function extractDocxText(file) {
    if (!file) {
        throw new Error("No file selected.");
    }

    if (typeof mammoth === "undefined") {
        throw new Error("DOCX parser failed to load in the browser.");
    }

    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".docx")) {
        throw new Error("Only DOCX files are supported in this demo.");
    }

    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    const extracted = result.value.replace(/\s+/g, " ").trim();

    if (!extracted) {
        throw new Error("The DOCX did not contain extractable text.");
    }

    return extracted;
}

async function handleUpload(event) {
    const file = event.target.files && event.target.files[0];
    uploadInputEl.value = "";

    if (!file || busy || guardPopupVisible) {
        return;
    }

    clearError();
    setBusy(true, "Send");

    try {
        const text = await extractDocxText(file);
        await guardAndHandle({
            text,
            sourceLabel: "document upload",
            kind: "upload",
            filename: file.name,
            busyAlreadySet: true
        });
    } catch (error) {
        setBusy(false);
        showError(`Upload stopped before screening could finish. ${error.message}`);
    }
}

async function checkBackend() {
    const dot = backendStatusEl.querySelector(".status-dot");

    try {
        const response = await fetch("/ready");
        const payload = await response.json();

        if (payload.ready) {
            dot.style.background = "#86efac";
            backendStatusTextEl.textContent = "Backend ready on /classify";
        } else {
            dot.style.background = "#facc15";
            const reasons = Array.isArray(payload.reasons) && payload.reasons.length
                ? ` (${payload.reasons.join("; ")})`
                : "";
            backendStatusTextEl.textContent = `Backend degraded${reasons}`;
        }
    } catch (error) {
        dot.style.background = "#fecaca";
        backendStatusTextEl.textContent = "Backend unreachable";
    }
}

sendButtonEl.addEventListener("click", handleSend);
uploadButtonEl.addEventListener("click", () => uploadInputEl.click());
uploadInputEl.addEventListener("change", handleUpload);
chatInputEl.addEventListener("input", () => {
    if (guardPopupVisible) {
        closeGuardPopup(false);
    }
    if (draftBlocked && chatInputEl.value.trim() !== blockedDraftText) {
        setDraftBlocked(false);
    }
});
chatInputEl.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        handleSend();
    }
});

guardDismissEl.addEventListener("click", () => closeGuardPopup(false));
guardConfirmEl.addEventListener("click", () => closeGuardPopup(true));
window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && guardPopupVisible) {
        closeGuardPopup(false);
    }
});

checkBackend();
window.setInterval(checkBackend, 10000);
refreshActionState();
