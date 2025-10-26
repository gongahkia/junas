import axios, { AxiosInstance } from 'axios';

/**
 * Base scraper class with common functionality
 */

export interface ScraperConfig {
  baseURL: string;
  timeout?: number;
  maxRetries?: number;
  retryDelay?: number;
  userAgent?: string;
}

export interface ScraperResult {
  success: boolean;
  data?: any;
  error?: string;
  cached?: boolean;
}

export class BaseScraper {
  protected client: AxiosInstance;
  protected config: Required<ScraperConfig>;
  protected cache: Map<string, { data: any; timestamp: number }>;
  protected cacheTimeout: number = 3600000; // 1 hour

  constructor(config: ScraperConfig) {
    this.config = {
      timeout: 10000,
      maxRetries: 3,
      retryDelay: 1000,
      userAgent: 'Mozilla/5.0 (compatible; JunasBot/1.0)',
      ...config,
    };

    this.client = axios.create({
      baseURL: this.config.baseURL,
      timeout: this.config.timeout,
      headers: {
        'User-Agent': this.config.userAgent,
      },
    });

    this.cache = new Map();
  }

  /**
   * Fetch with retry logic
   */
  protected async fetchWithRetry(
    url: string,
    retries: number = this.config.maxRetries
  ): Promise<string> {
    try {
      const response = await this.client.get(url);
      return response.data;
    } catch (error: any) {
      if (retries > 0) {
        await this.sleep(this.config.retryDelay);
        return this.fetchWithRetry(url, retries - 1);
      }
      throw new Error(`Failed to fetch ${url}: ${error.message}`);
    }
  }

  /**
   * Get from cache or fetch
   */
  protected async getCached(
    key: string,
    fetcher: () => Promise<any>
  ): Promise<{ data: any; cached: boolean }> {
    const cached = this.cache.get(key);

    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return { data: cached.data, cached: true };
    }

    const data = await fetcher();
    this.cache.set(key, { data, timestamp: Date.now() });

    return { data, cached: false };
  }

  /**
   * Clear cache
   */
  public clearCache(): void {
    this.cache.clear();
  }

  /**
   * Sleep utility
   */
  protected sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
