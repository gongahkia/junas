const analyzeInput = document.getElementById("analyze-input");
const entityInput = document.getElementById("entity-input");
const classifyBtn = document.getElementById("classify-btn");
const resultsDisplay = document.getElementById("results-display");
const connectionText = document.getElementById("connection-text");
const statusDot = document.querySelector(".status-dot");
const apiBaseLabel = document.getElementById("api-base-label");
const layerStatusChips = document.getElementById("layer-status-chips");
const traceSummary = document.getElementById("trace-summary");
const architectureDiagram = document.getElementById("architecture-diagram");

const CANONICAL_LAYER_ORDER = ["lexicon", "embedding", "clustering", "model1", "model2", "mosaic", "regression"];
const LAYER_META = {
    lexicon: { id: "L1", title: "1. Lexicon Check", short: "Lexicon" },
    embedding: { id: "L2", title: "2. Embeddings Generation", short: "Embed" },
    clustering: { id: "L3", title: "3. Clustering", short: "Cluster" },
    model1: { id: "L4", title: "4. Classification Model 1", short: "M1" },
    model2: { id: "L4b", title: "4b. Classification Model 2", short: "M2" },
    mosaic: { id: "L5", title: "5. Mosaic Aggregation", short: "Mosaic" },
    regression: { id: "Reg", title: "6. Regression", short: "Reg" },
};
const NODE_LAYER_BY_ID = {
    L1: "lexicon",
    L2: "embedding",
    L3: "clustering",
    L4: "model1",
    L4b: "model2",
    L5: "mosaic",
    Reg: "regression",
};
const DIAGRAM_EDGES = [
    { key: "ingress_lexicon", from: "In", to: "L1", label: "Request ingress" },
    { key: "lexicon_embedding", from: "L1", to: "L2", label: "Continue" },
    { key: "lexicon_regression", from: "L1", to: "Reg", label: "Lexicon exit", dashed: true },
    { key: "lexicon_output", from: "L1", to: "Out", label: "Direct output", dashed: true },
    { key: "embedding_clustering", from: "L2", to: "L3", label: "Embedding branch" },
    { key: "embedding_model1", from: "L2", to: "L4", label: "Classifier branch" },
    { key: "clustering_mosaic", from: "L3", to: "L5", label: "Anomaly signal" },
    { key: "clustering_regression", from: "L3", to: "Reg", label: "Feature handoff", dashed: true },
    { key: "model1_model2", from: "L4", to: "L4b", label: "Severity gate" },
    { key: "model1_mosaic", from: "L4", to: "L5", label: "Safe / entity path" },
    { key: "model1_regression", from: "L4", to: "Reg", label: "Risk handoff", dashed: true },
    { key: "model1_output", from: "L4", to: "Out", label: "Direct output", dashed: true },
    { key: "model2_mosaic", from: "L4b", to: "L5", label: "Severity / entity path" },
    { key: "model2_regression", from: "L4b", to: "Reg", label: "Severity handoff", dashed: true },
    { key: "model2_output", from: "L4b", to: "Out", label: "Direct output", dashed: true },
    { key: "mosaic_regression", from: "L5", to: "Reg", label: "Aggregate" },
    { key: "mosaic_output", from: "L5", to: "Out", label: "Direct output", dashed: true },
    { key: "regression_output", from: "Reg", to: "Out", label: "Final score" },
];
const EDGE_STYLE_BY_KIND = {
    success: "stroke:#16a34a,stroke-width:3px;",
    warning: "stroke:#d97706,stroke-width:3px;",
    danger: "stroke:#dc2626,stroke-width:3px;",
    waiting: "stroke:#60a5fa,stroke-width:2.5px;",
    skipped: "stroke:#9ca3af,stroke-width:1.5px;",
    inactive: "stroke:#d1d5db,stroke-width:1.5px;",
    unavailable: "stroke:#fb7185,stroke-width:2.5px;",
    neutral: "stroke:#4b5563,stroke-width:1.5px;",
};
const MAX_SCREENING_TEXT_LENGTH = 100000;
const SCREENING_CONTROL_CHAR_PATTERN = /[\u0000-\u001f\u007f-\u009f]/;

let latestReadyState = null;
let latestDiagnosticsState = null;
let lastClassificationResponse = null;

function normalizeApiBase(value) {
    return value ? value.replace(/\/+$/, "") : "";
}

function resolveApiBase() {
    const params = new URLSearchParams(window.location.search);
    const queryBase = normalizeApiBase(params.get("api"));
    if (queryBase) {
        window.localStorage.setItem("noupe.apiBase", queryBase);
        return queryBase;
    }

    const savedBase = normalizeApiBase(window.localStorage.getItem("noupe.apiBase"));
    if (savedBase) {
        return savedBase;
    }

    if (window.location.port === "8000" && /^https?:$/.test(window.location.protocol)) {
        return normalizeApiBase(window.location.origin);
    }

    return "http://localhost:8000";
}

const API_BASE = resolveApiBase();
const API_HOST_LABEL = (() => {
    try {
        return new URL(API_BASE).host;
    } catch (error) {
        return API_BASE;
    }
})();

if (apiBaseLabel) {
    apiBaseLabel.textContent = API_BASE;
}

mermaid.initialize({ startOnLoad: false, theme: "default" });

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function safeArray(value) {
    return Array.isArray(value) ? value : [];
}

function uniqueOrdered(values) {
    return [...new Set(values.filter(Boolean))];
}

