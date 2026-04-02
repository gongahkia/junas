import Link from "next/link";
import {
  predictScotus as apiPredictScotus,
  predictEcthr as apiPredictEcthr,
  predictCasehold as apiPredictCasehold,
  predictEurlex as apiPredictEurlex,
} from "../../lib/api-server";

type PredictionTab = "scotus" | "ecthr" | "casehold" | "eurlex";

type ScotusResponse = {
  prediction: {
    issue_area: string;
    issue_area_id: number | null;
    confidence: number;
  };
  alternatives: Array<{ issue_area: string; issue_area_id: number | null; confidence: number }>;
  model_info: { model: string; input_length: number };
};

type EcthrResponse = {
  predictions: Array<{ article: string; article_id: number; right: string; confidence: number }>;
  no_violation_probability: number;
  task: "violation" | "alleged";
};

type CaseholdResponse = {
  selected_option: number;
  selected_text: string;
  confidence: number;
  option_scores: number[];
};

type EurlexResponse = {
  labels: Array<{ eurovoc_id: number; concept: string; confidence: number }>;
  total_labels: number;
};

const sampleScotus =
  "The Court granted certiorari to decide whether admitting the evidence violated the petitioner's constitutional due process rights.";
const sampleEcthr =
  "The applicant alleged mistreatment in custody and argued that detention conditions violated Convention guarantees.";
const sampleCasehold =
  "In Smith v. Jones, the appellate court clarified that <HOLDING> for negligent misrepresentation claims in this jurisdiction.";
const sampleEurlex =
  "REGULATION (EU) No 1234/2026 of the European Parliament and of the Council on market surveillance and consumer protection requirements.";

const defaultCaseholdOptions = [
  "the claim is always barred when privity is absent",
  "a plaintiff must prove statutory standing before damages",
  "negligent misrepresentation requires foreseeable reliance",
  "punitive damages are mandatory for all violations",
  "federal preemption automatically applies to state contracts",
];

function normalizeTab(value: string | undefined): PredictionTab {
  if (value === "ecthr" || value === "casehold" || value === "eurlex") {
    return value;
  }
  return "scotus";
}

function toNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return parsed;
}

async function predictScotus(text: string, topK: number): Promise<{ result: ScotusResponse | null; error: string | null }> {
  const res = await apiPredictScotus(text, topK);
  if (res?.error) return { result: null, error: res.error };
  return { result: res as ScotusResponse, error: null };
}
async function predictEcthr(text: string, task: "violation" | "alleged", threshold: number): Promise<{ result: EcthrResponse | null; error: string | null }> {
  const res = await apiPredictEcthr(text, task, threshold);
  if (res?.error) return { result: null, error: res.error };
  return { result: res as EcthrResponse, error: null };
}
async function predictCasehold(context: string, options: string[]): Promise<{ result: CaseholdResponse | null; error: string | null }> {
  const res = await apiPredictCasehold(context, options);
  if (res?.error) return { result: null, error: res.error };
  return { result: res as CaseholdResponse, error: null };
}
async function predictEurlex(text: string, threshold: number, maxLabels: number): Promise<{ result: EurlexResponse | null; error: string | null }> {
  const res = await apiPredictEurlex(text, threshold, maxLabels);
  if (res?.error) return { result: null, error: res.error };
  return { result: res as EurlexResponse, error: null };
}

