/**
 * ONNX Model Manager for browser-based ML inference
 * Uses @xenova/transformers for WebAssembly-based model execution
 */

// Dynamic import to avoid SSR issues - transformers.js only works in browser
let pipeline: any = null;
let env: any = null;

async function getTransformers() {
  if (!pipeline) {
    const transformers = await import('@xenova/transformers');
    pipeline = transformers.pipeline;
    env = transformers.env;
    // Configure transformers.js to use browser cache
    env.useBrowserCache = true;
    env.allowLocalModels = false;
  }
  return { pipeline, env };
}

export type ModelType = 'summarization' | 'ner' | 'embeddings' | 'text-classification';

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

    // Create pipeline with progress callback
    const pipelineInstance = await pipeline(
      modelInfo.type === 'ner' ? 'token-classification' :
      modelInfo.type === 'embeddings' ? 'feature-extraction' :
      modelInfo.type,
      modelInfo.modelId,
      {
        progress_callback: (data: any) => {
          if (data.status === 'progress' && onProgress) {
            onProgress({
              modelId,
              progress: Math.round((data.loaded / data.total) * 100),
              loaded: data.loaded,
              total: data.total,
              status: 'downloading',
            });
          }
        },
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

  const pipelineInstance = await pipeline(
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
  const result = await summarizer(text, {
    max_length: maxLength,
    min_length: 30,
  });

  return result[0].summary_text;
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