function shortText(value, maxLength = 42) {
    const normalized = String(value || "").replace(/\s+/g, " ").trim();
    if (!normalized) {
        return "";
    }
    if (normalized.length <= maxLength) {
        return normalized;
    }
    return `${normalized.slice(0, maxLength - 1)}...`;
}

function formatPercent(value) {
    return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function formatNumber(value) {
    return Number(value || 0).toFixed(3);
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

function buildBackendContext(readyState, diagnosticsState) {
    const readyPipeline = safeArray(readyState && readyState.pipeline);
    const diagnosticsPipeline = safeArray(diagnosticsState && diagnosticsState.pipeline);
    const pipeline = diagnosticsPipeline.length ? diagnosticsPipeline : (readyPipeline.length ? readyPipeline : CANONICAL_LAYER_ORDER);

    const loadErrors = new Map();
    safeArray(diagnosticsState && diagnosticsState.load_errors).forEach((item) => {
        if (item && item.layer && !loadErrors.has(item.layer)) {
            loadErrors.set(item.layer, item);
        }
    });

    return {
        pipeline,
        loaded: new Set(safeArray(diagnosticsState && diagnosticsState.loaded_layers)),
        lazy: new Set(safeArray(diagnosticsState && diagnosticsState.lazy_layers)),
        warming: new Set(uniqueOrdered([
            ...safeArray(readyState && readyState.warming_required_layers),
            ...safeArray(diagnosticsState && diagnosticsState.warming_required_layers),
        ])),
        missing: new Set(safeArray(readyState && readyState.missing_required_layers)),
        loadErrors,
    };
}

function getBackendLayerState(layer, backendContext) {
    if (!backendContext.pipeline.includes(layer)) {
        return {
            kind: "configured",
            label: "Inactive",
            detail: "Not part of the active pipeline",
        };
    }

    if (backendContext.missing.has(layer)) {
        const error = backendContext.loadErrors.get(layer);
        return {
            kind: "unavailable",
            label: "Missing",
            detail: error ? shortText(error.error || error.message || "") : "Missing required layer",
        };
    }

    if (backendContext.warming.has(layer)) {
        return {
            kind: "warming",
            label: "Warming",
            detail: "Lazy layer is warming in the background",
        };
    }

    if (backendContext.loaded.has(layer)) {
        return {
            kind: "loaded",
            label: "Loaded",
            detail: "Ready for execution",
        };
    }

    if (backendContext.lazy.has(layer)) {
        return {
            kind: "lazy",
            label: "Lazy",
            detail: "Configured for lazy loading",
        };
    }

    if (backendContext.loadErrors.has(layer)) {
        const error = backendContext.loadErrors.get(layer);
        return {
            kind: "unavailable",
            label: "Unavailable",
            detail: shortText(error.error || error.message || ""),
        };
    }

    return {
        kind: "configured",
        label: "Configured",
        detail: "Configured but not yet loaded",
    };
}

function renderLayerStatusPanel() {
    if (!layerStatusChips) {
        return;
    }

    const backendContext = buildBackendContext(latestReadyState, latestDiagnosticsState);
    const html = backendContext.pipeline.map((layer) => {
        const state = getBackendLayerState(layer, backendContext);
        const detail = state.detail ? ` ${state.detail}` : "";
        const title = `${LAYER_META[layer].title}: ${state.label}.${detail}`;
        return `<span class="layer-chip layer-chip-${state.kind}" title="${escapeHtml(title)}"><span class="layer-chip-dot" aria-hidden="true"></span><span>${escapeHtml(LAYER_META[layer].short)}</span></span>`;
    }).join("");

    layerStatusChips.innerHTML = html || '<span class="layer-chip layer-chip-unknown">No diagnostics available</span>';
}

function setConnectionState(kind, text) {
    if (kind === "ready") {
        statusDot.style.backgroundColor = "#10b981";
        statusDot.style.boxShadow = "0 0 8px #10b981";
        connectionText.textContent = text;
        connectionText.style.color = "#10b981";
        return;
    }

    if (kind === "degraded") {
        statusDot.style.backgroundColor = "#f59e0b";
        statusDot.style.boxShadow = "0 0 8px #f59e0b";
        connectionText.textContent = text;
        connectionText.style.color = "#f59e0b";
        return;
    }

    statusDot.style.backgroundColor = "#ef4444";
    statusDot.style.boxShadow = "0 0 8px #ef4444";
    connectionText.textContent = text;
    connectionText.style.color = "#ef4444";
}

async function refreshBackendSnapshot() {
    try {
        const [readyResponse, diagnosticsResponse] = await Promise.all([
            fetch(`${API_BASE}/ready`),
            fetch(`${API_BASE}/diagnostics`),
        ]);

        if (!readyResponse.ok) {
            throw new Error(`ready endpoint HTTP ${readyResponse.status}`);
        }
        if (!diagnosticsResponse.ok) {
            throw new Error(`diagnostics endpoint HTTP ${diagnosticsResponse.status}`);
        }

        latestReadyState = await readyResponse.json();
        latestDiagnosticsState = await diagnosticsResponse.json();

        if (latestReadyState.ready === true) {
            setConnectionState("ready", `Backend at ${API_HOST_LABEL}: READY`);
        } else {
            const reasons = safeArray(latestReadyState.reasons);
            const suffix = reasons.length ? ` (${reasons.join("; ")})` : "";
            setConnectionState("degraded", `Backend at ${API_HOST_LABEL}: DEGRADED${suffix}`);
        }
    } catch (error) {
        latestReadyState = null;
        latestDiagnosticsState = null;
        setConnectionState("down", `Backend at ${API_HOST_LABEL}: DOWN`);
    }

    renderLayerStatusPanel();
    renderArchitectureDiagram(lastClassificationResponse);
}

function updateResults(data) {
    resultsDisplay.classList.remove("hidden");

    const classification = data.classification;
    const badgeClass = `badge-${classification.toLowerCase().replace("_", "-")}`;
    const observability = data.observability || {};
    const executed = safeArray(observability.executed_layers);
    const skipped = safeArray(observability.skipped_layers);
    const layerErrors = safeArray(observability.layer_errors);

    let html = `
        <div class="classification-badge ${badgeClass}">${classification}</div>
        <div style="font-size: 1.1rem; line-height: 1.4;">
            Analysis indicates this content is <strong>${classification.replace("_", " ")}</strong>.
        </div>
        <div class="details">
    `;

    if (data.lexicon && (data.lexicon.flagged || data.lexicon.total_score > 0)) {
        if (data.lexicon.high_risk_short_circuit) {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--high-red); font-weight: 600;">SHORT-CIRCUIT (Score: ${data.lexicon.total_score})</span></div>`;
        } else if (data.lexicon.flagged) {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--high-red); font-weight: 600;">FLAGGED (Score: ${data.lexicon.total_score})</span></div>`;
        } else {
            html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--safe-green); font-weight: 600;">INFO HIT (Score: ${data.lexicon.total_score})</span></div>`;
        }
        data.lexicon.hits.forEach((hit) => {
            html += `<div style="font-size: 0.75rem; color: #555; margin-left: 12px; margin-top: -8px; margin-bottom: 8px;">&bull; Match: "${escapeHtml(hit.matched_text)}" (${escapeHtml(hit.rule)}) - Score: ${hit.score}</div>`;
        });
    } else {
        html += `<div class="detail-item"><span>Lexicon Filter:</span> <span style="color: var(--safe-green);">CLEAN (Score: 0)</span></div>`;
    }

    if (data.model1) {
        html += `<div class="detail-item"><span>NLP Model 1 (Public/Private):</span> <span>${formatPercent(data.model1.confidence)} ${escapeHtml(data.model1.label)}</span></div>`;
    }

    if (data.model2) {
        html += `<div class="detail-item"><span>NLP Model 2 (Severity):</span> <span>${formatPercent(data.model2.confidence)} ${escapeHtml(data.model2.label.replace("_", " "))}</span></div>`;
    }

    if (data.clustering) {
        html += `<div class="detail-item"><span>Clustering:</span> <span>${data.clustering.is_anomaly ? "ANOMALY" : "NORMAL"} (${formatNumber(data.clustering.anomaly_score)})</span></div>`;
    }

    if (data.mosaic) {
        if (data.mosaic.escalated) {
            html += `<div class="detail-item"><span>Mosaic Aggregation:</span> <span style="color: var(--high-red); font-weight: 600;">ESCALATED (${data.mosaic.count} recent hits)</span></div>`;
        } else {
            html += `<div class="detail-item"><span>Mosaic Aggregation:</span> <span style="color: var(--low-yellow);">TRACKED (${data.mosaic.count} recent hits)</span></div>`;
        }
    }

    if (data.regression) {
        html += `<div class="detail-item"><span>Regression (Final Score):</span> <span>${data.regression.risk_score.toFixed(3)}</span></div>`;
        if (data.regression.reasoning) {
            html += `<div style="font-size: 0.75rem; color: #555; margin-left: 12px; margin-top: -8px; margin-bottom: 8px;">&bull; ${escapeHtml(data.regression.reasoning)}</div>`;
        }
    }

    html += `<div class="detail-item"><span>Active Pipeline:</span> <span>${escapeHtml(safeArray(observability.active_pipeline).join(" -> ") || "Unavailable")}</span></div>`;
    html += `<div class="detail-item"><span>Executed Layers:</span> <span>${escapeHtml(executed.join(", ") || "none")}</span></div>`;
    html += `<div class="detail-item"><span>Skipped Layers:</span> <span>${escapeHtml(skipped.join(", ") || "none")}</span></div>`;
    html += `<div class="detail-item"><span>Degraded:</span> <span>${observability.degraded ? "yes" : "no"}</span></div>`;

    if (layerErrors.length) {
        layerErrors.forEach((item) => {
            html += `<div class="detail-item"><span>Layer Error (${escapeHtml(item.layer)}):</span> <span>${escapeHtml(item.phase)} - ${escapeHtml(item.message)}</span></div>`;
        });
    }

    html += `</div>`;
    resultsDisplay.innerHTML = html;
}

