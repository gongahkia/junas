"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { askResearch, getResearchConversation, getResearchConfig } from "../../lib/api-client";

type SourceType = "statute" | "glossary" | "case_law";

type CitationItem = {
  citation: string;
  type: string;
  in_context: boolean;
  exists_in_index: boolean;
  position: [number, number];
};

type SourceChunk = {
  source_id: string;
  source_type: string;
  text_snippet: string;
  metadata: Record<string, unknown>;
  relevance_score: number;
};

type CitationReport = {
  citations?: CitationItem[];
  total_citations?: number;
  verified_citations?: number;
  hallucinated_citations?: CitationItem[];
  citation_rate?: number;
};

type AskResponse = {
  answer: string;
  sources: SourceChunk[];
  citations: CitationReport;
  conversation_id: string;
};

type ConversationTurn = {
  role: string;
  content: string;
  sources?: SourceChunk[];
  citations?: CitationReport;
  created_at?: string;
};

type ConversationResponse = {
  conversation_id: string;
  turns: ConversationTurn[];
};

type ConfigResponse = {
  provider: string;
  model: string;
  available_sources: string[];
  max_context_chunks: number;
};

const defaultSources: SourceType[] = ["statute", "glossary"];

function isSourceType(value: string): value is SourceType {
  return value === "statute" || value === "glossary" || value === "case_law";
}

function isConfigResponse(data: unknown): data is ConfigResponse {
  return typeof data === "object" && data !== null && Array.isArray((data as ConfigResponse).available_sources);
}

function isAskResponse(data: unknown): data is AskResponse {
  return typeof data === "object" && data !== null && typeof (data as AskResponse).conversation_id === "string";
}

function isConversationResponse(data: unknown): data is ConversationResponse {
  return typeof data === "object" && data !== null && Array.isArray((data as ConversationResponse).turns);
}

function apiError(data: unknown): string | null {
  if (typeof data !== "object" || data === null || !("error" in data)) return null;
  const error = (data as { error?: unknown }).error;
  return error ? String(error) : null;
}

function citationHref(citation: string): string | null {
  const orsMatch = citation.match(/^ORS\s+([0-9A-Z]+\.[0-9]+)/i);
  if (orsMatch) {
    return `/statutes/section/${encodeURIComponent(orsMatch[1])}`;
  }

  const glossaryMatch = citation.match(/: "([^"]+)"$/);
  if (glossaryMatch) {
    return `/glossary/${encodeURIComponent(glossaryMatch[1])}`;
  }

  return null;
}

