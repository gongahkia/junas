const messageStreamEl = document.getElementById("message-stream");
const messageInputEl = document.getElementById("message-input");
const sendButtonEl = document.getElementById("send-button");
const uploadButtonEl = document.getElementById("upload-button");
const uploadInputEl = document.getElementById("upload-input");
const errorBannerEl = document.getElementById("error-banner");
const noticeBannerEl = document.getElementById("notice-banner");
const backendStatusEl = document.getElementById("backend-status");
const backendStatusTextEl = document.getElementById("backend-status-text");
const guardPopupEl = document.getElementById("guard-popup");
const guardTitleEl = document.getElementById("guard-title");
const guardSummaryEl = document.getElementById("guard-summary");
const guardClassificationEl = document.getElementById("guard-classification");
const guardDetailsEl = document.getElementById("guard-details");
const guardDismissEl = document.getElementById("guard-dismiss");
const guardActionsEl = document.getElementById("guard-actions");
const guardConfirmEl = document.getElementById("guard-confirm");
const composerStatusEl = document.getElementById("composer-status");

const seededMessages = [
    {
        author: "Zoe Maxwell",
        time: "10:55 AM",
        avatar: "ZM",
        body: "Hi team. Reminder that we are reviewing final concepts for the new website today. Keep draft comments flowing in here.",
        chipLabel: "",
        chipClass: "",
        kind: "text"
    },
    {
        author: "Google Calendar",
        time: "11:00 AM",
        avatar: "GC",
        body: "5 minutes until next event",
        chipLabel: "APP",
        chipClass: "",
        kind: "event",
        title: "Website design review",
        excerpt: "When: Monday 10:30 AM to 12:00 PM. Where: UX Room, 4th Floor."
    }
];

const liveMessages = [];
const modalState = { resolve: null };

let busy = false;
let guardPopupVisible = false;
let draftBlocked = false;
let blockedDraftText = "";

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function summarizeText(text, maxLength = 160) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    if (normalized.length <= maxLength) {
        return normalized;
    }
    return `${normalized.slice(0, maxLength - 1)}...`;
}

function formatTime(date = new Date()) {
    return new Intl.DateTimeFormat([], {
        hour: "numeric",
        minute: "2-digit"
    }).format(date);
}

function showError(message) {
    errorBannerEl.textContent = message;
    errorBannerEl.classList.remove("hidden");
}

function clearError() {
    errorBannerEl.textContent = "";
    errorBannerEl.classList.add("hidden");
}

function showNotice(message) {
    noticeBannerEl.textContent = message;
    noticeBannerEl.classList.remove("hidden");
}

function clearNotice() {
    noticeBannerEl.textContent = "";
    noticeBannerEl.classList.add("hidden");
}

function setBusy(nextBusy) {
    busy = nextBusy;
    refreshActionState();
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

function refreshActionState() {
    const currentText = messageInputEl.value.trim();

    sendButtonEl.classList.remove("is-blocked");

    if (busy) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Screening...";
        composerStatusEl.textContent = "Screening channel content through Noupe...";
    } else if (draftBlocked) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Cannot send";
        sendButtonEl.classList.add("is-blocked");
        composerStatusEl.textContent = "Edit the blocked message before retrying send.";
    } else {
        sendButtonEl.disabled = guardPopupVisible || !currentText;
        sendButtonEl.textContent = "Send";
        composerStatusEl.textContent = "Cmd/Ctrl + Enter sends after screening.";
    }

    uploadButtonEl.disabled = busy || guardPopupVisible;
    messageInputEl.disabled = busy;
}

