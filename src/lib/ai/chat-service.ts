import { Message } from '@/types/chat';
import { StorageManager } from '@/lib/storage';

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
      console.error('Error checking provider status:', error);
    }

    return null;
  }

  static async sendMessage(
    messages: Message[],
    onChunk?: (chunk: string) => void
  ): Promise<string> {
    try {
      const provider = await this.getAvailableProvider();

      if (!provider) {
        throw new Error('No API keys configured. Please add an API key in settings.');
      }

      const settings = StorageManager.getSettings();

      // Convert messages to provider format
      const formattedMessages = messages.map(msg => ({
        role: msg.role,
        content: msg.content,
      }));

      // Add system prompt for legal context
      const systemPrompt = `You are Junas, a specialized AI legal assistant for Singapore law. You help lawyers, legal professionals, and individuals with:

- Contract analysis and review
- Case law research and analysis
- Statutory interpretation and compliance
- Legal document drafting
- Due diligence and risk assessment
- Citation and legal research

Always provide accurate, helpful legal information while being clear about limitations. When discussing Singapore law, be specific about relevant statutes, cases, and legal principles.

IMPORTANT: When citing legal cases, ALWAYS use the FULL legal citation format. Never use shortened case names alone. Examples of correct formats:
- [YYYY] X SLR(R) XXX (e.g., [2009] 2 SLR(R) 332)
- [YYYY] SLR XXX (e.g., [2015] SLR 123)
- [YYYY] SGCA XX (e.g., [2020] SGCA 45)
- [YYYY] SGHC XX (e.g., [2019] SGHC 123)

Always include the full citation immediately after or with the case name (e.g., "In Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] 4 SLR(R) 100, the Court of Appeal..."). Do not abbreviate citations or use shortened forms.`;

      const messagesWithSystem = [
        { role: 'system', content: systemPrompt },
        ...formattedMessages,
      ];

      // Determine model based on provider
      const model = provider === 'gemini' ? 'gemini-2.0-flash-exp' :
                   provider === 'openai' ? 'gpt-4o' : 'claude-3-5-sonnet-20241022';

      let fullResponse = '';

      if (onChunk) {
        // Streaming response via proxy
        const response = await fetch(`/api/providers/${provider}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: messagesWithSystem,
            model,
            temperature: settings.temperature,
            maxTokens: settings.maxTokens,
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
        // Non-streaming response via proxy
        const response = await fetch(`/api/providers/${provider}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: messagesWithSystem,
            model,
            temperature: settings.temperature,
            maxTokens: settings.maxTokens,
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

      return fullResponse;
    } catch (error: any) {
      console.error('Chat service error:', error);
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
