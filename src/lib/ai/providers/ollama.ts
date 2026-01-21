import { ProviderConfig, ProviderCapabilities } from '@/types/provider';

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

  // Note: Actual chat handling for Ollama will likely be client-side only 
  // to avoid server-side network restrictions to localhost if running in certain environments,
  // OR we can proxy it through a Next.js API route if the Next.js server can reach localhost.
  // Given the "local" nature, direct browser fetch is often preferred for localhost 
  // if CORS allows, but a proxy route is safer for mixed content (HTTPS vs HTTP).
  // For now, I'll follow the pattern of other providers which use the proxy, 
  // but we might need a specific route for Ollama that doesn't require API keys.
}
