import { Message, ChatSettings } from '@/types/chat';
import { getDefaultPromptConfig, generateSystemPrompt } from '@/lib/prompts/system-prompts';

export interface SendMessageResult {
  content: string;
}

export class ChatService {
  private static getAvailableProvider(configuredProviders: Record<string, boolean>): string | null {
    // Return first available provider in priority order
    const availableProviders = ['gemini', 'openai', 'claude', 'ollama', 'lmstudio'];
    for (const provider of availableProviders) {
      if (configuredProviders[provider]) {
        return provider;
      }
    }
    return null;
  }
  private static csrfToken: string | null = null;

  private static async getCsrfToken(): Promise<string> {
    if (this.csrfToken) return this.csrfToken;
    try {
      const res = await fetch('/api/auth/csrf');
      const token = res.headers.get('X-CSRF-Token');
      if (token) {
        this.csrfToken = token;
        return token;
      }
    } catch (e) {
      console.error('Failed to fetch CSRF token', e);
    }
    return '';
  }

  static async sendMessage(
    messages: Message[],
    configuredProviders: Record<string, boolean>,
    settings: ChatSettings,
    onChunk?: (chunk: string) => void,
    preferredProvider?: string
  ): Promise<SendMessageResult> {
    try {
      const csrfToken = await this.getCsrfToken();
      let provider: string | null = preferredProvider || null;

      // If no preferred provider or it's not configured, get available provider
      if (!provider) {
        provider = this.getAvailableProvider(configuredProviders);
      } else {
        // Verify the preferred provider is configured
        if (!configuredProviders[provider]) {
          // Fall back to any available provider
          provider = this.getAvailableProvider(configuredProviders);
        }
      }

      if (!provider) {
        throw new Error('No API keys configured. Please add an API key in settings.');
      }

      // Determine model based on provider
      const model =
        provider === 'gemini'
          ? 'gemini-2.0-flash-exp'
          : provider === 'openai'
            ? 'gpt-4o'
            : provider === 'claude'
              ? 'claude-3-5-sonnet-20241022'
              : provider === 'ollama'
                ? 'llama3'
                : 'local-model';

      // Get default system prompt config
      const config = getDefaultPromptConfig('standard');
      config.useTools = settings.agentMode; // Explicitly enable tools based on agentMode

      // Ensure current date is set dynamically if not already
      if (!config.currentDate) {
        config.currentDate = new Date().toLocaleDateString('en-SG', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
        });
      }

      // Resolve active profile and user context
      // Logic: Active Profile > Global Settings
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let activeProfile: any = null;
      if (settings.activeProfileId && settings.profiles) {
        activeProfile = settings.profiles.find((p) => p.id === settings.activeProfileId);
      }

      const role = activeProfile?.userRole || settings.userRole;
      const purpose = activeProfile?.userPurpose || settings.userPurpose;
      const customSystemPrompt = activeProfile?.systemPrompt || settings.systemPrompt;

      if (role || purpose) {
        config.userContext = {
          role: role || undefined,
          preferences: purpose || undefined,
        };
      }

      if (customSystemPrompt) {
        config.baseSystemPrompt = customSystemPrompt;
      }

      config.systemPrompt = generateSystemPrompt(config); // Regenerate prompt with full config

      // Format messages with system prompt
      const formattedMessages = [
        { role: 'system', content: config.systemPrompt },
        ...messages.map((msg) => ({
          role: msg.role,
          content: msg.content,
        })),
      ];

      let fullResponse = '';

      if (onChunk) {
        // Streaming
        const response = await fetch(`/api/providers/${provider}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify({
            messages: formattedMessages,
            model,
            temperature: 0.7,
            maxTokens: 4096,
            stream: true,
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to get AI response');
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n').filter((line) => line.trim());

            for (const line of lines) {
              try {
                const data = JSON.parse(line);
                if (data.content) {
                  fullResponse += data.content;
                  onChunk(data.content);
                }
              } catch (e) {
                // Skip invalid JSON lines
              }
            }
          }
        }
      } else {
        // Non-streaming
        const response = await fetch(`/api/providers/${provider}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify({
            messages: formattedMessages,
            model,
            temperature: 0.7,
            maxTokens: 4096,
            stream: false,
          }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Failed to get AI response');
        }

        const result = await response.json();
        fullResponse = result.content;
      }

      return {
        content: fullResponse,
      };
    } catch (error: any) {
      // Don't log expected API key configuration errors to console
      if (!error.message?.includes('No API keys configured')) {
        console.error('Chat service error:', error);
      }
      throw new Error(error.message || 'Failed to get AI response');
    }
  }
}
