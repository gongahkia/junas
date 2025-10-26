import { LegalSearchResult } from '@/types/tool';

/**
 * Search filters for legal results
 */

export interface SearchFilters {
  types?: Array<'statute' | 'case' | 'regulation'>;
  years?: { min?: number; max?: number };
  jurisdiction?: string;
  courts?: string[];
  minRelevance?: number;
}

export class SearchFilter {
  /**
   * Apply filters to search results
   */
  static applyFilters(
    results: LegalSearchResult[],
    filters: SearchFilters
  ): LegalSearchResult[] {
    let filtered = [...results];

    // Filter by type
    if (filters.types && filters.types.length > 0) {
      filtered = filtered.filter(r => r.type && filters.types!.includes(r.type as any));
    }

    // Filter by year range
    if (filters.years) {
      if (filters.years.min) {
        filtered = filtered.filter(r => !r.year || r.year >= filters.years!.min!);
      }
      if (filters.years.max) {
        filtered = filtered.filter(r => !r.year || r.year <= filters.years!.max!);
      }
    }

    // Filter by jurisdiction
    if (filters.jurisdiction) {
      filtered = filtered.filter(r =>
        r.jurisdiction?.toLowerCase() === filters.jurisdiction!.toLowerCase()
      );
    }

    // Filter by court
    if (filters.courts && filters.courts.length > 0) {
      filtered = filtered.filter(r =>
        r.court && filters.courts!.some(court =>
          r.court!.toLowerCase().includes(court.toLowerCase())
        )
      );
    }

    // Filter by minimum relevance
    if (filters.minRelevance !== undefined) {
      filtered = filtered.filter(r =>
        (r.relevanceScore || 0) >= filters.minRelevance!
      );
    }

    return filtered;
  }

  /**
   * Get available filter options from results
   */
  static getAvailableFilters(
    results: LegalSearchResult[]
  ): {
    types: string[];
    years: { min: number; max: number };
    jurisdictions: string[];
    courts: string[];
  } {
    const types = new Set<string>();
    const jurisdictions = new Set<string>();
    const courts = new Set<string>();
    const years: number[] = [];

    for (const result of results) {
      if (result.type) types.add(result.type);
      if (result.jurisdiction) jurisdictions.add(result.jurisdiction);
      if (result.court) courts.add(result.court);
      if (result.year) years.push(result.year);
    }

    const minYear = years.length > 0 ? Math.min(...years) : new Date().getFullYear() - 50;
    const maxYear = years.length > 0 ? Math.max(...years) : new Date().getFullYear();

    return {
      types: Array.from(types),
      years: { min: minYear, max: maxYear },
      jurisdictions: Array.from(jurisdictions),
      courts: Array.from(courts),
    };
  }
}
