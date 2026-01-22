import { ProviderConfig, ProviderCapabilities, ProviderResponse } from '@/types/provider';

export class OllamaProvider {
  private baseUrl: string;
  private model: string;

  constructor(baseUrl: string = 'http://localhost:11434', model: string = 'llama2') {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.model = model;
  }

  static getCapabilities(): ProviderCapabilities {
    return {
      supportsStreaming: true,
      supportsFunctionCalling: false, // Ollama function calling support varies by model
      supportsVision: false, // Varies by model
      maxContextLength: 4096, // Depends on model
      availableModels: [], // Dynamic
    };
  }

  async getAvailableModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`);
      if (!response.ok) return [];
      const data = await response.json();
      return data.models.map((m: any) => m.name);
    } catch (e) {
      console.error('Failed to fetch Ollama models:', e);
      return [];
    }
  }

  async generateResponse(
    messages: Array<{ role: string; content: string }>,
    tools?: Array<{ name: string; description: string; parameters: any }>,
    options?: {
      temperature?: number;
      maxTokens?: number;
    }
  ): Promise<ProviderResponse> {
    const payload = {
      model: this.model,
      messages: messages.map(m => ({ role: m.role, content: m.content })),
      stream: false,
      options: {
        temperature: options?.temperature,
        num_predict: options?.maxTokens,
      }
    };

    const response = await fetch(`${this.baseUrl}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
       throw new Error(`Ollama API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return {
      content: data.message.content,
      model: this.model,
      usage: {
          promptTokens: data.prompt_eval_count || 0,
          completionTokens: data.eval_count || 0,
          totalTokens: (data.prompt_eval_count || 0) + (data.eval_count || 0)
      },
      finishReason: data.done ? 'stop' : undefined
    };
  }

  // Note: Actual chat handling for Ollama will likely be client-side only 
  // to avoid server-side network restrictions to localhost if running in certain environments,
  // OR we can proxy it through a Next.js API route if the Next.js server can reach localhost.
  // Given the "local" nature, direct browser fetch is often preferred for localhost 
  // if CORS allows, but a proxy route is safer for mixed content (HTTPS vs HTTP).
  // For now, I'll follow the pattern of other providers which use the proxy, 
  // but we might need a specific route for Ollama that doesn't require API keys.
}
