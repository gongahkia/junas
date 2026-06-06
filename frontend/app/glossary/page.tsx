"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { listGlossaryJurisdictions, searchGlossary, suggestGlossary } from "../../lib/api-client";

type SearchResult = {
  phrase: string;
  definition_html: string;
  definition_text: string;
  jurisdiction: string;
  domain: string;
  source_title: string;
  source_url: string;
  score: number;
};
type SearchResponse = {
  total: number;
  page: number;
  per_page: number;
  results: SearchResult[];
  aggregations: { jurisdictions: Record<string, number>; domains: Record<string, number> };
};
type JurisdictionsResponse = {
  jurisdictions: Array<{ code: string; name: string; count: number; domains: string[] }>;
};
type SuggestResponse = { suggestions: string[] };

const emptySearch: SearchResponse = {
  total: 0,
  page: 1,
  per_page: 20,
  results: [],
  aggregations: { jurisdictions: {}, domains: {} },
};
const chipButtonStyle = { appearance: "none" as const, cursor: "pointer", fontFamily: "inherit" };

function isJurisdictionsResponse(data: unknown): data is JurisdictionsResponse {
  return typeof data === "object" && data !== null && Array.isArray((data as JurisdictionsResponse).jurisdictions);
}

function apiError(data: unknown): string | null {
  if (typeof data !== "object" || data === null || !("error" in data)) return null;
  const error = (data as { error?: unknown }).error;
  return error ? String(error) : null;
}

