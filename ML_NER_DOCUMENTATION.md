# ML-Based Named Entity Recognition Documentation

## Overview

The Junas ML-based NER system uses Transformers.js to provide accurate entity extraction from legal documents using state-of-the-art transformer models running entirely in the browser via WebAssembly.

## Architecture

### Components

1. **NER Processor** (`src/lib/ml/ner-processor.ts`)
   - Core ML entity extraction engine
   - BERT-based token classification
   - Entity type normalization
   - Confidence scoring

2. **Model Cache** (`src/lib/ml/model-cache.ts`)
   - LRU caching for loaded models
   - Memory management
   - Concurrent loading support
   - Usage statistics tracking

3. **NER Configuration** (`src/lib/ml/ner-config.ts`)
   - Entity type definitions
   - Configuration presets
   - Validation utilities

4. **Performance Optimizer** (`src/lib/ml/ner-optimizer.ts`)
   - Text chunking for large documents
   - Batch processing
   - Adaptive chunking
   - Result caching

## Usage

### Basic Entity Extraction

```typescript
import { extractEntities } from '@/lib/ml/ner-processor';

const result = await extractEntities('John Smith signed the contract on January 15, 2024.');

console.log(result.entities);
// [
//   { text: 'John Smith', type: 'PERSON', score: 0.95, start: 0, end: 10 },
//   { text: 'January 15, 2024', type: 'DATE', score: 0.92, start: 35, end: 51 }
// ]
```

### Legal Entity Extraction

```typescript
import { extractLegalEntities } from '@/lib/ml/ner-processor';

const result = await extractLegalEntities(legalText);

console.log('Parties:', result.parties);
console.log('Organizations:', result.organizations);
console.log('Locations:', result.locations);
console.log('Dates:', result.dates);
```

### Processing Large Documents

```typescript
import { globalNEROptimizer } from '@/lib/ml/ner-optimizer';

// Process large text in chunks
const result = await globalNEROptimizer.processLargeText(longDocument);

console.log(`Processed ${result.chunks} chunks in ${result.totalProcessingTime}ms`);
console.log('Entities:', result.entities);
```

### Batch Processing

```typescript
import { globalNEROptimizer } from '@/lib/ml/ner-optimizer';

const documents = [doc1, doc2, doc3];
const results = await globalNEROptimizer.batchProcess(documents);

results.forEach((result, index) => {
  console.log(`Document ${index}: ${result.entities.length} entities`);
});
```

### Streaming Processing

```typescript
import { globalNEROptimizer } from '@/lib/ml/ner-optimizer';

for await (const { entity, progress } of globalNEROptimizer.processStream(longText)) {
  console.log(`Progress: ${(progress * 100).toFixed(1)}%`);
  console.log('Entity:', entity);
}
```

## Entity Types

### Standard Types

- **PERSON**: Individual names, parties, plaintiffs, defendants
- **ORGANIZATION**: Companies, corporations, courts, government bodies
- **LOCATION**: Countries, cities, addresses, jurisdictions
- **DATE**: Dates, time periods, contract dates
- **MONEY**: Monetary amounts, damages, fees, compensation
- **MISCELLANEOUS**: Other entities

### Legal-Specific Types

- **LAW**: Statutes, regulations, legal provisions
- **STATUTE**: Specific statute references (s. 123, section 45)
- **CASE**: Case names and citations (Smith v. Jones)
- **CONTRACT_PARTY**: Parties to a contract
- **COURT**: Courts and tribunals
- **JURISDICTION**: Legal jurisdictions
- **LEGAL_ROLE**: Plaintiff, defendant, appellant, respondent

## Configuration

### Using Presets

```typescript
import { getPresetConfig, NER_PRESETS } from '@/lib/ml/ner-config';

// Fast processing (regex only)
const fastConfig = getPresetConfig('FAST');

// Balanced (ML + regex)
const balancedConfig = getPresetConfig('BALANCED');

// High accuracy (ML only)
const accurateConfig = getPresetConfig('ACCURATE');

// Legal document focus
const legalConfig = getPresetConfig('LEGAL');

// Contract focus
const contractConfig = getPresetConfig('CONTRACT');

// Case law focus
const caseLawConfig = getPresetConfig('CASE_LAW');
```

### Custom Configuration

```typescript
import { DEFAULT_NER_CONFIG, mergeNERConfig } from '@/lib/ml/ner-config';

const customConfig = mergeNERConfig(DEFAULT_NER_CONFIG, {
  enabledTypes: ['PERSON', 'ORGANIZATION', 'DATE'],
  confidenceThreshold: 0.8,
  useML: true,
  useRegex: true,
});
```

## Model Management

### Check Model Status

```typescript
import { MLNERProcessor } from '@/lib/ml/ner-processor';

const processor = MLNERProcessor.getInstance();

if (processor.isReady()) {
  console.log('Model is loaded and ready');
}
```

### Change Model

```typescript
await processor.changeModel('Xenova/roberta-base-NER');
```

### Cache Statistics

