import Link from "next/link";
import createDOMPurify from "dompurify";
import { JSDOM } from "jsdom";
import { getStatuteSection } from "../../../../lib/api-server";

const DOMPurify = createDOMPurify(new JSDOM("").window);

type SectionResponse = {
  number: string;
  name: string;
  chapter_number: string;
  edition: number;
  text_html: string;
  text_plain: string;
  amendment_history: string;
  cross_references: string[];
  referenced_by: string[];
};

export default async function SectionPage({ params }: { params: { number: string } }) {
  const number = decodeURIComponent(params.number);
  const section = (await getStatuteSection(number)) as SectionResponse | null;

  if (!section) {
    return (
      <section>
        <p>
          <Link href="/statutes">Statutes</Link> / Section {number}
        </p>
        <h2>Section not found</h2>
      </section>
    );
  }

  /*
   * audit finding #7: SSO HTML is user-influenceable through ingestion.
   * keep DOMPurify on this dangerouslySetInnerHTML source.
   */
  const sanitizedTextHtml = DOMPurify.sanitize(section.text_html);

  return (
    <section>
      <p>
        <Link href="/statutes">Statutes</Link> /{" "}
        <Link href={`/statutes/chapter/${encodeURIComponent(section.chapter_number)}`}>
          Chapter {section.chapter_number}
        </Link>{" "}
        / {section.number}
      </p>

      <h2>
        {section.number} - {section.name}
      </h2>
      <p>Edition: {section.edition}</p>

      <article className="result-card">
        <div className="definition-html" dangerouslySetInnerHTML={{ __html: sanitizedTextHtml }} />
      </article>

      {section.amendment_history ? (
        <details>
          <summary>Amendment history</summary>
          <p>{section.amendment_history}</p>
        </details>
      ) : null}

      <h3>Cross References</h3>
      <ul>
        {section.cross_references.map((ref) => (
          <li key={ref}>
            <Link href={`/statutes/section/${encodeURIComponent(ref)}`}>ORS {ref}</Link>
          </li>
        ))}
      </ul>

      <h3>Referenced By</h3>
      <ul>
        {section.referenced_by.map((ref) => (
          <li key={ref}>
            <Link href={`/statutes/section/${encodeURIComponent(ref)}`}>ORS {ref}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
