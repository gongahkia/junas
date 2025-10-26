/**
 * ML Library - Centralized exports for machine learning components
 */

// NER Processor
export {
  MLNERProcessor,
  extractEntities,
  extractLegalEntities,
  SUPPORTED_MODELS,
  type Entity,
  type NERResult,
} from './ner-processor';

// NER Configuration
export {
  ENTITY_TYPES,
  LEGAL_ENTITY_TYPES,
  DEFAULT_NER_CONFIG,
  NER_PRESETS,
  getEntityTypeConfig,
  getEnabledEntityTypes,
  getMLSupportedTypes,
  getRegexSupportedTypes,
  validateNERConfig,
  mergeNERConfig,
  getPresetConfig,
  type EntityTypeConfig,
  type NERConfig,
} from './ner-config';

// Model Cache
export {
  ModelCache,
  globalModelCache,
  warmupModels,
  ModelMemoryMonitor,
  type CachedModel,
  type ModelLoadingStats,
} from './model-cache';

// NER Optimizer
export {
  NEROptimizer,
  globalNEROptimizer,
  type ChunkProcessingResult,
} from './ner-optimizer';
