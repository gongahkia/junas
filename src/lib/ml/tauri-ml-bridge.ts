import { toErrorWithCode } from '@/lib/tauri-error';
import { isTauriRuntime } from '@/lib/runtime';

export interface NerEntity {
  entity: string;
  word: string;
  start: number;
  end: number;
  score: number;
}

export interface ClassifyResult {
  label: string;
  score: number;
}

export interface ModelCacheStatus {
  model_type: string;
  exists: boolean;
  file_path: string;
  size_bytes: number;
  sha256?: string | null;
}

function createUnsupportedRuntimeError(feature: string): Error & { code: string } {
  const error = new Error(`${feature} requires the Tauri desktop runtime.`) as Error & {
    code: string;
  };
  error.code = 'UNSUPPORTED_RUNTIME';
  return error;
}

async function invokeWithAppError<T>(command: string, args: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw createUnsupportedRuntimeError(`Command "${command}"`);
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<T>(command, args);
  } catch (error) {
    throw toErrorWithCode(error);
  }
}

export const loadModel = (modelType: string) =>
  invokeWithAppError<string>('load_model', { modelType });
export const downloadModel = (modelType: string) =>
  invokeWithAppError<string>('download_model', { modelType });
export const getModelStatus = (modelType: string) =>
  invokeWithAppError<ModelCacheStatus>('get_model_status', { modelType });
export const removeModelCache = (modelType: string) =>
  invokeWithAppError<boolean>('remove_model_cache', { modelType });
export const clearModelCache = () => invokeWithAppError<void>('clear_model_cache', {});
export const isOnnxRuntimeAvailable = () =>
  invokeWithAppError<boolean>('is_onnx_runtime_available', {});
export const runNer = (text: string) => invokeWithAppError<NerEntity[]>('run_ner', { text });
export const runSummarize = (text: string, maxLength: number) =>
  invokeWithAppError<string>('run_summarize', { text, maxLength });
export const runClassify = (text: string) =>
  invokeWithAppError<ClassifyResult[]>('run_classify', { text });
export const runEmbeddings = (text: string) =>
  invokeWithAppError<number[]>('run_embeddings', { text });
