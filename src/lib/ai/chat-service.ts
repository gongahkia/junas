import { Message, ReasoningMetadata, ThinkingStage } from '@/types/chat';
import { StorageManager } from '@/lib/storage';
import { analyzeQuery, overrideComplexity, type QueryAnalysis } from '@/lib/prompts/query-classifier';
import { StreamingReasoningEngine } from '@/lib/prompts/reasoning-engine';
import { ReasoningDepth } from '@/lib/prompts/system-prompts';

export interface SendMessageResult {
  content: string;
  reasoning: ReasoningMetadata;
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
      console.error('Error checking provider status:', error);
    }

    return null;
  }

  static async sendMessage(
    messages: Message[],
    onChunk?: (chunk: string) => void,
    options?: {
      reasoningDepth?: ReasoningDepth;
      skipMultiStage?: boolean;
      onReasoningUpdate?: (metadata: ReasoningMetadata) => void;
      onStageChange?: (stage: string, current: number, total: number) => void;
      onThinkingStage?: (stage: ThinkingStage) => void;
    }
  ): Promise<SendMessageResult> {
    try {
      const provider = await this.getAvailableProvider();

      if (!provider) {
        throw new Error('No API keys configured. Please add an API key in settings.');
      }

      const settings = StorageManager.getSettings();

      // Get the last user message for complexity analysis
      const lastUserMessage = messages.filter(m => m.role === 'user').slice(-1)[0];
      const query = lastUserMessage?.content || '';

      // Analyze query complexity
      let analysis = analyzeQuery(query);

      // Override with user preference if provided
      if (options?.reasoningDepth) {
        analysis = overrideComplexity(analysis, options.reasoningDepth);
      }

      // Check if user disabled multi-stage in settings
      const enableAdvancedReasoning = settings.enableAdvancedReasoning !== false;
      const skipMultiStage = options?.skipMultiStage || !enableAdvancedReasoning;

      if (skipMultiStage) {
        analysis.useMultiStage = false;
        analysis.useReAct = false;
      }

      // Determine model based on provider
      const model = provider === 'gemini' ? 'gemini-2.0-flash-exp' :
                   provider === 'openai' ? 'gpt-4o' : 'claude-3-5-sonnet-20241022';

      // Create API call function for reasoning engine
      const apiCallFn = async (
        formattedMessages: any[],
        config: { temperature: number; maxTokens: number },
        chunkCallback?: (chunk: string) => void
      ): Promise<string> => {
        let fullResponse = '';

        if (chunkCallback) {
          // Streaming
          const response = await fetch(`/api/providers/${provider}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              messages: formattedMessages,
              model,
              temperature: config.temperature,
              maxTokens: config.maxTokens,
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
                    chunkCallback(data.content);
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
              temperature: config.temperature,
              maxTokens: config.maxTokens,
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
      };

      // Use multi-stage reasoning engine for streaming
      if (onChunk) {
        const result = await StreamingReasoningEngine.processQueryStreaming(
          query,
          analysis,
          messages,
          apiCallFn,
          (stage, current, total) => {
            // Stage start callback - notify UI
            console.log(`Reasoning stage ${current}/${total}: ${stage}`);
            if (options?.onStageChange) {
              options.onStageChange(stage, current, total);
            }
          },
          onChunk,
          options?.onThinkingStage
        );

        const reasoningMetadata: ReasoningMetadata = {
          complexity: analysis.complexity,
          reasoningDepth: analysis.reasoningDepth,
          stages: result.stages.length,
          multiStage: result.stages.length > 1,
          reasoningTime: result.reasoningTime,
        };

        // Notify about final reasoning metadata
        if (options?.onReasoningUpdate) {
          options.onReasoningUpdate(reasoningMetadata);
        }

        return {
          content: result.finalResponse,
          reasoning: reasoningMetadata,
        };
      } else {
        // Non-streaming: use regular reasoning engine
        const { ReasoningEngine } = await import('@/lib/prompts/reasoning-engine');
        const result = await ReasoningEngine.processQuery(
          query,
          analysis,
          messages,
          apiCallFn
        );

        const reasoningMetadata: ReasoningMetadata = {
          complexity: analysis.complexity,
          reasoningDepth: analysis.reasoningDepth,
          stages: result.stages.length,
          multiStage: result.stages.length > 1,
          reasoningTime: result.reasoningTime,
        };

        // Notify about final reasoning metadata
        if (options?.onReasoningUpdate) {
          options.onReasoningUpdate(reasoningMetadata);
        }

        return {
          content: result.finalResponse,
          reasoning: reasoningMetadata,
        };
      }
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