```typescript
const stats = processor.getCacheStats();

console.log('Total loads:', stats.totalLoads);
console.log('Cache hits:', stats.cacheHits);
console.log('Cache misses:', stats.cacheMisses);
console.log('Hit rate:', (stats.cacheHits / (stats.cacheHits + stats.cacheMisses) * 100).toFixed(1) + '%');
```

### Clear Cache

```typescript
processor.clearCache();
```

## Performance Optimization

### Chunking Configuration

```typescript
import { globalNEROptimizer } from '@/lib/ml/ner-optimizer';

globalNEROptimizer.configure({
  maxChunkSize: 1024,  // tokens
  overlapSize: 100,    // tokens
});
```

### Adaptive Processing

```typescript
// Automatically adjusts chunk size based on text complexity
const result = await globalNEROptimizer.processAdaptive(complexLegalText);
```

### Result Caching

```typescript
// Automatically caches results for repeated extractions
const entities1 = await globalNEROptimizer.processWithCache(text);
const entities2 = await globalNEROptimizer.processWithCache(text); // Cache hit!
```

## Supported Models

### Default Model

- **Xenova/bert-base-NER**: BERT-based NER model trained on CoNLL-2003
- Supports: PERSON, ORGANIZATION, LOCATION, MISCELLANEOUS

### Alternative Models

- **Xenova/roberta-base-NER**: RoBERTa-based NER model
- **Xenova/bert-base-multilingual-cased-ner**: Multilingual support

## API Integration

The ML NER is integrated into the `/api/tools/ner` endpoint:

```bash
curl -X POST http://localhost:3000/api/tools/ner \
  -H "Content-Type: application/json" \
  -d '{"text": "John Smith signed the contract on January 15, 2024."}'
```

**Response**:

```json
{
  "success": true,
  "entities": {
    "PERSON": ["John Smith"],
    "ORGANIZATION": [],
    "LOCATION": [],
    "DATE": ["January 15, 2024"],
    "MONEY": [],
    "ALL_ML": [
      {
        "text": "John Smith",
        "type": "PERSON",
        "score": 0.95,
        "start": 0,
        "end": 10
      }
    ]
  },
  "mlConfidence": 0.93,
  "metadata": {
    "textLength": 52,
    "processingTime": 245,
    "mlEntitiesCount": 2,
    "method": "hybrid-ml"
  }
}
```

## Performance Metrics

### Model Loading

- **First Load**: ~2-5 seconds (downloads model)
- **Cached Load**: ~50-100ms (from memory)
- **Model Size**: ~100MB (quantized)

### Inference Speed

- **Short Text** (<100 words): ~100-200ms
- **Medium Text** (100-500 words): ~300-600ms
- **Long Text** (>500 words): ~1-3s with chunking

### Accuracy

- **PERSON**: 90-95% F1 score
- **ORGANIZATION**: 85-90% F1 score
- **LOCATION**: 85-90% F1 score
- **DATE**: 80-85% F1 score (improved with regex)

## Hybrid Approach

The system uses a hybrid approach combining ML and regex:

1. **ML Models**: Extract general entities (PERSON, ORG, LOCATION)
2. **Regex Extractors**: Extract legal-specific entities (STATUTE, CASE, MONEY)
3. **Combination**: Merge results with deduplication
4. **Confidence**: Weight ML confidence with pattern matches

## Best Practices

### 1. Preload Models

```typescript
// In app initialization
import { MLNERProcessor } from '@/lib/ml/ner-processor';

const processor = MLNERProcessor.getInstance();
await processor.initialize();
```

### 2. Use Appropriate Configuration

- Legal documents → `LEGAL` preset
- Contracts → `CONTRACT` preset
- Case law → `CASE_LAW` preset
- Fast processing → `FAST` preset

### 3. Process Large Documents in Chunks

```typescript
if (text.length > 10000) {
  // Use optimizer for large texts
  const result = await globalNEROptimizer.processLargeText(text);
} else {
  // Direct processing for small texts
  const result = await extractEntities(text);
}
```

### 4. Monitor Cache Performance

```typescript
const stats = processor.getCacheStats();

if (stats.cacheHits / (stats.cacheHits + stats.cacheMisses) < 0.5) {
  console.warn('Low cache hit rate, consider increasing cache size');
}
```

## Troubleshooting

### Issue: Model Loading Fails

**Cause**: Network error or CORS issue
**Solution**: Check network connection, ensure CDN is accessible

### Issue: Slow Performance

**Cause**: Model not cached, processing large text
**Solution**: Preload models, use chunking for large texts

### Issue: Low Accuracy

**Cause**: Wrong model or configuration
**Solution**: Try different model, adjust confidence threshold

### Issue: Memory Issues

**Cause**: Too many models cached
**Solution**: Reduce cache size, clear unused models

## Future Enhancements

1. **Fine-tuned Legal Models**: Train models specifically on legal texts
2. **Multi-language Support**: Add support for non-English documents
3. **Custom Entity Types**: Allow user-defined entity types
4. **GPU Acceleration**: Use WebGPU when available
5. **Active Learning**: Improve models based on user corrections
6. **Relationship Extraction**: Extract relationships between entities

## License

Part of Junas legal assistant application.