export default function ResearchPage() {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(8);
  const [selectedSources, setSelectedSources] = useState<SourceType[]>(defaultSources);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [latestSources, setLatestSources] = useState<SourceChunk[]>([]);
  const [latestCitations, setLatestCitations] = useState<CitationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let isActive = true;
    (async () => {
      try {
        const data = await getResearchConfig();
        if (!isActive || !isConfigResponse(data)) return;
        setConfig(data);
      } catch {
        if (isActive) setConfig(null);
      }
    })();
    return () => {
      isActive = false;
    };
  }, []);

  const availableSources = (config?.available_sources ?? ["statute", "glossary", "case_law"]).filter(
    (source): source is SourceType => isSourceType(source),
  );
  const turns = conversation?.turns ?? [];
  const latestAssistant = [...turns].reverse().find((turn) => turn.role === "assistant") ?? null;
  const renderedSources = latestSources.length > 0 ? latestSources : latestAssistant?.sources ?? [];
  const renderedCitations = latestCitations ?? latestAssistant?.citations ?? null;

  const toggleSource = (source: SourceType) => {
    setSelectedSources((current) =>
      current.includes(source) ? current.filter((item) => item !== source) : [...current, source],
    );
  };

  const resetConversation = () => {
    setQuestion("");
    setTopK(8);
    setSelectedSources(defaultSources);
    setConversationId(null);
    setConversation(null);
    setLatestSources([]);
    setLatestCitations(null);
    setError(null);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) {
      setError("Enter a question before asking the research assistant.");
      setConversation(null);
      setLatestSources([]);
      setLatestCitations(null);
      return;
    }

    const requestSources = selectedSources.filter((source) => availableSources.includes(source));
    if (requestSources.length === 0) {
      setError("Select at least one source.");
      return;
    }

    const boundedTopK = Math.min(12, Math.max(1, Number(topK) || 8));
    setTopK(boundedTopK);
    setIsLoading(true);
    setError(null);

    try {
      const data = await askResearch(
        normalizedQuestion,
        requestSources,
        boundedTopK,
        conversationId ?? undefined,
      );
      const askError = apiError(data);
      if (askError) {
        setError(askError);
        return;
      }
      if (!isAskResponse(data)) {
        setError("Research request failed.");
        return;
      }

      const nextConversationId = data.conversation_id;
      setConversationId(nextConversationId);
      setLatestSources(data.sources ?? []);
      setLatestCitations(data.citations ?? null);

      const fetched = await getResearchConversation(nextConversationId);
      if (isConversationResponse(fetched)) {
        setConversation(fetched);
      } else {
        setConversation({
          conversation_id: nextConversationId,
          turns: [
            { role: "user", content: normalizedQuestion },
            { role: "assistant", content: data.answer, sources: data.sources, citations: data.citations },
          ],
        });
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Research request failed.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="research-grid">
      <div>
        <h2>Legal Research Assistant</h2>
        <p>Ask legal questions grounded in statutes, glossary definitions, case law, and Rome Statute treaty text.</p>

        <form method="post" className="ner-form" onSubmit={onSubmit}>
          <label htmlFor="question">Question</label>
          <textarea
            id="question"
            name="question"
            rows={5}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What constitutes genocide under the Rome Statute?"
          />

          <label htmlFor="top_k">Context chunks</label>
          <input
            id="top_k"
            name="top_k"
            type="number"
            min={1}
            max={12}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value) || 8)}
          />

          <div className="chip-row">
            {availableSources.includes("statute") ? (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  name="sources"
                  value="statute"
                  checked={selectedSources.includes("statute")}
                  onChange={() => toggleSource("statute")}
                />
                Statutes
              </label>
            ) : null}
            {availableSources.includes("glossary") ? (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  name="sources"
                  value="glossary"
                  checked={selectedSources.includes("glossary")}
                  onChange={() => toggleSource("glossary")}
                />
                Glossary
              </label>
            ) : null}
            {availableSources.includes("case_law") ? (
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  name="sources"
                  value="case_law"
                  checked={selectedSources.includes("case_law")}
                  onChange={() => toggleSource("case_law")}
                />
                Case law
              </label>
            ) : null}
          </div>

          <div className="chip-row">
            <button type="submit" disabled={isLoading}>
              {isLoading ? "Asking..." : "Ask"}
            </button>
            <button
              type="button"
              className="chip"
              onClick={resetConversation}
              style={{
                background: "transparent",
                border: "1px solid #D6D3D1",
                borderRadius: "999px",
                color: "inherit",
                padding: "0.2rem 0.6rem",
              }}
            >
              New Conversation
            </button>
          </div>
        </form>

        {error ? (
          <article className="result-card">
            <h3>Request failed</h3>
            <p>{error}</p>
          </article>
        ) : null}

        <div className="chat-thread">
          {turns.length === 0 ? (
            <p>Submit a question to begin a conversation.</p>
          ) : (
            turns.map((turn, index) => (
              <article
                key={`${turn.role}-${index}-${turn.created_at ?? ""}`}
                className={`chat-message ${turn.role === "user" ? "chat-user" : "chat-assistant"}`}
              >
                <p className="meta-line">{turn.role === "user" ? "You" : "Junas"}</p>
                <p>{turn.content}</p>
              </article>
            ))
          )}
        </div>
      </div>

      <aside>
        <h3>Conversation</h3>
        <ul className="chapter-list">
          <li>conversation_id: {conversationId ?? "-"}</li>
          <li>turns: {turns.length}</li>
          <li>llm: {config ? `${config.provider} / ${config.model}` : "-"}</li>
        </ul>

        <h3>Citation Report</h3>
        {renderedCitations ? (
          <>
            <ul className="chapter-list">
              <li>total: {renderedCitations.total_citations ?? 0}</li>
              <li>verified: {renderedCitations.verified_citations ?? 0}</li>
              <li>hallucinated: {(renderedCitations.hallucinated_citations ?? []).length}</li>
            </ul>

            <ul className="chapter-list">
              {(renderedCitations.citations ?? []).map((item, index) => {
                const href = citationHref(item.citation);
                const statusClass =
                  item.exists_in_index && item.in_context
                    ? "citation-ok"
                    : item.exists_in_index
                      ? "citation-warn"
                      : "citation-bad";

                return (
                  <li key={`${item.citation}-${index}`} className={statusClass}>
                    {href ? <Link href={href}>{item.citation}</Link> : item.citation}
                  </li>
                );
              })}
            </ul>
          </>
        ) : (
          <p>No citations yet.</p>
        )}

        <h3>Retrieved Sources</h3>
        {renderedSources.length === 0 ? (
          <p>No source chunks yet.</p>
        ) : (
          <ul className="results-list">
            {renderedSources.map((source) => (
              <li key={`${source.source_type}-${source.source_id}`} className="result-card">
                <div className="result-header">
                  <strong>{source.source_id}</strong>
                  <span className="badge">{source.source_type}</span>
                </div>
                <p>{source.text_snippet.slice(0, 220)}...</p>
                <p className="meta-line">score: {source.relevance_score.toFixed(4)}</p>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </section>
  );
}
