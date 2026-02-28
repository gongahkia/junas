import * as ml from './tauri-ml-bridge';

export type ModelType =
  | 'summarization'
  | 'ner'
  | 'embeddings'
  | 'text-classification'
  | 'text2text-generation';

export interface ModelInfo {
  id: string;
  name: string;
  type: ModelType;
  modelId: string;
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

export const AVAILABLE_MODELS: Omit<
  ModelInfo,
  'isDownloaded' | 'isLoading' | 'downloadProgress'
>[] = [
  {
    id: 'chat',
    name: 'Local Chat (LaMini)',
    type: 'text2text-generation',
    modelId: 'LaMini-Flan-T5-248M',
    size: '~250MB',
    description: 'General purpose chat and instruction following',
  },
  {
    id: 'summarization',
    name: 'Summarization',
    type: 'summarization',
    modelId: 'distilbart-cnn-6-6',
    size: '~300MB',
    description: 'Summarize long legal documents into concise summaries',
  },
  {
    id: 'ner',
    name: 'Named Entity Recognition',
    type: 'ner',
    modelId: 'bert-base-NER',
    size: '~400MB',
    description: 'Advanced entity extraction (people, organizations, locations)',
  },
  {
    id: 'embeddings',
    name: 'Text Embeddings',
    type: 'embeddings',
    modelId: 'all-MiniLM-L6-v2',
    size: '~80MB',
    description: 'Generate embeddings for semantic search and similarity',
  },
  {
    id: 'text-classification',
    name: 'Text Classification',
    type: 'text-classification',
    modelId: 'distilbert-base-uncased-finetuned-sst-2-english',
    size: '~250MB',
    description: 'Classify text sentiment and categories',
  },
];

const STORAGE_KEY = 'junas_downloaded_models';

function getLocalDownloadedModels(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    return Array.isArray(parsed) ? parsed.map((id) => String(id)) : [];
  } catch {
    return [];
  }
}

function setLocalDownloadedModels(modelIds: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(modelIds));
}

export function getDownloadedModels(): string[] {
  return getLocalDownloadedModels();
}

export function removeModelFromDownloaded(modelId: string): void {
  const downloaded = getLocalDownloadedModels().filter((id) => id !== modelId);
  setLocalDownloadedModels(downloaded);
  void ml.removeModelCache(modelId).catch((error) => {
    console.warn(`Failed to remove cached model ${modelId}:`, error);
  });
}

export async function clearAllModels(): Promise<void> {
  setLocalDownloadedModels([]);
  await ml.clearModelCache();
}

export function isModelDownloaded(modelId: string): boolean {
  return getLocalDownloadedModels().includes(modelId);
}

export function isModelLoaded(modelId: string): boolean {
  return isModelDownloaded(modelId);
}

export function getModelsWithStatus(): ModelInfo[] {
  const downloaded = getLocalDownloadedModels();
  return AVAILABLE_MODELS.map((model) => ({
    ...model,
    isDownloaded: downloaded.includes(model.id),
    isLoading: false,
    downloadProgress: downloaded.includes(model.id) ? 100 : 0,
  }));
}

export async function downloadModel(
  modelId: string,
  onProgress?: (progress: DownloadProgress) => void
): Promise<boolean> {
  const modelInfo = AVAILABLE_MODELS.find((model) => model.id === modelId);
  if (!modelInfo) throw new Error(`Unknown model: ${modelId}`);

  onProgress?.({ modelId, progress: 5, loaded: 0, total: 0, status: 'downloading' });

  try {
    await ml.downloadModel(modelInfo.id);
    onProgress?.({ modelId, progress: 85, loaded: 0, total: 0, status: 'loading' });

    await ml.loadModel(modelInfo.id);

    const downloaded = getLocalDownloadedModels();
    if (!downloaded.includes(modelId)) {
      downloaded.push(modelId);
      setLocalDownloadedModels(downloaded);
    }

    onProgress?.({ modelId, progress: 100, loaded: 0, total: 0, status: 'ready' });
    return true;
  } catch (error) {
    onProgress?.({
      modelId,
      progress: 0,
      loaded: 0,
      total: 0,
      status: 'error',
      error: error instanceof Error ? error.message : String(error),
    });
    throw error;
  }
}

export async function loadModel(modelId: string): Promise<boolean> {
  await ml.loadModel(modelId);
  return true;
}

export async function summarize(text: string, maxLength: number = 150): Promise<string> {
  return ml.runSummarize(text, maxLength);
}

export async function generateText(prompt: string, _maxNewTokens: number = 256): Promise<string> {
  return ml.runSummarize(prompt, _maxNewTokens);
}

export async function extractNamedEntities(text: string) {
  return ml.runNer(text);
}

export async function generateEmbeddings(text: string): Promise<number[]> {
  return ml.runEmbeddings(text);
}

export async function classifyText(text: string) {
  return ml.runClassify(text);
}
