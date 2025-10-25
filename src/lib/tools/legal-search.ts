import { LegalSearchResult } from '@/types/tool';

export class LegalSearchEngine {
  static async searchSingaporeStatutes(query: string): Promise<LegalSearchResult[]> {
    // This would integrate with Singapore Statutes Online (SSO)
    // For now, return mock results
    const mockResults: LegalSearchResult[] = [
      {
        title: 'Companies Act 1967',
        url: 'https://sso.agc.gov.sg/Act/CoA1967',
        type: 'statute',
        jurisdiction: 'Singapore',
        year: 1967,
        summary: 'An Act relating to companies and other bodies corporate.',
        relevanceScore: 0.95,
      },
      {
        title: 'Employment Act 1968',
        url: 'https://sso.agc.gov.sg/Act/EA1968',
        type: 'statute',
        jurisdiction: 'Singapore',
        year: 1968,
        summary: 'An Act relating to the employment of employees.',
        relevanceScore: 0.90,
      },
    ];

    return mockResults.filter(result => 
      result.title.toLowerCase().includes(query.toLowerCase()) ||
      result.summary.toLowerCase().includes(query.toLowerCase())
    );
  }

  static async searchCaseLaw(query: string): Promise<LegalSearchResult[]> {
    // This would integrate with LawNet or other case law databases
    // For now, return mock results
    const mockResults: LegalSearchResult[] = [
      {
        title: 'Lim Swee Khiang v Borden Co (Pte) Ltd [2006] 4 SLR(R) 745',
        url: 'https://www.lawnet.sg/lawnet/web/lawnet/free-resources?p_p_id=freeresources_WAR_lawnet3baseportlet&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_freeresources_WAR_lawnet3baseportlet_action=openContentPage&_freeresources_WAR_lawnet3baseportlet_docId=%2Fcontent%2Flawnet%2Flegal-resources%2Flegal-updates%2Fcase-summaries%2Flim-swee-khiang-v-borden-co-pte-ltd-2006-4-slr-r-745',
        type: 'case',
        jurisdiction: 'Singapore',
        year: 2006,
        summary: 'Case involving employment law and wrongful dismissal.',
        relevanceScore: 0.85,
      },
      {
        title: 'Tan Kok Tim Stanley v Personal Representatives of the Estate of Tan Ah Kng, deceased [2019] SGCA 50',
        url: 'https://www.lawnet.sg/lawnet/web/lawnet/free-resources?p_p_id=freeresources_WAR_lawnet3baseportlet&p_p_lifecycle=1&p_p_state=normal&p_p_mode=view&_freeresources_WAR_lawnet3baseportlet_action=openContentPage&_freeresources_WAR_lawnet3baseportlet_docId=%2Fcontent%2Flawnet%2Flegal-resources%2Flegal-updates%2Fcase-summaries%2Ftan-kok-tim-stanley-v-personal-representatives-of-the-estate-of-tan-ah-kng-deceased-2019-sgca-50',
        type: 'case',
        jurisdiction: 'Singapore',
        year: 2019,
        summary: 'Case involving inheritance and estate law.',
        relevanceScore: 0.80,
      },
    ];

    return mockResults.filter(result => 
      result.title.toLowerCase().includes(query.toLowerCase()) ||
      result.summary.toLowerCase().includes(query.toLowerCase())
    );
  }

  static async searchRegulations(query: string): Promise<LegalSearchResult[]> {
    // This would integrate with regulatory databases
    // For now, return mock results
    const mockResults: LegalSearchResult[] = [
      {
        title: 'Companies (Amendment) Regulations 2020',
        url: 'https://sso.agc.gov.sg/SL/CoA1967-S1-2020',
        type: 'regulation',
        jurisdiction: 'Singapore',
        year: 2020,
        summary: 'Amendments to the Companies Act regulations.',
        relevanceScore: 0.88,
      },
      {
        title: 'Employment (Amendment) Regulations 2019',
        url: 'https://sso.agc.gov.sg/SL/EA1968-S1-2019',
        type: 'regulation',
        jurisdiction: 'Singapore',
        year: 2019,
        summary: 'Amendments to the Employment Act regulations.',
        relevanceScore: 0.82,
      },
    ];

    return mockResults.filter(result => 
      result.title.toLowerCase().includes(query.toLowerCase()) ||
      result.summary.toLowerCase().includes(query.toLowerCase())
    );
  }

