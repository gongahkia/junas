import { GoogleGenerativeAI } from '@google/generative-ai';
import { ProviderResponse, StreamingResponse, ProviderCapabilities, ProviderError } from '@/types/provider';

export class GeminiProvider {
  private client: GoogleGenerativeAI;
  private model: string;
  private apiKey: string;

  constructor(apiKey: string, model: string = 'gemini-2.0-flash-exp') {
    this.client = new GoogleGenerativeAI(apiKey);
    this.model = model;
    this.apiKey = apiKey;
  }

  static getCapabilities(): ProviderCapabilities {
    return {
      supportsStreaming: true,
      supportsFunctionCalling: true,
      supportsVision: true,
      maxContextLength: 1000000, // 1M tokens
      availableModels: [
        'gemini-2.0-flash-exp',
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-1.0-pro',
        'gemini-pro',
      ],
    };
  }

  async listAvailableModels(): Promise<string[]> {
    try {
      // Try to list models using the API
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models?key=${this.apiKey}`,
        { method: 'GET' }
      );

      if (response.ok) {
        const data = await response.json();
        const models = data.models?.map((m: { name: string }) => m.name.replace('models/', '')) || [];
        return models;
      }
    } catch (error) {
      console.error('[Gemini] Failed to list models:', error);
    }

    // Fallback to default models
    return GeminiProvider.getCapabilities().availableModels;
  }

  async generateResponse(
    messages: Array<{ role: string; content: string }>,
    tools?: Array<{ name: string; description: string; parameters: any }>,
    options?: {
      temperature?: number;
      maxTokens?: number;
    }
  ): Promise<ProviderResponse> {
    try {
      const model = this.client.getGenerativeModel({
        model: this.model,
        generationConfig: {
          temperature: options?.temperature || 0.7,
          maxOutputTokens: options?.maxTokens || 4000,
        },
      });

      // Convert messages to Gemini chat format
      const { history, currentMessage } = this.formatMessagesForGemini(messages);

      // Use chat session for proper conversation context
      const chat = model.startChat({
        history,
      });

      const result = await chat.sendMessage(currentMessage);
      const response = await result.response;
      const text = response.text();

      return {
        content: text,
        model: this.model,
        finishReason: 'stop',
      };
    } catch (error: unknown) {
      console.error('[Gemini] Error details:', error);
      throw this.handleError(error);
    }
  }

  async *generateStreamingResponse(
    messages: Array<{ role: string; content: string }>,
    tools?: Array<{ name: string; description: string; parameters: any }>,
    options?: {
      temperature?: number;
      maxTokens?: number;
    }
  ): AsyncGenerator<StreamingResponse> {
    try {
      const model = this.client.getGenerativeModel({
        model: this.model,
        generationConfig: {
          temperature: options?.temperature || 0.7,
          maxOutputTokens: options?.maxTokens || 4000,
        },
      });

      // Convert messages to Gemini chat format
      const { history, currentMessage } = this.formatMessagesForGemini(messages);

      // Use chat session for proper conversation context
      const chat = model.startChat({
        history,
      });

      const result = await chat.sendMessageStream(currentMessage);

      let fullContent = '';

      for await (const chunk of result.stream) {
        const chunkText = chunk.text();
        fullContent += chunkText;

        yield {
          content: chunkText,
          done: false,
        };
      }

      yield {
        content: '',
        done: true,
      };
    } catch (error: unknown) {
      throw this.handleError(error);
    }
  }

  private formatMessagesForGemini(messages: Array<{ role: string; content: string }>): {
    history: Array<{ role: 'user' | 'model'; parts: Array<{ text: string }> }>;
    currentMessage: string;
  } {
    // Gemini uses 'user' and 'model' roles
    // History should contain all messages except the last one
    // Last message is sent separately

    if (messages.length === 0) {
      return { history: [], currentMessage: '' };
    }

    // Convert all messages except the last to Gemini format
    const history = messages.slice(0, -1).map(msg => ({
      role: msg.role === 'assistant' ? ('model' as const) : ('user' as const),
      parts: [{ text: msg.content }],
    }));

    // Get the last message content
    const lastMessage = messages[messages.length - 1];
    const currentMessage = lastMessage.content;

    return {
      history,
      currentMessage,
    };
  }

  private handleError(error: unknown): ProviderError {
    const errorMessage = error instanceof Error ? error.message : String(error);

    if (errorMessage.includes('API key')) {
      return {
        code: 'INVALID_API_KEY',
        message: 'Invalid API key. Please check your Gemini API key.',
        retryable: false,
      };
    }

    if (errorMessage.includes('not found') || errorMessage.includes('404')) {
      return {
        code: 'MODEL_NOT_FOUND',
        message: `Model "${this.model}" not found. Try these models: "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", or "gemini-pro". Check available models at https://ai.google.dev/gemini-api/docs/models/gemini`,
        retryable: false,
      };
    }

    if (errorMessage.includes('quota')) {
      return {
        code: 'QUOTA_EXCEEDED',
        message: 'API quota exceeded. Please try again later.',
        retryable: true,
      };
    }

    if (errorMessage.includes('safety')) {
      return {
        code: 'SAFETY_FILTER',
        message: 'Response blocked by safety filters. Please rephrase your request.',
        retryable: false,
      };
    }

    return {
      code: 'UNKNOWN_ERROR',
      message: errorMessage || 'An unknown error occurred',
      retryable: true,
    };
  }
}
