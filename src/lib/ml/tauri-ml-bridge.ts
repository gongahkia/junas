import { invoke } from '@tauri-apps/api/core';
import { toErrorWithCode } from '@/lib/tauri-error';

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

async function invokeWithAppError<T>(command: string, args: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw toErrorWithCode(error);
  }
}

export const loadModel = (modelType: string) =>
  invokeWithAppError<string>('load_model', { modelType });
export const runNer = (text: string) => invokeWithAppError<NerEntity[]>('run_ner', { text });
export const runSummarize = (text: string, maxLength: number) =>
  invokeWithAppError<string>('run_summarize', { text, maxLength });
export const runClassify = (text: string) =>
  invokeWithAppError<ClassifyResult[]>('run_classify', { text });
export const runEmbeddings = (text: string) =>
  invokeWithAppError<number[]>('run_embeddings', { text });
