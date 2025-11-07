import { Citation } from '@/types/chat';

/**
 * Export citations to BibTeX format
 */
export function exportToBibTeX(citations: Citation[]): string {
  const entries = citations.map((c, i) => {
    const key = `${c.type}${c.year || ''}${i}`;
    const type = c.type === 'case' ? 'misc' : c.type === 'article' ? 'article' : 'misc';
    
    let entry = `@${type}{${key},\n`;
    entry += `  title = {${c.title}},\n`;
    if (c.year) entry += `  year = {${c.year}},\n`;
    if (c.jurisdiction) entry += `  note = {${c.jurisdiction}},\n`;
    entry += `  url = {${c.url}}\n`;
    entry += `}\n`;
    
    return entry;
  });

  return entries.join('\n');
}

/**
 * Export citations to EndNote format (RIS)
 */
export function exportToEndNote(citations: Citation[]): string {
  const entries = citations.map(c => {
    const typeMap: Record<Citation['type'], string> = {
      case: 'CASE',
      statute: 'STAT',
      regulation: 'STAT',
      article: 'JOUR',
    };

    let entry = `TY  - ${typeMap[c.type]}\n`;
    entry += `TI  - ${c.title}\n`;
    if (c.year) entry += `PY  - ${c.year}\n`;
    if (c.jurisdiction) entry += `AD  - ${c.jurisdiction}\n`;
    entry += `UR  - ${c.url}\n`;
    entry += `ER  - \n`;

    return entry;
  });

  return entries.join('\n');
}

/**
 * Export citations to Zotero-compatible JSON format
 */
export function exportToZotero(citations: Citation[]): string {
  const items = citations.map(c => {
    const itemTypeMap: Record<Citation['type'], string> = {
      case: 'case',
      statute: 'statute',
      regulation: 'statute',
      article: 'journalArticle',
    };

    return {
      itemType: itemTypeMap[c.type],
      title: c.title,
      url: c.url,
      date: c.year?.toString(),
      jurisdiction: c.jurisdiction,
    };
  });

  return JSON.stringify(items, null, 2);
}

/**
 * Download exported citations as a file
 */
export function downloadCitationFile(content: string, format: 'bibtex' | 'endnote' | 'zotero') {
  const extensionMap = {
    bibtex: 'bib',
    endnote: 'ris',
    zotero: 'json',
  };

  const mimeMap = {
    bibtex: 'application/x-bibtex',
    endnote: 'application/x-research-info-systems',
    zotero: 'application/json',
  };

  const blob = new Blob([content], { type: mimeMap[format] });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `citations.${extensionMap[format]}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
