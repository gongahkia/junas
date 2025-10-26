import * as cheerio from 'cheerio';
import { BaseScraper, ScraperResult } from './base-scraper';

/**
 * Singapore Statutes Online (SSO) scraper
 * Scrapes https://sso.agc.gov.sg for Singapore legislation
 */

export interface StatuteResult {
  title: string;
  url: string;
  summary: string;
  year?: string;
  chapter?: string;
  sections?: string[];
}

export class SSOScraper extends BaseScraper {
  constructor() {
    super({
      baseURL: 'https://sso.agc.gov.sg',
      timeout: 15000,
      maxRetries: 3,
    });
  }

  /**
   * Search for statutes by keyword
   */
  async searchStatutes(query: string): Promise<ScraperResult> {
    try {
      const cacheKey = `statutes:${query}`;

      const { data, cached } = await this.getCached(cacheKey, async () => {
        // Search URL format
        const searchURL = `/search?query=${encodeURIComponent(query)}`;

        try {
          const html = await this.fetchWithRetry(searchURL);
          const $ = cheerio.load(html);

          const results: StatuteResult[] = [];

          // Parse search results
          $('.search-result').each((_, element) => {
            const $elem = $(element);
            const title = $elem.find('.title').text().trim();
            const url = $elem.find('a').attr('href');
            const summary = $elem.find('.summary').text().trim();

            if (title && url) {
              results.push({
                title,
                url: url.startsWith('http') ? url : `${this.config.baseURL}${url}`,
                summary,
              });
            }
          });

          return results;
        } catch (error) {
          // Fallback to browse by title
          return await this.browseByTitle(query);
        }
      });

      return {
        success: true,
        data,
        cached,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to search statutes',
      };
    }
  }

  /**
   * Browse statutes by title (alphabetical listing)
   */
  private async browseByTitle(query: string): Promise<StatuteResult[]> {
    const browseURL = '/Browse/Title';
    const html = await this.fetchWithRetry(browseURL);
    const $ = cheerio.load(html);

    const results: StatuteResult[] = [];
    const queryLower = query.toLowerCase();

    // Find matching acts in alphabetical list
    $('a[href^="/Act/"]').each((_, element) => {
      const $elem = $(element);
      const title = $elem.text().trim();
      const href = $elem.attr('href');

      if (title.toLowerCase().includes(queryLower) && href) {
        results.push({
          title,
          url: `${this.config.baseURL}${href}`,
          summary: title,
        });
      }
    });

    return results.slice(0, 10); // Limit to top 10 results
  }

  /**
   * Get statute details by URL
   */
  async getStatuteDetails(url: string): Promise<ScraperResult> {
    try {
      const cacheKey = `statute:${url}`;

      const { data, cached } = await this.getCached(cacheKey, async () => {
        const html = await this.fetchWithRetry(url);
        const $ = cheerio.load(html);

        const title = $('h1').first().text().trim();
        const year = $('.act-year').text().trim() ||
                     title.match(/\d{4}/)?.[0] || '';
        const chapter = $('.act-chapter').text().trim();

        // Extract sections
        const sections: string[] = [];
        $('a[href*="#section"]').each((_, elem) => {
          const section = $(elem).text().trim();
          if (section && !sections.includes(section)) {
            sections.push(section);
          }
        });

        return {
          title,
          url,
          year,
          chapter,
          sections: sections.slice(0, 20), // First 20 sections
          summary: $('.act-summary').text().trim() ||
                   `${title} (${year})`,
        };
      });

      return {
        success: true,
        data,
        cached,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to fetch statute details',
      };
    }
  }

  /**
   * Get all acts by category
   */
  async getActsByCategory(category: string): Promise<ScraperResult> {
    try {
      const categoryMap: Record<string, string> = {
        'constitutional': 'Constitutional',
        'civil': 'Civil',
        'criminal': 'Criminal',
        'commercial': 'Commercial',
        'family': 'Family',
        'property': 'Property',
      };

      const categoryPath = categoryMap[category.toLowerCase()] || 'All';
      const cacheKey = `category:${categoryPath}`;

      const { data, cached } = await this.getCached(cacheKey, async () => {
        const browseURL = `/Browse/Category/${categoryPath}`;

        try {
          const html = await this.fetchWithRetry(browseURL);
          const $ = cheerio.load(html);

          const results: StatuteResult[] = [];

          $('.act-listing a').each((_, element) => {
            const $elem = $(element);
            const title = $elem.text().trim();
            const href = $elem.attr('href');

            if (title && href) {
              results.push({
                title,
                url: href.startsWith('http') ? href : `${this.config.baseURL}${href}`,
                summary: title,
              });
            }
          });

          return results;
        } catch {
          // Fallback to general browse
          return [];
        }
      });

      return {
        success: true,
        data,
        cached,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message || 'Failed to browse category',
      };
    }
  }
}

// Export singleton instance
export const ssoScraper = new SSOScraper();
