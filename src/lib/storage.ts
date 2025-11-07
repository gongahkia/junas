import { ChatState, ChatSettings, Message, Conversation } from '@/types/chat';

const STORAGE_KEYS = {
  CHAT_STATE: 'junas_chat_state',
  API_KEYS: 'junas_api_keys',
  SETTINGS: 'junas_settings',
  CONVERSATIONS: 'junas_conversations',
  DISCLAIMER_SEEN: 'junas_disclaimer_seen',
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
      systemPrompt: 'You are Junas, a legal AI assistant specialized in Singapore law. Provide accurate, helpful legal information while being clear about limitations.',
      autoSave: true,
      darkMode: false,
      enableAdvancedReasoning: true,
      defaultReasoningDepth: 'standard',
      showReasoningStages: true,
    };
  }

  static saveSettings(settings: ChatSettings): void {
    try {
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
    } catch (error) {
      console.error('Error saving settings:', error);
    }
  }

  // Conversation Management
  static getConversations(): Message[][] {
    try {
      if (typeof window === 'undefined') return [];
      const stored = window.localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      // Backward compatibility: previously stored as Message[][]
      if (Array.isArray(parsed) && parsed.length > 0 && Array.isArray(parsed[0])) {
        return parsed as Message[][];
      }
      // If stored as Conversation[], map to Message[][] for legacy callers
      if (Array.isArray(parsed) && parsed[0] && parsed[0].messages) {
        return (parsed as Conversation[]).map(c => c.messages);
      }
      return [];
    } catch (error) {
      console.error('Error loading conversations:', error);
      return [];
    }
  }

  static saveConversation(messages: Message[]): void {
    try {
      // Migrate to Conversation[] format
      const existing = this.getConversationObjects();
      const conv: Conversation = {
        id: cryptoRandomId(),
        title: generateConversationTitle(messages),
        messages,
        createdAt: new Date(),
        updatedAt: new Date(),
      };
      existing.push(conv);

      // Keep only last 20 conversations to prevent storage bloat
      if (existing.length > 20) {
        existing.splice(0, existing.length - 20);
      }

      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(existing));
    } catch (error) {
      console.error('Error saving conversation:', error);
    }
  }

  // New: Full conversation object APIs
  static getConversationObjects(): Conversation[] {
    try {
      if (typeof window === 'undefined') return [];
      const stored = window.localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed[0] && parsed[0].messages) {
        // Parse dates
        return (parsed as any[]).map((c) => ({
          ...c,
          createdAt: c.createdAt ? new Date(c.createdAt) : new Date(),
          updatedAt: c.updatedAt ? new Date(c.updatedAt) : new Date(),
        }));
      }
      // Legacy migration from Message[][]
      if (Array.isArray(parsed) && parsed.length > 0 && Array.isArray(parsed[0])) {
        const migrated: Conversation[] = (parsed as Message[][]).map((msgs, i) => ({
          id: cryptoRandomId(),
          title: generateConversationTitle(msgs),
          messages: msgs,
          createdAt: new Date(),
          updatedAt: new Date(),
        }));
        window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(migrated));
        return migrated;
      }
      return [];
    } catch (error) {
      console.error('Error loading conversation objects:', error);
      return [];
    }
  }

  static saveConversationObject(conversation: Conversation): void {
    try {
      const list = this.getConversationObjects();
      const idx = list.findIndex((c) => c.id === conversation.id);
      if (idx >= 0) {
        list[idx] = { ...conversation, updatedAt: new Date() };
      } else {
        list.push({ ...conversation, createdAt: new Date(), updatedAt: new Date() });
      }
      if (typeof window === 'undefined') return;
      window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(list));
    } catch (error) {
      console.error('Error saving conversation object:', error);
    }
  }

  static createBranchFrom(messages: Message[], atMessageId: string, opts?: { title?: string; tags?: string[]; parentId?: string }): Conversation {
    const index = messages.findIndex((m) => m.id === atMessageId);
    const branched = index >= 0 ? messages.slice(0, index + 1) : messages.slice();
    const conv: Conversation = {
      id: cryptoRandomId(),
      title: opts?.title || generateConversationTitle(branched),
      messages: branched,
      createdAt: new Date(),
      updatedAt: new Date(),
      tags: opts?.tags,
      parentId: opts?.parentId,
    };
    this.saveConversationObject(conv);
    return conv;
  }

  static updateConversationTags(conversationId: string, tags: string[]) {
    const list = this.getConversationObjects();
    const idx = list.findIndex((c) => c.id === conversationId);
    if (idx >= 0) {
      list[idx].tags = tags;
      list[idx].updatedAt = new Date();
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(list));
      }
    }
  }

  static deleteConversation(conversationId: string) {
    const list = this.getConversationObjects();
    const filtered = list.filter((c) => c.id !== conversationId);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(filtered));
    }
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

// Helpers (outside class to avoid syntax errors inside class scope)
function cryptoRandomId(): string {
  try {
    // @ts-ignore
    const arr = crypto?.getRandomValues?.(new Uint32Array(4));
    if (arr) return Array.from(arr).map((n) => n.toString(16)).join('');
  } catch {}
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function generateConversationTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === 'user');
  const base = firstUser?.content?.slice(0, 60) || 'New Conversation';
  return base.replace(/\s+/g, ' ').trim();
}