function renderMessages() {
    const messages = [...seededMessages, ...liveMessages];
    messageStreamEl.innerHTML = messages.map((message) => {
        const chip = message.chipLabel
            ? `<span class="timeline-chip ${escapeHtml(message.chipClass)}">${escapeHtml(message.chipLabel)}</span>`
            : "";

        const extraBlock = message.kind === "event"
            ? `
                <div class="event-block">
                    <strong>${escapeHtml(message.title)}</strong>
                    <div>${escapeHtml(message.excerpt)}</div>
                </div>
            `
            : message.kind === "file"
                ? `
                    <div class="file-block">
                        <strong>${escapeHtml(message.title)}</strong>
                        <div>${escapeHtml(message.excerpt)}</div>
                    </div>
                `
                : "";

        return `
            <article class="message-item">
                <div class="message-avatar">${escapeHtml(message.avatar)}</div>
                <div class="message-card">
                    <div class="message-meta">
                        <span class="message-author">${escapeHtml(message.author)}</span>
                        <span>${escapeHtml(message.time)}</span>
                        ${chip}
                    </div>
                    <p class="message-body">${escapeHtml(message.body)}</p>
                    ${extraBlock}
                </div>
            </article>
        `;
    }).join("");
    messageStreamEl.scrollTop = messageStreamEl.scrollHeight;
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
        const state = result.mosaic.escalated ? "escalated" : "tracked";
        details.push(`Mosaic layer ${state} this entity with ${result.mosaic.count} recent hit(s).`);
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
            summary: `Noupe classified this ${sourceLabel} as HIGH_RISK. It cannot be posted in this channel.`,
            classificationClass: "screening-high",
            confirmLabel: "Blocked"
        };
    }

    if (classification === "LOW_RISK") {
        return {
            ...shared,
            canProceed: true,
            title: "Low-risk content needs review",
            summary: `Noupe classified this ${sourceLabel} as LOW_RISK. You can override the warning, but posting is intentionally interrupted first.`,
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
    guardClassificationEl.className = `guard-classification ${context.classificationClass}`.trim();
    guardClassificationEl.textContent = context.classification;
    guardDetailsEl.innerHTML = context.details
        .map((detail) => `<div class="guard-detail">${escapeHtml(detail)}</div>`)
        .join("");
    guardConfirmEl.textContent = context.confirmLabel;
    guardActionsEl.classList.toggle("hidden", !context.canProceed);
    guardConfirmEl.classList.toggle("hidden", !context.canProceed);
    setGuardPopupVisible(true);

    return new Promise((resolve) => {
        modalState.resolve = resolve;
    });
}

async function classifyContent(text) {
    const response = await fetch("/classify", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ text })
    });

    if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
            const payload = await response.json();
            if (payload && typeof payload.detail === "string" && payload.detail.trim()) {
                detail = payload.detail.trim();
            }
        } catch (error) {
            // Keep generic detail.
        }
        throw new Error(detail);
    }

    return response.json();
}

