'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { StorageManager } from '@/lib/storage';
import { ChatState, ChatSettings, Message, Conversation } from '@/types/chat';

interface JunasState {
  settings: ChatSettings;
  chatState: ChatState | null;
  conversations: Conversation[];
  configuredProviders: Record<string, boolean>;

  // Actions
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

  // Initial load
  useEffect(() => {
    // Load state from local storage
    setSettings(StorageManager.getSettings());
    setChatState(StorageManager.getChatState());
    setConversations(StorageManager.getConversations());
    refreshConfiguredProviders();
  }, []);

  const refreshConfiguredProviders = async () => {
    try {
      const response = await fetch('/api/auth/keys');
      if (response.ok) {
        const { configured } = await response.json();
        setConfiguredProviders(configured || {});
      }
    } catch (error) {
      console.error('Failed to fetch configured providers:', error);
    }
  };

  const updateSettings = (newSettings: ChatSettings) => {
    setSettings(newSettings);
    StorageManager.saveSettings(newSettings);
  };

  // Apply theme side-effects
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
    setConversations(StorageManager.getConversations()); // Reload list
  };

  const deleteConversation = (id: string) => {
    StorageManager.deleteConversation(id);
    setConversations(StorageManager.getConversations()); // Reload list
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
  if (context === undefined) {
    throw new Error('useJunasContext must be used within a JunasProvider');
  }
  return context;
}
