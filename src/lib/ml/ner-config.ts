/**
 * NER Configuration and entity type definitions
 */

export interface EntityTypeConfig {
  name: string;
  label: string;
  description: string;
  color: string;
  enabled: boolean;
  mlSupported: boolean;
  regexSupported: boolean;
}

/**
 * Standard entity types configuration
 */
export const ENTITY_TYPES: Record<string, EntityTypeConfig> = {
  PERSON: {
    name: 'PERSON',
    label: 'Person',
    description: 'Individual names, parties, plaintiffs, defendants',
    color: '#3b82f6',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  ORGANIZATION: {
    name: 'ORGANIZATION',
    label: 'Organization',
    description: 'Companies, corporations, courts, government bodies',
    color: '#8b5cf6',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  LOCATION: {
    name: 'LOCATION',
    label: 'Location',
    description: 'Countries, cities, addresses, jurisdictions',
    color: '#10b981',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  DATE: {
    name: 'DATE',
    label: 'Date',
    description: 'Dates, time periods, contract dates',
    color: '#f59e0b',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  MONEY: {
    name: 'MONEY',
    label: 'Money',
    description: 'Monetary amounts, damages, fees, compensation',
    color: '#ef4444',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  LAW: {
    name: 'LAW',
    label: 'Law',
    description: 'Statutes, regulations, case citations, legal provisions',
    color: '#6366f1',
    enabled: true,
    mlSupported: false,
    regexSupported: true,
  },
  STATUTE: {
    name: 'STATUTE',
    label: 'Statute',
    description: 'Specific statute references (s. 123, section 45)',
    color: '#14b8a6',
    enabled: true,
    mlSupported: false,
    regexSupported: true,
  },
  CASE: {
    name: 'CASE',
    label: 'Case',
    description: 'Case names and citations (Smith v. Jones)',
    color: '#ec4899',
    enabled: true,
    mlSupported: false,
    regexSupported: true,
  },
  MISCELLANEOUS: {
    name: 'MISCELLANEOUS',
    label: 'Miscellaneous',
    description: 'Other entities not fitting standard categories',
    color: '#64748b',
    enabled: false,
    mlSupported: true,
    regexSupported: false,
  },
};

/**
 * Legal document-specific entity types
 */
export const LEGAL_ENTITY_TYPES: Record<string, EntityTypeConfig> = {
  CONTRACT_PARTY: {
    name: 'CONTRACT_PARTY',
    label: 'Contract Party',
    description: 'Parties to a contract',
    color: '#0ea5e9',
    enabled: true,
    mlSupported: false,
    regexSupported: true,
  },
  COURT: {
    name: 'COURT',
    label: 'Court',
    description: 'Courts and tribunals',
    color: '#84cc16',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  JURISDICTION: {
    name: 'JURISDICTION',
    label: 'Jurisdiction',
    description: 'Legal jurisdictions',
    color: '#f97316',
    enabled: true,
    mlSupported: true,
    regexSupported: true,
  },
  LEGAL_ROLE: {
    name: 'LEGAL_ROLE',
    label: 'Legal Role',
    description: 'Plaintiff, defendant, appellant, respondent',
    color: '#a855f7',
    enabled: true,
    mlSupported: false,
    regexSupported: true,
  },
};

/**
 * NER processing configuration
 */
export interface NERConfig {
  enabledTypes: string[];
  confidenceThreshold: number;
  useML: boolean;
  useRegex: boolean;
  combineResults: boolean;
  deduplicateEntities: boolean;
  maxTextLength: number;
  modelName?: string;
}

/**
 * Default NER configuration
 */
export const DEFAULT_NER_CONFIG: NERConfig = {
  enabledTypes: [
    'PERSON',
    'ORGANIZATION',
    'LOCATION',
    'DATE',
    'MONEY',
    'LAW',
  ],
  confidenceThreshold: 0.7,
  useML: true,
  useRegex: true,
  combineResults: true,
  deduplicateEntities: true,
  maxTextLength: 100000,
  modelName: 'Xenova/bert-base-NER',
};

/**
 * Configuration presets for different use cases
 */
export const NER_PRESETS: Record<string, Partial<NERConfig>> = {
  // Fast processing, regex only
  FAST: {
    useML: false,
    useRegex: true,
    confidenceThreshold: 0.5,
  },

  // Balanced processing
  BALANCED: {
    useML: true,
    useRegex: true,
    confidenceThreshold: 0.7,
  },

  // High accuracy, ML only
  ACCURATE: {
    useML: true,
    useRegex: false,
    confidenceThreshold: 0.8,
  },

  // Legal document focus
  LEGAL: {
    enabledTypes: [
      'PERSON',
      'ORGANIZATION',
      'DATE',
      'MONEY',
      'LAW',
      'STATUTE',
      'CASE',
      'CONTRACT_PARTY',
      'COURT',
    ],
    useML: true,
    useRegex: true,
    confidenceThreshold: 0.7,
  },

  // Contract focus
  CONTRACT: {
    enabledTypes: [
      'CONTRACT_PARTY',
      'DATE',
      'MONEY',
      'ORGANIZATION',
      'LOCATION',
    ],
    useML: true,
    useRegex: true,
    confidenceThreshold: 0.75,
  },

  // Case law focus
  CASE_LAW: {
    enabledTypes: [
      'PERSON',
      'CASE',
      'COURT',
      'DATE',
      'LAW',
      'STATUTE',
      'JURISDICTION',
    ],
    useML: true,
    useRegex: true,
    confidenceThreshold: 0.8,
  },
};

/**
 * Get entity type configuration
 */
export function getEntityTypeConfig(entityType: string): EntityTypeConfig | undefined {
  return ENTITY_TYPES[entityType] || LEGAL_ENTITY_TYPES[entityType];
}

/**
 * Get all enabled entity types
 */
export function getEnabledEntityTypes(): string[] {
  return [
    ...Object.keys(ENTITY_TYPES).filter(key => ENTITY_TYPES[key].enabled),
    ...Object.keys(LEGAL_ENTITY_TYPES).filter(key => LEGAL_ENTITY_TYPES[key].enabled),
  ];
}

/**
 * Get entity types supported by ML
 */
export function getMLSupportedTypes(): string[] {
  return [
    ...Object.keys(ENTITY_TYPES).filter(key => ENTITY_TYPES[key].mlSupported),
    ...Object.keys(LEGAL_ENTITY_TYPES).filter(key => LEGAL_ENTITY_TYPES[key].mlSupported),
  ];
}

/**
 * Get entity types supported by regex
 */
export function getRegexSupportedTypes(): string[] {
  return [
    ...Object.keys(ENTITY_TYPES).filter(key => ENTITY_TYPES[key].regexSupported),
    ...Object.keys(LEGAL_ENTITY_TYPES).filter(key => LEGAL_ENTITY_TYPES[key].regexSupported),
  ];
}

/**
 * Validate NER configuration
 */
export function validateNERConfig(config: Partial<NERConfig>): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  if (config.confidenceThreshold !== undefined) {
    if (config.confidenceThreshold < 0 || config.confidenceThreshold > 1) {
      errors.push('Confidence threshold must be between 0 and 1');
    }
  }

  if (config.maxTextLength !== undefined) {
    if (config.maxTextLength < 1 || config.maxTextLength > 500000) {
      errors.push('Max text length must be between 1 and 500,000');
    }
  }

  if (config.enabledTypes !== undefined) {
    const allTypes = [...Object.keys(ENTITY_TYPES), ...Object.keys(LEGAL_ENTITY_TYPES)];
    const invalidTypes = config.enabledTypes.filter(type => !allTypes.includes(type));
    if (invalidTypes.length > 0) {
      errors.push(`Invalid entity types: ${invalidTypes.join(', ')}`);
    }
  }

  if (config.useML === false && config.useRegex === false) {
    errors.push('At least one extraction method (ML or regex) must be enabled');
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Merge configurations
 */
export function mergeNERConfig(
  base: NERConfig,
  override: Partial<NERConfig>
): NERConfig {
  return {
    ...base,
    ...override,
  };
}

/**
 * Get configuration preset
 */
export function getPresetConfig(presetName: string): NERConfig {
  const preset = NER_PRESETS[presetName] || {};
  return mergeNERConfig(DEFAULT_NER_CONFIG, preset);
}
