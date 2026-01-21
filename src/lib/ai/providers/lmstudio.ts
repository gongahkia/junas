import { ProviderCapabilities } from '@/types/provider';

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
}
