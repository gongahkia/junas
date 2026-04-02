import Link from "next/link";
import type { ReactNode } from "react";
import { listEntityTypes, extractEntities } from "../../lib/api-server";

type NerEntity = {
  text: string;
  type: string;
  type_label: string;
  start: number;
  end: number;
  confidence: number;
  language?: "de" | "en";
  gazetteer_match?: boolean;
  gazetteer_corrected?: boolean;
};

type NerExtractionResponse = {
  text: string;
  entities: NerEntity[];
  entity_counts: Record<string, number>;
  model_info: {
    model: string;
    language: "de" | "en";
    granularity: "fine" | "coarse";
    gazetteer_applied: boolean;
  };
};

type EntityTypesResponse = {
  fine_grained: Array<{ tag: string; label: string; description: string; category: string }>;
  coarse_grained: Array<{ tag: string; label: string; members: string[] }>;
};

const exampleTextsByLanguage: Record<"de" | "en", string[]> = {
  de: [
    "Der BGH hat in seinem Urteil vom 12. März 2023 (Az. III ZR 100/22) entschieden, dass § 433 BGB im vorliegenden Fall anzuwenden ist.",
    "Die Klägerin Frau Müller wurde von Rechtsanwalt Schneider vor dem Landgericht Berlin vertreten.",
    "Nach Art. 6 DSGVO und der Verordnung (EU) 2016/679 ist die Verarbeitung personenbezogener Daten nur unter bestimmten Voraussetzungen zulässig.",
  ],
  en: [
    "The Supreme Court held in Brown v. Board of Education, 347 U.S. 483 (1954), that racial segregation in public schools is unconstitutional.",
    "Counsel for the claimant argued that Article 7 of the Rome Statute defines crimes against humanity.",
    "Under Regulation (EU) 2016/679, personal data processing requires a lawful basis.",
  ],
};

async function fetchEntityTypes(): Promise<EntityTypesResponse> {
  return (await listEntityTypes()) as EntityTypesResponse;
}

async function fetchExtraction(
  text: string,
  language: "de" | "en",
  granularity: "fine" | "coarse",
  useGazetteer: boolean,
): Promise<{ result: NerExtractionResponse | null; error: string | null }> {
  if (!text.trim()) return { result: null, error: null };
  const data = await extractEntities(text, language, granularity, useGazetteer);
  if (data?.error) return { result: null, error: data.error };
  return { result: data as NerExtractionResponse, error: null };
}

function renderAnnotatedText(text: string, entities: NerEntity[]): ReactNode[] {
  const sorted = [...entities].sort((a, b) => {
    if (a.start !== b.start) {
      return a.start - b.start;
    }
    return a.end - b.end;
  });

  const nodes: ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((entity, index) => {
    const start = Math.max(cursor, Math.max(0, entity.start));
    const end = Math.max(start, Math.min(text.length, entity.end));
    if (start > cursor) {
      nodes.push(<span key={`text-${index}-${cursor}`}>{text.slice(cursor, start)}</span>);
    }
    if (end > start) {
      nodes.push(
        <span
          key={`ent-${index}-${start}`}
          className={`entity-chip entity-${entity.type}`}
          title={`${entity.type_label} (${entity.confidence.toFixed(2)})`}
        >
          {text.slice(start, end)}
        </span>,
      );
    }
    cursor = end;
  });

  if (cursor < text.length) {
    nodes.push(<span key={`text-tail-${cursor}`}>{text.slice(cursor)}</span>);
  }
  return nodes;
}

