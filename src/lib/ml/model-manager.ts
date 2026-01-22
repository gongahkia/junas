/**
 * ONNX Model Manager for browser-based ML inference
 * Uses @huggingface/transformers for WebAssembly-based model execution
 */

// Dynamic import to avoid SSR issues - transformers.js only works in browser
let pipelineCache: any = null;

async function getTransformers() {
  if (!pipelineCache) {
    const transformers = await import('@huggingface/transformers');
    pipelineCache = transformers.pipeline;
  }
  return { pipeline: pipelineCache };
}

export type ModelType = 'summarization' | 'ner' | 'embeddings' | 'text-classification' | 'text2text-generation';

export interface ModelInfo {
  id: string;
  name: string;
  type: ModelType;
  modelId: string; // HuggingFace model ID
  size: string;
  description: string;
  isDownloaded: boolean;
  isLoading: boolean;
  downloadProgress: number;
}

export interface DownloadProgress {
  modelId: string;
  progress: number;
  loaded: number;
  total: number;
  status: 'downloading' | 'loading' | 'ready' | 'error';
  error?: string;
}

// Available models
export const AVAILABLE_MODELS: Omit<ModelInfo, 'isDownloaded' | 'isLoading' | 'downloadProgress'>[] = [
  {
    id: 'chat',
    name: 'Local Chat (LaMini)',
    type: 'text2text-generation',
    modelId: 'Xenova/LaMini-Flan-T5-248M',
    size: '~250MB',
    description: 'General purpose chat and instruction following',
  },
  {
    id: 'summarization',
    name: 'Summarization',
    type: 'summarization',
    modelId: 'Xenova/distilbart-cnn-6-6',
    size: '~300MB',
    description: 'Summarize long legal documents into concise summaries',
  },
  {
    id: 'ner',
    name: 'Named Entity Recognition',
    type: 'ner',
    modelId: 'Xenova/bert-base-NER',
    size: '~400MB',
    description: 'Advanced entity extraction (people, organizations, locations)',
  },
  {
    id: 'embeddings',
    name: 'Text Embeddings',
    type: 'embeddings',
    modelId: 'Xenova/all-MiniLM-L6-v2',
    size: '~80MB',
    description: 'Generate embeddings for semantic search and similarity',
  },
  {
    id: 'text-classification',
    name: 'Text Classification',
    type: 'text-classification',
    modelId: 'Xenova/distilbert-base-uncased-finetuned-sst-2-english',
    size: '~250MB',
    description: 'Classify text sentiment and categories',
  },
];

// Storage key for tracking downloaded models
const STORAGE_KEY = 'junas_downloaded_models';

// Loaded pipeline instances
const loadedPipelines: Map<string, any> = new Map();

// Progress callbacks
const progressCallbacks: Map<string, (progress: DownloadProgress) => void> = new Map();

/**
 * Get list of downloaded model IDs from storage
 */
export function getDownloadedModels(): string[] {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored ? JSON.parse(stored) : [];
}

/**
 * Mark a model as downloaded in storage
 */
function markModelDownloaded(modelId: string) {
  const downloaded = getDownloadedModels();
  if (!downloaded.includes(modelId)) {
    downloaded.push(modelId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(downloaded));
  }
}

/**
 * Remove a model from downloaded list
 */
export function removeModelFromDownloaded(modelId: string) {
  const downloaded = getDownloadedModels();
  const filtered = downloaded.filter(id => id !== modelId);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
  loadedPipelines.delete(modelId);
}

/**
 * Clear all downloaded models from storage and cache
 */
export async function clearAllModels(): Promise<void> {
  // Clear local storage
  localStorage.removeItem(STORAGE_KEY);
  loadedPipelines.clear();

  // Clear browser cache used by transformers.js
  if (typeof window !== 'undefined' && 'caches' in window) {
    try {
      const cacheNames = await caches.keys();
      for (const cacheName of cacheNames) {
        if (cacheName.startsWith('transformers-cache')) {
          await caches.delete(cacheName);
        }
      }
    } catch (e) {
      console.error('Failed to clear model cache:', e);
    }
  }
}

