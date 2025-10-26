/**
 * Custom error types for search operations
 */

export class SearchError extends Error {
  constructor(
    message: string,
    public code: string,
    public retryable: boolean = false
  ) {
    super(message);
    this.name = 'SearchError';
  }
}

export class ScraperError extends SearchError {
  constructor(message: string, public source: string) {
    super(message, 'SCRAPER_ERROR', true);
    this.name = 'ScraperError';
  }
}

export class NetworkError extends SearchError {
  constructor(message: string = 'Network request failed') {
    super(message, 'NETWORK_ERROR', true);
    this.name = 'NetworkError';
  }
}

export class TimeoutError extends SearchError {
  constructor(message: string = 'Request timed out') {
    super(message, 'TIMEOUT', true);
    this.name = 'TimeoutError';
  }
}

export class InvalidQueryError extends SearchError {
  constructor(message: string = 'Invalid search query') {
    super(message, 'INVALID_QUERY', false);
    this.name = 'InvalidQueryError';
  }
}

/**
 * Error handler for search operations
 */
export class SearchErrorHandler {
  static handle(error: any): SearchError {
    if (error instanceof SearchError) {
      return error;
    }

    if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      return new NetworkError(error.message);
    }

    if (error.code === 'ETIMEDOUT' || error.message?.includes('timeout')) {
      return new TimeoutError(error.message);
    }

    return new SearchError(
      error.message || 'An unknown search error occurred',
      'UNKNOWN_ERROR',
      false
    );
  }

  static isRetryable(error: any): boolean {
    if (error instanceof SearchError) {
      return error.retryable;
    }
    return false;
  }
}