export default async function PredictionsPage({
  searchParams,
}: {
  searchParams?: {
    tab?: string;
    run?: "0" | "1";
    text?: string;
    context?: string;
    top_k?: string;
    task?: "violation" | "alleged";
    threshold?: string;
    max_labels?: string;
    option_0?: string;
    option_1?: string;
    option_2?: string;
    option_3?: string;
    option_4?: string;
  };
}) {
  const tab = normalizeTab(searchParams?.tab);
  const shouldRun = searchParams?.run === "1";

  const textDefault =
    tab === "scotus" ? sampleScotus : tab === "ecthr" ? sampleEcthr : tab === "eurlex" ? sampleEurlex : "";
  const text = (searchParams?.text ?? textDefault).trim();
  const context = (searchParams?.context ?? sampleCasehold).trim();

  const topK = Math.min(14, Math.max(1, toNumber(searchParams?.top_k, 3)));
  const ecthrTask: "violation" | "alleged" = searchParams?.task === "alleged" ? "alleged" : "violation";
  const threshold = Math.min(1, Math.max(0, toNumber(searchParams?.threshold, 0.5)));
  const maxLabels = Math.min(100, Math.max(1, toNumber(searchParams?.max_labels, 10)));

  const caseholdOptions = [
    (searchParams?.option_0 ?? defaultCaseholdOptions[0]).trim(),
    (searchParams?.option_1 ?? defaultCaseholdOptions[1]).trim(),
    (searchParams?.option_2 ?? defaultCaseholdOptions[2]).trim(),
    (searchParams?.option_3 ?? defaultCaseholdOptions[3]).trim(),
    (searchParams?.option_4 ?? defaultCaseholdOptions[4]).trim(),
  ];

  const scotusResult =
    tab === "scotus" && shouldRun && text
      ? await predictScotus(text, topK)
      : { result: null as ScotusResponse | null, error: null as string | null };
  const ecthrResult =
    tab === "ecthr" && shouldRun && text
      ? await predictEcthr(text, ecthrTask, threshold)
      : { result: null as EcthrResponse | null, error: null as string | null };
  const caseholdResult =
    tab === "casehold" && shouldRun && context
      ? await predictCasehold(context, caseholdOptions)
      : { result: null as CaseholdResponse | null, error: null as string | null };
  const eurlexResult =
    tab === "eurlex" && shouldRun && text
      ? await predictEurlex(text, threshold, maxLabels)
      : { result: null as EurlexResponse | null, error: null as string | null };

  const activeError = scotusResult.error ?? ecthrResult.error ?? caseholdResult.error ?? eurlexResult.error;

  return (
    <section className="predictions-grid">
      <div>
        <h2>Court Decision Prediction Suite</h2>
        <p>Run LexGLUE task demos for SCOTUS, ECtHR, CaseHOLD, and EUR-LEX classifiers.</p>

        <div className="chip-row">
          <Link href="/predictions?tab=scotus" className={`chip ${tab === "scotus" ? "chip-active" : ""}`}>
            SCOTUS
          </Link>
          <Link href="/predictions?tab=ecthr" className={`chip ${tab === "ecthr" ? "chip-active" : ""}`}>
            ECtHR
          </Link>
          <Link href="/predictions?tab=casehold" className={`chip ${tab === "casehold" ? "chip-active" : ""}`}>
            CaseHOLD
          </Link>
          <Link href="/predictions?tab=eurlex" className={`chip ${tab === "eurlex" ? "chip-active" : ""}`}>
            EUR-LEX
          </Link>
        </div>

        {tab === "scotus" ? (
          <form method="get" action="/predictions" className="ner-form">
            <input type="hidden" name="tab" value="scotus" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="text">Opinion text</label>
            <textarea id="text" name="text" rows={10} defaultValue={text} />

            <label htmlFor="top_k">Top predictions</label>
            <input id="top_k" name="top_k" type="number" min={1} max={14} defaultValue={topK} />

            <button type="submit">Predict Issue Area</button>
          </form>
        ) : null}

        {tab === "ecthr" ? (
          <form method="get" action="/predictions" className="ner-form">
            <input type="hidden" name="tab" value="ecthr" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="text">Case facts</label>
            <textarea id="text" name="text" rows={10} defaultValue={text} />

            <label htmlFor="task">Task</label>
            <select id="task" name="task" defaultValue={ecthrTask}>
              <option value="violation">Violation (Task A)</option>
              <option value="alleged">Alleged (Task B)</option>
            </select>

            <label htmlFor="threshold">Confidence threshold</label>
            <input id="threshold" name="threshold" type="number" min={0} max={1} step={0.05} defaultValue={threshold} />

            <button type="submit">Predict Articles</button>
          </form>
        ) : null}

        {tab === "casehold" ? (
          <form method="get" action="/predictions" className="ner-form">
            <input type="hidden" name="tab" value="casehold" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="context">Context with &lt;HOLDING&gt;</label>
            <textarea id="context" name="context" rows={8} defaultValue={context} />

            {caseholdOptions.map((option, index) => (
              <div key={`option-${index}`}>
                <label htmlFor={`option_${index}`}>Option {index}</label>
                <input id={`option_${index}`} name={`option_${index}`} defaultValue={option} />
              </div>
            ))}

            <button type="submit">Select Holding</button>
          </form>
        ) : null}

        {tab === "eurlex" ? (
          <form method="get" action="/predictions" className="ner-form">
            <input type="hidden" name="tab" value="eurlex" />
            <input type="hidden" name="run" value="1" />

            <label htmlFor="text">EU legislation text</label>
            <textarea id="text" name="text" rows={10} defaultValue={text} />

            <label htmlFor="threshold">Confidence threshold</label>
            <input id="threshold" name="threshold" type="number" min={0} max={1} step={0.05} defaultValue={threshold} />

            <label htmlFor="max_labels">Max labels</label>
            <input id="max_labels" name="max_labels" type="number" min={1} max={100} defaultValue={maxLabels} />

            <button type="submit">Classify EuroVoc Labels</button>
          </form>
        ) : null}

        {activeError ? (
          <article className="result-card">
            <h3>Request failed</h3>
            <p>{activeError}</p>
          </article>
        ) : null}

        {tab === "scotus" && scotusResult.result ? (
          <article className="result-card">
            <h3>Predicted Issue Area</h3>
            <p>
              <strong>{scotusResult.result.prediction.issue_area}</strong> ({scotusResult.result.prediction.confidence.toFixed(3)})
            </p>
            <ul className="results-list">
              {scotusResult.result.alternatives.map((item) => (
                <li key={`${item.issue_area}-${item.issue_area_id}`}>
                  {item.issue_area}: {item.confidence.toFixed(3)}
                </li>
              ))}
            </ul>
          </article>
        ) : null}

        {tab === "ecthr" && ecthrResult.result ? (
          <article className="result-card">
            <h3>Predicted Articles</h3>
            {ecthrResult.result.predictions.length === 0 ? (
              <p>No article above threshold. no_violation_probability: {ecthrResult.result.no_violation_probability.toFixed(3)}</p>
            ) : (
              <ul className="results-list">
                {ecthrResult.result.predictions.map((item) => (
                  <li key={`${item.article}-${item.article_id}`}>
                    <strong>{item.article}</strong> ({item.confidence.toFixed(3)}) - {item.right}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ) : null}

        {tab === "casehold" && caseholdResult.result ? (
          <article className="result-card">
            <h3>Selected Holding</h3>
            <p>
              Option {caseholdResult.result.selected_option}: {caseholdResult.result.selected_text}
            </p>
            <p className="meta-line">confidence: {caseholdResult.result.confidence.toFixed(3)}</p>
            <ul className="results-list">
              {caseholdResult.result.option_scores.map((score, index) => (
                <li
                  key={`score-${index}`}
                  className={index === caseholdResult.result.selected_option ? "prediction-selected" : undefined}
                >
                  option {index}: {score.toFixed(3)}
                </li>
              ))}
            </ul>
          </article>
        ) : null}

        {tab === "eurlex" && eurlexResult.result ? (
          <article className="result-card">
            <h3>Predicted EuroVoc Labels ({eurlexResult.result.total_labels})</h3>
            <ul className="results-list">
              {eurlexResult.result.labels.map((item) => (
                <li key={`${item.eurovoc_id}-${item.concept}`}>
                  {item.concept} ({item.eurovoc_id}) - {item.confidence.toFixed(3)}
                </li>
              ))}
            </ul>
          </article>
        ) : null}
      </div>

      <aside>
        <h3>Active Task</h3>
        <ul className="chapter-list">
          <li>tab: {tab}</li>
          <li>run: {shouldRun ? "yes" : "no"}</li>
          <li>api: server</li>
        </ul>

        <h3>Tips</h3>
        <ul className="chapter-list">
          <li>SCOTUS and ECtHR work better with longer factual summaries.</li>
          <li>CaseHOLD requires exactly five candidate options.</li>
          <li>EUR-LEX threshold controls label precision/recall tradeoff.</li>
        </ul>
      </aside>
    </section>
  );
}