function buildTraceContext(responseData) {
    const backendContext = buildBackendContext(latestReadyState, latestDiagnosticsState);
    const observability = responseData && responseData.observability ? responseData.observability : {};
    const activePipeline = safeArray(observability.active_pipeline).length ? observability.active_pipeline : backendContext.pipeline;
    const responseErrors = new Map();
    safeArray(observability.layer_errors).forEach((item) => {
        if (item && item.layer && !responseErrors.has(item.layer)) {
            responseErrors.set(item.layer, item);
        }
    });

    return {
        responseData,
        backendContext,
        activePipeline,
        executed: new Set(safeArray(observability.executed_layers)),
        skipped: new Set(safeArray(observability.skipped_layers)),
        responseErrors,
        degraded: Boolean(observability.degraded),
    };
}

function classifyRegressionState(responseData) {
    if (!responseData || !responseData.regression) {
        return {
            kind: "waiting",
            summary: "Unavailable",
            detail: "Regression response not present",
        };
    }

    const score = Number(responseData.regression.risk_score || 0);
    if (score >= 0.7 || responseData.classification === "HIGH_RISK") {
        return {
            kind: "danger",
            summary: `High ${score.toFixed(2)}`,
            detail: "Final score indicates high risk",
        };
    }
    if (score >= 0.4 || responseData.classification === "LOW_RISK") {
        return {
            kind: "warning",
            summary: `Low ${score.toFixed(2)}`,
            detail: "Final score indicates low risk",
        };
    }
    return {
        kind: "success",
        summary: `Safe ${score.toFixed(2)}`,
        detail: "Final score indicates safe content",
    };
}

