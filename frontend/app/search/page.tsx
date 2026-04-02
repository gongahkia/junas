import Link from "next/link";
import { searchCases, listCharges } from "../../lib/api-server";

type SearchResult = {
  case_id: string;
  case_name: string;
  facts: string;
  judgment: string;
  charges: string[];
  relevance_score?: number;
  retrieval_stage: string;
};

type SearchResponse = {
  query: string;
  results: SearchResult[];
  retrieval_info: {
    stages_used: string[];
    bm25_candidates: number;
    dense_candidates: number;
    total_time_ms: number;
  };
};

type ChargesResponse = {
  charges: string[];
};

const defaultQuery =
  "2018年1月15日14时10分许，被告人莫新国酒后驾驶小型轿车被交警查获，经鉴定血液乙醇含量超过醉驾标准。";

function normalizeStages(raw: string | string[] | undefined): string[] {
  if (Array.isArray(raw)) {
    return raw.filter((stage) => stage === "bm25" || stage === "dense" || stage === "rerank");
  }
  if (typeof raw === "string" && raw.trim()) {
    return raw === "bm25" || raw === "dense" || raw === "rerank" ? [raw] : [];
  }
  return ["bm25", "dense", "rerank"];
}

async function fetchCaseSearch(
  query: string,
  topK: number,
  stages: string[],
  includeScores: boolean,
): Promise<{ result: SearchResponse | null; error: string | null }> {
  if (!query.trim()) return { result: null, error: null };
  const data = await searchCases(query, topK, stages, includeScores);
  if (data?.error) return { result: null, error: data.error };
  return { result: data as SearchResponse, error: null };
}

async function fetchCharges(): Promise<ChargesResponse> {
  return (await listCharges()) as ChargesResponse;
}

export default async function CaseSearchPage({
  searchParams,
}: {
  searchParams?: {
    query?: string;
    top_k?: string;
    stages?: string | string[];
    include_scores?: "true" | "false";
    run?: "0" | "1";
  };
}) {
  const query = searchParams?.query ?? defaultQuery;
  const topK = Number(searchParams?.top_k ?? "10") || 10;
  const stages = normalizeStages(searchParams?.stages);
  const includeScores = searchParams?.include_scores !== "false";
  const shouldRun = searchParams?.run === "1";

  const [charges, search] = await Promise.all([
    fetchCharges(),
    shouldRun
      ? fetchCaseSearch(query, topK, stages, includeScores)
      : Promise.resolve({ result: null, error: null }),
  ]);

  const result = search.result;

  return (
    <section className="search-grid">
      <div>
        <h2>Case Retrieval (LeCaRD)</h2>
        <p>
          Search Chinese criminal case facts with a three-stage pipeline: BM25 retrieval, optional dense
          retrieval, and optional cross-encoder re-ranking.
        </p>
        <p className="meta-line">
          Dataset note: LeCaRD is used for retrieval benchmarking and research comparison.
        </p>

        <form method="get" action="/search" className="ner-form">
          <input type="hidden" name="run" value="1" />

          <label htmlFor="query">Case fact description (Chinese)</label>
          <textarea id="query" name="query" rows={10} defaultValue={query} />

          <label htmlFor="top_k">Results</label>
          <input id="top_k" name="top_k" type="number" min={1} max={50} defaultValue={topK} />

          <div className="chip-row">
            <label className="checkbox-row">
              <input type="checkbox" name="stages" value="bm25" defaultChecked={stages.includes("bm25")} />
              BM25
            </label>
            <label className="checkbox-row">
              <input type="checkbox" name="stages" value="dense" defaultChecked={stages.includes("dense")} />
              Dense
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                name="stages"
                value="rerank"
                defaultChecked={stages.includes("rerank")}
              />
              Re-rank
            </label>
          </div>

          <label className="checkbox-row">
            <input type="checkbox" name="include_scores" value="true" defaultChecked={includeScores} />
            Include relevance scores
          </label>

          <button type="submit">Search Cases</button>
        </form>

        <p>
          <Link href="/search/metrics">View evaluation metrics</Link>
        </p>

        {search.error ? (
          <article className="result-card">
            <h3>Search unavailable</h3>
            <p>{search.error}</p>
          </article>
        ) : null}

        {result ? (
          <>
            <h3>Results ({result.results.length})</h3>
            <ul className="results-list">
              {result.results.map((item) => (
                <li key={item.case_id} className="result-card">
                  <div className="result-header">
                    <strong>{item.case_name || item.case_id}</strong>
                    <span className="badge muted">{item.case_id}</span>
                    <span className="badge">{item.retrieval_stage}</span>
                  </div>
                  <p>{item.facts.slice(0, 320)}...</p>
                  <p className="meta-line">{item.judgment.slice(0, 180)}...</p>
                  {item.charges.length > 0 ? (
                    <div className="chip-row">
                      {item.charges.map((charge) => (
                        <span key={`${item.case_id}-${charge}`} className="chip">
                          {charge}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {typeof item.relevance_score === "number" ? (
                    <p className="meta-line">score: {item.relevance_score.toFixed(4)}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>Submit a query to run retrieval.</p>
        )}
      </div>

      <aside>
        <h3>Pipeline Stats</h3>
        {result ? (
          <ul className="chapter-list">
            <li>stages: {result.retrieval_info.stages_used.join(" -> ")}</li>
            <li>bm25 candidates: {result.retrieval_info.bm25_candidates}</li>
            <li>dense candidates: {result.retrieval_info.dense_candidates}</li>
            <li>time: {result.retrieval_info.total_time_ms} ms</li>
          </ul>
        ) : (
          <p>No run yet.</p>
        )}

        <h3>Known Charges</h3>
        <div className="chip-row">
          {charges.charges.slice(0, 40).map((charge) => (
            <span key={charge} className="chip">
              {charge}
            </span>
          ))}
        </div>
      </aside>
    </section>
  );
}
