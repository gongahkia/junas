# Legal Search System Documentation

## Overview

The Junas legal search system provides comprehensive search capabilities for Singapore legal resources including statutes, case law, and regulations.

## Architecture

### Components

1. **Scrapers** (`src/lib/scrapers/`)
   - `base-scraper.ts`: Base class with caching and retry logic
   - `sso-scraper.ts`: Singapore Statutes Online scraper
   - `case-scraper.ts`: Case law scraper with mock data

2. **Search Engine** (`src/lib/tools/legal-search.ts`)
   - Unified interface for all search operations
   - Parallel search across multiple sources
   - Integration with ranking and filtering

3. **Ranking** (`src/lib/search-ranking.ts`)
   - Multi-factor relevance scoring
   - Query match, recency, authority, citations
   - Result filtering by relevance threshold

4. **Filters** (`src/lib/search-filters.ts`)
   - Filter by type, year, jurisdiction, court
   - Dynamic filter options from results

5. **Configuration** (`src/lib/search-config.ts`)
   - Centralized configuration constants
   - Ranking weights and authority levels

6. **Error Handling** (`src/lib/search-errors.ts`)
   - Custom error types
   - Retryable error detection

## Usage

### Basic Search

```typescript
import { LegalSearchEngine } from '@/lib/tools/legal-search';

// Search all sources
const results = await LegalSearchEngine.searchAll('employment contract');

// Search statutes only
const statutes = await LegalSearchEngine.searchSingaporeStatutes('Companies Act');

// Search case law
const cases = await LegalSearchEngine.searchCaseLaw('negligence');
```

### Advanced Filtering

```typescript
import { SearchFilter, SearchFilters } from '@/lib/search-filters';

const filters: SearchFilters = {
  types: ['case'],
  years: { min: 2010, max: 2024 },
  courts: ['Court of Appeal'],
  minRelevance: 0.5,
};

const filtered = SearchFilter.applyFilters(results, filters);
```

### Ranking

```typescript
import { SearchRanker } from '@/lib/search-ranking';

const ranked = SearchRanker.rankResults(results, 'employment law');
const highQuality = SearchRanker.filterByRelevance(ranked, 0.7);
```

## API Integration

### Singapore Statutes Online (SSO)

- **Base URL**: `https://sso.agc.gov.sg`
- **Methods**: Search, browse by title, browse by category
- **Caching**: 1 hour default
- **Rate Limiting**: 3 retries with 1s delay

### Case Law Database

- **Source**: Structured mock data (LawNet requires auth)
- **Coverage**: Landmark Singapore cases
- **Topics**: Contract, tort, employment, property, criminal

## Configuration

Edit `src/lib/search-config.ts` to adjust:

- Result limits (default: 20)
- Relevance thresholds (min: 0.3)
- Cache timeout (default: 1 hour)
- Ranking weights
- Court authority levels

## Error Handling

All errors inherit from `SearchError`:

- **ScraperError**: Scraping failures (retryable)
- **NetworkError**: Connection issues (retryable)
- **TimeoutError**: Request timeouts (retryable)
- **InvalidQueryError**: Bad queries (not retryable)

## Performance

- **Caching**: In-memory cache with 1-hour TTL
- **Parallel Requests**: All sources searched concurrently
- **Retry Logic**: 3 retries with exponential backoff
- **Timeouts**: 15 seconds per request

## Future Enhancements

1. **Authentication**: LawNet API integration
2. **Elasticsearch**: Full-text search indexing
3. **Redis**: Distributed caching
4. **Analytics**: Search query tracking
5. **ML Models**: Learning-to-rank algorithms

## Testing

```bash
# Run search tests
npm test src/lib/tools/legal-search.test.ts

# Test scrapers
npm test src/lib/scrapers/*.test.ts
```

## License

Part of Junas legal assistant application.
