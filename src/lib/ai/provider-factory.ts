import { AIProvider, ProviderConfig } from '@/types/provider';
export class ProviderFactory {
  static getAvailableProviders(): AIProvider[] {
    return ['gemini', 'openai', 'claude', 'ollama', 'lmstudio'];
  }
  static getDefaultConfig(provider: AIProvider): Partial<ProviderConfig> {
    const baseConfig = { temperature: 0.7, maxTokens: 4000, enabled: true };
    switch (provider) {
      case 'gemini': return { ...baseConfig, name: 'gemini', displayName: 'Google Gemini', model: 'gemini-2.0-flash-exp' };
      case 'openai': return { ...baseConfig, name: 'openai', displayName: 'OpenAI GPT', model: 'gpt-4' };
      case 'claude': return { ...baseConfig, name: 'claude', displayName: 'Anthropic Claude', model: 'claude-3-5-sonnet-20241022' };
      case 'ollama': return { ...baseConfig, name: 'ollama', displayName: 'Ollama (Local)', model: 'llama3', apiKey: 'http://localhost:11434' };
      case 'lmstudio': return { ...baseConfig, name: 'lmstudio', displayName: 'LM Studio (Local)', model: 'local-model', apiKey: 'http://localhost:1234/v1' };
      default: throw new Error(`Unsupported provider: ${provider}`);
    }
  }
  static validateConfig(config: ProviderConfig): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    if (!config.name) errors.push('Provider name is required');
    if (config.name !== 'ollama' && config.name !== 'lmstudio' && (!config.apiKey || config.apiKey.trim() === '')) errors.push('API key is required');
    if (!config.model || config.model.trim() === '') errors.push('Model is required');
    if (config.temperature < 0 || config.temperature > 2) errors.push('Temperature must be between 0 and 2');
    if (config.maxTokens < 1 || config.maxTokens > 100000) errors.push('Max tokens must be between 1 and 100,000');
    return { valid: errors.length === 0, errors };
  }
}
