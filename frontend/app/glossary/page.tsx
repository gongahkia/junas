import Link from "next/link";
import { searchGlossary, listGlossaryJurisdictions, suggestGlossary } from "../../lib/api-server";

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
  aggregations: {
    jurisdictions: Record<string, number>;
    domains: Record<string, number>;
  };
};

type JurisdictionsResponse = {
  jurisdictions: Array<{ code: string; name: string; count: number; domains: string[] }>;
};

type SuggestResponse = {
  suggestions: string[];
};

async function fetchSearch(
  q: string,
  jurisdiction: string,
  domain: string,
  page: number,
  perPage: number,
): Promise<SearchResponse> {
  if (!q.trim()) {
    return { total: 0, page, per_page: perPage, results: [], aggregations: { jurisdictions: {}, domains: {} } };
  }
  const data = await searchGlossary(q, jurisdiction.trim(), domain.trim(), page, perPage);
  return { total: 0, page, per_page: perPage, results: [], aggregations: { jurisdictions: {}, domains: {} }, ...data } as SearchResponse;
}

async function fetchJurisdictions(): Promise<JurisdictionsResponse> {
  return (await listGlossaryJurisdictions()) as JurisdictionsResponse;
}

async function fetchSuggestions(q: string): Promise<SuggestResponse> {
  if (!q.trim()) return { suggestions: [] };
  return (await suggestGlossary(q.trim(), 8)) as SuggestResponse;
}

export default async function GlossaryPage({
  searchParams,
}: {
  searchParams?: {
    q?: string;
    jurisdiction?: string;
    domain?: string;
    page?: string;
    per_page?: string;
  };
}) {
  const q = searchParams?.q ?? "";
  const jurisdiction = searchParams?.jurisdiction ?? "";
  const domain = searchParams?.domain ?? "";
  const page = Number(searchParams?.page ?? "1") || 1;
  const perPage = Number(searchParams?.per_page ?? "20") || 20;

  const [search, jurisdictions, suggestions] = await Promise.all([
    fetchSearch(q, jurisdiction, domain, page, perPage),
    fetchJurisdictions(),
    fetchSuggestions(q),
  ]);

  return (
    <section className="glossary-grid">
      <div>
        <h2>Multi-Jurisdiction Glossary</h2>
        <p>
          Search legal terms across Australia, Canada, Ireland, New Zealand, United Kingdom,
          and United States sources.
        </p>

        <form method="get" action="/glossary" className="glossary-form">
          <label htmlFor="q">Search term</label>
          <input id="q" name="q" defaultValue={q} placeholder="acquittal" />

          <label htmlFor="jurisdiction">Jurisdiction filter (comma-separated)</label>
          <input
            id="jurisdiction"
            name="jurisdiction"
            defaultValue={jurisdiction}
            placeholder="USA,AUS"
          />

          <label htmlFor="domain">Domain filter (comma-separated)</label>
          <input id="domain" name="domain" defaultValue={domain} placeholder="criminal,family" />

          <button type="submit">Search</button>
        </form>

        {suggestions.suggestions.length > 0 ? (
          <div className="suggestions">
            <p>Autocomplete</p>
            <div className="chip-row">
              {suggestions.suggestions.map((term) => (
                <Link
                  key={term}
                  href={`/glossary?q=${encodeURIComponent(term)}&jurisdiction=${encodeURIComponent(
                    jurisdiction,
                  )}&domain=${encodeURIComponent(domain)}`}
                  className="chip"
                >
                  {term}
                </Link>
              ))}
            </div>
          </div>
        ) : null}

        <h3>Results ({search.total})</h3>
        <ul className="results-list">
          {search.results.map((result) => (
            <li key={`${result.phrase}-${result.jurisdiction}-${result.domain}`} className="result-card">
              <div className="result-header">
                <Link href={`/glossary/${encodeURIComponent(result.phrase)}`}>
                  <strong>{result.phrase}</strong>
                </Link>
                <span className="badge">{result.jurisdiction}</span>
                <span className="badge muted">{result.domain}</span>
              </div>
              <p>{result.definition_text.slice(0, 280)}...</p>
              <p className="meta-line">
                Source: <a href={result.source_url}>{result.source_title || result.source_url}</a>
              </p>
            </li>
          ))}
        </ul>
      </div>

      <aside>
        <h3>Jurisdictions</h3>
        <div className="chip-row">
          {jurisdictions.jurisdictions.map((entry) => (
            <Link
              key={entry.code}
              href={`/glossary?q=${encodeURIComponent(q)}&jurisdiction=${encodeURIComponent(entry.code)}`}
              className="chip"
            >
              {entry.code} ({entry.count})
            </Link>
          ))}
        </div>

        <h3>Aggregations</h3>
        <p>Jurisdiction counts</p>
        <ul>
          {Object.entries(search.aggregations.jurisdictions).map(([name, count]) => (
            <li key={name}>
              {name}: {count}
            </li>
          ))}
        </ul>

        <p>Domain counts</p>
        <ul>
          {Object.entries(search.aggregations.domains).map(([name, count]) => (
            <li key={name}>
              {name}: {count}
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
