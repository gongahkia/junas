"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import { searchSSO } from "../../lib/api-client";

type SgResult = { title: string; url: string; snippet: string; source: string };

function apiError(data: unknown): string | null {
  if (typeof data !== "object" || data === null || !("error" in data)) return null;
  const error = (data as { error?: unknown }).error;
  return error ? String(error) : null;
}

export default function StatutesPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SgResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = q.trim();
    setError(null);
    if (!query) {
      setResults([]);
      return;
    }
    setIsLoading(true);
    try {
      const data = await searchSSO(query);
      if (!Array.isArray(data)) {
        setError(apiError(data) ?? "Singapore statute search failed.");
        setResults([]);
        return;
      }
      setResults(data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Statute search request failed.");
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section>
      <h2>Singapore Statute Browser</h2>
      <p className="meta-line" style={{ marginBottom: "1.25rem" }}>Search Singapore Statutes Online materials.</p>

      <form method="post" className="glossary-form" onSubmit={onSubmit}>
        <input name="jurisdiction" type="hidden" value="sg" readOnly />
        <label htmlFor="q">Search statutes</label>
        <input
          id="q"
          name="q"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="personal data protection act"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Searching..." : "Search"}
        </button>
      </form>

      {error ? (
        <article className="result-card">
          <h3>Search unavailable</h3>
          <p>{error}</p>
        </article>
      ) : null}

      <h3>Singapore Statutes ({results.length})</h3>
      <ul className="results-list">
        {results.map((row: SgResult, i: number) => (
          <li key={`${row.url}-${i}`} className="result-card">
            <div className="result-header">
              <a href={row.url} target="_blank" rel="noopener noreferrer"><strong>{row.title}</strong></a>
              <span className="badge muted">{row.source}</span>
            </div>
            {row.snippet ? <p className="meta-line">{row.snippet}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
