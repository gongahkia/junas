import { LegalSearchResult } from '@/types/tool';

/**
 * Search result ranking and relevance scoring
 */

export interface RankingFactors {
  queryMatch: number;      // 0-1: How well query matches title/content
  recency: number;          // 0-1: How recent the legal document is
  authority: number;        // 0-1: Court level or statute importance
  citations: number;        // 0-1: Number of times cited
}

export class SearchRanker {
  /**
   * Calculate relevance score based on multiple factors
   */
  static calculateRelevance(
    result: LegalSearchResult,
    query: string,
    factors: Partial<RankingFactors> = {}
  ): number {
    const queryMatch = this.calculateQueryMatch(result, query);
    const recency = this.calculateRecency(result.year);
    const authority = this.calculateAuthority(result);
    const citations = factors.citations || 0.5;

    // Weighted average
    const weights = {
      queryMatch: 0.4,
      recency: 0.2,
      authority: 0.3,
      citations: 0.1,
    };

    return (
      queryMatch * weights.queryMatch +
      recency * weights.recency +
      authority * weights.authority +
      citations * weights.citations
    );
  }

  /**
   * Calculate how well the query matches the result
   */
  private static calculateQueryMatch(result: LegalSearchResult, query: string): number {
    const queryLower = query.toLowerCase();
    const titleLower = result.title.toLowerCase();
    const summaryLower = (result.summary || '').toLowerCase();

    let score = 0;

    // Exact title match gets highest score
    if (titleLower === queryLower) {
      return 1.0;
    }

    // Title contains full query
    if (titleLower.includes(queryLower)) {
      score += 0.8;
    }

    // Summary contains full query
    if (summaryLower.includes(queryLower)) {
      score += 0.3;
    }

    // Calculate word overlap
    const queryWords = queryLower.split(/\s+/);
    const titleWords = titleLower.split(/\s+/);
    const summaryWords = summaryLower.split(/\s+/);

    let matchedWords = 0;
    for (const word of queryWords) {
      if (word.length < 3) continue; // Skip short words
      if (titleWords.includes(word)) matchedWords++;
      if (summaryWords.includes(word)) matchedWords += 0.5;
    }

    const wordScore = matchedWords / queryWords.length;
    score += wordScore * 0.5;

    return Math.min(score, 1.0);
  }

  /**
   * Calculate recency score (more recent = higher score)
   */
  private static calculateRecency(year?: number): number {
    if (!year) return 0.5;

    const currentYear = new Date().getFullYear();
    const age = currentYear - year;

    // Documents from last 5 years get highest score
    if (age <= 5) return 1.0;
    if (age <= 10) return 0.8;
    if (age <= 20) return 0.6;
    if (age <= 30) return 0.4;
    return 0.2;
  }

  /**
   * Calculate authority score based on type and court
   */
  private static calculateAuthority(result: LegalSearchResult): number {
    // Statutes have high authority
    if (result.type === 'statute') {
      return 0.9;
    }

    // Case law authority depends on court
    if (result.type === 'case' && result.court) {
      const courtLower = result.court.toLowerCase();
      if (courtLower.includes('court of appeal') || courtLower.includes('supreme')) {
        return 1.0;
      }
      if (courtLower.includes('high court')) {
        return 0.8;
      }
      if (courtLower.includes('district')) {
        return 0.6;
      }
      if (courtLower.includes('magistrate')) {
        return 0.5;
      }
    }

    // Regulations have moderate authority
    if (result.type === 'regulation') {
      return 0.7;
    }

    return 0.5;
  }

  /**
   * Rank and sort search results
   */
  static rankResults(
    results: LegalSearchResult[],
    query: string
  ): LegalSearchResult[] {
    return results
      .map(result => ({
        ...result,
        relevanceScore: this.calculateRelevance(result, query),
      }))
      .sort((a, b) => (b.relevanceScore || 0) - (a.relevanceScore || 0));
  }

  /**
   * Filter results by relevance threshold
   */
  static filterByRelevance(
    results: LegalSearchResult[],
    threshold: number = 0.3
  ): LegalSearchResult[] {
    return results.filter(result => (result.relevanceScore || 0) >= threshold);
  }

  /**
   * Group results by type
   */
  static groupByType(
    results: LegalSearchResult[]
  ): Record<string, LegalSearchResult[]> {
    const grouped: Record<string, LegalSearchResult[]> = {
      statute: [],
      case: [],
      regulation: [],
      other: [],
    };

    for (const result of results) {
      const type = result.type || 'other';
      if (!grouped[type]) {
        grouped[type] = [];
      }
      grouped[type].push(result);
    }

    return grouped;
  }
}