export default async function NerPage({
  searchParams,
}: {
  searchParams?: {
    text?: string;
    language?: "de" | "en";
    granularity?: "fine" | "coarse";
    use_gazetteer?: "true" | "false";
    run?: "0" | "1";
  };
}) {
  const language = searchParams?.language === "en" ? "en" : "de";
  const examples = exampleTextsByLanguage[language];
  const text = searchParams?.text ?? examples[0];
  const granularity = searchParams?.granularity === "coarse" ? "coarse" : "fine";
  const useGazetteer = searchParams?.use_gazetteer !== "false";
  const shouldRun = searchParams?.run === "1";

  const [types, extraction] = await Promise.all([
    fetchEntityTypes(),
    shouldRun
      ? fetchExtraction(text, language, granularity, useGazetteer)
      : Promise.resolve({ result: null, error: null }),
  ]);

  const result = extraction.result;
  const entityTotal = result ? Object.values(result.entity_counts).reduce((sum, value) => sum + value, 0) : 0;

  return (
    <section className="ner-grid">
      <div>
        <h2>Legal Named Entity Recognition</h2>
        <p>
          Extract people, organizations, legal norms, court references, and other legal entities from
          German and English legal text.
        </p>
        <p className="meta-line">
          Dataset license note: Legal-Entity-Recognition is distributed under CC-BY-NC-SA 4.0.
        </p>

        <form method="get" action="/ner" className="ner-form">
          <input type="hidden" name="run" value="1" />

          <label htmlFor="language">Language</label>
          <select id="language" name="language" defaultValue={language}>
            <option value="de">German (de)</option>
            <option value="en">English (en)</option>
          </select>

          <label htmlFor="text">Legal text</label>
          <textarea id="text" name="text" rows={10} defaultValue={text} placeholder="Paste legal text..." />

          <label htmlFor="granularity">Entity granularity</label>
          <select id="granularity" name="granularity" defaultValue={granularity}>
            <option value="fine">fine (19 entity types)</option>
            <option value="coarse">coarse (7 entity groups)</option>
          </select>

          <label className="checkbox-row">
            <input type="checkbox" name="use_gazetteer" value="true" defaultChecked={useGazetteer} />
            Apply gazetteer post-processing (German only)
          </label>

          <button type="submit">Extract Entities</button>
        </form>

        <div className="chip-row">
          {examples.map((example, index) => (
            <Link
              key={`example-${language}-${index}`}
              className="chip"
              href={`/ner?run=1&language=${language}&granularity=${granularity}&use_gazetteer=${useGazetteer ? "true" : "false"}&text=${encodeURIComponent(example)}`}
            >
              Example {index + 1}
            </Link>
          ))}
        </div>

        {extraction.error ? (
          <article className="result-card">
            <h3>Extraction unavailable</h3>
            <p>{extraction.error}</p>
          </article>
        ) : null}

        {result ? (
          <>
            <h3>Annotated Text</h3>
            <article className="result-card annotated-text">{renderAnnotatedText(result.text, result.entities)}</article>

            <h3>Entities ({result.entities.length})</h3>
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Text</th>
                  <th>Type</th>
                  <th>Confidence</th>
                  <th>Gazetteer</th>
                </tr>
              </thead>
              <tbody>
                {result.entities.map((entity, index) => (
                  <tr key={`${entity.type}-${entity.start}-${entity.end}-${index}`}>
                    <td>{entity.text}</td>
                    <td>
                      {entity.type} ({entity.type_label})
                    </td>
                    <td>{entity.confidence.toFixed(4)}</td>
                    <td>
                      {entity.gazetteer_corrected
                        ? "corrected"
                        : entity.gazetteer_match
                          ? "matched"
                          : "none"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
      </div>

      <aside>
        <h3>Model Info</h3>
        <ul className="chapter-list">
          <li>model: {result?.model_info.model ?? "-"}</li>
          <li>language: {result?.model_info.language ?? language}</li>
          <li>granularity: {result?.model_info.granularity ?? granularity}</li>
        </ul>

        <h3>Entity Distribution</h3>
        {result ? (
          <ul className="chapter-list">
            {Object.entries(result.entity_counts).map(([tag, count]) => (
              <li key={tag}>
                <div className="distribution-row">
                  <strong>{tag}</strong> <span>{count}</span>
                </div>
                <div className="distribution-track">
                  <div
                    className={`distribution-bar entity-${tag}`}
                    style={{ width: `${Math.max(4, Math.round((count / Math.max(1, entityTotal)) * 100))}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p>Submit text to view extracted entity counts.</p>
        )}

        <h3>Fine-Grained Types</h3>
        <ul className="chapter-list">
          {types.fine_grained.map((item) => (
            <li key={item.tag}>
              <strong>{item.tag}</strong>: {item.label}
            </li>
          ))}
        </ul>

        <h3>Coarse Mapping</h3>
        <ul className="chapter-list">
          {types.coarse_grained.map((item) => (
            <li key={item.tag}>
              <strong>{item.tag}</strong>: {item.members.join(", ")}
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
