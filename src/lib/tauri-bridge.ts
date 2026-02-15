import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
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
// keychain
export const getApiKey = (provider: string) => invoke<string>("get_api_key", { provider });
export const setApiKey = (provider: string, key: string) => invoke<void>("set_api_key", { provider, key });
export const deleteApiKey = (provider: string) => invoke<void>("delete_api_key", { provider });
// chat providers
export const chatClaude = (messages: Message[], model: string, settings: ChatSettings, apiKey: string) =>
  invoke<ProviderResponse>("chat_claude", { messages, model, settings, apiKey });
export const chatOpenai = (messages: Message[], model: string, settings: ChatSettings, apiKey: string) =>
  invoke<ProviderResponse>("chat_openai", { messages, model, settings, apiKey });
export const chatGemini = (messages: Message[], model: string, settings: ChatSettings, apiKey: string) =>
  invoke<ProviderResponse>("chat_gemini", { messages, model, settings, apiKey });
export const chatOllama = (messages: Message[], model: string, endpoint: string, settings: ChatSettings) =>
  invoke<ProviderResponse>("chat_ollama", { messages, model, endpoint, settings });
export const chatLmstudio = (messages: Message[], model: string, endpoint: string, settings: ChatSettings) =>
  invoke<ProviderResponse>("chat_lmstudio", { messages, model, endpoint, settings });
// tools
export const fetchUrl = (url: string) => invoke<string>("fetch_url", { url });
export const webSearch = (query: string, apiKey: string) => invoke<SearchResult[]>("web_search", { query, apiKey });
export const healthCheck = (provider: string, endpoint?: string) => invoke<boolean>("health_check", { provider, endpoint });
// streaming
export const onChatStream = (callback: (chunk: StreamChunk) => void): Promise<UnlistenFn> =>
  listen<StreamChunk>("chat-stream", (event) => callback(event.payload));
