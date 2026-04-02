import { toErrorWithCode } from '@/lib/tauri-error';
import { isTauriRuntime } from '@/lib/runtime';

export interface Message {
  role: string;
  content: string;
}

export interface ChatSettings {
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  system_prompt?: string;
}

export interface ProviderResponse {
  content: string;
  model: string;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
}

export interface StreamChunk {
  delta: string;
  done: boolean;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
}

type UnlistenFn = () => void;

interface OpenAIStyleResponse {
  choices?: Array<{ message?: { content?: string } }>;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
}

const WEB_KEY_PREFIX = 'junas_web_api_key_';
const MAX_FETCH_TEXT_CHARS = 50_000;

function createAppError(code: string, message: string): Error & { code: string } {
  const error = new Error(message) as Error & { code: string };
  error.code = code;
  return error;
}

function normalizeRole(role: string): 'user' | 'assistant' {
  return role === 'assistant' ? 'assistant' : 'user';
}

function clampText(text: string, maxChars: number): string {
  return text.length <= maxChars ? text : `${text.slice(0, maxChars)}\n\n[Truncated output]`;
}

function extractHtmlText(html: string): string {
  if (typeof DOMParser === 'undefined') return html;
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  return parsed.body?.textContent?.replace(/\s+/g, ' ').trim() || '';
}

function readWebApiKey(provider: string): string {
  if (typeof window === 'undefined') {
    throw createAppError('KEYCHAIN_ERROR', 'API key storage is unavailable outside the browser.');
  }
  return localStorage.getItem(`${WEB_KEY_PREFIX}${provider}`) || '';
}

function writeWebApiKey(provider: string, key: string): void {
  if (typeof window === 'undefined') {
    throw createAppError('KEYCHAIN_ERROR', 'API key storage is unavailable outside the browser.');
  }
  localStorage.setItem(`${WEB_KEY_PREFIX}${provider}`, key);
}

function removeWebApiKey(provider: string): void {
  if (typeof window === 'undefined') {
    throw createAppError('KEYCHAIN_ERROR', 'API key storage is unavailable outside the browser.');
  }
  localStorage.removeItem(`${WEB_KEY_PREFIX}${provider}`);
}

async function tauriInvoke<T>(command: string, args: Record<string, unknown>): Promise<T> {
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    return await invoke<T>(command, args);
  } catch (error) {
    throw toErrorWithCode(error);
  }
}

async function invokeWithRuntime<T>(
  command: string,
  args: Record<string, unknown>
): Promise<T> {
  if (!isTauriRuntime()) {
    throw createAppError('UNSUPPORTED_RUNTIME', `Command "${command}" requires Tauri runtime.`);
  }
  return tauriInvoke<T>(command, args);
}

function normalizeOpenAIEndpoint(endpoint: string): string {
  const trimmed = endpoint.replace(/\/+$/, '');
  if (trimmed.endsWith('/v1')) return `${trimmed}/chat/completions`;
  if (trimmed.endsWith('/chat/completions')) return trimmed;
  return `${trimmed}/v1/chat/completions`;
}

function ensureUrl(pathOrUrl: string): string {
  try {
    new URL(pathOrUrl);
    return pathOrUrl;
  } catch {
    throw createAppError('NETWORK_ERROR', `Invalid URL: ${pathOrUrl}`);
  }
}

async function fetchJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(ensureUrl(url), init);
  if (!response.ok) {
    const errorBody = await response.text().catch(() => '');
    throw createAppError(
      'PROVIDER_ERROR',
      `Request failed (${response.status} ${response.statusText}): ${errorBody || 'No details'}`
    );
  }
  return (await response.json()) as T;
}

function buildWebChatSettings(settings: ChatSettings): ChatSettings {
  return {
    temperature: settings.temperature ?? 0.7,
    max_tokens: settings.max_tokens ?? 4096,
    top_p: settings.top_p ?? 0.95,
    system_prompt: settings.system_prompt,
  };
}

async function chatOpenAiWeb(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  const body = {
    model,
    messages: messages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
    temperature: settings.temperature,
    max_tokens: settings.max_tokens,
    top_p: settings.top_p,
    stream: false,
  };
  const result = await fetchJson<OpenAIStyleResponse>('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  });
  const content = result.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw createAppError('PROVIDER_ERROR', 'OpenAI returned an empty response.');
  }
  return {
    content,
    model,
    usage: result.usage,
  };
}

interface ClaudeBlock {
  type: string;
  text?: string;
}

interface ClaudeResponse {
  content?: ClaudeBlock[];
}

