import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { StorageManager } from '@/lib/storage';
import { ChatState, ChatSettings, Conversation } from '@/types/chat';
import { getApiKey } from '@/lib/tauri-bridge';
import { listConversations, loadConversation } from '@/lib/storage/file-storage';
interface JunasState {
  settings: ChatSettings;
  chatState: ChatState | null;
  conversations: Conversation[];
  configuredProviders: Record<string, boolean>;
  updateSettings: (settings: ChatSettings) => void;
  updateChatState: (state: ChatState) => void;
  saveConversation: (conversation: Conversation) => void;
  deleteConversation: (id: string) => void;
  refreshConfiguredProviders: () => Promise<void>;
}
const JunasContext = createContext<JunasState | undefined>(undefined);
export function JunasProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<ChatSettings>(StorageManager.getSettings());
  const [chatState, setChatState] = useState<ChatState | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [configuredProviders, setConfiguredProviders] = useState<Record<string, boolean>>({});
  const hydrateConversations = async () => {
    try {
      const summaries = await listConversations();
      const loaded = await Promise.all(
        summaries.map(async (summary) => {
          const raw = await loadConversation(summary.id);
          if (!raw || typeof raw !== 'object') return null;

          const conversation = raw as Partial<Conversation> & Record<string, unknown>;
          if (!Array.isArray(conversation.messages)) return null;

          return {
            ...conversation,
            id: typeof conversation.id === 'string' ? conversation.id : summary.id,
            title:
              typeof conversation.title === 'string' && conversation.title.trim().length > 0
                ? conversation.title
                : summary.name,
            createdAt: conversation.createdAt
              ? new Date(conversation.createdAt as string)
              : new Date(),
            updatedAt: conversation.updatedAt
              ? new Date(conversation.updatedAt as string)
              : new Date(),
            messages: conversation.messages,
            artifacts: Array.isArray(conversation.artifacts) ? conversation.artifacts : [],
          } as Conversation;
        })
      );

      setConversations(loaded.filter((c): c is Conversation => c !== null));
    } catch {
      setConversations([]);
    }
  };

  useEffect(() => {
    StorageManager.init().then(() => {
      setSettings(StorageManager.getSettings());
      setChatState(StorageManager.getChatState());
      hydrateConversations();
    });
    refreshConfiguredProviders();
  }, []);
  const refreshConfiguredProviders = async () => {
    const providers = ['gemini', 'openai', 'claude', 'ollama', 'lmstudio'];
    const configured: Record<string, boolean> = {};
    for (const p of providers) {
      try {
        const k = await getApiKey(p);
        configured[p] = !!k;
      } catch {
        configured[p] = false;
      }
    }
    setConfiguredProviders(configured);
  };
  const updateSettings = (newSettings: ChatSettings) => {
    setSettings(newSettings);
    StorageManager.saveSettings(newSettings);
  };
  useEffect(() => {
    if (settings.darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    if (settings.theme) {
      document.documentElement.setAttribute('data-theme', settings.theme);
    }
  }, [settings.darkMode, settings.theme]);
  const updateChatState = (newState: ChatState) => {
    setChatState(newState);
    StorageManager.saveChatState(newState);
  };
  const saveConversation = (conversation: Conversation) => {
    StorageManager.saveConversation(conversation);
  };
  const deleteConversation = (id: string) => {
    StorageManager.deleteConversation(id);
  };
  return (
    <JunasContext.Provider
      value={{
        settings,
        chatState,
        conversations,
        configuredProviders,
        updateSettings,
        updateChatState,
        saveConversation,
        deleteConversation,
        refreshConfiguredProviders,
      }}
    >
      {children}
    </JunasContext.Provider>
  );
}
export function useJunasContext() {
  const context = useContext(JunasContext);
  if (context === undefined) throw new Error('useJunasContext must be used within a JunasProvider');
  return context;
}
