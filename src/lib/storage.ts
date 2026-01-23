import { ChatState, ChatSettings, Message, Conversation } from '@/types/chat';

const STORAGE_KEYS = {
  CHAT_STATE: 'junas_chat_state',
  API_KEYS: 'junas_api_keys',
  SETTINGS: 'junas_settings',
  CONVERSATIONS: 'junas_conversations',
  DISCLAIMER_SEEN: 'junas_disclaimer_seen',
  ONBOARDING_COMPLETED: 'junas_onboarding_completed',
} as const;

export class StorageManager {
  // Chat State Management
  static getChatState(): ChatState | null {
    try {
      if (typeof window === 'undefined') return null;
      const stored = window.localStorage.getItem(STORAGE_KEYS.CHAT_STATE);
      return stored ? JSON.parse(stored) : null;
    } catch (error) {
      console.error('Error loading chat state:', error);
      return null;
    }
  }

  static saveChatState(state: ChatState): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.CHAT_STATE, JSON.stringify(state));
    } catch (error) {
      console.error('Error saving chat state:', error);
    }
  }

  static clearChatState(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(STORAGE_KEYS.CHAT_STATE);
  }

  // API Keys Management
  static getApiKeys(): Record<string, string> {
    try {
      if (typeof window === 'undefined') return {};
      const stored = window.localStorage.getItem(STORAGE_KEYS.API_KEYS);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('Error loading API keys:', error);
      return {};
    }
  }

  static saveApiKeys(keys: Record<string, string>): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.API_KEYS, JSON.stringify(keys));
    } catch (error) {
      console.error('Error saving API keys:', error);
    }
  }

  static getApiKey(provider: string): string | null {
    const keys = this.getApiKeys();
    return keys[provider] || null;
  }

  static setApiKey(provider: string, key: string): void {
    const keys = this.getApiKeys();
    keys[provider] = key;
    this.saveApiKeys(keys);
  }

  static removeApiKey(provider: string): void {
    const keys = this.getApiKeys();
    delete keys[provider];
    this.saveApiKeys(keys);
  }

  // Settings Management
  static getSettings(): ChatSettings {
    try {
      if (typeof window === 'undefined') throw new Error('no window');
      const stored = window.localStorage.getItem(STORAGE_KEYS.SETTINGS);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (error) {
      console.error('Error loading settings:', error);
    }
    
    // Return default settings
    return {
      temperature: 0.7,
      maxTokens: 4000,
      topP: 0.95,
      topK: 40,
      frequencyPenalty: 0.0,
      presencePenalty: 0.0,
      systemPrompt: 'You are Junas, a legal AI assistant specialized in Singapore law. Provide accurate, helpful legal information while being clear about limitations.',
      autoSave: true,
      darkMode: false,
      agentMode: false,
      focusMode: false,
      theme: 'vanilla',
      profiles: [],
      activeProfileId: undefined,
      snippets: [],
    };
  }

  static saveSettings(settings: ChatSettings): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
      window.dispatchEvent(new Event('junas-settings-change'));
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  }

  // Conversation Management
  static getConversations(): Conversation[] {
    try {
      if (typeof window === 'undefined') return [];
      const stored = window.localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading conversations:', error);
      return [];
    }
  }

  static saveConversation(conversation: Conversation): void {
    try {
      const conversations = this.getConversations();
      const index = conversations.findIndex(c => c.id === conversation.id);
      
      if (index !== -1) {
        conversations[index] = conversation;
      } else {
        conversations.unshift(conversation);
      }
      
      // Keep only last 20 conversations to prevent storage bloat
      if (conversations.length > 20) {
        conversations.splice(20);
      }
      
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(conversations));
    } catch (error) {
      console.error('Error saving conversation:', error);
    }
  }

  static deleteConversation(id: string): void {
    try {
      const conversations = this.getConversations();
      const filtered = conversations.filter(c => c.id !== id);
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(filtered));
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  }

  static clearConversations(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(STORAGE_KEYS.CONVERSATIONS);
  }

  static clearAllData(): void {
    if (typeof window === 'undefined') return;
    Object.values(STORAGE_KEYS).forEach(key => {
      window.localStorage.removeItem(key);
    });
  }

  // Disclaimer Management
  static hasSeenDisclaimer(): boolean {
    try {
      if (typeof window === 'undefined') return false;

      // Check new key first
      const seen = window.localStorage.getItem(STORAGE_KEYS.DISCLAIMER_SEEN);
      if (seen === 'true') return true;

      // Migrate from old key if it exists
      const oldDismissed = window.localStorage.getItem('junas_disclaimer_dismissed');
      if (oldDismissed === 'true') {
        this.setDisclaimerSeen();
        window.localStorage.removeItem('junas_disclaimer_dismissed');
        return true;
      }

      return false;
    } catch (error) {
      console.error('Error checking disclaimer status:', error);
      return false;
    }
  }

  static setDisclaimerSeen(): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.DISCLAIMER_SEEN, 'true');
    } catch (error) {
      console.error('Error setting disclaimer status:', error);
    }
  }

  // Onboarding Management
  static hasCompletedOnboarding(): boolean {
    try {
      if (typeof window === 'undefined') return false;
      return window.localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED) === 'true';
    } catch (error) {
      console.error('Error checking onboarding status:', error);
      return false;
    }
  }

  static setOnboardingCompleted(): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.ONBOARDING_COMPLETED, 'true');
    } catch (error) {
      console.error('Error setting onboarding status:', error);
    }
  }

  // Utility methods
  static hasApiKey(provider: string): boolean {
    return !!this.getApiKey(provider);
  }

  static hasAnyApiKey(): boolean {
    const keys = this.getApiKeys();
    return Object.values(keys).some(key => key && key.trim() !== '');
  }

  static exportData(): string {
    const data = {
      chatState: this.getChatState(),
      apiKeys: this.getApiKeys(),
      settings: this.getSettings(),
      conversations: this.getConversations(),
      exportDate: new Date().toISOString(),
    };
    
    return JSON.stringify(data, null, 2);
  }

  static importData(jsonData: string): boolean {
    try {
      const data = JSON.parse(jsonData);
      
      if (data.chatState) this.saveChatState(data.chatState);
      if (data.apiKeys) this.saveApiKeys(data.apiKeys);
      if (data.settings) this.saveSettings(data.settings);
      if (data.conversations) {
        localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(data.conversations));
      }
      
      return true;
    } catch (error) {
      console.error('Error importing data:', error);
      return false;
    }
  }
}
