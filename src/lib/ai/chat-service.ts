import { Message, ChatSettings } from '@/types/chat';
import { AIProvider } from '@/types/provider';
import { getDefaultPromptConfig, generateSystemPrompt } from '@/lib/prompts/system-prompts';
import * as bridge from '@/lib/tauri-bridge';
import { getApiKey } from '@/lib/tauri-bridge';
import { getProviderRegistryEntry, PROVIDER_IDS } from '@/lib/providers/registry';
import {
  extractSingaporeCitations,
  normalizeExtractedCitations,
  validateCitations,
} from '@/lib/citations';

export interface SendMessageResult {
  content: string;
}

export interface SendMessageOptions {
  signal?: AbortSignal;
}

const LEGAL_ANALYSIS_KEYWORDS = [
  'legal',
  'law',
  'case',
  'case law',
  'statute',
  'act',
  'regulation',
  'court',
  'judgment',
  'citation',
  'negligence',
  'liability',
  'contract',
  'tort',
  'precedent',
  'compliance',
];

const LEGAL_ACCURACY_CAUTION_BLOCK =
  '\n\n**Legal Accuracy Notice:** No valid legal citations were detected in this answer. Verify with authoritative Singapore legal sources before relying on this analysis.';

function createAbortError(): Error {
  const error = new Error('Request cancelled by user.');
  error.name = 'AbortError';
  return error;
}

function isAbortError(error: unknown): boolean {
  const hasDomAbort =
    typeof DOMException !== 'undefined' &&
    error instanceof DOMException &&
    error.name === 'AbortError';
  const hasErrorAbort = error instanceof Error && error.name === 'AbortError';
  return hasDomAbort || hasErrorAbort;
}

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) {
    throw createAbortError();
  }
}

async function withAbortSignal<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return operation;
  throwIfAborted(signal);

  let abortHandler: (() => void) | null = null;
  const abortPromise = new Promise<never>((_, reject) => {
    abortHandler = () => reject(createAbortError());
    signal.addEventListener('abort', abortHandler, { once: true });
  });

  try {
    return await Promise.race([operation, abortPromise]);
  } finally {
    if (abortHandler) {
      signal.removeEventListener('abort', abortHandler);
    }
  }
}

function isLikelyLegalAnalysisPrompt(messages: Message[]): boolean {
  const lastUserMessage = [...messages].reverse().find((message) => message.role === 'user');
  if (!lastUserMessage) return false;

  const lowered = lastUserMessage.content.toLowerCase();
  return LEGAL_ANALYSIS_KEYWORDS.some((keyword) => lowered.includes(keyword));
}

function hasValidCitation(content: string): boolean {
  const extracted = extractSingaporeCitations(content);
  if (extracted.length === 0) return false;

  const normalized = normalizeExtractedCitations(extracted);
  const validated = validateCitations(normalized);
  return validated.some((citation) => citation.validationStatus === 'valid');
}

function applyLegalAccuracyCaution(messages: Message[], content: string): string {
  if (!isLikelyLegalAnalysisPrompt(messages)) return content;
  if (hasValidCitation(content)) return content;
  if (content.includes('Legal Accuracy Notice:')) return content;
  return `${content}${LEGAL_ACCURACY_CAUTION_BLOCK}`;
}

export class ChatService {
  private static getAvailableProvider(configuredProviders: Record<string, boolean>): string | null {
    for (const provider of PROVIDER_IDS) {
      if (configuredProviders[provider]) return provider;
    }
    return null;
  }
  static async sendMessage(
    messages: Message[],
    configuredProviders: Record<string, boolean>,
    settings: ChatSettings,
    onChunk?: (chunk: string) => void,
    preferredProvider?: string,
    options?: SendMessageOptions
  ): Promise<SendMessageResult> {
    try {
      const signal = options?.signal;
      throwIfAborted(signal);

      let provider: string | null = preferredProvider || null;
      if (!provider || !configuredProviders[provider]) {
        provider = this.getAvailableProvider(configuredProviders);
      }
      if (!provider) throw new Error('No API keys configured. Please add an API key in settings.');
      const model = getProviderRegistryEntry(provider as AIProvider).defaultModel;
      const config = getDefaultPromptConfig('standard');
      config.useTools = settings.agentMode;
      if (!config.currentDate) {
        config.currentDate = new Date().toLocaleDateString('en-SG', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        });
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let activeProfile: any = null;
      if (settings.activeProfileId && settings.profiles) {
        activeProfile = settings.profiles.find((p) => p.id === settings.activeProfileId);
      }
      const role = activeProfile?.userRole || settings.userRole;
      const purpose = activeProfile?.userPurpose || settings.userPurpose;
      const customSystemPrompt = activeProfile?.systemPrompt || settings.systemPrompt;
      if (role || purpose) {
        config.userContext = { role: role || undefined, preferences: purpose || undefined };
      }
      if (customSystemPrompt) config.baseSystemPrompt = customSystemPrompt;
      config.systemPrompt = generateSystemPrompt(config);
      const formattedMessages: bridge.Message[] = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));
      const chatSettings: bridge.ChatSettings = {
        temperature: 0.7,
        max_tokens: 4096,
        system_prompt: config.systemPrompt,
      };
      let unlisten: (() => void) | null = null;
      let removeAbortListener: (() => void) | null = null;
      let fullResponse = '';
      if (onChunk) {
        unlisten = await bridge.onChatStream((chunk) => {
          if (signal?.aborted) return;
          if (!chunk.done && chunk.delta) {
            fullResponse += chunk.delta;
            onChunk(chunk.delta);
          }
        });
      }
      if (signal) {
        const handleAbort = () => {
          if (unlisten) {
            unlisten();
            unlisten = null;
          }
        };
        signal.addEventListener('abort', handleAbort, { once: true });
        removeAbortListener = () => signal.removeEventListener('abort', handleAbort);
      }
      try {
        const executeProviderRequest = async (): Promise<bridge.ProviderResponse> => {
          throwIfAborted(signal);
          if (provider === 'claude') {
            const apiKey = await getApiKey('claude');
            return bridge.chatClaude(formattedMessages, model, chatSettings, apiKey);
          }
          if (provider === 'openai') {
            const apiKey = await getApiKey('openai');
            return bridge.chatOpenai(formattedMessages, model, chatSettings, apiKey);
          }
          if (provider === 'gemini') {
            const apiKey = await getApiKey('gemini');
            return bridge.chatGemini(formattedMessages, model, chatSettings, apiKey);
          }
          if (provider === 'ollama') {
            const endpoint = 'http://localhost:11434';
            return bridge.chatOllama(formattedMessages, model, endpoint, chatSettings);
          }
          if (provider === 'lmstudio') {
            const endpoint = 'http://localhost:1234';
            return bridge.chatLmstudio(formattedMessages, model, endpoint, chatSettings);
          }
          throw new Error(`Unsupported provider: ${provider}`);
        };

        const result = await withAbortSignal(executeProviderRequest(), signal);
        throwIfAborted(signal);
        fullResponse = result.content;
      } finally {
        if (removeAbortListener) removeAbortListener();
        if (unlisten) unlisten();
      }
      return { content: applyLegalAccuracyCaution(messages, fullResponse) };
    } catch (error: any) {
      if (isAbortError(error)) throw error;
      if (!error.message?.includes('No API keys configured'))
        console.error('Chat service error:', error);
      if (error && typeof error === 'object' && typeof error.code === 'string') {
        throw error;
      }
      throw new Error(error.message || 'Failed to get AI response');
    }
  }
}