async function chatClaudeWeb(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  const body = {
    model,
    max_tokens: settings.max_tokens ?? 4096,
    temperature: settings.temperature ?? 0.7,
    system: settings.system_prompt || undefined,
    messages: messages
      .filter((message) => message.role !== 'system')
      .map((message) => ({
        role: normalizeRole(message.role),
        content: message.content,
      })),
  };
  const result = await fetchJson<ClaudeResponse>('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify(body),
  });
  const content = (result.content || [])
    .filter((block) => block.type === 'text' && typeof block.text === 'string')
    .map((block) => block.text || '')
    .join('\n')
    .trim();
  if (!content) {
    throw createAppError('PROVIDER_ERROR', 'Claude returned an empty response.');
  }
  return { content, model };
}

interface GeminiPart {
  text?: string;
}

interface GeminiResponse {
  candidates?: Array<{
    content?: {
      parts?: GeminiPart[];
    };
  }>;
}

async function chatGeminiWeb(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  const body = {
    system_instruction: settings.system_prompt
      ? {
          parts: [{ text: settings.system_prompt }],
        }
      : undefined,
    contents: messages
      .filter((message) => message.role !== 'system')
      .map((message) => ({
        role: message.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: message.content }],
      })),
    generationConfig: {
      temperature: settings.temperature ?? 0.7,
      topP: settings.top_p ?? 0.95,
      maxOutputTokens: settings.max_tokens ?? 4096,
    },
  };

  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
    model
  )}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const result = await fetchJson<GeminiResponse>(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const parts = result.candidates?.[0]?.content?.parts || [];
  const content = parts
    .map((part) => part.text || '')
    .join('\n')
    .trim();
  if (!content) {
    throw createAppError('PROVIDER_ERROR', 'Gemini returned an empty response.');
  }
  return { content, model };
}

async function chatOllamaWeb(
  messages: Message[],
  model: string,
  endpoint: string,
  settings: ChatSettings
): Promise<ProviderResponse> {
  const base = endpoint.replace(/\/+$/, '');
  const url = `${base}/api/chat`;
  const result = await fetchJson<{ message?: { content?: string } }>(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
      options: {
        temperature: settings.temperature ?? 0.7,
        top_p: settings.top_p ?? 0.95,
        num_predict: settings.max_tokens ?? 4096,
      },
    }),
  });
  const content = result.message?.content?.trim();
  if (!content) {
    throw createAppError('PROVIDER_ERROR', 'Ollama returned an empty response.');
  }
  return { content, model };
}

async function chatLmStudioWeb(
  messages: Message[],
  model: string,
  endpoint: string,
  settings: ChatSettings
): Promise<ProviderResponse> {
  const url = normalizeOpenAIEndpoint(endpoint);
  const result = await fetchJson<OpenAIStyleResponse>(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: settings.temperature ?? 0.7,
      top_p: settings.top_p ?? 0.95,
      max_tokens: settings.max_tokens ?? 4096,
      stream: false,
    }),
  });
  const content = result.choices?.[0]?.message?.content?.trim();
  if (!content) {
    throw createAppError('PROVIDER_ERROR', 'LM Studio returned an empty response.');
  }
  return {
    content,
    model,
    usage: result.usage,
  };
}

// keychain
export async function getApiKey(provider: string): Promise<string> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<string>('get_api_key', { provider });
  }
  return readWebApiKey(provider);
}

export async function setApiKey(provider: string, key: string): Promise<void> {
  if (isTauriRuntime()) {
    await invokeWithRuntime<void>('set_api_key', { provider, key });
    return;
  }
  writeWebApiKey(provider, key);
}

export async function deleteApiKey(provider: string): Promise<void> {
  if (isTauriRuntime()) {
    await invokeWithRuntime<void>('delete_api_key', { provider });
    return;
  }
  removeWebApiKey(provider);
}

// chat providers
export async function chatClaude(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<ProviderResponse>('chat_claude', {
      messages,
      model,
      settings: buildWebChatSettings(settings),
      apiKey,
    });
  }
  return chatClaudeWeb(messages, model, settings, apiKey);
}

export async function chatOpenai(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<ProviderResponse>('chat_openai', {
      messages,
      model,
      settings: buildWebChatSettings(settings),
      apiKey,
    });
  }
  return chatOpenAiWeb(messages, model, settings, apiKey);
}

export async function chatGemini(
  messages: Message[],
  model: string,
  settings: ChatSettings,
  apiKey: string
): Promise<ProviderResponse> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<ProviderResponse>('chat_gemini', {
      messages,
      model,
      settings: buildWebChatSettings(settings),
      apiKey,
    });
  }
  return chatGeminiWeb(messages, model, settings, apiKey);
}