function inferSkipReason(layer, traceContext) {
    const responseData = traceContext.responseData;
    const responseErrors = traceContext.responseErrors;

    if (!responseData) {
        return "No request yet";
    }

    if (responseData.lexicon && responseData.lexicon.high_risk_short_circuit) {
        return "Skipped after lexicon short-circuit";
    }

    if (layer === "model2") {
        if (responseErrors.has("model1")) {
            return "Blocked because Model 1 failed";
        }
        if (responseData.model1 && responseData.model1.label === "safe") {
            return "Gated because Model 1 returned safe";
        }
        return "Severity model not reached";
    }

    if (layer === "mosaic") {
        if (responseErrors.has("model1") || responseErrors.has("model2")) {
            return "Upstream classifier unavailable";
        }
        if (!responseData.entity_id && !(responseData.lexicon && safeArray(responseData.lexicon.restricted_entities).length)) {
            return "No entity available for aggregation";
        }
        return "Aggregation not applicable in this path";
    }

    if (layer === "clustering" && responseErrors.has("embedding")) {
        return "Skipped because embeddings were unavailable";
    }

    return "Skipped in this request path";
}

function getLayerTraceState(layer, traceContext) {
    const responseData = traceContext.responseData;
    const backendContext = traceContext.backendContext;

    if (!traceContext.activePipeline.includes(layer)) {
        return {
            kind: "inactive",
            summary: "Inactive",
            detail: "Not configured in the active pipeline",
        };
    }

    if (traceContext.responseErrors.has(layer)) {
        const error = traceContext.responseErrors.get(layer);
        return {
            kind: error.phase === "runtime" ? "danger" : "unavailable",
            summary: error.phase === "runtime" ? "Runtime error" : "Unavailable",
            detail: shortText(error.message || ""),
        };
    }

    if (traceContext.executed.has(layer)) {
        if (layer === "lexicon") {
            if (responseData.lexicon && responseData.lexicon.high_risk_short_circuit) {
                return {
                    kind: "danger",
                    summary: "Short-circuit",
                    detail: `HIGH_RISK at score ${responseData.lexicon.total_score}`,
                };
            }
            if (responseData.lexicon && responseData.lexicon.flagged) {
                return {
                    kind: "warning",
                    summary: "Flagged",
                    detail: `Score ${responseData.lexicon.total_score}`,
                };
            }
            return {
                kind: "success",
                summary: "Clean",
                detail: `Score ${responseData.lexicon ? responseData.lexicon.total_score : 0}`,
            };
        }

        if (layer === "embedding") {
            return {
                kind: "success",
                summary: "Executed",
                detail: "Embeddings generated successfully",
            };
        }

        if (layer === "clustering") {
            if (responseData.clustering && responseData.clustering.is_anomaly) {
                return {
                    kind: "warning",
                    summary: "Anomaly",
                    detail: `Score ${formatNumber(responseData.clustering.anomaly_score)}`,
                };
            }
            return {
                kind: "success",
                summary: "Normal",
                detail: responseData.clustering ? `Score ${formatNumber(responseData.clustering.anomaly_score)}` : "Executed",
            };
        }

        if (layer === "model1") {
            if (responseData.model1 && responseData.model1.label === "risk") {
                return {
                    kind: "warning",
                    summary: "Risk gate",
                    detail: formatPercent(responseData.model1.confidence),
                };
            }
            return {
                kind: "success",
                summary: "Safe gate",
                detail: responseData.model1 ? formatPercent(responseData.model1.confidence) : "Executed",
            };
        }

        if (layer === "model2") {
            if (responseData.model2 && responseData.model2.label === "high_risk") {
                return {
                    kind: "danger",
                    summary: "HIGH_RISK",
                    detail: formatPercent(responseData.model2.confidence),
                };
            }
            return {
                kind: "warning",
                summary: "LOW_RISK",
                detail: responseData.model2 ? formatPercent(responseData.model2.confidence) : "Executed",
            };
        }

        if (layer === "mosaic") {
            if (responseData.mosaic && responseData.mosaic.escalated) {
                return {
                    kind: "danger",
                    summary: "Escalated",
                    detail: `Count ${responseData.mosaic.count}`,
                };
            }
            return {
                kind: "warning",
                summary: responseData.mosaic ? "Tracked" : "Executed",
                detail: responseData.mosaic ? `Count ${responseData.mosaic.count}` : "Executed",
            };
        }

        if (layer === "regression") {
            return classifyRegressionState(responseData);
        }
    }

    if (traceContext.skipped.has(layer)) {
        return {
            kind: "skipped",
            summary: "Skipped",
            detail: inferSkipReason(layer, traceContext),
        };
    }

    if (responseData) {
        const backendState = getBackendLayerState(layer, backendContext);
        if (backendState.kind === "loaded") {
            return {
                kind: "waiting",
                summary: "Ready",
                detail: "Available but not used in this request path",
            };
        }
        if (backendState.kind === "lazy") {
            return {
                kind: "waiting",
                summary: "Lazy",
                detail: "Waiting for first use",
            };
        }
        if (backendState.kind === "warming") {
            return {
                kind: "waiting",
                summary: "Warming",
                detail: "Still warming after startup",
            };
        }
        if (backendState.kind === "unavailable") {
            return {
                kind: "unavailable",
                summary: "Unavailable",
                detail: backendState.detail,
            };
        }
    }

    const backendState = getBackendLayerState(layer, backendContext);
    if (backendState.kind === "loaded") {
        return {
            kind: "waiting",
            summary: "Loaded",
            detail: "Ready for the first request",
        };
    }
    if (backendState.kind === "warming") {
        return {
            kind: "warming",
            summary: "Warming",
            detail: "Still warming at startup",
        };
    }
    if (backendState.kind === "lazy") {
        return {
            kind: "waiting",
            summary: "Lazy",
            detail: "Configured for lazy loading",
        };
    }
    if (backendState.kind === "unavailable") {
        return {
            kind: "unavailable",
            summary: "Unavailable",
            detail: backendState.detail,
        };
    }
    if (backendState.kind === "configured") {
        return {
            kind: "inactive",
            summary: backendState.label,
            detail: backendState.detail,
        };
    }

    return {
        kind: "waiting",
        summary: "Pending",
        detail: "Waiting for backend state",
    };
}

