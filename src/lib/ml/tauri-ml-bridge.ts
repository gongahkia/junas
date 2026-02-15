import { invoke } from "@tauri-apps/api/core";
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
export const loadModel = (modelType: string) => invoke<string>("load_model", { modelType });
export const runNer = (text: string) => invoke<NerEntity[]>("run_ner", { text });
export const runSummarize = (text: string, maxLength: number) => invoke<string>("run_summarize", { text, maxLength });
export const runClassify = (text: string) => invoke<ClassifyResult[]>("run_classify", { text });
export const runEmbeddings = (text: string) => invoke<number[]>("run_embeddings", { text });
