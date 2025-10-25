import { AIProvider, ProviderConfig } from '@/types/provider';
import { GeminiProvider } from './providers/gemini';
import { OpenAIProvider } from './providers/openai';
import { ClaudeProvider } from './providers/claude';

export class ProviderFactory {
  static createProvider(provider: AIProvider, config: ProviderConfig) {
    switch (provider) {
      case 'gemini':
        return new GeminiProvider(config.apiKey, config.model);
      case 'openai':
        return new OpenAIProvider(config.apiKey, config.model);
      case 'claude':
        return new ClaudeProvider(config.apiKey, config.model);
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static getProviderCapabilities(provider: AIProvider) {
    switch (provider) {
      case 'gemini':
        return GeminiProvider.getCapabilities();
      case 'openai':
        return OpenAIProvider.getCapabilities();
      case 'claude':
        return ClaudeProvider.getCapabilities();
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static getAvailableProviders(): AIProvider[] {
    return ['gemini', 'openai', 'claude'];
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
          model: 'gemini-1.5-flash-latest',
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
      default:
        throw new Error(`Unsupported provider: ${provider}`);
    }
  }

  static validateConfig(config: ProviderConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!config.name) {
      errors.push('Provider name is required');
    }

    if (!config.apiKey || config.apiKey.trim() === '') {
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
