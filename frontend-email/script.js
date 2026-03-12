const mailListEl = document.getElementById("mail-list");
const toInputEl = document.getElementById("to-input");
const subjectInputEl = document.getElementById("subject-input");
const bodyInputEl = document.getElementById("body-input");
const sendButtonEl = document.getElementById("send-button");
const discardButtonEl = document.getElementById("discard-button");
const attachButtonEl = document.getElementById("attach-button");
const uploadInputEl = document.getElementById("upload-input");
const attachmentStripEl = document.getElementById("attachment-strip");
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
const draftStatusEl = document.getElementById("draft-status");
const newMessageButtonEl = document.getElementById("new-message-button");

const inboxSeed = [
    {
        sender: "SMU Student Care",
        subject: "Clear your mind with a short break",
        preview: "A calm inbox item to contrast with guarded drafts. This list is static except for local sent messages.",
        time: "5:01 PM",
        footer: "From the mock inbox",
        tagLabel: "Inbox",
        tagClass: ""
    },
    {
        sender: "SocSc Seminar",
        subject: "Invite to register for multipolarity lecture",
        preview: "Use this pane as a visual reference only. Noupe screening happens in the compose surface on the right.",
        time: "4:42 PM",
        footer: "Focused view",
        tagLabel: "Inbox",
        tagClass: ""
    },
    {
        sender: "Career Champions",
        subject: "Company visit to the analytics lab",
        preview: "The demo keeps this mailbox intentionally lightweight and local.",
        time: "2:42 PM",
        footer: "Preview only",
        tagLabel: "Inbox",
        tagClass: ""
    }
];

const sentMessages = [];
const attachments = [];
const modalState = { resolve: null };