/**
 * Check if a model is downloaded
 */
export function isModelDownloaded(modelId: string): boolean {
  return getDownloadedModels().includes(modelId);
}

/**
 * Check if a model is loaded in memory
 */
export function isModelLoaded(modelId: string): boolean {
  return loadedPipelines.has(modelId);
}

/**
 * Get model info with download status
 */
export function getModelsWithStatus(): ModelInfo[] {
  const downloaded = getDownloadedModels();
  return AVAILABLE_MODELS.map(model => ({
    ...model,
    isDownloaded: downloaded.includes(model.id),
    isLoading: false,
    downloadProgress: downloaded.includes(model.id) ? 100 : 0,
  }));
}

/**
 * Download and load a model
 */
export async function downloadModel(
  modelId: string,
  onProgress?: (progress: DownloadProgress) => void
): Promise<boolean> {
  const modelInfo = AVAILABLE_MODELS.find(m => m.id === modelId);
  if (!modelInfo) {
    throw new Error(`Unknown model: ${modelId}`);
  }

  if (onProgress) {
    progressCallbacks.set(modelId, onProgress);
  }

  try {
    onProgress?.({
      modelId,
      progress: 0,
      loaded: 0,
      total: 0,
      status: 'downloading',
    });

    // Get pipeline from dynamic import
    const { pipeline: pipelineFn } = await getTransformers();

    // Create pipeline with progress callback
    const pipelineInstance = await pipelineFn(
      modelInfo.type === 'ner' ? 'token-classification' :
      modelInfo.type === 'embeddings' ? 'feature-extraction' :
      modelInfo.type,
      modelInfo.modelId,
      {
        progress_callback: (data: any) => {
          if (onProgress && data && typeof data === 'object') {
            // Handle different progress event formats
            if (data.status === 'progress' && data.loaded && data.total) {
              onProgress({
                modelId,
                progress: Math.round((data.loaded / data.total) * 100),
                loaded: data.loaded,
                total: data.total,
                status: 'downloading',
              });
            } else if (data.progress !== undefined) {
              onProgress({
                modelId,
                progress: Math.round(data.progress * 100),
                loaded: data.loaded || 0,
                total: data.total || 0,
                status: 'downloading',
              });
            }
          }
        },
        dtype: 'fp32', // Use fp32 for better browser compatibility
      }
    );

    loadedPipelines.set(modelId, pipelineInstance);
    markModelDownloaded(modelId);

    onProgress?.({
      modelId,
      progress: 100,
      loaded: 0,
      total: 0,
      status: 'ready',
    });

    return true;
  } catch (error: any) {
    onProgress?.({
      modelId,
      progress: 0,
      loaded: 0,
      total: 0,
      status: 'error',
      error: error.message,
    });
    throw error;
  } finally {
    progressCallbacks.delete(modelId);
  }
}

/**
 * Load a previously downloaded model into memory
 */
export async function loadModel(modelId: string): Promise<boolean> {
  if (loadedPipelines.has(modelId)) {
    return true;
  }

  const modelInfo = AVAILABLE_MODELS.find(m => m.id === modelId);
  if (!modelInfo) {
    throw new Error(`Unknown model: ${modelId}`);
  }

  // Get pipeline from dynamic import
  const { pipeline: pipelineFn } = await getTransformers();

  const pipelineInstance = await pipelineFn(
    modelInfo.type === 'ner' ? 'token-classification' :
    modelInfo.type === 'embeddings' ? 'feature-extraction' :
    modelInfo.type,
    modelInfo.modelId
  );

  loadedPipelines.set(modelId, pipelineInstance);
  return true;
}

/**
 * Summarize text using the summarization model
 * Handles large documents by chunking and recursive summarization
 */
