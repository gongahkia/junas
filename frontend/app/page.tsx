import Link from "next/link";
import { getReady, getMetrics } from "../lib/api-server";

type ReadyResponse = {
  services: Record<string, boolean>;
};

type MetricsResponse = {
  uptime_seconds: number;
  models_loaded: string[];
  benchmark_runs: number;
  conversations: number;
};

const featureCards = [
  { href: "/chat", title: "AI Chat", description: "BYOK streaming chat with Claude, OpenAI, Gemini, Ollama, LM Studio." },
  { href: "/glossary", title: "Glossary", description: "Compare legal terms across jurisdictions and legal domains." },
  { href: "/statutes", title: "Statutes", description: "Search and browse statute indices." },
  { href: "/search", title: "Case Retrieval", description: "Multi-stage case retrieval with BM25, dense, and reranking." },
  { href: "/research", title: "Research Assistant", description: "RAG-powered legal Q&A with citation verification." },
  { href: "/contracts", title: "Contract Analysis", description: "Classify contract clauses and scan unfair ToS terms." },
  { href: "/clauses", title: "Clause Library", description: "Browse legal clauses with tone variants." },
  { href: "/templates", title: "Templates", description: "Legal document templates with variable rendering." },
  { href: "/compliance", title: "Compliance", description: "Check documents against PDPA, Employment Act, and more." },
  { href: "/ner", title: "Legal NER", description: "Extract legal entities from multilingual text." },
  { href: "/predictions", title: "Court Prediction", description: "SCOTUS, ECtHR, CaseHOLD, and EUR-LEX predictors." },
  { href: "/benchmarks", title: "Benchmarks", description: "LexGLUE model performance and baseline deltas." },
  { href: "/rome-statute", title: "Rome Statute", description: "Browse and search ICC treaty articles." },
];

export default async function HomePage() {
  const [status, metrics] = await Promise.all([getReady(), getMetrics()]);
  const services = Object.entries(status.services);

  return (
    <section>
      <div className="hero-card">
        <p className="hero-kicker">Legal AI Platform</p>
        <h2>Junas</h2>
        <p>
          Multi-jurisdiction legal retrieval, BYOK AI chat, contract analysis, compliance checking,
          court prediction, and document drafting — all in one platform.
        </p>
        <div className="chip-row">
          <Link href="/chat" className="chip chip-active">
            Start Chat
          </Link>
          <Link href="/benchmarks" className="chip">
            View Benchmarks
          </Link>
        </div>
      </div>

      <h3>System Status</h3>
      {services.length === 0 ? (
        <p>Status unavailable. Confirm API connectivity.</p>
      ) : (
        <ul className="status-grid">
          {services.map(([name, healthy]) => (
            <li key={name} className="result-card">
              <div className="result-header">
                <strong>{name}</strong>
                <span className={`status-dot ${healthy ? "status-green" : "status-red"}`} />
              </div>
              <p className="meta-line">{healthy ? "ready" : "unavailable"}</p>
            </li>
          ))}
        </ul>
      )}

      {metrics ? (
        <div className="summary-grid">
          <article className="result-card">
            <h4>Uptime</h4>
            <p>{metrics.uptime_seconds}s</p>
          </article>
          <article className="result-card">
            <h4>Models Loaded</h4>
            <p>{metrics.models_loaded.length}</p>
          </article>
          <article className="result-card">
            <h4>Benchmark Runs</h4>
            <p>{metrics.benchmark_runs}</p>
          </article>
          <article className="result-card">
            <h4>Conversations</h4>
            <p>{metrics.conversations}</p>
          </article>
        </div>
      ) : null}

      <h3>Feature Modules</h3>
      <div className="feature-grid">
        {featureCards.map((card) => (
          <Link key={card.href} href={card.href} className="result-card feature-card">
            <h4>{card.title}</h4>
            <p>{card.description}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
