import { GoogleGenerativeAI } from '@google/generative-ai';
import { ProviderResponse, StreamingResponse, ToolCall, ProviderCapabilities, ProviderError } from '@/types/provider';

export class GeminiProvider {
  private client: GoogleGenerativeAI;
  private model: string;
  private apiKey: string;

  constructor(apiKey: string, model: string = 'gemini-1.5-flash') {
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
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-1.0-pro',
        'gemini-2.0-flash-exp',
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
        const models = data.models?.map((m: any) => m.name.replace('models/', '')) || [];
        console.log('[Gemini] Available models:', models);
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
      console.log('[Gemini] Using model:', this.model);
      const model = this.client.getGenerativeModel({
        model: this.model,
        generationConfig: {
          temperature: options?.temperature || 0.7,
          maxOutputTokens: options?.maxTokens || 4000,
        },
      });

      // Convert messages to Gemini format
      const prompt = this.formatMessagesForGemini(messages);

      const result = await model.generateContent(prompt);
      const response = await result.response;
      const text = response.text();

      return {
        content: text,
        model: this.model,
        finishReason: 'stop',
      };
    } catch (error: any) {
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

      const prompt = this.formatMessagesForGemini(messages);
      
      const result = await model.generateContentStream(prompt);
      
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
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  private formatMessagesForGemini(messages: Array<{ role: string; content: string }>): string {
    // Gemini doesn't use a message array format, so we concatenate the conversation
    return messages
      .map(msg => {
        if (msg.role === 'user') {
          return `User: ${msg.content}`;
        } else if (msg.role === 'assistant') {
          return `Assistant: ${msg.content}`;
        } else {
          return msg.content;
        }
      })
      .join('\n\n');
  }

  private handleError(error: any): ProviderError {
    if (error.message?.includes('API key')) {
      return {
        code: 'INVALID_API_KEY',
        message: 'Invalid API key. Please check your Gemini API key.',
        retryable: false,
      };
    }

    if (error.message?.includes('not found') || error.message?.includes('404')) {
      return {
        code: 'MODEL_NOT_FOUND',
        message: `Model "${this.model}" not found. Try these models: "gemini-1.5-flash", "gemini-1.5-pro", or "gemini-pro". Check available models at https://ai.google.dev/gemini-api/docs/models/gemini`,
        retryable: false,
      };
    }

    if (error.message?.includes('quota')) {
      return {
        code: 'QUOTA_EXCEEDED',
        message: 'API quota exceeded. Please try again later.',
        retryable: true,
      };
    }

    if (error.message?.includes('safety')) {
      return {
        code: 'SAFETY_FILTER',
        message: 'Response blocked by safety filters. Please rephrase your request.',
        retryable: false,
      };
    }

    return {
      code: 'UNKNOWN_ERROR',
      message: error.message || 'An unknown error occurred',
      retryable: true,
    };
  }
}
