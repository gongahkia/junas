import { Message } from '@/types/chat';
import { StorageManager } from '@/lib/storage';
import { getDefaultPromptConfig } from '@/lib/prompts/system-prompts';

export interface SendMessageResult {
  content: string;
}

export class ChatService {
  private static async getAvailableProvider(): Promise<string | null> {
    // Check which provider is configured via session
    try {
      const response = await fetch('/api/auth/keys');
      if (!response.ok) return null;

      const { configured } = await response.json();

      // Return first available provider in priority order
      const availableProviders = ['gemini', 'openai', 'claude'];
      for (const provider of availableProviders) {
        if (configured[provider]) {
          return provider;
        }
      }
    } catch (error) {
      // Silently handle provider check errors - user will see toast notification
    }

    return null;
  }

  static async sendMessage(
    messages: Message[],
    onChunk?: (chunk: string) => void,
    preferredProvider?: string
  ): Promise<SendMessageResult> {
    try {
      let provider: string | null = preferredProvider || null;

      // If no preferred provider or it's not configured, get available provider
      if (!provider) {
        provider = await this.getAvailableProvider();
      } else {
        // Verify the preferred provider is configured
        const response = await fetch('/api/auth/keys');
        if (response.ok) {
          const { configured } = await response.json();
          if (!configured[provider]) {
            // Fall back to any available provider
            provider = await this.getAvailableProvider();
          }
        }
      }

      if (!provider) {
        throw new Error('No API keys configured. Please add an API key in settings.');
      }

      const settings = StorageManager.getSettings();

      // Determine model based on provider
      const model = provider === 'gemini' ? 'gemini-2.0-flash-exp' :
                   provider === 'openai' ? 'gpt-4o' : 'claude-3-5-sonnet-20241022';

      // Get default system prompt config
      const config = getDefaultPromptConfig('standard');

      // Format messages with system prompt
      const formattedMessages = [
        { role: 'system', content: config.systemPrompt },
        ...messages.map(msg => ({
          role: msg.role,
          content: msg.content,
        })),
      ];

      let fullResponse = '';

      if (onChunk) {
        // Streaming
        const response = await fetch(`/api/providers/${provider}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
            const lines = chunk.split('\n').filter(line => line.trim());

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
          headers: { 'Content-Type': 'application/json' },
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


  static async analyzeDocument(text: string, type: 'contract' | 'case' | 'statute' = 'contract') {
    try {
      const response = await fetch('/api/tools/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text, type }),
      });

      if (!response.ok) {
        throw new Error('Document analysis failed');
      }

      return await response.json();
    } catch (error: any) {
      console.error('Document analysis error:', error);
      throw new Error(error.message || 'Failed to analyze document');
    }
  }

  static async searchLegalDatabase(query: string, type?: string) {
    try {
      const response = await fetch('/api/tools/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query, type }),
      });

      if (!response.ok) {
        throw new Error('Legal search failed');
      }

      return await response.json();
    } catch (error: any) {
      console.error('Legal search error:', error);
      throw new Error(error.message || 'Failed to search legal database');
    }
  }
}
