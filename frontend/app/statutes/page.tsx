"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { listStatuteChapters, searchSSO, searchStatutes } from "../../lib/api-client";

type SearchMode = "hybrid" | "keyword" | "semantic";
type Jurisdiction = "us" | "sg";

type SgResult = { title: string; url: string; snippet: string; source: string };

type StatuteResult = {
  number: string;
  name: string;
  chapter_number: string;
  text_html: string;
  text_plain: string;
  cross_references: string[];
  score: number;
  search_mode: string;
};

type StatuteSearchResponse = {
  total: number;
  results: StatuteResult[];
};

type ChapterItem = {
  chapter_number: string;
  section_count: number;
  first_section: string;
};

type ChaptersResponse = {
  chapters: ChapterItem[];
};

const emptySearch: StatuteSearchResponse = { total: 0, results: [] };

function isSearchMode(value: string): value is SearchMode {
  return value === "hybrid" || value === "keyword" || value === "semantic";
}

function isChaptersResponse(data: unknown): data is ChaptersResponse {
  return typeof data === "object" && data !== null && Array.isArray((data as ChaptersResponse).chapters);
}

function isStatuteSearchResponse(data: unknown): data is StatuteSearchResponse {
  return typeof data === "object" && data !== null && Array.isArray((data as StatuteSearchResponse).results);
}

function apiError(data: unknown): string | null {
  if (typeof data !== "object" || data === null || !("error" in data)) return null;
  const error = (data as { error?: unknown }).error;
  return error ? String(error) : null;
}

export default function StatutesPage() {
  const [q, setQ] = useState("");
  const [chapter, setChapter] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("us");
  const [search, setSearch] = useState<StatuteSearchResponse>(emptySearch);
  const [chapters, setChapters] = useState<ChaptersResponse>({ chapters: [] });
  const [sgResults, setSgResults] = useState<SgResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isActive = true;
    (async () => {
      try {
        const data = await listStatuteChapters();
        if (!isActive || !isChaptersResponse(data)) return;
        setChapters(data);
      } catch {
        if (isActive) setChapters({ chapters: [] });
      }
    })();
    return () => {
      isActive = false;
    };
  }, []);

  const isSg = jurisdiction === "sg";
  const visibleChapters = isSg ? [] : chapters.chapters;

  const onJurisdictionChange = (value: string) => {
    setJurisdiction(value === "sg" ? "sg" : "us");
    setSearch(emptySearch);
    setSgResults([]);
    setError(null);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const query = q.trim();
    setError(null);
    if (!query) {
      setSearch(emptySearch);
      setSgResults([]);
      return;
    }

    setIsLoading(true);
    try {
      if (jurisdiction === "sg") {
        const data = await searchSSO(query);
        if (!Array.isArray(data)) {
          setError(apiError(data) ?? "Singapore statute search failed.");
          setSgResults([]);
          return;
        }
        setSgResults(data);
        setSearch(emptySearch);
        return;
      }

      const data = await searchStatutes(query, chapter.trim(), mode, 1, 20);
      const searchError = apiError(data);
      if (searchError) {
        setError(searchError);
        setSearch(emptySearch);
      } else if (isStatuteSearchResponse(data)) {
        setSearch({ total: Number(data.total ?? 0) || 0, results: data.results });
      } else {
        setSearch(emptySearch);
      }
      setSgResults([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Statute search request failed.");
      setSearch(emptySearch);
      setSgResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="statute-grid">
      <div>
        <h2>Statute Browser</h2>
        <p>Search statutes across jurisdictions</p>

        <form method="post" className="glossary-form" onSubmit={onSubmit}>
          <label htmlFor="jurisdiction">Jurisdiction</label>
          <select id="jurisdiction" name="jurisdiction" value={jurisdiction} onChange={(event) => onJurisdictionChange(event.target.value)}>
            <option value="us">Oregon (US)</option>
            <option value="sg">Singapore (SSO)</option>
          </select>

          <label htmlFor="q">Search statutes</label>
          <input
            id="q"
            name="q"
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder={isSg ? "employment act" : "naturopathic physician"}
          />

          {!isSg && (
            <>
              <label htmlFor="mode">Mode</label>
              <select
                id="mode"
                name="mode"
                value={mode}
                onChange={(event) => setMode(isSearchMode(event.target.value) ? event.target.value : "hybrid")}
              >
                <option value="hybrid">hybrid</option>
                <option value="keyword">keyword</option>
                <option value="semantic">semantic</option>
              </select>
              <label htmlFor="chapter">Chapter filter</label>
              <input
                id="chapter"
                name="chapter"
                value={chapter}
                onChange={(event) => setChapter(event.target.value)}
                placeholder="685"
              />
            </>
          )}

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

        {isSg ? (
          <>
            <h3>Singapore Statutes ({sgResults.length})</h3>
            <ul className="results-list">
              {sgResults.map((row: SgResult, i: number) => (
                <li key={`${row.url}-${i}`} className="result-card">
                  <div className="result-header">
                    <a href={row.url} target="_blank" rel="noopener noreferrer"><strong>{row.title}</strong></a>
                    <span className="badge muted">{row.source}</span>
                  </div>
                  {row.snippet ? <p className="meta-line">{row.snippet}</p> : null}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <h3>Results ({search.total})</h3>
            <ul className="results-list">
              {search.results.map((row: StatuteResult) => (
                <li key={`${row.number}-${row.search_mode}`} className="result-card">
                  <div className="result-header">
                    <Link href={`/statutes/section/${encodeURIComponent(row.number)}`}><strong>{row.number}</strong></Link>
                    <span>{row.name}</span>
                  </div>
                  <p><Link href={`/statutes/chapter/${encodeURIComponent(row.chapter_number)}`}>Chapter {row.chapter_number}</Link></p>
                  <p>{row.text_plain.slice(0, 400)}...</p>
                  <p className="meta-line">mode: {row.search_mode} | score: {row.score.toFixed(4)}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      <aside>
        <h3>Chapters</h3>
        <ul className="chapter-list">
          {visibleChapters.map((item: ChapterItem) => (
            <li key={item.chapter_number}>
              <Link href={`/statutes/chapter/${encodeURIComponent(item.chapter_number)}`}>
                {item.chapter_number}
              </Link>{" "}
              ({item.section_count})
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