function getFinalOutputState(traceContext) {
    if (!traceContext.responseData) {
        return {
            kind: "waiting",
            label: "Final Output<br/>Awaiting request",
        };
    }

    const classification = traceContext.responseData.classification || "SAFE";
    if (classification === "HIGH_RISK") {
        return {
            kind: "danger",
            label: "Final Output<br/>HIGH_RISK",
        };
    }
    if (classification === "LOW_RISK") {
        return {
            kind: "warning",
            label: "Final Output<br/>LOW_RISK",
        };
    }
    return {
        kind: "success",
        label: "Final Output<br/>SAFE",
    };
}

function buildNodeLabel(layer, state) {
    return `${LAYER_META[layer].title}<br/>${escapeHtml(state.summary)}${state.detail ? `<br/>${escapeHtml(state.detail)}` : ""}`;
}

function getBlockingLayer(traceContext) {
    const responseData = traceContext.responseData;
    if (!responseData || responseData.classification !== "HIGH_RISK") {
        return null;
    }

    if (responseData.lexicon && responseData.lexicon.high_risk_short_circuit) {
        return "lexicon";
    }
    if (responseData.mosaic && responseData.mosaic.escalated) {
        return "mosaic";
    }
    if (responseData.model2 && responseData.model2.label === "high_risk") {
        return "model2";
    }
    if (responseData.regression && traceContext.executed.has("regression")) {
        return "regression";
    }

    return null;
}

function getVisualNodeKind(layer, state, traceContext, blockingLayer) {
    if (blockingLayer === layer) {
        return "danger";
    }

    if (traceContext.responseErrors.has(layer)) {
        return state.kind;
    }

    if (traceContext.responseData) {
        if (traceContext.executed.has(layer)) {
            return "success";
        }
        return state.kind;
    }

    if (traceContext.activePipeline.includes(layer) && state.kind !== "inactive" && state.kind !== "unavailable") {
        return "success";
    }

    return state.kind;
}

