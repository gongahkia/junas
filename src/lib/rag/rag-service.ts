import { chunkText } from './chunker';
import { isTauriRuntime } from '@/lib/runtime';
import { toErrorWithCode } from '@/lib/tauri-error';

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

function createUnsupportedRuntimeError(): Error & { code: string } {
  const error = new Error('RAG indexing is available only in the desktop app.') as Error & {
    code: string;
  };
  error.code = 'UNSUPPORTED_RUNTIME';
  return error;
}

async function invokeRag<T>(command: string, args: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw createUnsupportedRuntimeError();
  }

  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<T>(command, args);
  } catch (error) {
    throw toErrorWithCode(error);
  }
}

async function embedText(text: string): Promise<number[]> {
  return invokeRag<number[]>('run_embeddings', { text });
}

export async function indexDocument(
  collectionName: string,
  text: string,
  onProgress?: (done: number, total: number) => void
): Promise<number> {
  const chunks = chunkText(text, 512, 64, collectionName);
  const entries: VectorEntry[] = [];
  for (let i = 0; i < chunks.length; i += 1) {
    const embedding = await embedText(chunks[i].text);
    entries.push({
      chunk_id: chunks[i].id,
      text: chunks[i].text,
      embedding,
    });
    onProgress?.(i + 1, chunks.length);
  }
  return invokeRag<number>('index_document', {
    collection: collectionName,
    entries,
  });
}

export async function queryRelevantChunks(
  collectionName: string,
  query: string,
  topK = 5
): Promise<SimilarityResult[]> {
  const queryEmbedding = await embedText(query);
  return invokeRag<SimilarityResult[]>('query_similar', {
    collection: collectionName,
    queryEmbedding,
    topK,
  });
}

export function formatRagContext(results: SimilarityResult[]): string {
  if (results.length === 0) return '';
  const header = '**Reference Material (from uploaded documents):**\n\n';
  const body = results
    .map((result, index) => `[${index + 1}] (relevance: ${(result.score * 100).toFixed(0)}%)\n${result.text}`)
    .join('\n\n');
  return `${header}${body}\n\n---\n\n`;
}

export async function listCollections(): Promise<string[]> {
  if (!isTauriRuntime()) return [];
  return invokeRag<string[]>('list_collections', {});
}

export async function deleteCollection(name: string): Promise<boolean> {
  if (!isTauriRuntime()) return false;
  return invokeRag<boolean>('delete_collection', { collection: name });
}
