import OpenAI from 'openai';
import { ProviderResponse, StreamingResponse, ToolCall, ProviderCapabilities, ProviderError } from '@/types/provider';

export class OpenAIProvider {
  private client: OpenAI;
  private model: string;

  constructor(apiKey: string, model: string = 'gpt-4') {
    this.client = new OpenAI({
      apiKey,
      dangerouslyAllowBrowser: true, // Required for client-side usage
    });
    this.model = model;
  }

  static getCapabilities(): ProviderCapabilities {
    return {
      supportsStreaming: true,
      supportsFunctionCalling: true,
      supportsVision: true,
      maxContextLength: 128000, // 128K tokens for GPT-4
      availableModels: [
        'gpt-4',
        'gpt-4-turbo',
        'gpt-3.5-turbo',
        'gpt-4o',
        'gpt-4o-mini',
      ],
    };
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
      const response = await this.client.chat.completions.create({
        model: this.model,
        messages: messages as any,
        tools: tools ? this.formatToolsForOpenAI(tools) : undefined,
        temperature: options?.temperature || 0.7,
        max_tokens: options?.maxTokens || 4000,
      });

      const choice = response.choices[0];
      const message = choice.message;

      return {
        content: message.content || '',
        usage: response.usage ? {
          promptTokens: response.usage.prompt_tokens,
          completionTokens: response.usage.completion_tokens,
          totalTokens: response.usage.total_tokens,
        } : undefined,
        model: this.model,
        finishReason: choice.finish_reason || undefined,
      };
    } catch (error: any) {
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
      const stream = await this.client.chat.completions.create({
        model: this.model,
        messages: messages as any,
        tools: tools ? this.formatToolsForOpenAI(tools) : undefined,
        temperature: options?.temperature || 0.7,
        max_tokens: options?.maxTokens || 4000,
        stream: true,
      });

      let fullContent = '';
      let totalTokens = 0;

      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta;
        if (delta?.content) {
          fullContent += delta.content;
          yield {
            content: delta.content,
            done: false,
          };
        }
        
        if (chunk.usage) {
          totalTokens = chunk.usage.total_tokens;
        }
      }

      yield {
        content: '',
        done: true,
        usage: totalTokens ? {
          promptTokens: 0,
          completionTokens: totalTokens,
          totalTokens,
        } : undefined,
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  private formatToolsForOpenAI(tools: Array<{ name: string; description: string; parameters: any }>) {
    return tools.map(tool => ({
      type: 'function' as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters,
      },
    }));
  }

  private handleError(error: any): ProviderError {
    if (error.status === 401) {
      return {
        code: 'INVALID_API_KEY',
        message: 'Invalid API key. Please check your OpenAI API key.',
        status: 401,
        retryable: false,
      };
    }
    
    if (error.status === 429) {
      return {
        code: 'RATE_LIMIT',
        message: 'Rate limit exceeded. Please try again later.',
        status: 429,
        retryable: true,
      };
    }
    
    if (error.status === 400 && error.message?.includes('context_length')) {
      return {
        code: 'CONTEXT_TOO_LONG',
        message: 'Message too long. Please shorten your input.',
        status: 400,
        retryable: false,
      };
    }
    
    return {
      code: 'UNKNOWN_ERROR',
      message: error.message || 'An unknown error occurred',
      status: error.status,
      retryable: true,
    };
  }
}
