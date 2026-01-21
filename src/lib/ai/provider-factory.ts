import { AIProvider, ProviderConfig } from '@/types/provider';

/**
 * ProviderFactory with dynamic imports to reduce bundle size
 * Each provider SDK is only loaded when actually used
 */
export class ProviderFactory {
  static async createProvider(provider: AIProvider, config: ProviderConfig) {
    switch (provider) {
      case 'gemini': {
        const { GeminiProvider } = await import('./providers/gemini');
        return new GeminiProvider(config.apiKey, config.model);
      }
      case 'openai': {
        const { OpenAIProvider } = await import('./providers/openai');
        return new OpenAIProvider(config.apiKey, config.model);
      }
      case 'claude': {
        const { ClaudeProvider } = await import('./providers/claude');
        return new ClaudeProvider(config.apiKey, config.model);
      }
      case 'ollama': {
        const { OllamaProvider } = await import('./providers/ollama');
        // For Ollama, apiKey field is repurposed as baseUrl
        return new OllamaProvider(config.apiKey || 'http://localhost:11434', config.model);
      }
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static async getProviderCapabilities(provider: AIProvider) {
    switch (provider) {
      case 'gemini': {
        const { GeminiProvider } = await import('./providers/gemini');
        return GeminiProvider.getCapabilities();
      }
      case 'openai': {
        const { OpenAIProvider } = await import('./providers/openai');
        return OpenAIProvider.getCapabilities();
      }
      case 'claude': {
        const { ClaudeProvider } = await import('./providers/claude');
        return ClaudeProvider.getCapabilities();
      }
      case 'ollama': {
        const { OllamaProvider } = await import('./providers/ollama');
        return OllamaProvider.getCapabilities();
      }
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static getAvailableProviders(): AIProvider[] {
    return ['gemini', 'openai', 'claude', 'ollama'];
  }

  static getDefaultConfig(provider: AIProvider): Partial<ProviderConfig> {
    const baseConfig = {
      temperature: 0.7,
      maxTokens: 4000,
      enabled: true,
    };

    switch (provider) {
      case 'gemini':
        return {
          ...baseConfig,
          name: 'gemini',
          displayName: 'Google Gemini',
          model: 'gemini-2.0-flash-exp',
        };
      case 'openai':
        return {
          ...baseConfig,
          name: 'openai',
          displayName: 'OpenAI GPT',
          model: 'gpt-4',
        };
      case 'claude':
        return {
          ...baseConfig,
          name: 'claude',
          displayName: 'Anthropic Claude',
          model: 'claude-3-5-sonnet-20241022',
        };
      case 'ollama':
        return {
          ...baseConfig,
          name: 'ollama',
          displayName: 'Ollama (Local)',
          model: 'llama3',
          apiKey: 'http://localhost:11434', // Repurposed as Base URL
        };
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static validateConfig(config: ProviderConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!config.name) {
      errors.push('Provider name is required');
    }

    if (config.name !== 'ollama' && (!config.apiKey || config.apiKey.trim() === '')) {
      errors.push('API key is required');
    }

    if (!config.model || config.model.trim() === '') {
      errors.push('Model is required');
    }

    if (config.temperature < 0 || config.temperature > 2) {
      errors.push('Temperature must be between 0 and 2');
    }

    if (config.maxTokens < 1 || config.maxTokens > 100000) {
      errors.push('Max tokens must be between 1 and 100,000');
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }
}
