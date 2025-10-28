import { Citation } from '@/types/chat'
import { LegalSearchEngine } from './legal-search'

/**
 * Patterns for Singapore legal citations
 */
const CITATION_PATTERNS = {
  // [YYYY] X SLR(R) XXX or [YYYY] SLR(R) XXX
  slr: /\[(\d{4})\]\s+(?:(\d+)\s+)?SLR\(R\)\s+(\d+)/gi,
  // [YYYY] X SLR XXX or [YYYY] SLR XXX
  slrShort: /\[(\d{4})\]\s+(?:(\d+)\s+)?SLR\s+(\d+)/gi,
  // [YYYY] SGCA XX
  sgca: /\[(\d{4})\]\s+SGCA\s+(\d+)/gi,
  // [YYYY] SGHC XX
  sghc: /\[(\d{4})\]\s+SGHC\s+(\d+)/gi,
  // [YYYY] SGDC XX
  sgdc: /\[(\d{4})\]\s+SGDC\s+(\d+)/gi,
  // [YYYY] SGMC XX
  sgmc: /\[(\d{4})\]\s+SGMC\s+(\d+)/gi,
  // Common case name patterns (case_name v case_name)
  caseName: /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+v\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b/g,
}

/**
 * Extract all legal citations from text
 * @param text - Text to search for citations
 * @returns Array of unique citation strings
 */
export function extractCitations(text: string): string[] {
  const citations = new Set<string>()

  // Extract all citation patterns
  Object.values(CITATION_PATTERNS).forEach(pattern => {
    // Reset lastIndex for global regex
    pattern.lastIndex = 0
    const matches = text.matchAll(pattern)
    for (const match of matches) {
      citations.add(match[0].trim())
    }
  })

  return Array.from(citations)
}

/**
 * Extract case names from text
 * @param text - Text to search for case names
 * @returns Array of case name patterns (e.g., "Smith v Jones")
 */
export function extractCaseNames(text: string): string[] {
  const caseNames = new Set<string>()

  // Reset lastIndex for global regex
  CITATION_PATTERNS.caseName.lastIndex = 0
  const matches = text.matchAll(CITATION_PATTERNS.caseName)

  for (const match of matches) {
    const caseName = match[0].trim()
    // Filter out common false positives
    if (!isFalsePositiveCaseName(caseName)) {
      caseNames.add(caseName)
    }
  }

  return Array.from(caseNames)
}

/**
 * Check if a case name is likely a false positive
 */
function isFalsePositiveCaseName(caseName: string): boolean {
  const lowerCase = caseName.toLowerCase()

  // Common false positives
  const falsePositives = [
    'good v bad',
    'right v wrong',
    'true v false',
    'high v low',
    'state v federal',
  ]

  return falsePositives.some(fp => lowerCase.includes(fp))
}

/**
 * Look up legal citations and return Citation objects
 * @param text - Text containing citations to look up
 * @returns Promise resolving to array of Citation objects with metadata
 */
export async function extractAndLookupCitations(text: string): Promise<Citation[]> {
  const citations: Citation[] = []

  // Extract citations from text
  const citationStrings = extractCitations(text)

  // Look up each citation
  for (const citation of citationStrings) {
    try {
      const results = await LegalSearchEngine.searchByCitation(citation)

      if (results.length > 0) {
        const result = results[0]
        citations.push({
          id: `citation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          title: `${result.title} ${citation}`,
          url: result.url,
          type: 'case',
          jurisdiction: 'Singapore',
          year: extractYearFromCitation(citation),
        })
      }
    } catch (error) {
      console.error(`Failed to lookup citation: ${citation}`, error)
      // Continue with other citations even if one fails
    }
  }

  // Also look up case names
  const caseNames = extractCaseNames(text)

  for (const caseName of caseNames) {
    try {
      const results = await LegalSearchEngine.searchCaseLaw(caseName)

      if (results.length > 0) {
        const result = results[0]
        // Only add if we haven't already added this case via citation
        const alreadyExists = citations.some(c => c.title.includes(result.title))

        if (!alreadyExists) {
          citations.push({
            id: `case-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            title: result.title,
            url: result.url,
            type: 'case',
            jurisdiction: 'Singapore',
          })
        }
      }
    } catch (error) {
      console.error(`Failed to lookup case name: ${caseName}`, error)
      // Continue with other case names even if one fails
    }
  }

  return citations
}

/**
 * Extract year from citation string
 */
function extractYearFromCitation(citation: string): number | undefined {
  const yearMatch = citation.match(/\[(\d{4})\]/)
  return yearMatch ? parseInt(yearMatch[1]) : undefined
}

/**
 * Format citation for display with full legal citation
 * @param citation - Citation object
 * @returns Formatted string with full citation details
 */
export function formatCitationForDisplay(citation: Citation): string {
  const parts = [citation.title]

  if (citation.year) {
    parts.push(`[${citation.year}]`)
  }

  if (citation.jurisdiction) {
    parts.push(citation.jurisdiction)
  }

  return parts.join(' - ')
}
