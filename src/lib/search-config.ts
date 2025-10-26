/**
 * Search configuration and constants
 */

export const SEARCH_CONFIG = {
  // Result limits
  MAX_RESULTS: 20,
  DEFAULT_RESULTS: 10,

  // Relevance thresholds
  MIN_RELEVANCE: 0.3,
  HIGH_RELEVANCE: 0.7,

  // Caching
  CACHE_TIMEOUT: 3600000, // 1 hour in milliseconds

  // Scraper timeouts
  SCRAPER_TIMEOUT: 15000, // 15 seconds
  SCRAPER_RETRIES: 3,

  // Ranking weights
  RANKING_WEIGHTS: {
    queryMatch: 0.4,
    recency: 0.2,
    authority: 0.3,
    citations: 0.1,
  },

  // Court authority levels
  COURT_AUTHORITY: {
    'Court of Appeal': 1.0,
    'Supreme Court': 1.0,
    'High Court': 0.8,
    'District Court': 0.6,
    'Magistrate Court': 0.5,
  },

  // Document type authority
  TYPE_AUTHORITY: {
    statute: 0.9,
    case: 0.8,
    regulation: 0.7,
  },
};

export default SEARCH_CONFIG;