export async function chatOllama(
  messages: Message[],
  model: string,
  endpoint: string,
  settings: ChatSettings
): Promise<ProviderResponse> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<ProviderResponse>('chat_ollama', {
      messages,
      model,
      endpoint,
      settings: buildWebChatSettings(settings),
    });
  }
  return chatOllamaWeb(messages, model, endpoint, settings);
}

export async function chatLmstudio(
  messages: Message[],
  model: string,
  endpoint: string,
  settings: ChatSettings
): Promise<ProviderResponse> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<ProviderResponse>('chat_lmstudio', {
      messages,
      model,
      endpoint,
      settings: buildWebChatSettings(settings),
    });
  }
  return chatLmStudioWeb(messages, model, endpoint, settings);
}

// tools
export async function fetchUrl(url: string): Promise<string> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<string>('fetch_url', { url });
  }

  try {
    const response = await fetch(ensureUrl(url), { method: 'GET' });
    if (!response.ok) {
      throw createAppError(
        'NETWORK_ERROR',
        `Unable to fetch URL (${response.status} ${response.statusText}).`
      );
    }
    const contentType = response.headers.get('content-type') || '';
    const rawText = await response.text();
    if (contentType.includes('text/html')) {
      return clampText(extractHtmlText(rawText), MAX_FETCH_TEXT_CHARS);
    }
    return clampText(rawText, MAX_FETCH_TEXT_CHARS);
  } catch (error) {
    if (error instanceof Error && 'code' in error) throw error;
    throw toErrorWithCode(error);
  }
}

export async function webSearch(query: string, apiKey: string): Promise<SearchResult[]> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<SearchResult[]>('web_search', { query, apiKey });
  }

  try {
    const response = await fetch('https://google.serper.dev/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-KEY': apiKey,
      },
      body: JSON.stringify({ q: query, num: 8 }),
    });
    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw createAppError(
        'NETWORK_ERROR',
        `Serper search failed (${response.status} ${response.statusText}): ${body || 'No details'}.`
      );
    }
    const payload = (await response.json()) as {
      organic?: Array<{ title?: string; link?: string; snippet?: string }>;
    };
    return (payload.organic || [])
      .filter((item) => typeof item.title === 'string' && typeof item.link === 'string')
      .map((item) => ({
        title: item.title || 'Untitled Result',
        url: item.link || '',
        snippet: item.snippet || '',
      }));
  } catch (error) {
    if (error instanceof Error && 'code' in error) throw error;
    throw toErrorWithCode(error);
  }
}

export async function healthCheck(provider: string, endpoint?: string): Promise<boolean> {
  if (isTauriRuntime()) {
    return invokeWithRuntime<boolean>('health_check', { provider, endpoint });
  }

  if (provider === 'ollama') {
    const base = (endpoint || 'http://localhost:11434').replace(/\/+$/, '');
    const response = await fetch(`${base}/api/tags`, { method: 'GET' }).catch(() => null);
    return Boolean(response?.ok);
  }

  if (provider === 'lmstudio') {
    const base = (endpoint || 'http://localhost:1234').replace(/\/+$/, '');
    const response = await fetch(`${base}/v1/models`, { method: 'GET' }).catch(() => null);
    return Boolean(response?.ok);
  }

  const key = await getApiKey(provider).catch(() => '');
  return key.trim().length > 0;
}

// document parsing
export interface ParsedDocument {
  filename: string;
  text: string;
  page_count: number;
  char_count: number;
}

export async function parsePdf(path: string): Promise<ParsedDocument> {
  if (!isTauriRuntime()) {
    throw createAppError(
      'UNSUPPORTED_RUNTIME',
      'PDF parsing is available only in the desktop app.'
    );
  }
  return invokeWithRuntime<ParsedDocument>('parse_pdf', { path });
}

export async function parseDocx(path: string): Promise<ParsedDocument> {
  if (!isTauriRuntime()) {
    throw createAppError(
      'UNSUPPORTED_RUNTIME',
      'DOCX parsing is available only in the desktop app.'
    );
  }
  return invokeWithRuntime<ParsedDocument>('parse_docx', { path });
}

// streaming
export async function onChatStream(callback: (chunk: StreamChunk) => void): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => undefined;
  }

  try {
    const { listen } = await import('@tauri-apps/api/event');
    return await listen<StreamChunk>('chat-stream', (event) => callback(event.payload));
  } catch (error) {
    throw toErrorWithCode(error);
  }
}