  static async searchAll(query: string): Promise<LegalSearchResult[]> {
    const [statutes, cases, regulations] = await Promise.all([
      this.searchSingaporeStatutes(query),
      this.searchCaseLaw(query),
      this.searchRegulations(query),
    ]);

    return [...statutes, ...cases, ...regulations]
      .sort((a, b) => b.relevanceScore - a.relevanceScore);
  }

  static async searchByTopic(topic: string): Promise<LegalSearchResult[]> {
    const topicQueries = {
      'employment': ['employment act', 'employment law', 'workplace', 'employee rights'],
      'contract': ['contract act', 'contract law', 'agreement', 'breach of contract'],
      'property': ['property act', 'property law', 'real estate', 'land law'],
      'corporate': ['companies act', 'corporate law', 'company law', 'corporate governance'],
      'family': ['family law', 'divorce', 'custody', 'inheritance'],
      'criminal': ['criminal law', 'penal code', 'criminal procedure'],
    };

    const relevantTopics = topicQueries[topic.toLowerCase() as keyof typeof topicQueries] || [topic];
    
    const allResults: LegalSearchResult[] = [];
    
    for (const query of relevantTopics) {
      const results = await this.searchAll(query);
      allResults.push(...results);
    }

    // Remove duplicates and sort by relevance
    const uniqueResults = allResults.filter((result, index, self) => 
      index === self.findIndex(r => r.title === result.title)
    );

    return uniqueResults.sort((a, b) => b.relevanceScore - a.relevanceScore);
  }

  static async searchByCitation(citation: string): Promise<LegalSearchResult | null> {
    // Parse different citation formats
    const citationPatterns = [
      // Case citations: [Year] SGCA 50, [Year] SGHC 100, etc.
      /\[(\d{4})\]\s+SG(CA|HC|DC|MC)\s+(\d+)/i,
      // Statute citations: s. 123, section 123, etc.
      /(?:s\.|section)\s*(\d+[a-z]?)/i,
      // Act citations: Companies Act 1967, etc.
      /([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act\s+(\d{4})/i,
    ];

    for (const pattern of citationPatterns) {
      const match = citation.match(pattern);
      if (match) {
        // Search for the specific citation
        const results = await this.searchAll(citation);
        return results[0] || null;
      }
    }

    return null;
  }

  static async getRecentUpdates(days: number = 30): Promise<LegalSearchResult[]> {
    // This would fetch recent legal updates
    // For now, return mock results
    const mockResults: LegalSearchResult[] = [
      {
        title: 'Companies (Amendment) Act 2024',
        url: 'https://sso.agc.gov.sg/Act/CoA1967-2024',
        type: 'statute',
        jurisdiction: 'Singapore',
        year: 2024,
        summary: 'Latest amendments to the Companies Act.',
        relevanceScore: 1.0,
      },
      {
        title: 'Employment (Amendment) Act 2024',
        url: 'https://sso.agc.gov.sg/Act/EA1968-2024',
        type: 'statute',
        jurisdiction: 'Singapore',
        year: 2024,
        summary: 'Latest amendments to the Employment Act.',
        relevanceScore: 1.0,
      },
    ];

    return mockResults;
  }

  static async getPopularSearches(): Promise<string[]> {
    return [
      'employment law',
      'contract law',
      'company law',
      'property law',
      'family law',
      'criminal law',
      'intellectual property',
      'data protection',
      'cybersecurity',
      'fintech',
    ];
  }

  static async getSearchSuggestions(query: string): Promise<string[]> {
    const suggestions = [
      'employment act',
      'companies act',
      'contract act',
      'property act',
      'family law',
      'criminal law',
      'intellectual property',
      'data protection',
      'cybersecurity',
      'fintech',
    ];

    return suggestions.filter(suggestion => 
      suggestion.toLowerCase().includes(query.toLowerCase())
    );
  }
}
