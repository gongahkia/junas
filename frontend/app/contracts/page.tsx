import Link from "next/link";
import { classifyContract as classifyContractApi, scanToS as scanToSApi } from "../../lib/api-server";

type ClauseResult = {
  segment_index: number;
  text: string;
  start: number;
  end: number;
  clause_type: string;
  confidence: number;
  alternatives: Array<{ type: string; confidence: number }>;
};

type ContractClassifyResponse = {
  total_clauses: number;
  clauses: ClauseResult[];
  clause_distribution: Record<string, number>;
};

type ToSSentence = {
  index: number;
  text: string;
  is_unfair: boolean;
  unfair_categories: Array<{ category: string; confidence: number }>;
};

type ToSResponse = {
  total_sentences: number;
  unfair_count: number;
  fair_count: number;
  severity_score: number;
  sentences: ToSSentence[];
  summary: Record<string, number>;
};

const sampleContract = `SECTION 1. DEFINITIONS. As used in this Agreement, "Confidential Information" means all non-public business information.

SECTION 2. GOVERNING LAW. This Agreement shall be governed by the laws of the State of New York.

SECTION 3. INDEMNIFICATION. The Company shall indemnify and hold harmless the Contractor against all claims arising from performance.`;

const sampleToS = `By using our service, you agree to these terms. We may terminate your account at any time without notice. We may update these terms unilaterally by posting changes on our website.`;

async function classifyContract(
  text: string,
  topKTypes: number,
): Promise<{ result: ContractClassifyResponse | null; error: string | null }> {
  if (!text.trim()) return { result: null, error: null };
  const data = await classifyContractApi(text, topKTypes);
  if (data?.error) return { result: null, error: data.error };
  return { result: data as ContractClassifyResponse, error: null };
}

async function scanToS(
  text: string,
  threshold: number,
): Promise<{ result: ToSResponse | null; error: string | null }> {
  if (!text.trim()) return { result: null, error: null };
  const data = await scanToSApi(text, threshold);
  if (data?.error) return { result: null, error: data.error };
  return { result: data as ToSResponse, error: null };
}

export default async function ContractsPage({
  searchParams,
}: {
  searchParams?: {
    tab?: "classify" | "tos";
    text?: string;
    top_k_types?: string;
    threshold?: string;
    run?: "0" | "1";
  };
}) {
  const tab = searchParams?.tab === "tos" ? "tos" : "classify";
  const text = searchParams?.text ?? (tab === "classify" ? sampleContract : sampleToS);
  const topKTypes = Number(searchParams?.top_k_types ?? "3") || 3;
  const threshold = Number(searchParams?.threshold ?? "0.5") || 0.5;
  const shouldRun = searchParams?.run === "1";

  const classifyResult =
    tab === "classify" && shouldRun
      ? await classifyContract(text, topKTypes)
      : { result: null as ContractClassifyResponse | null, error: null as string | null };
  const tosResult =
    tab === "tos" && shouldRun
      ? await scanToS(text, threshold)
      : { result: null as ToSResponse | null, error: null as string | null };

  return (
    <section className="contracts-grid">
      <div>
        <h2>Contract Analysis</h2>
        <p>Classify contract clauses and detect potentially unfair Terms of Service language.</p>

        <div className="chip-row">
          <Link href="/contracts?tab=classify" className={`chip ${tab === "classify" ? "chip-active" : ""}`}>
            Clause Classification
          </Link>
          <Link href="/contracts?tab=tos" className={`chip ${tab === "tos" ? "chip-active" : ""}`}>
            ToS Scanner
          </Link>
        </div>

        {tab === "classify" ? (
          <form method="get" action="/contracts" className="ner-form">
            <input type="hidden" name="tab" value="classify" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="text">Contract text</label>
            <textarea id="text" name="text" rows={12} defaultValue={text} />

            <label htmlFor="top_k_types">Top clause types per segment</label>
            <input id="top_k_types" name="top_k_types" type="number" min={1} max={5} defaultValue={topKTypes} />

            <button type="submit">Analyze Contract</button>
          </form>
        ) : (
          <form method="get" action="/contracts" className="ner-form">
            <input type="hidden" name="tab" value="tos" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="text">Terms of service text</label>
            <textarea id="text" name="text" rows={12} defaultValue={text} />

            <label htmlFor="threshold">Unfair confidence threshold</label>
            <input
              id="threshold"
              name="threshold"
              type="number"
              step={0.05}
              min={0}
              max={1}
              defaultValue={threshold}
            />

            <button type="submit">Scan for Unfair Clauses</button>
          </form>
        )}

        {tab === "classify" && classifyResult.error ? (
          <article className="result-card">
            <p>{classifyResult.error}</p>
          </article>
        ) : null}
        {tab === "tos" && tosResult.error ? (
          <article className="result-card">
            <p>{tosResult.error}</p>
          </article>
        ) : null}

        {tab === "classify" && classifyResult.result ? (
          <>
            <h3>Classified Clauses ({classifyResult.result.total_clauses})</h3>
            <ul className="results-list">
              {classifyResult.result.clauses.map((clause) => (
                <li key={`${clause.segment_index}-${clause.start}`} className="result-card">
                  <div className="result-header">
                    <strong>{clause.clause_type}</strong>
                    <span className="badge">{clause.confidence.toFixed(4)}</span>
                  </div>
                  <p>{clause.text.slice(0, 420)}...</p>
                  <div className="chip-row">
                    {clause.alternatives.map((alt) => (
                      <span key={`${clause.segment_index}-${alt.type}`} className="chip">
                        {alt.type} ({alt.confidence.toFixed(3)})
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === "tos" && tosResult.result ? (
          <>
            <h3>
              ToS Scan ({tosResult.result.unfair_count}/{tosResult.result.total_sentences} unfair)
            </h3>
            <ul className="results-list">
              {tosResult.result.sentences.map((sentence) => {
                const highest = Math.max(
                  0,
                  ...sentence.unfair_categories.map((item) => Number(item.confidence ?? 0)),
                );
                const severityClass =
                  highest > 0.8 ? "unfair-high" : sentence.is_unfair ? "unfair-medium" : "unfair-none";

                return (
                  <li key={`sentence-${sentence.index}`} className={`result-card ${severityClass}`}>
                    <p>{sentence.text}</p>
                    {sentence.unfair_categories.length > 0 ? (
                      <div className="chip-row">
                        {sentence.unfair_categories.map((item) => (
                          <span key={`${sentence.index}-${item.category}`} className="chip">
                            {item.category} ({item.confidence.toFixed(3)})
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="meta-line">No unfair category detected.</p>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        ) : null}
      </div>

      <aside>
        <h3>Summary</h3>
        {tab === "classify" && classifyResult.result ? (
          <ul className="chapter-list">
            {Object.entries(classifyResult.result.clause_distribution).map(([clauseType, count]) => (
              <li key={clauseType}>
                {clauseType}: {count}
              </li>
            ))}
          </ul>
        ) : null}

        {tab === "tos" && tosResult.result ? (
          <>
            <p>Severity score: {tosResult.result.severity_score.toFixed(3)}</p>
            <ul className="chapter-list">
              {Object.entries(tosResult.result.summary).map(([category, count]) => (
                <li key={category}>
                  {category}: {count}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </aside>
    </section>
  );
}
