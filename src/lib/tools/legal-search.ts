import { LegalSearchResult } from '@/types/tool';
import { ssoScraper } from '@/lib/scrapers/sso-scraper';
import { caseScraper } from '@/lib/scrapers/case-scraper';
import { SearchRanker } from '@/lib/search-ranking';

/**
 * Enhanced Legal Search Engine using real scrapers
 */

export class LegalSearchEngine {
  /**
   * Search Singapore Statutes using SSO scraper
   */
  static async searchSingaporeStatutes(query: string): Promise<LegalSearchResult[]> {
    try {
      const result = await ssoScraper.searchStatutes(query);

      if (!result.success || !result.data) {
        console.error('SSO search failed:', result.error);
        return [];
      }

      // Convert scraper results to LegalSearchResult format
      return result.data.map((statute: any, index: number) => ({
        title: statute.title,
        url: statute.url,
        type: 'statute' as const,
        jurisdiction: 'Singapore',
        year: statute.year ? parseInt(statute.year) : undefined,
        summary: statute.summary,
        relevanceScore: 0.95 - (index * 0.05), // Decrease score by position
      }));
    } catch (error) {
      console.error('Error searching statutes:', error);
      return [];
    }
  }

  /**
   * Search Case Law using case scraper
   */
  static async searchCaseLaw(query: string): Promise<LegalSearchResult[]> {
    try {
      const result = await caseScraper.searchCases(query);

      if (!result.success || !result.data) {
        console.error('Case search failed:', result.error);
        return [];
      }

      // Convert scraper results to LegalSearchResult format
      return result.data.map((caseItem: any, index: number) => ({
        title: `${caseItem.title} ${caseItem.citation}`,
        url: caseItem.url,
        type: 'case' as const,
        jurisdiction: 'Singapore',
        year: caseItem.year ? parseInt(caseItem.year) : undefined,
        summary: caseItem.summary,
        relevanceScore: 0.90 - (index * 0.05),
        citation: caseItem.citation,
        court: caseItem.court,
      }));
    } catch (error) {
      console.error('Error searching cases:', error);
      return [];
    }
  }

  /**
   * Search regulations (combines with statutes)
   */
  static async searchRegulations(query: string): Promise<LegalSearchResult[]> {
    try {
      // Regulations are part of SSO
      const result = await ssoScraper.searchStatutes(`regulation ${query}`);

      if (!result.success || !result.data) {
        return [];
      }

      return result.data
        .filter((item: any) =>
          item.title.toLowerCase().includes('regulation') ||
          item.title.toLowerCase().includes('rules')
        )
        .map((regulation: any, index: number) => ({
          title: regulation.title,
          url: regulation.url,
          type: 'regulation' as const,
          jurisdiction: 'Singapore',
          year: regulation.year ? parseInt(regulation.year) : undefined,
          summary: regulation.summary,
          relevanceScore: 0.85 - (index * 0.05),
        }));
    } catch (error) {
      console.error('Error searching regulations:', error);
      return [];
    }
  }

  /**
   * Search by topic
   */
  static async searchByTopic(topic: string): Promise<LegalSearchResult[]> {
    try {
      const topicMap: Record<string, string> = {
        employment: 'employment',
        contract: 'contract',
        property: 'property',
        corporate: 'companies',
        family: 'family',
        criminal: 'criminal',
      };

      const searchTerm = topicMap[topic.toLowerCase()] || topic;

      // Search both statutes and cases
      const [statutes, cases] = await Promise.all([
        this.searchSingaporeStatutes(searchTerm),
        this.searchCaseLaw(searchTerm),
      ]);

      // Combine and sort by relevance
      return [...statutes, ...cases].sort((a, b) =>
        (b.relevanceScore || 0) - (a.relevanceScore || 0)
      );
    } catch (error) {
      console.error('Error searching by topic:', error);
      return [];
    }
  }

  /**
   * Search all sources with intelligent ranking
   */
  static async searchAll(query: string): Promise<LegalSearchResult[]> {
    try {
      // Search all sources in parallel
      const [statutes, cases, regulations] = await Promise.all([
        this.searchSingaporeStatutes(query),
        this.searchCaseLaw(query),
        this.searchRegulations(query),
      ]);

      // Combine all results
      const allResults = [...statutes, ...cases, ...regulations];

      // Re-rank using intelligent ranking algorithm
      const rankedResults = SearchRanker.rankResults(allResults, query);

      // Filter by relevance threshold and limit results
      return SearchRanker.filterByRelevance(rankedResults, 0.3).slice(0, 20);
    } catch (error) {
      console.error('Error in comprehensive search:', error);
      return [];
    }
  }

  /**
   * Search by citation
   */
  static async searchByCitation(citation: string): Promise<LegalSearchResult[]> {
    try {
      const result = await caseScraper.searchByCitation(citation);

      if (!result.success || !result.data) {
        return [];
      }

      return [{
        title: `${result.data.title} ${result.data.citation}`,
        url: result.data.url,
        type: 'case' as const,
        jurisdiction: 'Singapore',
        year: result.data.year ? parseInt(result.data.year) : undefined,
        summary: result.data.summary,
        relevanceScore: 1.0,
        citation: result.data.citation,
        court: result.data.court,
      }];
    } catch (error) {
      console.error('Error searching by citation:', error);
      return [];
    }
  }

  /**
   * Get statute details
   */
  static async getStatuteDetails(url: string): Promise<any> {
    try {
      const result = await ssoScraper.getStatuteDetails(url);
      return result.success ? result.data : null;
    } catch (error) {
      console.error('Error getting statute details:', error);
      return null;
    }
  }
}
