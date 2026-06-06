"use client";
import { useState } from "react";
import { searchSSO, searchCommonLII } from "../../lib/api-client";

type Tab = "sso" | "commonlii";
type Result = { title: string; url: string; snippet: string; source: string };
type SourceEntry = {
  id: string;
  name: string;
  url: string;
  scope: string;
  attribution: string;
  crawlDelay: string;
};

const LEGAL_SOURCES: SourceEntry[] = [
  {
    id: "sso",
    name: "Singapore Statutes Online",
    url: "https://sso.agc.gov.sg",
    scope: "Legislation and subsidiary legislation from AGC's public SSO service.",
    attribution: "Attribution required under the SSO Terms of Use.",
    crawlDelay: "crawl_delay: 3s",
  },
  {
    id: "commonlii",
    name: "CommonLII Singapore",
    url: "http://www.commonlii.org/sg/",
    scope: "Singapore case law index used for public case-law retrieval.",
    attribution: "Attribution required to CommonLII and the original court source.",
    crawlDelay: "crawl_delay: 5s",
  },
];

export default function LegalSourcesPage() {
  const [tab, setTab] = useState<Tab>("sso");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true); setSearched(true);
    try {
      const data = tab === "sso" ? await searchSSO(query) : await searchCommonLII(query);
      setResults(Array.isArray(data) ? data : []);
    } catch { setResults([]); }
    setLoading(false);
  };

  return (
    <div>
      <h2>Legal Sources</h2>
      <p className="meta-line">Search Singapore Statutes Online (SSO) and CommonLII case law databases directly</p>
      <ul className="results-list" style={{ marginBottom: "1rem" }}>
        {LEGAL_SOURCES.map((source) => (
          <li key={source.id} className="result-card">
            <div className="result-header">
              <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ color: "#1d4ed8", fontWeight: 600, textDecoration: "none" }}>{source.name}</a>
              <span className="badge muted">{source.id.toUpperCase()}</span>
            </div>
            <p className="meta-line" style={{ margin: "0.2rem 0 0" }}>{source.scope}</p>
            <p className="meta-line" style={{ margin: "0.1rem 0 0", fontSize: "0.75rem" }}>{source.attribution} {source.crawlDelay}.</p>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.75rem" }}>
        {(["sso", "commonlii"] as Tab[]).map((t) => (
          <button key={t} type="button" onClick={() => { setTab(t); setResults([]); setSearched(false); }} style={{ padding: "0.35rem 0.7rem", borderRadius: "0.5rem", border: tab === t ? "2px solid #1d4ed8" : "1px solid #94a3b8", background: tab === t ? "#dbeafe" : "#f8fafc", cursor: "pointer", fontWeight: tab === t ? 700 : 400, fontSize: "0.85rem" }}>
            {t === "sso" ? "SSO (Statutes)" : "CommonLII (Cases)"}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1rem" }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder={tab === "sso" ? "Search Singapore statutes..." : "Search Singapore case law..."} style={{ flex: 1, padding: "0.5rem", borderRadius: "0.5rem", border: "1px solid #94a3b8", font: "inherit" }} />
        <button type="button" onClick={search} disabled={loading} style={{ padding: "0.5rem 1rem", borderRadius: "0.5rem", border: "none", background: "#0f172a", color: "#fff", cursor: loading ? "not-allowed" : "pointer", font: "inherit" }}>{loading ? "..." : "Search"}</button>
      </div>
      {searched && results.length === 0 && !loading && <p className="meta-line">No results found.</p>}
      <ul className="results-list">
        {results.map((r, i) => (
          <li key={i} className="result-card">
            <div className="result-header">
              <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "#1d4ed8", fontWeight: 600, textDecoration: "none" }}>{r.title}</a>
              <span className="badge muted">{r.source}</span>
            </div>
            {r.snippet && <p className="meta-line" style={{ margin: "0.2rem 0 0" }}>{r.snippet}</p>}
            <p className="meta-line" style={{ margin: "0.1rem 0 0", fontSize: "0.75rem" }}>{r.url}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
