"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getContractBatch, type BatchJob } from "../../../lib/api-client";

export default function BatchDetailPage({ params }: { params: { batchId: string } }) {
  const [batch, setBatch] = useState<BatchJob | null>(null);

  useEffect(() => {
    void getContractBatch(params.batchId).then(setBatch);
  }, [params.batchId]);

  if (!batch) {
    return (
      <main>
        <Link href="/batch-analysis" style={{ color: "#1d4ed8", fontSize: "0.85rem" }}>Back to batch analysis</Link>
        <p className="meta-line" style={{ marginTop: "1rem" }}>Loading batch...</p>
      </main>
    );
  }

  return (
    <main>
      <Link href="/batch-analysis" style={{ color: "#1d4ed8", fontSize: "0.85rem" }}>Back to batch analysis</Link>
      <h2 style={{ marginTop: "0.75rem" }}>Batch Drill-down</h2>
      <p className="meta-line">Batch {batch.id} · {batch.status} · {batch.completed}/{batch.total} complete</p>
      <div style={{ display: "grid", gap: "1rem", marginTop: "1rem" }}>
        {batch.results.map((result) => (
          <section key={result.document_id} id={result.document_id} className="result-card">
            <div className="result-header">
              <strong>{result.file_name}</strong>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase" }}>{result.status}</span>
            </div>
            {result.error && <p style={{ color: "#b91c1c" }}>{result.error}</p>}
            {result.summary && <p className="meta-line" style={{ margin: "0.35rem 0" }}>{result.summary}</p>}

            <h3 style={{ fontSize: "0.95rem", margin: "0.75rem 0 0.35rem" }}>Reasoning</h3>
            <pre style={{ whiteSpace: "pre-wrap", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "0.4rem", padding: "0.6rem", fontSize: "0.78rem" }}>{result.reasoning || "No reasoning available."}</pre>

            <h3 style={{ fontSize: "0.95rem", margin: "0.75rem 0 0.35rem" }}>Flagged Clauses</h3>
            {result.flagged_clauses.length === 0 ? (
              <p className="meta-line">No flagged clauses.</p>
            ) : (
              <ul className="results-list">
                {result.flagged_clauses.map((flag, index) => (
                  <li key={index} className="result-card">
                    <strong>Sentence {flag.index}</strong>
                    <p style={{ margin: "0.25rem 0", whiteSpace: "pre-wrap" }}>{flag.text}</p>
                    <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: "0.75rem" }}>{JSON.stringify(flag.unfair_categories || [], null, 2)}</pre>
                  </li>
                ))}
              </ul>
            )}

            <h3 style={{ fontSize: "0.95rem", margin: "0.75rem 0 0.35rem" }}>Classified Clauses</h3>
            <div style={{ display: "grid", gap: "0.45rem" }}>
              {result.clauses.map((clause, index) => (
                <div key={index} style={{ border: "1px solid #e2e8f0", borderRadius: "0.4rem", padding: "0.55rem" }}>
                  <strong>{clause.clause_type || "Unknown"}</strong>
                  <span className="meta-line" style={{ marginLeft: "0.35rem" }}>{Number(clause.confidence || 0).toFixed(2)}</span>
                  <p style={{ margin: "0.3rem 0 0", whiteSpace: "pre-wrap", fontSize: "0.82rem" }}>{clause.text}</p>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
