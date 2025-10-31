import { MLNERProcessor, Entity, NERResult } from './ner-processor';

/**
 * Performance optimization utilities for NER processing
 */

export interface ChunkProcessingResult {
  entities: Entity[];
  chunks: number;
  totalProcessingTime: number;
  averageChunkTime: number;
}

/**
 * NER Performance Optimizer
 */
export class NEROptimizer {
  private maxChunkSize: number = 512; // Max tokens per chunk
  private overlapSize: number = 50; // Overlap between chunks

  /**
   * Process large text in chunks to avoid memory issues
   */
  async processLargeText(text: string): Promise<ChunkProcessingResult> {
    const processor = MLNERProcessor.getInstance();
    const startTime = performance.now();

    // Split text into chunks
    const chunks = this.splitIntoChunks(text, this.maxChunkSize, this.overlapSize);

    // Process chunks
    const allEntities: Entity[] = [];
    let totalChunkTime = 0;

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const chunkStart = performance.now();

      const result = await processor.extractEntities(chunk.text);
      totalChunkTime += performance.now() - chunkStart;

      // Adjust entity positions based on chunk offset
      const adjustedEntities = result.entities.map(entity => ({
        ...entity,
        start: entity.start + chunk.offset,
        end: entity.end + chunk.offset,
      }));

      allEntities.push(...adjustedEntities);
    }

    // Remove duplicates from overlapping regions
    const deduplicatedEntities = this.deduplicateEntities(allEntities);

    const totalProcessingTime = performance.now() - startTime;

    return {
      entities: deduplicatedEntities,
      chunks: chunks.length,
      totalProcessingTime,
      averageChunkTime: totalChunkTime / chunks.length,
    };
  }

  /**
   * Split text into overlapping chunks
   */
  private splitIntoChunks(
    text: string,
    maxSize: number,
    overlap: number
  ): Array<{ text: string; offset: number }> {
    const chunks: Array<{ text: string; offset: number }> = [];

    // Approximate token count (1 token ≈ 4 characters)
    const approxChunkChars = maxSize * 4;
    const approxOverlapChars = overlap * 4;

    let offset = 0;

    while (offset < text.length) {
      const chunkEnd = Math.min(offset + approxChunkChars, text.length);

      // Try to break at sentence boundaries
      let breakPoint = chunkEnd;
      if (chunkEnd < text.length) {
        const sentenceEnd = text.lastIndexOf('.', chunkEnd);
        if (sentenceEnd > offset + approxChunkChars / 2) {
          breakPoint = sentenceEnd + 1;
        }
      }

      chunks.push({
        text: text.slice(offset, breakPoint).trim(),
        offset,
      });

      // Move to next chunk with overlap
      offset = breakPoint - approxOverlapChars;
      if (offset < 0) offset = breakPoint;
    }

    return chunks;
  }

  /**
   * Remove duplicate entities from overlapping chunks
   */
  private deduplicateEntities(entities: Entity[]): Entity[] {
    const seen = new Map<string, Entity>();

    for (const entity of entities) {
      const key = `${entity.text}:${entity.type}:${entity.start}`;

      // Keep entity with higher confidence score
      const existing = seen.get(key);
      if (!existing || entity.score > existing.score) {
        seen.set(key, entity);
      }
    }

    return Array.from(seen.values()).sort((a, b) => a.start - b.start);
  }

  /**
   * Batch process multiple texts
   */
  async batchProcess(texts: string[]): Promise<NERResult[]> {
    const processor = MLNERProcessor.getInstance();
    const results: NERResult[] = [];

    // Process in parallel batches
    const batchSize = 5;

    for (let i = 0; i < texts.length; i += batchSize) {
      const batch = texts.slice(i, i + batchSize);
      const batchResults = await Promise.all(
        batch.map(text => processor.extractEntities(text))
      );
      results.push(...batchResults);
    }

    return results;
  }

  /**
   * Adaptive chunking based on text complexity
   */
  async processAdaptive(text: string): Promise<ChunkProcessingResult> {
    // Estimate text complexity
    const complexity = this.estimateComplexity(text);

    // Adjust chunk size based on complexity
    const adaptiveChunkSize = Math.floor(this.maxChunkSize / complexity);

    const originalChunkSize = this.maxChunkSize;
    this.maxChunkSize = adaptiveChunkSize;

    const result = await this.processLargeText(text);

    // Restore original chunk size
    this.maxChunkSize = originalChunkSize;

    return result;
  }

  /**
   * Estimate text complexity (1.0 = simple, 2.0+ = complex)
   */
  private estimateComplexity(text: string): number {
    let complexity = 1.0;

    // Long sentences increase complexity
    const sentences = text.split(/[.!?]+/);
    const avgSentenceLength = text.length / sentences.length;
    if (avgSentenceLength > 100) complexity += 0.3;

    // Many proper nouns increase complexity
    const properNouns = text.match(/\b[A-Z][a-z]+\b/g) || [];
    const properNounRatio = properNouns.length / text.split(/\s+/).length;
    if (properNounRatio > 0.2) complexity += 0.3;

    // Legal terminology increases complexity
    const legalTerms = [
      'pursuant',
      'hereinafter',
      'aforementioned',
      'notwithstanding',
      'whereas',
    ];
    const legalTermCount = legalTerms.filter(term =>
      text.toLowerCase().includes(term)
    ).length;
    if (legalTermCount > 2) complexity += 0.4;

    return Math.min(complexity, 2.0);
  }

  /**
   * Stream processing for very large documents
   */
  async *processStream(
    text: string
  ): AsyncGenerator<{ entity: Entity; progress: number }> {
    const chunks = this.splitIntoChunks(text, this.maxChunkSize, this.overlapSize);
    const processor = MLNERProcessor.getInstance();

    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      const result = await processor.extractEntities(chunk.text);

      for (const entity of result.entities) {
        yield {
          entity: {
            ...entity,
            start: entity.start + chunk.offset,
            end: entity.end + chunk.offset,
          },
          progress: (i + 1) / chunks.length,
        };
      }
    }
  }

  /**
   * Optimize entity extraction with caching
   */
  private cache: Map<string, Entity[]> = new Map();

  async processWithCache(text: string): Promise<Entity[]> {
    // Check cache
    const cacheKey = this.hashText(text);
    const cached = this.cache.get(cacheKey);
    if (cached) {
      console.log('Cache hit for entity extraction');
      return cached;
    }

    // Process and cache
    const processor = MLNERProcessor.getInstance();
    const result = await processor.extractEntities(text);
    this.cache.set(cacheKey, result.entities);

    // Limit cache size
    if (this.cache.size > 100) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }

    return result.entities;
  }

  /**
   * Simple hash function for text
   */
  private hashText(text: string): string {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      const char = text.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString(36);
  }

  /**
   * Configure optimizer settings
   */
  configure(options: {
    maxChunkSize?: number;
    overlapSize?: number;
  }): void {
    if (options.maxChunkSize !== undefined) {
      this.maxChunkSize = options.maxChunkSize;
    }
    if (options.overlapSize !== undefined) {
      this.overlapSize = options.overlapSize;
    }
  }
}

/**
 * Global optimizer instance
 */
export const globalNEROptimizer = new NEROptimizer();
