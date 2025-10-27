import { Message } from '@/types/chat';
import { ProviderFactory } from './provider-factory';
import { StorageManager } from '@/lib/storage';

export class ChatService {
  private static async getProvider() {
    const apiKeys = StorageManager.getApiKeys();
    const settings = StorageManager.getSettings();
    
    // Find the first available provider
    const availableProviders = ['gemini', 'openai', 'claude'];
    for (const provider of availableProviders) {
      if (apiKeys[provider] && apiKeys[provider].trim() !== '') {
        return ProviderFactory.createProvider(provider as any, {
          name: provider,
          displayName: provider,
          apiKey: apiKeys[provider],
          model: provider === 'gemini' ? 'gemini-2.0-flash-exp' :
                 provider === 'openai' ? 'gpt-4' : 'claude-3-5-sonnet-20241022',
          temperature: settings.temperature,
          maxTokens: settings.maxTokens,
          enabled: true,
        });
      }
    }
    
    throw new Error('No API keys configured. Please add an API key in settings.');
  }

  static async sendMessage(
    messages: Message[],
    onChunk?: (chunk: string) => void
  ): Promise<string> {
    try {
      const provider = await this.getProvider();

      // Convert messages to provider format, including file attachments
      const formattedMessages = messages.map(msg => {
        let content = msg.content;

        // If the message has file attachments, append their content
        if (msg.attachments && msg.attachments.length > 0) {
          const attachmentContents = msg.attachments
            .map(att => {
              // Include file name and content
              return `\n\n[File: ${att.name}]\n${att.content}`;
            })
            .join('\n');

          content = content + attachmentContents;
        }

        return {
          role: msg.role,
          content: content,
        };
      });

      // Add system prompt for legal context
      const systemPrompt = `You are Junas, a specialized AI legal assistant for Singapore law. You help lawyers, legal professionals, and individuals with:

- Contract analysis and review
- Case law research and analysis
- Statutory interpretation and compliance
- Legal document drafting
- Due diligence and risk assessment
- Citation and legal research

Always provide accurate, helpful legal information while being clear about limitations. When discussing Singapore law, be specific about relevant statutes, cases, and legal principles.`;

      const messagesWithSystem = [
        { role: 'system', content: systemPrompt },
        ...formattedMessages,
      ];

      let fullResponse = '';

      if (onChunk) {
        // Streaming response
        for await (const chunk of provider.generateStreamingResponse(messagesWithSystem)) {
          if (chunk.content) {
            fullResponse += chunk.content;
            onChunk(chunk.content);
          }
          if (chunk.done) break;
        }
      } else {
        // Non-streaming response
        const response = await provider.generateResponse(messagesWithSystem);
        fullResponse = response.content;
      }

      return fullResponse;
    } catch (error: any) {
      console.error('Chat service error:', error);
      throw new Error(error.message || 'Failed to get AI response');
    }
  }

  static async processFile(file: File): Promise<{ text: string; metadata: any }> {
    try {
      // Import the FileProcessor dynamically to avoid bundling issues
      const { FileProcessor } = await import('@/lib/file-processor');

      // Process the file client-side
      const processed = await FileProcessor.processFile(file);

      return {
        text: processed.text,
        metadata: processed.metadata,
      };
    } catch (error: any) {
      console.error('File processing error:', error);
      throw new Error(error.message || 'Failed to process file');
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