function escapeMermaidLabel(value) {
    return String(value || "").replace(/"/g, '\\"');
}

function nodeIdToLayer(nodeId) {
    return NODE_LAYER_BY_ID[nodeId] || null;
}

function nodeConfigured(nodeId, traceContext) {
    const layer = nodeIdToLayer(nodeId);
    return !layer || traceContext.activePipeline.includes(layer);
}

function nodeExecuted(nodeId, traceContext) {
    const layer = nodeIdToLayer(nodeId);
    return !layer || traceContext.executed.has(layer);
}

function stateKindToEdgeKind(kind) {
    if (kind === "danger" || kind === "warning" || kind === "success" || kind === "waiting" || kind === "skipped" || kind === "inactive" || kind === "unavailable") {
        return kind;
    }
    return "neutral";
}

function finalStateToEdgeKind(finalState) {
    return stateKindToEdgeKind(finalState.kind);
}

function getConfiguredRegressionSourceNode(traceContext) {
    if (!traceContext.activePipeline.includes("regression")) {
        return null;
    }
    if (traceContext.activePipeline.includes("mosaic")) {
        return "L5";
    }
    if (traceContext.activePipeline.includes("model2")) {
        return "L4b";
    }
    if (traceContext.activePipeline.includes("model1")) {
        return "L4";
    }
    if (traceContext.activePipeline.includes("clustering")) {
        return "L3";
    }
    return "L1";
}

function getExecutedRegressionSourceNode(traceContext) {
    if (!traceContext.executed.has("regression")) {
        return null;
    }
    if (traceContext.executed.has("mosaic")) {
        return "L5";
    }
    if (traceContext.executed.has("model2")) {
        return "L4b";
    }
    if (traceContext.executed.has("model1")) {
        return "L4";
    }
    if (traceContext.executed.has("clustering")) {
        return "L3";
    }
    return "L1";
}

function getConfiguredOutputSourceNode(traceContext) {
    if (traceContext.activePipeline.includes("regression")) {
        return "Reg";
    }
    if (traceContext.activePipeline.includes("mosaic")) {
        return "L5";
    }
    if (traceContext.activePipeline.includes("model2")) {
        return "L4b";
    }
    if (traceContext.activePipeline.includes("model1")) {
        return "L4";
    }
    return "L1";
}

function getExecutedOutputSourceNode(traceContext) {
    if (!traceContext.responseData) {
        return getConfiguredOutputSourceNode(traceContext);
    }
    if (traceContext.executed.has("regression")) {
        return "Reg";
    }
    if (traceContext.responseData.lexicon && traceContext.responseData.lexicon.high_risk_short_circuit) {
        return "L1";
    }
    if (traceContext.executed.has("mosaic")) {
        return "L5";
    }
    if (traceContext.executed.has("model2")) {
        return "L4b";
    }
    if (traceContext.executed.has("model1")) {
        return "L4";
    }
    return "L1";
}

function regressionSourceNodeToEdgeKey(nodeId) {
    return {
        L1: "lexicon_regression",
        L3: "clustering_regression",
        L4: "model1_regression",
        L4b: "model2_regression",
        L5: "mosaic_regression",
    }[nodeId] || null;
}

function outputSourceNodeToEdgeKey(nodeId) {
    return {
        L1: "lexicon_output",
        L4: "model1_output",
        L4b: "model2_output",
        L5: "mosaic_output",
        Reg: "regression_output",
    }[nodeId] || null;
}

function getPathPreviewText(traceContext) {
    if (!traceContext.responseData) {
        const preview = traceContext.activePipeline.length ? traceContext.activePipeline.join(" -> ") : "no active layers";
        return `Configured path preview: ${preview}. Green edges indicate the current configured route; dashed gray edges are inactive.`;
    }

    const executedText = traceContext.executed.size ? [...traceContext.executed].join(" -> ") : "none";
    return `Path update: green edges show the executed route for this request (${executedText} -> output). If the request is blocked, the blocking layer turns red. Dashed gray edges were inactive or skipped.`;
}

function buildEdgeStateMap(traceContext, nodeStates, finalState) {
    const edgeStates = {};
    const blockingLayer = getBlockingLayer(traceContext);
    const blockingNodeId = blockingLayer ? LAYER_META[blockingLayer].id : null;

    DIAGRAM_EDGES.forEach((edge) => {
        edgeStates[edge.key] = {
            kind: "inactive",
            label: edge.label,
        };
    });

    if (!traceContext.responseData) {
        const plannedRegressionSource = getConfiguredRegressionSourceNode(traceContext);
        const plannedOutputSource = getConfiguredOutputSourceNode(traceContext);

        DIAGRAM_EDGES.forEach((edge) => {
            const sourceReady = nodeConfigured(edge.from, traceContext);
            const targetReady = nodeConfigured(edge.to, traceContext);

            if (edge.key === "ingress_lexicon") {
                edgeStates[edge.key] = { kind: "success", label: edge.label };
                return;
            }

            if (edge.key === "regression_output") {
                edgeStates[edge.key] = {
                    kind: plannedOutputSource === "Reg" ? "success" : "inactive",
                    label: edge.label,
                };
                return;
            }

            if (edge.to === "Out") {
                edgeStates[edge.key] = {
                    kind: outputSourceNodeToEdgeKey(plannedOutputSource) === edge.key ? "success" : "inactive",
                    label: edge.label,
                };
                return;
            }

            if (edge.to === "Reg") {
                edgeStates[edge.key] = {
                    kind: regressionSourceNodeToEdgeKey(plannedRegressionSource) === edge.key ? "success" : "inactive",
                    label: edge.label,
                };
                return;
            }

            edgeStates[edge.key] = {
                kind: sourceReady && targetReady ? "success" : "inactive",
                label: edge.label,
            };
        });

        return edgeStates;
    }

    const activeEdges = new Set(["ingress_lexicon"]);

    if (traceContext.executed.has("embedding")) {
        activeEdges.add("lexicon_embedding");
    } else if (traceContext.skipped.has("embedding")) {
        edgeStates.lexicon_embedding = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "lexicon_embedding").label };
    }

    if (traceContext.executed.has("clustering")) {
        activeEdges.add("embedding_clustering");
    } else if (traceContext.skipped.has("clustering")) {
        edgeStates.embedding_clustering = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "embedding_clustering").label };
    }

    if (traceContext.executed.has("model1")) {
        activeEdges.add("embedding_model1");
    } else if (traceContext.skipped.has("model1")) {
        edgeStates.embedding_model1 = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "embedding_model1").label };
    }

    if (traceContext.executed.has("model2")) {
        activeEdges.add("model1_model2");
    } else if (traceContext.skipped.has("model2")) {
        edgeStates.model1_model2 = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "model1_model2").label };
    }

    if (traceContext.executed.has("mosaic")) {
        if (traceContext.executed.has("clustering")) {
            activeEdges.add("clustering_mosaic");
        }
        if (traceContext.executed.has("model2")) {
            activeEdges.add("model2_mosaic");
        } else if (traceContext.executed.has("model1")) {
            activeEdges.add("model1_mosaic");
        }
    } else if (traceContext.skipped.has("mosaic")) {
        if (traceContext.executed.has("clustering")) {
            edgeStates.clustering_mosaic = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "clustering_mosaic").label };
        }
        if (traceContext.executed.has("model2")) {
            edgeStates.model2_mosaic = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "model2_mosaic").label };
        } else if (traceContext.executed.has("model1")) {
            edgeStates.model1_mosaic = { kind: "skipped", label: DIAGRAM_EDGES.find((edge) => edge.key === "model1_mosaic").label };
        }
    }

    const regressionSource = getExecutedRegressionSourceNode(traceContext);
    if (regressionSource) {
        const regressionEdgeKey = regressionSourceNodeToEdgeKey(regressionSource);
        if (regressionEdgeKey) {
            activeEdges.add(regressionEdgeKey);
        }
        activeEdges.add("regression_output");
    }

    const outputSource = getExecutedOutputSourceNode(traceContext);
    if (!traceContext.executed.has("regression")) {
        const outputEdgeKey = outputSourceNodeToEdgeKey(outputSource);
        if (outputEdgeKey) {
            activeEdges.add(outputEdgeKey);
        }
    }

    if (traceContext.responseData.lexicon && traceContext.responseData.lexicon.high_risk_short_circuit) {
        if (traceContext.executed.has("regression")) {
            activeEdges.add("lexicon_regression");
        } else {
            activeEdges.add("lexicon_output");
        }
    }

    DIAGRAM_EDGES.forEach((edge) => {
        const targetLayer = nodeIdToLayer(edge.to);
        const targetState = targetLayer ? nodeStates[targetLayer] : null;

        if (activeEdges.has(edge.key)) {
            let kind = "success";
            if (blockingNodeId && edge.from === blockingNodeId) {
                kind = "danger";
            } else if (edge.to === "Out" && finalState.kind === "danger" && (!blockingNodeId || edge.from === blockingNodeId)) {
                kind = "danger";
            }
            edgeStates[edge.key] = {
                kind,
                label: edge.label,
            };
            return;
        }

        if (targetLayer && traceContext.responseErrors.has(targetLayer)) {
            edgeStates[edge.key] = { kind: "unavailable", label: edge.label };
            return;
        }

        if (edge.to === "Reg" && traceContext.responseErrors.has("regression")) {
            edgeStates[edge.key] = { kind: "unavailable", label: edge.label };
            return;
        }

        const sourceReady = nodeConfigured(edge.from, traceContext);
        const targetReady = nodeConfigured(edge.to, traceContext);
        edgeStates[edge.key] = {
            kind: sourceReady && targetReady ? "inactive" : "inactive",
            label: edge.label,
        };
    });

    return edgeStates;
}

