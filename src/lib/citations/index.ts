export type { ExtractedCitation, SingaporeCitationKind } from './extract';
export { extractSingaporeCitations } from './extract';
export type { NormalizedCitation } from './normalize';
export { normalizeExtractedCitation, normalizeExtractedCitations } from './normalize';
export type {
  CitationValidationIssue,
  CitationValidationStatus,
  ValidatedCitation,
} from './validate';
export { validateCitation, validateCitations } from './validate';
