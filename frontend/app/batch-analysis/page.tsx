"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  cancelContractBatch,
  contractBatchEventsUrl,
  createContractBatch,
  getContractBatch,
  parseDocument,
  type BatchJob,
  type BatchResult,
} from "../../lib/api-client";

type SortKey = "file_name" | "status" | "summary";
type SortDir = "asc" | "desc";
type LocalFile = { id: string; file: File; status: "queued" | "parsing" | "ready" | "error"; error?: string };

function fileId(file: File, index: number): string {
  return `${file.name.replace(/[^a-z0-9_.-]+/gi, "-")}-${file.size}-${index}`;
}

function statusColor(status: string): string {
  if (status === "done" || status === "completed") return "#16a34a";
  if (status === "error") return "#dc2626";
  if (status === "running") return "#d97706";
  if (status === "cancelled") return "#64748b";
  return "#94a3b8";
}

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function downloadCsv(batch: BatchJob) {
  const rows = [
    ["file_name", "status", "summary", "flagged_count", "clause_count", "error"],
    ...batch.results.map((result) => [
      result.file_name,
      result.status,
      result.summary,
      result.flagged_clauses.length,
      result.clauses.length,
      result.error || "",
    ]),
  ];
  const csv = rows.map((row) => row.map(csvEscape).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `junas-batch-${batch.id}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function BatchAnalysisPage() {
  const [files, setFiles] = useState<LocalFile[]>([]);
  const [batch, setBatch] = useState<BatchJob | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("file_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const lastBatchId = localStorage.getItem("junas_last_batch_id");
    if (!lastBatchId) return;
    void getContractBatch(lastBatchId).then((stored) => {
      if (stored) setBatch(stored);
    });
  }, []);

  useEffect(() => () => sourceRef.current?.close(), []);

  const addFiles = (incoming: File[]) => {
    setError("");
    setFiles((prev) => {
      const combined = [...prev, ...incoming].slice(0, 50);
      if (prev.length + incoming.length > 50) setError("50 document cap enforced.");
      return combined.map((entry, index) => entry instanceof File ? { id: fileId(entry, index), file: entry, status: "queued" } : entry);
    });
  };

  const onInputFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) addFiles(Array.from(event.target.files));
    event.target.value = "";
  };

  const parseFile = async (entry: LocalFile): Promise<{ id: string; file_name: string; text: string }> => {
    setFiles((prev) => prev.map((item) => item.id === entry.id ? { ...item, status: "parsing", error: undefined } : item));
    try {
      const text = entry.file.name.endsWith(".txt") || entry.file.name.endsWith(".md")
        ? await entry.file.text()
        : (await parseDocument(entry.file)).text;
      setFiles((prev) => prev.map((item) => item.id === entry.id ? { ...item, status: "ready" } : item));
      return { id: entry.id, file_name: entry.file.name, text };
    } catch (err: any) {
      setFiles((prev) => prev.map((item) => item.id === entry.id ? { ...item, status: "error", error: err?.message || "Parse failed" } : item));
      throw err;
    }
  };

  const attachEvents = (batchId: string) => {
    sourceRef.current?.close();
    const source = new EventSource(contractBatchEventsUrl(batchId));
    source.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.batch) setBatch(payload.batch);
    };
    ["queued", "started", "document_started", "document_completed", "document_error", "completed", "cancelled"].forEach((name) => {
      source.addEventListener(name, (event) => {
        const payload = JSON.parse((event as MessageEvent).data);
        if (payload.batch) setBatch(payload.batch);
        if (name === "completed" || name === "cancelled") {
          setRunning(false);
          source.close();
        }
      });
    });
    source.onerror = () => {
      setRunning(false);
      source.close();
    };
    sourceRef.current = source;
  };

  const runBatch = async () => {
    if (files.length === 0 || running) return;
    setRunning(true);
    setError("");
    try {
      const documents = await Promise.all(files.map(parseFile));
      const created = await createContractBatch(documents);
      if (created.error) throw new Error(created.error);
      setBatch(created);
      localStorage.setItem("junas_last_batch_id", created.id);
      attachEvents(created.id);
    } catch (err: any) {
      setError(err?.message || "Batch failed");
      setRunning(false);
    }
  };

  const cancel = async () => {
    if (!batch || !running) return;
    const cancelled = await cancelContractBatch(batch.id);
    if (!cancelled.error) setBatch(cancelled);
    setRunning(false);
    sourceRef.current?.close();
  };

  const sortedResults = useMemo(() => {
    const rows = [...(batch?.results || [])];
    return rows.sort((a, b) => {
      const av = String(a[sortKey] || "");
      const bv = String(b[sortKey] || "");
      const cmp = av.localeCompare(bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [batch, sortDir, sortKey]);

  const progress = batch ? Math.round((batch.completed / Math.max(batch.total, 1)) * 100) : 0;
  const setSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((dir) => dir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };

  return (
    <main>
      <h2>Batch Document Analysis</h2>
      <p className="meta-line">Upload up to 50 documents for contract classification and flagged-clause review.</p>

      <section
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          addFiles(Array.from(event.dataTransfer.files));
        }}
        style={{ border: "1px dashed #94a3b8", borderRadius: "0.5rem", padding: "1rem", margin: "0.75rem 0", background: "#f8fafc" }}
      >
        <input type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={onInputFiles} />
        <p className="meta-line" style={{ margin: "0.5rem 0 0" }}>{files.length}/50 queued</p>
      </section>

      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center", marginBottom: "0.75rem" }}>
        <button type="button" onClick={runBatch} disabled={running || files.length === 0} style={{ padding: "0.45rem 0.8rem", borderRadius: "0.4rem", border: "none", background: "#0f172a", color: "#fff", cursor: running ? "not-allowed" : "pointer" }}>
          {running ? "Running..." : `Analyze ${files.length} document(s)`}
        </button>
        <button type="button" onClick={cancel} disabled={!running || !batch} style={{ padding: "0.45rem 0.8rem", borderRadius: "0.4rem", border: "1px solid #fecaca", background: "#fff", color: "#b91c1c" }}>Cancel</button>
        <button type="button" onClick={() => batch && downloadCsv(batch)} disabled={!batch?.results.length} style={{ padding: "0.45rem 0.8rem", borderRadius: "0.4rem", border: "1px solid #cbd5e1", background: "#fff" }}>Export CSV</button>
        {batch && <Link href={`/batch-analysis/${encodeURIComponent(batch.id)}`} style={{ fontSize: "0.85rem", color: "#1d4ed8" }}>Open drill-down</Link>}
      </div>

      {error && <p style={{ color: "#b91c1c", fontSize: "0.85rem" }}>{error}</p>}

      {batch && (
        <section style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.35rem" }}>
            <span>Status: <strong>{batch.status}</strong></span>
            <span>{batch.completed}/{batch.total} complete</span>
          </div>
          <div style={{ height: "0.5rem", background: "#e2e8f0", borderRadius: "999px", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${progress}%`, background: statusColor(batch.status), transition: "width 0.2s" }} />
          </div>
        </section>
      )}

      {files.length > 0 && !batch && (
        <ul className="results-list">
          {files.map((entry) => (
            <li key={entry.id} className="result-card">
              <div className="result-header">
                <strong>{entry.file.name}</strong>
                <span style={{ color: statusColor(entry.status), fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase" }}>{entry.status}</span>
              </div>
              {entry.error && <p style={{ color: "#b91c1c", margin: "0.25rem 0 0", fontSize: "0.82rem" }}>{entry.error}</p>}
            </li>
          ))}
        </ul>
      )}

      {batch && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ background: "#f1f5f9" }}>
                <th style={th} onClick={() => setSort("file_name")}>Document</th>
                <th style={th} onClick={() => setSort("status")}>Status</th>
                <th style={th} onClick={() => setSort("summary")}>Summary</th>
                <th style={th}>Flags</th>
                <th style={th}>Clauses</th>
              </tr>
            </thead>
            <tbody>
              {sortedResults.map((result: BatchResult) => (
                <tr key={result.document_id}>
                  <td style={td}>
                    <Link href={`/batch-analysis/${encodeURIComponent(batch.id)}#${encodeURIComponent(result.document_id)}`} style={{ color: "#1d4ed8" }}>{result.file_name}</Link>
                  </td>
                  <td style={{ ...td, color: statusColor(result.status), fontWeight: 700 }}>{result.status}</td>
                  <td style={td}>{result.error || result.summary}</td>
                  <td style={td}>{result.flagged_clauses.length}</td>
                  <td style={td}>{result.clauses.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

const th: React.CSSProperties = { border: "1px solid #cbd5e1", padding: "0.5rem", textAlign: "left", cursor: "pointer" };
const td: React.CSSProperties = { border: "1px solid #e2e8f0", padding: "0.5rem", verticalAlign: "top" };