export default function GlossaryPage() {
  const [q, setQ] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [domain, setDomain] = useState("");
  const [search, setSearch] = useState<SearchResponse>(emptySearch);
  const [jurisdictions, setJurisdictions] = useState<JurisdictionsResponse>({ jurisdictions: [] });
  const [suggestions, setSuggestions] = useState<SuggestResponse>({ suggestions: [] });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const activeJurisdiction = jurisdiction.toUpperCase();

  useEffect(() => {
    let isActive = true;
    (async () => {
      try {
        const data = await listGlossaryJurisdictions();
        if (!isActive || !isJurisdictionsResponse(data)) return;
        setJurisdictions(data);
      } catch {
        if (isActive) setJurisdictions({ jurisdictions: [] });
      }
    })();
    return () => {
      isActive = false;
    };
  }, []);

  const runSearch = async (nextQ: string, nextJurisdiction = jurisdiction, nextDomain = domain) => {
    const query = nextQ.trim();
    setError(null);

    if (!query) {
      setSearch(emptySearch);
      setSuggestions({ suggestions: [] });
      return;
    }

    setIsLoading(true);
    try {
      const [searchData, suggestionData] = await Promise.all([
        searchGlossary(query, nextJurisdiction.trim(), nextDomain.trim(), 1, 20),
        suggestGlossary(query, 8),
      ]);

      const searchError = apiError(searchData);
      if (searchError) {
        setError(searchError);
        setSearch(emptySearch);
      } else {
        setSearch({ ...emptySearch, ...(searchData as SearchResponse) });
      }

      if (apiError(suggestionData) || !Array.isArray((suggestionData as SuggestResponse | null)?.suggestions)) {
        setSuggestions({ suggestions: [] });
      } else {
        setSuggestions(suggestionData as SuggestResponse);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Glossary search request failed.");
      setSearch(emptySearch);
      setSuggestions({ suggestions: [] });
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await runSearch(q);
  };

  const onJurisdictionClick = async (nextJurisdiction: string) => {
    setJurisdiction(nextJurisdiction);
    await runSearch(q, nextJurisdiction, domain);
  };

  const onSuggestionClick = async (term: string) => {
    setQ(term);
    await runSearch(term);
  };

  const onDomainClick = async (nextDomain: string) => {
    setDomain(nextDomain);
    await runSearch(q, jurisdiction, nextDomain);
  };

  return (
    <section>
      <h2 style={{ marginBottom: "0.25rem" }}>Legal Glossary</h2>
      <p className="meta-line" style={{ marginBottom: "1.25rem" }}>
        Search legal definitions across {jurisdictions.jurisdictions.length || 6} jurisdictions.
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", marginBottom: "1rem" }}>
        <button
          type="button"
          className={`chip ${!jurisdiction ? "chip-active" : ""}`}
          style={chipButtonStyle}
          onClick={() => onJurisdictionClick("")}
        >
          All
        </button>
        {jurisdictions.jurisdictions.map((item) => (
          <button
            key={item.code}
            type="button"
            className={`chip ${activeJurisdiction === item.code.toUpperCase() ? "chip-active" : ""}`}
            style={chipButtonStyle}
            onClick={() => onJurisdictionClick(item.code)}
          >
            {item.name}
          </button>
        ))}
      </div>

      <form method="post" onSubmit={onSubmit} style={{ display: "flex", gap: "0.5rem", marginBottom: "1.25rem" }}>
        <input name="jurisdiction" type="hidden" value={jurisdiction} readOnly />
        <input name="domain" type="hidden" value={domain} readOnly />
        <input
          name="q"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Search for a legal term..."
          style={{
            flex: 1, padding: "0.6rem 0.8rem", borderRadius: "0.5rem", border: "1px solid #D6D3D1",
            fontFamily: "inherit", fontSize: "0.92rem", outline: "none",
          }}
        />
        <button
          type="submit"
          disabled={isLoading}
          style={{
            padding: "0.6rem 1.25rem", borderRadius: "0.5rem", border: "none",
            background: "#1C1917", color: "#FAFAF9", fontFamily: "inherit",
            fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
          }}
        >
          {isLoading ? "Searching..." : "Search"}
        </button>
      </form>

      {error ? (
        <article className="result-card">
          <h3>Search unavailable</h3>
          <p>{error}</p>
        </article>
      ) : null}

      {suggestions.suggestions.length > 0 && (
        <div style={{ marginBottom: "1.25rem" }}>
          <p className="meta-line" style={{ marginBottom: "0.35rem", fontSize: "0.78rem" }}>Did you mean:</p>
          <div className="chip-row">
            {suggestions.suggestions.map((term) => (
              <button
                key={term}
                type="button"
                className="chip"
                style={chipButtonStyle}
                onClick={() => onSuggestionClick(term)}
              >
                {term}
              </button>
            ))}
          </div>
        </div>
      )}

      {q ? (
        <p style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.75rem" }}>
          {search.total > 0 ? `${search.total} result${search.total !== 1 ? "s" : ""} for "${q}"` : `No results for "${q}"`}
        </p>
      ) : null}

      {!q ? (
        <div style={{ textAlign: "center", padding: "3rem 1rem", color: "#A8A29E" }}>
          <p style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>Search for a legal term above</p>
          <p style={{ fontSize: "0.82rem" }}>Try: acquittal, estoppel, habeas corpus, tort, fiduciary</p>
        </div>
      ) : null}

      <ul className="results-list">
        {search.results.map((result) => (
          <li key={`${result.phrase}-${result.jurisdiction}-${result.domain}`} className="result-card">
            <div className="result-header">
              <Link href={`/glossary/${encodeURIComponent(result.phrase)}`}><strong>{result.phrase}</strong></Link>
              <span className="badge">{result.jurisdiction}</span>
              {result.domain ? <span className="badge muted">{result.domain}</span> : null}
            </div>
            <div className="definition-html" style={{ marginTop: "0.35rem", fontSize: "0.88rem", lineHeight: 1.6 }}>
              {result.definition_text.slice(0, 350)}{result.definition_text.length > 350 ? "..." : ""}
            </div>
            {result.source_title ? (
              <p className="meta-line" style={{ marginTop: "0.35rem" }}>
                Source: {result.source_url ? <a href={result.source_url} target="_blank" rel="noopener noreferrer">{result.source_title}</a> : result.source_title}
              </p>
            ) : null}
          </li>
        ))}
      </ul>

      {q && Object.keys(search.aggregations.domains).length > 0 ? (
        <div style={{ marginTop: "1.5rem" }}>
          <p style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.35rem" }}>Filter by practice area</p>
          <div className="chip-row">
            {Object.entries(search.aggregations.domains).sort((a, b) => b[1] - a[1]).map(([itemDomain, count]) => (
              <button
                key={itemDomain}
                type="button"
                className={`chip ${domain === itemDomain ? "chip-active" : ""}`}
                style={chipButtonStyle}
                onClick={() => onDomainClick(itemDomain)}
              >
                {itemDomain} ({count})
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