function renderTraceSummary(responseData, traceContext) {
    if (!traceSummary) {
        return;
    }

    if (!responseData) {
        const warming = safeArray(latestReadyState && latestReadyState.warming_required_layers);
        const waitingText = warming.length
            ? `Currently warming: ${warming.join(", ")}.`
            : "The diagram is showing backend pipeline readiness from /ready and /diagnostics.";
        traceSummary.innerHTML = `
            <span class="trace-chip trace-chip-neutral">No classification yet</span>
            <span class="trace-copy">${escapeHtml(waitingText)}</span>
            <span class="trace-copy">${escapeHtml(getPathPreviewText(traceContext))}</span>
        `;
        return;
    }

    const chips = [];
    if (responseData.classification === "HIGH_RISK") {
        chips.push('<span class="trace-chip trace-chip-high">HIGH_RISK</span>');
    } else if (responseData.classification === "LOW_RISK") {
        chips.push('<span class="trace-chip trace-chip-low">LOW_RISK</span>');
    } else {
        chips.push('<span class="trace-chip trace-chip-safe">SAFE</span>');
    }

    if (traceContext.degraded) {
        chips.push('<span class="trace-chip trace-chip-high">Degraded response</span>');
    } else {
        chips.push('<span class="trace-chip trace-chip-safe">Full response path</span>');
    }

    chips.push(`<span class="trace-chip trace-chip-neutral">Executed: ${traceContext.executed.size}</span>`);
    chips.push(`<span class="trace-chip trace-chip-neutral">Skipped: ${traceContext.skipped.size}</span>`);
    chips.push(`<span class="trace-chip trace-chip-neutral">Errors: ${traceContext.responseErrors.size}</span>`);

    const executedText = traceContext.executed.size ? [...traceContext.executed].join(" -> ") : "none";
    const skippedText = traceContext.skipped.size ? [...traceContext.skipped].join(", ") : "none";
    const errorText = traceContext.responseErrors.size
        ? [...traceContext.responseErrors.values()].map((item) => `${item.layer}: ${item.message}`).join(" | ")
        : "none";

    traceSummary.innerHTML = `
        ${chips.join("")}
        <span class="trace-copy">Executed path: ${escapeHtml(executedText)}.</span>
        <span class="trace-copy">Skipped: ${escapeHtml(skippedText)}.</span>
        <span class="trace-copy">Layer errors: ${escapeHtml(errorText)}.</span>
        <span class="trace-copy">${escapeHtml(getPathPreviewText(traceContext))}</span>
    `;
}

