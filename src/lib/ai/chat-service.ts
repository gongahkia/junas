import { Message, ChatSettings } from '@/types/chat';
import { getDefaultPromptConfig, generateSystemPrompt } from '@/lib/prompts/system-prompts';
import * as bridge from '@/lib/tauri-bridge';
import { getApiKey } from '@/lib/tauri-bridge';
export interface SendMessageResult {
  content: string;
}
export class ChatService {
  private static getAvailableProvider(configuredProviders: Record<string, boolean>): string | null {
    const availableProviders = ['gemini', 'openai', 'claude', 'ollama', 'lmstudio'];
    for (const provider of availableProviders) {
      if (configuredProviders[provider]) return provider;
    }
    return null;
  }
  static async sendMessage(
    messages: Message[],
    configuredProviders: Record<string, boolean>,
    settings: ChatSettings,
    onChunk?: (chunk: string) => void,
    preferredProvider?: string
  ): Promise<SendMessageResult> {
    try {
      let provider: string | null = preferredProvider || null;
      if (!provider || !configuredProviders[provider]) {
        provider = this.getAvailableProvider(configuredProviders);
      }
      if (!provider) throw new Error('No API keys configured. Please add an API key in settings.');
      const model = provider === 'gemini' ? 'gemini-2.0-flash-exp'
        : provider === 'openai' ? 'gpt-4o'
        : provider === 'claude' ? 'claude-3-5-sonnet-20241022'
        : provider === 'ollama' ? 'llama3' : 'local-model';
      const config = getDefaultPromptConfig('standard');
      config.useTools = settings.agentMode;
      if (!config.currentDate) {
        config.currentDate = new Date().toLocaleDateString('en-SG', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
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
      const formattedMessages: bridge.Message[] = messages.map((msg) => ({ role: msg.role, content: msg.content }));
      const chatSettings: bridge.ChatSettings = {
        temperature: 0.7,
        max_tokens: 4096,
        system_prompt: config.systemPrompt,
      };
      let unlisten: (() => void) | null = null;
      let fullResponse = '';
      if (onChunk) {
        unlisten = await bridge.onChatStream((chunk) => {
          if (!chunk.done && chunk.delta) {
            fullResponse += chunk.delta;
            onChunk(chunk.delta);
          }
        });
      }
      try {
        if (provider === 'claude') {
          const apiKey = await getApiKey('claude');
          const result = await bridge.chatClaude(formattedMessages, model, chatSettings, apiKey);
          if (!onChunk) fullResponse = result.content;
        } else if (provider === 'openai') {
          const apiKey = await getApiKey('openai');
          const result = await bridge.chatOpenai(formattedMessages, model, chatSettings, apiKey);
          if (!onChunk) fullResponse = result.content;
        } else if (provider === 'gemini') {
          const apiKey = await getApiKey('gemini');
          const result = await bridge.chatGemini(formattedMessages, model, chatSettings, apiKey);
          if (!onChunk) fullResponse = result.content;
        } else if (provider === 'ollama') {
          const endpoint = 'http://localhost:11434';
          const result = await bridge.chatOllama(formattedMessages, model, endpoint, chatSettings);
          if (!onChunk) fullResponse = result.content;
        } else if (provider === 'lmstudio') {
          const endpoint = 'http://localhost:1234';
          const result = await bridge.chatLmstudio(formattedMessages, model, endpoint, chatSettings);
          if (!onChunk) fullResponse = result.content;
        }
      } finally {
        if (unlisten) unlisten();
      }
      return { content: fullResponse };
    } catch (error: any) {
      if (!error.message?.includes('No API keys configured')) console.error('Chat service error:', error);
      throw new Error(error.message || 'Failed to get AI response');
    }
  }
}