async function extractDocxText(file) {
    if (!file) {
        throw new Error("No file selected.");
    }

    if (typeof mammoth === "undefined") {
        throw new Error("DOCX parser failed to load in the browser.");
    }

    if (!file.name.toLowerCase().endsWith(".docx")) {
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

function pushLiveMessage({ body, chipLabel, chipClass, kind = "text", title = "", excerpt = "" }) {
    liveMessages.push({
        author: "You",
        time: formatTime(),
        avatar: "YO",
        body,
        chipLabel,
        chipClass,
        kind,
        title,
        excerpt
    });
    renderMessages();
}

async function handleSend() {
    const text = messageInputEl.value.trim();
    if (!text || busy || guardPopupVisible || draftBlocked) {
        return;
    }

    clearError();
    clearNotice();
    setBusy(true);

    try {
        const result = await classifyContent(text);
        const context = buildModalContext(result, "channel message");

        if (context.classification === "HIGH_RISK") {
            setDraftBlocked(true, text);
            setBusy(false);
            await openGuardPopup(context);
            showError("Message blocked because Noupe classified it as HIGH_RISK.");
            return;
        }

        let allowed = true;
        let chipLabel = "SAFE screened";
        let chipClass = "tone-safe";

        if (context.classification === "LOW_RISK") {
            setBusy(false);
            allowed = await openGuardPopup(context);
            chipLabel = "LOW_RISK override";
            chipClass = "tone-low";
        }

        if (!allowed) {
            showNotice("Message was not posted after the LOW_RISK warning.");
            return;
        }

        pushLiveMessage({
            body: text,
            chipLabel,
            chipClass
        });
        messageInputEl.value = "";
        setDraftBlocked(false);
        showNotice(context.classification === "LOW_RISK"
            ? "Message posted after LOW_RISK override."
            : "Message screened and posted to the channel.");
    } catch (error) {
        showError(`Unable to screen this message through Noupe. ${error.message}`);
    } finally {
        setBusy(false);
    }
}

async function handleUpload(event) {
    const file = event.target.files && event.target.files[0];
    uploadInputEl.value = "";

    if (!file || busy || guardPopupVisible) {
        return;
    }

    clearError();
    clearNotice();
    setBusy(true);

    try {
        const extractedText = await extractDocxText(file);
        const result = await classifyContent(extractedText);
        const context = buildModalContext(result, `attachment ${file.name}`);

        if (context.classification === "HIGH_RISK") {
            setBusy(false);
            await openGuardPopup(context);
            showError("Attachment rejected because Noupe classified the extracted text as HIGH_RISK.");
            return;
        }

        let allowed = true;
        let chipLabel = "SAFE screened";
        let chipClass = "tone-safe";

        if (context.classification === "LOW_RISK") {
            setBusy(false);
            allowed = await openGuardPopup(context);
            chipLabel = "LOW_RISK override";
            chipClass = "tone-low";
        }

        if (!allowed) {
            showNotice("Attachment was not posted to the channel.");
            return;
        }

        pushLiveMessage({
            body: "Shared a screened DOCX upload in the channel.",
            chipLabel,
            chipClass,
            kind: "file",
            title: file.name,
            excerpt: summarizeText(extractedText, 120)
        });
        showNotice(context.classification === "LOW_RISK"
            ? "Attachment posted after LOW_RISK override."
            : "Attachment screened and posted to the channel.");
    } catch (error) {
        showError(`Upload stopped before screening could finish. ${error.message}`);
    } finally {
        setBusy(false);
    }
}

function handleDraftInput() {
    clearError();
    if (guardPopupVisible) {
        closeGuardPopup(false);
    }
    if (draftBlocked && messageInputEl.value.trim() !== blockedDraftText) {
        setDraftBlocked(false);
        clearNotice();
        showNotice("Message changed. Send is available again after a fresh screening pass.");
    } else {
        refreshActionState();
    }
}

async function checkBackend() {
    const dot = backendStatusEl.querySelector(".status-dot");

    try {
        const response = await fetch("/ready");
        const payload = await response.json();

        if (payload.ready) {
            dot.style.background = "#148567";
            dot.style.boxShadow = "0 0 0 6px rgba(20, 133, 103, 0.14)";
            backendStatusTextEl.textContent = "Backend ready on /classify";
        } else {
            dot.style.background = "#d97706";
            dot.style.boxShadow = "0 0 0 6px rgba(217, 119, 6, 0.14)";
            const reasons = Array.isArray(payload.reasons) && payload.reasons.length
                ? ` (${payload.reasons.join("; ")})`
                : "";
            backendStatusTextEl.textContent = `Backend degraded${reasons}`;
        }
    } catch (error) {
        dot.style.background = "#d61f3a";
        dot.style.boxShadow = "0 0 0 6px rgba(214, 31, 58, 0.14)";
        backendStatusTextEl.textContent = "Backend unreachable";
    }
}

sendButtonEl.addEventListener("click", handleSend);
uploadButtonEl.addEventListener("click", () => uploadInputEl.click());
uploadInputEl.addEventListener("change", handleUpload);
messageInputEl.addEventListener("input", handleDraftInput);
messageInputEl.addEventListener("keydown", (event) => {
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

renderMessages();
checkBackend();
window.setInterval(checkBackend, 10000);
refreshActionState();
