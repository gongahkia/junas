import type { ExtractedCitation } from '@/lib/citations/extract';

export interface CitationPattern {
  kind: string;
  regex: RegExp;
  map: (match: RegExpMatchArray, start: number) => ExtractedCitation | null;
}
export interface JurisdictionConfig {
  id: string;
  name: string;
  shortName: string;
  citationPatterns: CitationPattern[];
  legalSourceDomains: {
    caseLaw: string[];
    statutes: string[];
  };
  systemPromptAddition: string;
  templateIds: string[];
}