async function renderArchitectureDiagram(responseData) {
    const traceContext = buildTraceContext(responseData);
    renderTraceSummary(responseData, traceContext);

    const nodeStates = {};
    CANONICAL_LAYER_ORDER.forEach((layer) => {
        nodeStates[layer] = getLayerTraceState(layer, traceContext);
    });
    const finalState = getFinalOutputState(traceContext);
    const blockingLayer = getBlockingLayer(traceContext);
    const visualNodeKinds = {};
    CANONICAL_LAYER_ORDER.forEach((layer) => {
        visualNodeKinds[layer] = getVisualNodeKind(layer, nodeStates[layer], traceContext, blockingLayer);
    });
    const edgeStates = buildEdgeStateMap(traceContext, nodeStates, finalState);
    const edgeLines = DIAGRAM_EDGES.map((edge) => {
        const label = escapeMermaidLabel(edge.label);
        if (edge.dashed) {
            return `    ${edge.from} -. "${label}" .-> ${edge.to}`;
        }
        return `    ${edge.from} -- "${label}" --> ${edge.to}`;
    }).join("\n");
    const linkStyles = DIAGRAM_EDGES.map((edge, index) => {
        const style = EDGE_STYLE_BY_KIND[edgeStates[edge.key].kind] || EDGE_STYLE_BY_KIND.neutral;
        return `    linkStyle ${index} ${style}`;
    }).join("\n");

    const mermaidDef = `
flowchart TD
    classDef success fill:#dcfce7,stroke:#16a34a,stroke-width:1px,color:#166534;
    classDef warning fill:#fef3c7,stroke:#d97706,stroke-width:1px,color:#92400e;
    classDef danger fill:#fee2e2,stroke:#dc2626,stroke-width:1px,color:#991b1b;
    classDef waiting fill:#eff6ff,stroke:#60a5fa,stroke-width:1px,color:#1d4ed8;
    classDef skipped fill:#f3f4f6,stroke:#9ca3af,stroke-width:1px,color:#6b7280,stroke-dasharray: 5 5;
    classDef inactive fill:#fafafa,stroke:#d1d5db,stroke-width:1px,color:#9ca3af,stroke-dasharray: 3 3;
    classDef unavailable fill:#fff1f2,stroke:#fb7185,stroke-width:1px,color:#be123c,stroke-dasharray: 6 4;
    classDef neutral fill:#ffffff,stroke:#333333,stroke-width:1px,color:#111111;

    In["Ingestion<br/>Request entrypoint"]
    L1["${buildNodeLabel("lexicon", nodeStates.lexicon)}"]
    L2["${buildNodeLabel("embedding", nodeStates.embedding)}"]
    L3["${buildNodeLabel("clustering", nodeStates.clustering)}"]
    L4["${buildNodeLabel("model1", nodeStates.model1)}"]
    L4b["${buildNodeLabel("model2", nodeStates.model2)}"]
    L5["${buildNodeLabel("mosaic", nodeStates.mosaic)}"]
    Reg["${buildNodeLabel("regression", nodeStates.regression)}"]
    Out["${finalState.label}"]

${edgeLines}

    class In neutral;
    class L1 ${visualNodeKinds.lexicon};
    class L2 ${visualNodeKinds.embedding};
    class L3 ${visualNodeKinds.clustering};
    class L4 ${visualNodeKinds.model1};
    class L4b ${visualNodeKinds.model2};
    class L5 ${visualNodeKinds.mosaic};
    class Reg ${visualNodeKinds.regression};
    class Out ${finalState.kind};
${linkStyles}
`;

    try {
        const { svg } = await mermaid.render(`mermaid-chart-${Date.now().toString()}`, mermaidDef);
        architectureDiagram.innerHTML = svg;
    } catch (error) {
        console.error(error);
        architectureDiagram.innerHTML = '<span class="diagram-placeholder" style="color: var(--high-red);">Failed to render classification trace.</span>';
    }
}

function updateDebugView(reqBody, responseData) {
    const curl = `curl -X POST "${API_BASE}/classify" \\\n     -H "Content-Type: application/json" \\\n     -d '${JSON.stringify(reqBody).replace(/'/g, "'\\''")}'`;
    const jsonResponse = JSON.stringify(responseData, null, 2);

    const curlCode = document.getElementById("curl-code");
    const jsonCode = document.getElementById("json-code");

    if (curlCode && jsonCode) {
        curlCode.textContent = curl;
        jsonCode.textContent = jsonResponse;

        curlCode.removeAttribute("data-highlighted");
        jsonCode.removeAttribute("data-highlighted");

        hljs.highlightElement(curlCode);
        hljs.highlightElement(jsonCode);
    }

    renderArchitectureDiagram(responseData);
}

async function handleClassify() {
    const text = analyzeInput.value.trim();
    if (!text) {
        resultsDisplay.classList.remove("hidden");
        resultsDisplay.innerHTML = '<div style="color: var(--high-red);">Error: Classification input must contain non-whitespace printable content.</div>';
        renderArchitectureDiagram(null);
        return;
    }

    const entityId = entityInput ? entityInput.value.trim() : "";

    classifyBtn.disabled = true;
    classifyBtn.textContent = "Analyzing...";

    try {
        const reqBody = {
            text: validateScreeningText(text, "Classification input"),
        };
        if (entityId) {
            reqBody.entity_id = entityId;
        }

        const response = await fetch(`${API_BASE}/classify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(reqBody),
        });

        if (!response.ok) {
            let message = "API request failed";
            try {
                const payload = await response.json();
                const parsedDetail = extractApiErrorDetail(payload);
                if (parsedDetail) {
                    message = parsedDetail;
                }
            } catch (error) {
                // Keep generic message.
            }
            throw new Error(`${message} (HTTP ${response.status})`);
        }

        const data = await response.json();
        lastClassificationResponse = data;
        updateResults(data);
        updateDebugView(reqBody, data);
    } catch (error) {
        lastClassificationResponse = null;
        resultsDisplay.classList.remove("hidden");
        resultsDisplay.innerHTML = `<div style="color: var(--high-red);">Error: ${escapeHtml(error.message)}. Check the API target, readiness state, and layer load status.</div>`;
        renderArchitectureDiagram(null);
    } finally {
        classifyBtn.disabled = false;
        classifyBtn.textContent = "Classify Text";
    }
}

classifyBtn.addEventListener("click", handleClassify);

analyzeInput.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        handleClassify();
    }
});

refreshBackendSnapshot();
setInterval(refreshBackendSnapshot, 10000);
