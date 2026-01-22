import { ProviderCapabilities, ProviderResponse } from '@/types/provider';

export class LMStudioProvider {
  private baseUrl: string;
  private model: string;

  constructor(baseUrl: string = 'http://localhost:1234/v1', model: string = 'local-model') {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.model = model;
  }

  static getCapabilities(): ProviderCapabilities {
    return {
      supportsStreaming: true,
      supportsFunctionCalling: false, 
      supportsVision: false, 
      maxContextLength: 4096, // Depends on loaded model
      availableModels: [], // Dynamic
    };
  }

  // LM Studio typically exposes an OpenAI compatible endpoint
  // We can fetch available models from /v1/models if needed
  async getAvailableModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/models`);
      if (!response.ok) return [];
      const data = await response.json();
      return data.data.map((m: any) => m.id);
    } catch (e) {
      console.error('Failed to fetch LM Studio models:', e);
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
      temperature: options?.temperature,
      max_tokens: options?.maxTokens,
      stream: false
    };
    
    // LM Studio often runs at /v1/chat/completions but constructor might take base url
    // If baseUrl already ends with /v1, we append /chat/completions.
    // If user provided full path to /chat/completions, we use it.
    // Assuming standard OpenAI compatible structure:
    const endpoint = this.baseUrl.endsWith('/chat/completions') 
        ? this.baseUrl 
        : `${this.baseUrl}/chat/completions`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
       throw new Error(`LM Studio API error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    const choice = data.choices[0];
    
    return {
      content: choice.message.content,
      model: data.model || this.model,
      usage: {
          promptTokens: data.usage?.prompt_tokens || 0,
          completionTokens: data.usage?.completion_tokens || 0,
          totalTokens: data.usage?.total_tokens || 0
      },
      finishReason: choice.finish_reason
    };
  }
}
