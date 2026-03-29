import { invoke } from '@tauri-apps/api/core';
import { chunkText } from './chunker';

interface VectorEntry {
  chunk_id: string;
  text: string;
  embedding: number[];
}
interface SimilarityResult {
  chunk_id: string;
  text: string;
  score: number;
}

async function embedText(text: string): Promise<number[]> {
  return invoke<number[]>('run_embeddings', { text });
}

export async function indexDocument(
  collectionName: string,
  text: string,
  onProgress?: (done: number, total: number) => void,
): Promise<number> {
  const chunks = chunkText(text, 512, 64, collectionName);
  const entries: VectorEntry[] = [];
  for (let i = 0; i < chunks.length; i++) {
    const embedding = await embedText(chunks[i].text);
    entries.push({
      chunk_id: chunks[i].id,
      text: chunks[i].text,
      embedding,
    });
    onProgress?.(i + 1, chunks.length);
  }
  return invoke<number>('index_document', {
    collection: collectionName,
    entries,
  });
}

export async function queryRelevantChunks(
  collectionName: string,
  query: string,
  topK = 5,
): Promise<SimilarityResult[]> {
  const queryEmbedding = await embedText(query);
  return invoke<SimilarityResult[]>('query_similar', {
    collection: collectionName,
    queryEmbedding,
    topK,
  });
}

export function formatRagContext(results: SimilarityResult[]): string {
  if (results.length === 0) return '';
  const header = '**Reference Material (from uploaded documents):**\n\n';
  const body = results
    .map((r, i) => `[${i + 1}] (relevance: ${(r.score * 100).toFixed(0)}%)\n${r.text}`)
    .join('\n\n');
  return header + body + '\n\n---\n\n';
}

export async function listCollections(): Promise<string[]> {
  return invoke<string[]>('list_collections', {});
}

export async function deleteCollection(name: string): Promise<boolean> {
  return invoke<boolean>('delete_collection', { collection: name });
}
