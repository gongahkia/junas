import Anthropic from '@anthropic-ai/sdk';
import { ProviderResponse, StreamingResponse, ProviderCapabilities, ProviderError } from '@/types/provider';

export class ClaudeProvider {
  private client: Anthropic;
  private model: string;

  constructor(apiKey: string, model: string = 'claude-3-5-sonnet-20241022') {
    this.client = new Anthropic({
      apiKey,
    });
    this.model = model;
  }

  static getCapabilities(): ProviderCapabilities {
    return {
      supportsStreaming: true,
      supportsFunctionCalling: true,
      supportsVision: true,
      maxContextLength: 200000, // 200K tokens
      availableModels: [
        'claude-3-5-sonnet-20241022',
        'claude-3-5-haiku-20241022',
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307',
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
      // Convert messages to Claude format
      const { system, messages: claudeMessages } = this.formatMessagesForClaude(messages);
      
      const response = await this.client.messages.create({
        model: this.model,
        system: system,
        messages: claudeMessages,
        tools: tools ? this.formatToolsForClaude(tools) : undefined,
        temperature: options?.temperature || 0.7,
        max_tokens: options?.maxTokens || 4000,
      });

      const content = response.content[0];
      const text = content.type === 'text' ? content.text : '';

      return {
        content: text,
        usage: {
          promptTokens: response.usage.input_tokens,
          completionTokens: response.usage.output_tokens,
          totalTokens: response.usage.input_tokens + response.usage.output_tokens,
        },
        model: this.model,
        finishReason: response.stop_reason ?? undefined,
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
      const { system, messages: claudeMessages } = this.formatMessagesForClaude(messages);
      
      const stream = await this.client.messages.create({
        model: this.model,
        system: system,
        messages: claudeMessages,
        tools: tools ? this.formatToolsForClaude(tools) : undefined,
        temperature: options?.temperature || 0.7,
        max_tokens: options?.maxTokens || 4000,
        stream: true,
      });

      let fullContent = '';
      let inputTokens = 0;
      let outputTokens = 0;

      for await (const event of stream) {
        if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
          const text = event.delta.text;
          fullContent += text;
          yield {
            content: text,
            done: false,
          };
        }

        if (event.type === 'message_start') {
          inputTokens = event.message.usage.input_tokens;
        }

        if (event.type === 'message_delta') {
          outputTokens = event.usage.output_tokens;
        }
      }

      yield {
        content: '',
        done: true,
        usage: {
          promptTokens: inputTokens,
          completionTokens: outputTokens,
          totalTokens: inputTokens + outputTokens,
        },
      };
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  private formatMessagesForClaude(messages: Array<{ role: string; content: string }>): {
    system: string;
    messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  } {
    let system = '';
    const claudeMessages: Array<{ role: 'user' | 'assistant'; content: string }> = [];
    
    for (const message of messages) {
      if (message.role === 'system') {
        system = message.content;
      } else if (message.role === 'user' || message.role === 'assistant') {
        claudeMessages.push({
          role: message.role,
          content: message.content,
        });
      }
    }
    
    return { system, messages: claudeMessages };
  }

  private formatToolsForClaude(tools: Array<{ name: string; description: string; parameters: any }>) {
    return tools.map(tool => ({
      name: tool.name,
      description: tool.description,
      input_schema: tool.parameters,
    }));
  }

  private handleError(error: any): ProviderError {
    if (error.status === 401) {
      return {
        code: 'INVALID_API_KEY',
        message: 'Invalid API key. Please check your Anthropic API key.',
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
