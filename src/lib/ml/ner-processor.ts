import { pipeline, TokenClassificationPipeline } from '@xenova/transformers';

/**
 * ML-based Named Entity Recognition using Transformers.js
 */

export interface Entity {
  text: string;
  type: string;
  score: number;
  start: number;
  end: number;
}

export interface NERResult {
  entities: Entity[];
  text: string;
  processingTime: number;
}

/**
 * NER Processor using transformer models
 */
export class MLNERProcessor {
  private static instance: MLNERProcessor;
  private pipeline: TokenClassificationPipeline | null = null;
  private isLoading: boolean = false;
  private modelName: string = 'Xenova/bert-base-NER';

  private constructor() {}

  /**
   * Get singleton instance
   */
  static getInstance(): MLNERProcessor {
    if (!MLNERProcessor.instance) {
      MLNERProcessor.instance = new MLNERProcessor();
    }
    return MLNERProcessor.instance;
  }

  /**
   * Initialize the NER pipeline
   */
  async initialize(): Promise<void> {
    if (this.pipeline || this.isLoading) {
      return;
    }

    this.isLoading = true;

    try {
      // Load the token classification model
      this.pipeline = await pipeline(
        'token-classification',
        this.modelName,
        {
          quantized: true, // Use quantized model for faster inference
        }
      ) as TokenClassificationPipeline;

      console.log('NER model loaded successfully');
    } catch (error) {
      console.error('Failed to load NER model:', error);
      throw new Error('Failed to initialize NER model');
    } finally {
      this.isLoading = false;
    }
  }

  /**
   * Extract entities from text
   */
  async extractEntities(text: string): Promise<NERResult> {
    const startTime = performance.now();

    // Initialize if not already done
    if (!this.pipeline) {
      await this.initialize();
    }

    if (!this.pipeline) {
      throw new Error('NER pipeline not initialized');
    }

    try {
      // Run NER inference
      const output = await this.pipeline(text, {
        ignore_labels: ['O'], // Ignore non-entity tokens
      });

      // Convert output to our Entity format
      const entities: Entity[] = this.processModelOutput(output);

      const processingTime = performance.now() - startTime;

      return {
        entities,
        text,
        processingTime,
      };
    } catch (error) {
      console.error('Entity extraction failed:', error);
      throw new Error('Failed to extract entities');
    }
  }

  /**
   * Process model output into entities
   */
  private processModelOutput(output: any[]): Entity[] {
    const entities: Entity[] = [];
    let currentEntity: Entity | null = null;

    for (const item of output) {
      const entityType = this.normalizeEntityType(item.entity);
      const word = item.word;
      const score = item.score;
      const start = item.start;
      const end = item.end;

      // Check if this is a continuation of the previous entity (B- vs I- tags)
      const isBeginning = item.entity.startsWith('B-');
      const isInside = item.entity.startsWith('I-');

      if (isBeginning) {
        // Save previous entity if exists
        if (currentEntity) {
          entities.push(currentEntity);
        }

        // Start new entity
        currentEntity = {
          text: word,
          type: entityType,
          score: score,
          start: start,
          end: end,
        };
      } else if (isInside && currentEntity && currentEntity.type === entityType) {
        // Continue current entity
        currentEntity.text += word.startsWith('##') ? word.slice(2) : ' ' + word;
        currentEntity.end = end;
        currentEntity.score = (currentEntity.score + score) / 2; // Average score
      } else {
        // Single-token entity or no current entity
        if (currentEntity) {
          entities.push(currentEntity);
        }

        currentEntity = {
          text: word,
          type: entityType,
          score: score,
          start: start,
          end: end,
        };
      }
    }

    // Add final entity
    if (currentEntity) {
      entities.push(currentEntity);
    }

    return entities;
  }

  /**
   * Normalize entity type labels
   */
  private normalizeEntityType(label: string): string {
    // Remove B- and I- prefixes
    const cleanLabel = label.replace(/^[BI]-/, '');

    // Map to our standard entity types
    const typeMap: Record<string, string> = {
      'PER': 'PERSON',
      'LOC': 'LOCATION',
      'ORG': 'ORGANIZATION',
      'MISC': 'MISCELLANEOUS',
      'DATE': 'DATE',
      'TIME': 'TIME',
      'MONEY': 'MONEY',
      'PERCENT': 'PERCENT',
    };

    return typeMap[cleanLabel] || cleanLabel;
  }

  /**
   * Extract entities of specific types
   */
  async extractEntitiesByType(
    text: string,
    types: string[]
  ): Promise<Entity[]> {
    const result = await this.extractEntities(text);

    return result.entities.filter(entity =>
      types.includes(entity.type)
    );
  }

  /**
   * Group entities by type
   */
  groupEntitiesByType(entities: Entity[]): Record<string, Entity[]> {
    const grouped: Record<string, Entity[]> = {};

    for (const entity of entities) {
      if (!grouped[entity.type]) {
        grouped[entity.type] = [];
      }
      grouped[entity.type].push(entity);
    }

    return grouped;
  }

  /**
   * Filter entities by confidence score
   */
  filterByConfidence(entities: Entity[], minScore: number = 0.7): Entity[] {
    return entities.filter(entity => entity.score >= minScore);
  }

  /**
   * Get unique entity texts
   */
  getUniqueEntities(entities: Entity[]): string[] {
    const uniqueTexts = new Set(entities.map(e => e.text.toLowerCase()));
    return Array.from(uniqueTexts);
  }

  /**
   * Change the model being used
   */
  async changeModel(modelName: string): Promise<void> {
    this.modelName = modelName;
    this.pipeline = null;
    await this.initialize();
  }

  /**
   * Check if model is loaded
   */
  isReady(): boolean {
    return this.pipeline !== null;
  }
}

/**
 * Convenience function to extract entities
 */
export async function extractEntities(text: string): Promise<NERResult> {
  const processor = MLNERProcessor.getInstance();
  return processor.extractEntities(text);
}

/**
 * Extract legal entities (parties, organizations, locations)
 */
export async function extractLegalEntities(text: string): Promise<{
  parties: Entity[];
  organizations: Entity[];
  locations: Entity[];
  dates: Entity[];
  allEntities: Entity[];
}> {
  const processor = MLNERProcessor.getInstance();
  const result = await processor.extractEntities(text);

  // Filter by confidence
  const highConfidenceEntities = processor.filterByConfidence(result.entities, 0.7);

  // Group by type
  const grouped = processor.groupEntitiesByType(highConfidenceEntities);

  return {
    parties: grouped['PERSON'] || [],
    organizations: grouped['ORGANIZATION'] || [],
    locations: grouped['LOCATION'] || [],
    dates: grouped['DATE'] || [],
    allEntities: highConfidenceEntities,
  };
}

/**
 * Supported NER models
 */
export const SUPPORTED_MODELS = {
  DEFAULT: 'Xenova/bert-base-NER',
  LEGAL: 'Xenova/roberta-base-NER', // Alternative model
  MULTILINGUAL: 'Xenova/bert-base-multilingual-cased-ner',
};
