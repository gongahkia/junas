import { ChatState, ChatSettings, Conversation } from '@/types/chat';
import * as fs from '@/lib/storage/file-storage';
const DEFAULT_SETTINGS: ChatSettings = {
  temperature: 0.7,
  maxTokens: 4000,
  topP: 0.95,
  topK: 40,
  frequencyPenalty: 0.0,
  presencePenalty: 0.0,
  systemPrompt:
    'You are Junas, a legal AI assistant specialized in Singapore law. Provide accurate, helpful legal information while being clear about limitations.',
  autoSave: true,
  darkMode: false,
  agentMode: false,
  focusMode: false,
  theme: 'vanilla',
  profiles: [],
  activeProfileId: undefined,
  snippets: [],
  asciiLogo: '5',
};
let cachedSettings: ChatSettings | null = null; // in-memory cache for sync access
let cachedChatState: ChatState | null = null;
export class StorageManager {
  static getChatState(): ChatState | null {
    return cachedChatState;
  }
  static saveChatState(state: ChatState): void {
    cachedChatState = state;
    fs.saveSettings({ ...cachedSettings, _chatState: state }).catch(console.error);
  }
  static clearChatState(): void {
    cachedChatState = null;
  }
  static getSettings(): ChatSettings {
    return cachedSettings || DEFAULT_SETTINGS;
  }
  static saveSettings(settings: ChatSettings): void {
    cachedSettings = settings;
    fs.saveSettings(settings).catch(console.error);
  }
  static getConversations(): Conversation[] {
    return [];
  } // async wrapper needed; sync stub
  static async getConversationsAsync(): Promise<{ id: string; name: string; updatedAt: string }[]> {
    return fs.listConversations();
  }
  static async loadConversationById(id: string): Promise<Conversation | null> {
    const raw = await fs.loadConversation(id);
    if (!raw || typeof raw !== 'object') return null;

    const conversation = raw as Partial<Conversation> & Record<string, unknown>;
    if (!Array.isArray(conversation.messages)) return null;

    return {
      ...conversation,
      id: typeof conversation.id === 'string' ? conversation.id : id,
      title:
        typeof conversation.title === 'string' && conversation.title.trim().length > 0
          ? conversation.title
          : id,
      createdAt: conversation.createdAt ? new Date(conversation.createdAt as string) : new Date(),
      updatedAt: conversation.updatedAt ? new Date(conversation.updatedAt as string) : new Date(),
      messages: conversation.messages,
      artifacts: Array.isArray(conversation.artifacts) ? conversation.artifacts : [],
    } as Conversation;
  }
  static saveConversation(conversation: Conversation): void {
    fs.saveConversation(conversation.id, {
      ...conversation,
      updatedAt: new Date().toISOString(),
    }).catch(console.error);
  }
  static deleteConversation(id: string): void {
    fs.deleteConversation(id).catch(console.error);
  }
  static clearConversations(): void {} // no-op; individual deletes preferred
  static clearAllData(): void {
    cachedSettings = null;
    cachedChatState = null;
  }
  static hasSeenDisclaimer(): boolean {
    try {
      return localStorage.getItem('junas_disclaimer_seen') === 'true';
    } catch {
      return false;
    }
  }
  static setDisclaimerSeen(): void {
    try {
      localStorage.setItem('junas_disclaimer_seen', 'true');
    } catch {}
  }
  static hasCompletedOnboarding(): boolean {
    try {
      return localStorage.getItem('junas_onboarding_completed') === 'true';
    } catch {
      return false;
    }
  }
  static setOnboardingCompleted(): void {
    try {
      localStorage.setItem('junas_onboarding_completed', 'true');
    } catch {}
  }
  static exportData(): string {
    return JSON.stringify(
      { settings: this.getSettings(), exportDate: new Date().toISOString() },
      null,
      2
    );
  }
  static importData(jsonData: string): boolean {
    try {
      const data = JSON.parse(jsonData);
      if (data.settings) this.saveSettings(data.settings);
      return true;
    } catch {
      return false;
    }
  }
  static async init(): Promise<void> {
    cachedSettings = await fs.loadSettings(DEFAULT_SETTINGS);
  }
}
