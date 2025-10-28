import { extractCitations, extractCaseNames, extractAndLookupCitations } from '../citation-extractor'

describe('Citation Extractor', () => {
  describe('extractCitations', () => {
    it('should extract SLR(R) citations', () => {
      const text = 'In Spandeck Engineering [2007] 4 SLR(R) 100, the court held...'
      const citations = extractCitations(text)
      expect(citations).toContain('[2007] 4 SLR(R) 100')
    })

    it('should extract SLR citations without (R)', () => {
      const text = 'See Public Prosecutor v Lim Ah Seng [2007] 2 SLR 957'
      const citations = extractCitations(text)
      expect(citations).toContain('[2007] 2 SLR 957')
    })

    it('should extract SGCA citations', () => {
      const text = 'The decision in [2020] SGCA 45 established...'
      const citations = extractCitations(text)
      expect(citations).toContain('[2020] SGCA 45')
    })

    it('should extract SGHC citations', () => {
      const text = 'As stated in [2019] SGHC 123, the test is...'
      const citations = extractCitations(text)
      expect(citations).toContain('[2019] SGHC 123')
    })

    it('should extract multiple citations from the same text', () => {
      const text = 'See [2007] 4 SLR(R) 100 and [2020] SGCA 45 for reference'
      const citations = extractCitations(text)
      expect(citations).toHaveLength(2)
      expect(citations).toContain('[2007] 4 SLR(R) 100')
      expect(citations).toContain('[2020] SGCA 45')
    })

    it('should handle text without citations', () => {
      const text = 'This is a regular paragraph without any legal citations'
      const citations = extractCitations(text)
      expect(citations).toHaveLength(0)
    })
  })

  describe('extractCaseNames', () => {
    it('should extract case names in "v" format', () => {
      const text = 'In Smith v Jones, the court held...'
      const caseNames = extractCaseNames(text)
      expect(caseNames).toContain('Smith v Jones')
    })

    it('should extract case names in "v." format', () => {
      const text = 'The decision in Public Prosecutor v. Tan was significant'
      const caseNames = extractCaseNames(text)
      expect(caseNames).toContain('Public Prosecutor v. Tan')
    })

    it('should extract multiple case names', () => {
      const text = 'Cases like Smith v Jones and Brown v Williams show...'
      const caseNames = extractCaseNames(text)
      expect(caseNames.length).toBeGreaterThanOrEqual(2)
    })

    it('should filter out false positives', () => {
      const text = 'This is good v bad example'
      const caseNames = extractCaseNames(text)
      expect(caseNames).toHaveLength(0)
    })
  })

  describe('extractAndLookupCitations', () => {
    it('should return an array of Citation objects', async () => {
      const text = 'Reference [2007] 4 SLR(R) 100 for details'
      const citations = await extractAndLookupCitations(text)
      expect(Array.isArray(citations)).toBe(true)
    })

    it('should handle text without citations gracefully', async () => {
      const text = 'This has no citations'
      const citations = await extractAndLookupCitations(text)
      expect(citations).toHaveLength(0)
    })

    it('should return citations with proper structure', async () => {
      const text = 'In [2009] 2 SLR(R) 332, the court...'
      const citations = await extractAndLookupCitations(text)

      if (citations.length > 0) {
        const citation = citations[0]
        expect(citation).toHaveProperty('id')
        expect(citation).toHaveProperty('title')
        expect(citation).toHaveProperty('url')
        expect(citation).toHaveProperty('type')
        expect(citation.type).toBe('case')
        expect(citation.jurisdiction).toBe('Singapore')
      }
    })
  })
})

// Example test data for manual verification
export const TEST_CASES = {
  multipleFormats: `
    This response discusses several cases:
    - Spandeck Engineering [2007] 4 SLR(R) 100
    - Public Prosecutor v Lim [2009] 2 SLR(R) 332
    - The case of [2020] SGCA 45
    - See also [2019] SGHC 123
  `,
  caseNames: `
    The landmark case of Smith v Jones established the principle.
    Later, in Brown v Williams, the court refined this test.
  `,
  mixed: `
    In Spandeck Engineering [2007] 4 SLR(R) 100, the Court of Appeal
    established a new test. This was later applied in Smith v Jones [2020] SGCA 45.
  `,
  noMatches: `
    This is a regular legal discussion without specific case citations.
    It discusses general principles and legal concepts.
  `,
}
