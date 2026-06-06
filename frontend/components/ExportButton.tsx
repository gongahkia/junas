"use client";

import { useState } from "react";
import { apiUrl } from "../lib/api-client";

type ReceiptProps = {
  kind: "receipt";
  runId: string;
};

type SessionMessage = { role: string; content: string; timestamp?: number };
type SessionProps = {
  kind: "session";
  sessionId: string;
  title?: string;
  messages: SessionMessage[];
  createdAt?: string;
};

type Props = (ReceiptProps | SessionProps) & {
  apiKey?: string;
  label?: string;
  className?: string;
};

export default function ExportButton(props: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = props.label ?? "Export .docx";

  const triggerDownload = (blob: Blob, fallbackName: string, contentDisposition: string | null) => {
    const match = contentDisposition?.match(/filename="?([^";]+)"?/i);
    const filename = match?.[1] ?? fallbackName;
    const href = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(href);
  };

  const exportReceipt = async (runId: string) => {
    const url = apiUrl(`/exports/receipt/${encodeURIComponent(runId)}.docx`);
    const headers: Record<string, string> = {};
    if (props.apiKey) headers["X-API-Key"] = props.apiKey;
    const resp = await fetch(url, { headers });
    if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
    const blob = await resp.blob();
    triggerDownload(blob, `junas-receipt-${runId}.docx`, resp.headers.get("Content-Disposition"));
  };

  const exportSession = async (p: SessionProps) => {
    const url = apiUrl(`/exports/session/${encodeURIComponent(p.sessionId)}.docx`);
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (props.apiKey) headers["X-API-Key"] = props.apiKey;
    const body = JSON.stringify({
      session_id: p.sessionId,
      title: p.title,
      created_at: p.createdAt,
      messages: p.messages,
    });
    const resp = await fetch(url, { method: "POST", headers, body });
    if (!resp.ok) throw new Error(`Export failed (${resp.status})`);
    const blob = await resp.blob();
    triggerDownload(blob, `junas-session-${p.sessionId}.docx`, resp.headers.get("Content-Disposition"));
  };

  const onClick = async () => {
    setError(null);
    setBusy(true);
    try {
      if (props.kind === "receipt") await exportReceipt(props.runId);
      else await exportSession(props);
    } catch (err: any) {
      setError(err?.message || "Export failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}>
      <button
        type="button"
        onClick={onClick}
        disabled={busy}
        className={props.className}
        style={{
          border: "1px solid #d6d3d1",
          background: busy ? "#f5f5f4" : "#ffffff",
          color: "#1c1917",
          fontSize: "0.78rem",
          fontWeight: 600,
          padding: "0.35rem 0.7rem",
          borderRadius: "0.35rem",
          cursor: busy ? "wait" : "pointer",
        }}
        title="Download as Microsoft Word document"
      >
        {busy ? "Exporting..." : label}
      </button>
      {error ? (
        <span style={{ color: "#b91c1c", fontSize: "0.72rem" }}>{error}</span>
      ) : null}
    </span>
  );
}