let busy = false;
let guardPopupVisible = false;
let draftBlocked = false;
let blockedDraftSignature = "";

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function summarizeText(text, maxLength = 140) {
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

function currentDraft() {
    const subject = subjectInputEl.value.trim();
    const body = bodyInputEl.value.trim();
    return {
        to: toInputEl.value.trim(),
        subject,
        body,
        screeningText: [subject, body].filter(Boolean).join("\n\n")
    };
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

function setDraftBlocked(nextBlocked, signature = "") {
    draftBlocked = nextBlocked;
    blockedDraftSignature = nextBlocked ? signature : "";
    refreshActionState();
}

function setGuardPopupVisible(nextVisible) {
    guardPopupVisible = nextVisible;
    guardPopupEl.classList.toggle("hidden", !nextVisible);
    refreshActionState();
}

function refreshActionState() {
    const draft = currentDraft();

    sendButtonEl.classList.remove("is-blocked");

    if (busy) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Screening...";
    } else if (draftBlocked) {
        sendButtonEl.disabled = true;
        sendButtonEl.textContent = "Cannot send";
        sendButtonEl.classList.add("is-blocked");
    } else {
        sendButtonEl.disabled = guardPopupVisible || !draft.screeningText;
        sendButtonEl.textContent = "Send";
    }

    discardButtonEl.disabled = busy || guardPopupVisible;
    attachButtonEl.disabled = busy || guardPopupVisible;
    toInputEl.disabled = busy;
    subjectInputEl.disabled = busy;
    bodyInputEl.disabled = busy;

    if (draftBlocked) {
        draftStatusEl.textContent = "Edit subject or body to unlock sending after a HIGH_RISK block.";
    } else if (busy) {
        draftStatusEl.textContent = "Screening draft through Noupe...";
    } else if (attachments.length > 0) {
        draftStatusEl.textContent = `Draft has ${attachments.length} approved attachment${attachments.length === 1 ? "" : "s"}.`;
    } else {
        draftStatusEl.textContent = "Cmd/Ctrl + Enter sends after screening.";
    }
}

function renderMailList() {
    const messages = [...sentMessages, ...inboxSeed];
    mailListEl.innerHTML = messages.map((item) => `
        <article class="mail-item">
            <div class="mail-item-meta">
                <span class="mail-sender">${escapeHtml(item.sender)}</span>
                <span>${escapeHtml(item.time)}</span>
            </div>
            <h3>${escapeHtml(item.subject)}</h3>
            <p>${escapeHtml(item.preview)}</p>
            <div class="mail-item-footer">
                <span>${escapeHtml(item.footer)}</span>
                ${item.tagLabel ? `<span class="mail-chip ${escapeHtml(item.tagClass)}">${escapeHtml(item.tagLabel)}</span>` : ""}
            </div>
        </article>
    `).join("");
}

function renderAttachments() {
    if (attachments.length === 0) {
        attachmentStripEl.innerHTML = '<div class="attachment-empty">No approved attachments on this draft yet.</div>';
        return;
    }

    attachmentStripEl.innerHTML = attachments.map((item) => `
        <article class="attachment-item">
            <div class="attachment-item-head">
                <span class="attachment-name">${escapeHtml(item.name)}</span>
                <span class="attachment-chip ${escapeHtml(item.tagClass)}">${escapeHtml(item.tagLabel)}</span>
            </div>
            <p class="attachment-excerpt">${escapeHtml(item.excerpt)}</p>
        </article>
    `).join("");
}

function resetDraft() {
    toInputEl.value = "";
    subjectInputEl.value = "";
    bodyInputEl.value = "";
    attachments.length = 0;
    setDraftBlocked(false);
    renderAttachments();
    refreshActionState();
}

function addSentMessage(tagLabel, tagClass) {
    const draft = currentDraft();
    const attachmentSummary = attachments.length ? ` Attachments: ${attachments.map((item) => item.name).join(", ")}.` : "";
    sentMessages.unshift({
        sender: "You",
        subject: draft.subject || "(No subject)",
        preview: summarizeText(`${draft.body || "No body written."}${attachmentSummary}`),
        time: "Just now",
        footer: draft.to ? `Sent to ${draft.to}` : "Sent to unspecific recipient",
        tagLabel,
        tagClass
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
            summary: `Noupe classified this ${sourceLabel} as HIGH_RISK. It cannot be sent or attached in this mail draft.`,
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

async function handleAttachment(event) {
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
        let tagLabel = "SAFE screened";
        let tagClass = "tone-safe";

        if (context.classification === "LOW_RISK") {
            setBusy(false);
            allowed = await openGuardPopup(context);
            tagLabel = "LOW_RISK override";
            tagClass = "tone-low";
        }

        if (!allowed) {
            showNotice("Attachment was not added to the draft.");
            return;
        }

        attachments.push({
            name: file.name,
            excerpt: summarizeText(extractedText, 96),
            tagLabel,
            tagClass
        });
        renderAttachments();
        showNotice(context.classification === "LOW_RISK"
            ? "Attachment kept after LOW_RISK override."
            : "Attachment approved and kept on the draft.");
    } catch (error) {
        showError(`Upload stopped before screening could finish. ${error.message}`);
    } finally {
        setBusy(false);
    }
}

async function handleSend() {
    const draft = currentDraft();
    if (!draft.screeningText || busy || guardPopupVisible || draftBlocked) {
        return;
    }

    clearError();
    clearNotice();
    setBusy(true);

    try {
        const result = await classifyContent(draft.screeningText);
        const context = buildModalContext(result, "email draft");

        if (context.classification === "HIGH_RISK") {
            setDraftBlocked(true, draft.screeningText);
            setBusy(false);
            await openGuardPopup(context);
            showError("Email send blocked because the draft was classified as HIGH_RISK.");
            return;
        }

        let allowed = true;
        let tagLabel = "SAFE screened";
        let tagClass = "tone-safe";

        if (context.classification === "LOW_RISK") {
            setBusy(false);
            allowed = await openGuardPopup(context);
            tagLabel = "LOW_RISK override";
            tagClass = "tone-low";
        }

        if (!allowed) {
            showNotice("Draft kept in place after the LOW_RISK warning.");
            return;
        }

        addSentMessage(tagLabel, tagClass);
        renderMailList();
        resetDraft();
        showNotice(context.classification === "LOW_RISK"
            ? "Email sent after LOW_RISK override."
            : `Email screened and sent at ${formatTime()}.`);
    } catch (error) {
        showError(`Unable to screen this draft through Noupe. ${error.message}`);
    } finally {
        setBusy(false);
    }
}

function handleDiscard() {
    if (busy || guardPopupVisible) {
        return;
    }

    clearError();
    resetDraft();
    clearNotice();
    showNotice("Draft discarded.");
}

async function checkBackend() {
    const dot = backendStatusEl.querySelector(".status-dot");

    try {
        const response = await fetch("/ready");
        const payload = await response.json();

        if (payload.ready) {
            dot.style.background = "#29c288";
            dot.style.boxShadow = "0 0 0 6px rgba(41, 194, 136, 0.12)";
            backendStatusTextEl.textContent = "Backend ready on /classify";
        } else {
            dot.style.background = "#f4aa2d";
            dot.style.boxShadow = "0 0 0 6px rgba(244, 170, 45, 0.12)";
            const reasons = Array.isArray(payload.reasons) && payload.reasons.length
                ? ` (${payload.reasons.join("; ")})`
                : "";
            backendStatusTextEl.textContent = `Backend degraded${reasons}`;
        }
    } catch (error) {
        dot.style.background = "#ff5a77";
        dot.style.boxShadow = "0 0 0 6px rgba(255, 90, 119, 0.12)";
        backendStatusTextEl.textContent = "Backend unreachable";
    }
}

function handleDraftInputChange() {
    clearError();
    if (guardPopupVisible) {
        closeGuardPopup(false);
    }

    if (draftBlocked && currentDraft().screeningText !== blockedDraftSignature) {
        setDraftBlocked(false);
        clearNotice();
        showNotice("Draft changed. Send is available again after a fresh screening pass.");
    } else {
        refreshActionState();
    }
}

sendButtonEl.addEventListener("click", handleSend);
discardButtonEl.addEventListener("click", handleDiscard);
attachButtonEl.addEventListener("click", () => uploadInputEl.click());
uploadInputEl.addEventListener("change", handleAttachment);
guardDismissEl.addEventListener("click", () => closeGuardPopup(false));
guardConfirmEl.addEventListener("click", () => closeGuardPopup(true));
newMessageButtonEl.addEventListener("click", () => {
    resetDraft();
    clearError();
    clearNotice();
});

subjectInputEl.addEventListener("input", handleDraftInputChange);
bodyInputEl.addEventListener("input", handleDraftInputChange);
bodyInputEl.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        handleSend();
    }
});

window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && guardPopupVisible) {
        closeGuardPopup(false);
    }
});

renderMailList();
renderAttachments();
checkBackend();
window.setInterval(checkBackend, 10000);
refreshActionState();
