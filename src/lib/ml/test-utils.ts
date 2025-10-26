/**
 * Testing utilities for ML components
 */

import { Entity, NERResult } from './ner-processor';

/**
 * Mock entity data for testing
 */
export const MOCK_ENTITIES: Entity[] = [
  {
    text: 'John Smith',
    type: 'PERSON',
    score: 0.95,
    start: 0,
    end: 10,
  },
  {
    text: 'Apple Inc.',
    type: 'ORGANIZATION',
    score: 0.92,
    start: 25,
    end: 35,
  },
  {
    text: 'Singapore',
    type: 'LOCATION',
    score: 0.88,
    start: 50,
    end: 59,
  },
  {
    text: 'January 15, 2024',
    type: 'DATE',
    score: 0.90,
    start: 70,
    end: 86,
  },
];

/**
 * Mock NER result for testing
 */
export const MOCK_NER_RESULT: NERResult = {
  entities: MOCK_ENTITIES,
  text: 'John Smith works at Apple Inc. in Singapore on January 15, 2024.',
  processingTime: 150,
};

/**
 * Sample legal texts for testing
 */
export const SAMPLE_LEGAL_TEXTS = {
  contract: `
    This Agreement is made on January 15, 2024, between:

    John Smith ("Buyer"), an individual residing at 123 Main Street, Singapore

    AND

    Apple Inc. ("Seller"), a company incorporated in Delaware

    WHEREAS the Buyer wishes to purchase and the Seller agrees to sell certain
    property for the sum of S$500,000.
  `,

  caseLaw: `
    In the matter of Smith v. Jones [2024] SGCA 15, the Court of Appeal held that
    the defendant's conduct breached section 123 of the Companies Act. The plaintiff,
    represented by Lee & Associates, sought damages of $100,000.
  `,

  statute: `
    The Companies Act (Cap. 50) provides in section 123(1) that every director
    shall exercise reasonable care, skill and diligence. Failure to comply may
    result in penalties under section 125.
  `,
};

/**
 * Create mock entity
 */
export function createMockEntity(
  overrides: Partial<Entity> = {}
): Entity {
  return {
    text: 'Test Entity',
    type: 'PERSON',
    score: 0.9,
    start: 0,
    end: 11,
    ...overrides,
  };
}

/**
 * Create mock NER result
 */
export function createMockNERResult(
  overrides: Partial<NERResult> = {}
): NERResult {
  return {
    entities: [createMockEntity()],
    text: 'Test text',
    processingTime: 100,
    ...overrides,
  };
}

/**
 * Assertion helpers for entity testing
 */
export const EntityAssertions = {
  /**
   * Check if entity has required fields
   */
  hasRequiredFields(entity: Entity): boolean {
    return (
      typeof entity.text === 'string' &&
      typeof entity.type === 'string' &&
      typeof entity.score === 'number' &&
      typeof entity.start === 'number' &&
      typeof entity.end === 'number'
    );
  },

  /**
   * Check if entity score is valid
   */
  hasValidScore(entity: Entity): boolean {
    return entity.score >= 0 && entity.score <= 1;
  },

  /**
   * Check if entity positions are valid
   */
  hasValidPositions(entity: Entity, textLength: number): boolean {
    return (
      entity.start >= 0 &&
      entity.end > entity.start &&
      entity.end <= textLength
    );
  },

  /**
   * Check if entity text matches positions
   */
  textMatchesPositions(entity: Entity, fullText: string): boolean {
    const extractedText = fullText.slice(entity.start, entity.end);
    return extractedText === entity.text;
  },

  /**
   * Check if entity type is valid
   */
  hasValidType(entity: Entity, validTypes: string[]): boolean {
    return validTypes.includes(entity.type);
  },
};

/**
 * Performance testing utilities
 */
export class PerformanceTester {
  private measurements: Array<{ name: string; duration: number }> = [];

  /**
   * Measure execution time
   */
  async measure<T>(name: string, fn: () => Promise<T>): Promise<T> {
    const start = performance.now();
    const result = await fn();
    const duration = performance.now() - start;

    this.measurements.push({ name, duration });
    return result;
  }

  /**
   * Get all measurements
   */
  getMeasurements() {
    return [...this.measurements];
  }

  /**
   * Get average duration
   */
  getAverage(): number {
    if (this.measurements.length === 0) return 0;
    const total = this.measurements.reduce((sum, m) => sum + m.duration, 0);
    return total / this.measurements.length;
  }

  /**
   * Clear measurements
   */
  clear(): void {
    this.measurements = [];
  }

  /**
   * Print report
   */
  printReport(): void {
    console.log('\n=== Performance Report ===');
    this.measurements.forEach(({ name, duration }) => {
      console.log(`${name}: ${duration.toFixed(2)}ms`);
    });
    console.log(`Average: ${this.getAverage().toFixed(2)}ms`);
    console.log('========================\n');
  }
}

/**
 * Mock model for testing
 */
export class MockMLModel {
  private delay: number;

  constructor(delay: number = 100) {
    this.delay = delay;
  }

  /**
   * Simulate model inference
   */
  async predict(text: string): Promise<Entity[]> {
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, this.delay));

    // Return mock entities based on simple patterns
    const entities: Entity[] = [];

    // Find capitalized words (potential names)
    const namePattern = /\b[A-Z][a-z]+ [A-Z][a-z]+\b/g;
    let match;
    while ((match = namePattern.exec(text)) !== null) {
      entities.push({
        text: match[0],
        type: 'PERSON',
        score: 0.9,
        start: match.index,
        end: match.index + match[0].length,
      });
    }

    return entities;
  }
}

/**
 * Test data generators
 */
export const TestDataGenerator = {
  /**
   * Generate random entity
   */
  randomEntity(): Entity {
    const types = ['PERSON', 'ORGANIZATION', 'LOCATION', 'DATE', 'MONEY'];
    const texts = [
      'John Smith',
      'Apple Inc.',
      'Singapore',
      'January 1, 2024',
      '$10,000',
    ];

    const index = Math.floor(Math.random() * types.length);

    return {
      text: texts[index],
      type: types[index],
      score: 0.8 + Math.random() * 0.2,
      start: 0,
      end: texts[index].length,
    };
  },

  /**
   * Generate batch of entities
   */
  randomEntities(count: number): Entity[] {
    return Array.from({ length: count }, () => this.randomEntity());
  },

  /**
   * Generate legal text
   */
  randomLegalText(): string {
    const templates = [
      'This Agreement is made on {date} between {person1} and {person2}.',
      'In {case}, the Court held that {person} breached section {statute}.',
      '{organization} filed a claim for ${amount} in damages.',
    ];

    const template = templates[Math.floor(Math.random() * templates.length)];

    return template
      .replace('{date}', 'January 1, 2024')
      .replace('{person1}', 'John Smith')
      .replace('{person2}', 'Jane Doe')
      .replace('{person}', 'John Smith')
      .replace('{case}', 'Smith v. Jones [2024] SGCA 1')
      .replace('{statute}', '123')
      .replace('{organization}', 'ABC Corp')
      .replace('{amount}', '100,000');
  },
};