export async function summarize(text: string, maxLength: number = 150): Promise<string> {
  const modelId = 'summarization';

  if (!loadedPipelines.has(modelId)) {
    if (!isModelDownloaded(modelId)) {
      throw new Error('Summarization model not downloaded. Please download it from Config > Models.');
    }
    await loadModel(modelId);
  }

  const summarizer = loadedPipelines.get(modelId);
  
  // Simple chunking by character count (approximate token count)
  // DistilBART usually handles ~1024 tokens. 1 token ~ 4 chars.
  // Safe chunk size ~3000 chars
  const CHUNK_SIZE = 3000;
  
  if (text.length <= CHUNK_SIZE) {
    const result = await summarizer(text, {
      max_length: maxLength,
      min_length: Math.min(30, text.length),
    });
    return result[0].summary_text;
  }

  // Split into chunks
  const chunks = [];
  for (let i = 0; i < text.length; i += CHUNK_SIZE) {
    chunks.push(text.slice(i, i + CHUNK_SIZE));
  }

  // Summarize each chunk
  const chunkSummaries = await Promise.all(chunks.map(async (chunk) => {
    try {
      const result = await summarizer(chunk, {
        max_length: Math.max(50, Math.floor(maxLength / 2)),
        min_length: 20,
      });
      return result[0].summary_text;
    } catch (e) {
      console.error('Error summarizing chunk:', e);
      return '';
    }
  }));

  // Combine summaries and summarize again
  const combinedSummary = chunkSummaries.join(' ');
  
  // If combined summary is still too big, recurse (rare but possible)
  if (combinedSummary.length > CHUNK_SIZE) {
    return summarize(combinedSummary, maxLength);
  }

  // Final pass
  const finalResult = await summarizer(combinedSummary, {
    max_length: maxLength,
    min_length: 50,
  });

  return finalResult[0].summary_text;
}

/**
 * Generate text using the local chat model
 */
export async function generateText(prompt: string, maxNewTokens: number = 256): Promise<string> {
  const modelId = 'chat';

  if (!loadedPipelines.has(modelId)) {
    if (!isModelDownloaded(modelId)) {
      throw new Error('Chat model not downloaded. Please download it from Config > Models.');
    }
    await loadModel(modelId);
  }

  const generator = loadedPipelines.get(modelId);
  const result = await generator(prompt, {
    max_new_tokens: maxNewTokens,
    do_sample: true,
    temperature: 0.7,
  });

  // Handle different return formats depending on model type
  if (Array.isArray(result) && result.length > 0) {
    return result[0].generated_text || result[0].summary_text || JSON.stringify(result[0]);
  }
  
  return typeof result === 'string' ? result : JSON.stringify(result);
}

/**
 * Extract named entities using the NER model
 */
export async function extractNamedEntities(text: string): Promise<Array<{
  entity: string;
  word: string;
  score: number;
}>> {
  const modelId = 'ner';

  if (!loadedPipelines.has(modelId)) {
    if (!isModelDownloaded(modelId)) {
      throw new Error('NER model not downloaded. Please download it from Config > Models.');
    }
    await loadModel(modelId);
  }

  const ner = loadedPipelines.get(modelId);
  const result = await ner(text);

  return result.map((entity: any) => ({
    entity: entity.entity_group || entity.entity,
    word: entity.word,
    score: entity.score,
  }));
}

/**
 * Generate text embeddings
 */
export async function generateEmbeddings(text: string): Promise<number[]> {
  const modelId = 'embeddings';

  if (!loadedPipelines.has(modelId)) {
    if (!isModelDownloaded(modelId)) {
      throw new Error('Embeddings model not downloaded. Please download it from Config > Models.');
    }
    await loadModel(modelId);
  }

  const embedder = loadedPipelines.get(modelId);
  const result = await embedder(text, { pooling: 'mean', normalize: true });

  return Array.from(result.data);
}

/**
 * Classify text
 */
export async function classifyText(text: string): Promise<Array<{
  label: string;
  score: number;
}>> {
  const modelId = 'text-classification';

  if (!loadedPipelines.has(modelId)) {
    if (!isModelDownloaded(modelId)) {
      throw new Error('Classification model not downloaded. Please download it from Config > Models.');
    }
    await loadModel(modelId);
  }

  const classifier = loadedPipelines.get(modelId);
  const result = await classifier(text);

  return result;
}
