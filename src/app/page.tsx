'use client';

import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ShareDialog } from '@/components/chat/ShareDialog';
import { ConfigDialog } from '@/components/ConfigDialog';
import { AboutDialog } from '@/components/AboutDialog';
import { ThemeDialog } from '@/components/ThemeDialog';
import { HistoryDialog } from '@/components/chat/HistoryDialog';
import { CommandPalette } from '@/components/chat/CommandPalette';
import { StorageManager } from '@/lib/storage';
import { Message, Conversation } from '@/types/chat';
import IntroAnimation from '@/components/IntroAnimation';

export default function Home() {
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showAboutDialog, setShowAboutDialog] = useState(false);
  const [showThemeDialog, setShowThemeDialog] = useState(false);
  const [showHistoryDialog, setShowHistoryDialog] = useState(false);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [chatKey, setChatKey] = useState(0); // Key to force re-render of ChatInterface
  const [hasMessages, setHasMessages] = useState(false);
  const [currentMessages, setCurrentMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'chat' | 'artifacts'>('chat');

  // Check if there are messages on mount and update periodically
  useEffect(() => {
    // Apply dark mode preference immediately
    const settings = StorageManager.getSettings();
    if (settings.darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }

    const checkMessages = () => {
      const chatState = StorageManager.getChatState();
      const messages = chatState?.messages || [];
      setHasMessages(messages.length > 0);
      setCurrentMessages(messages);
    };

    checkMessages();

    // Listen for theme changes
    const handleThemeChange = (e: CustomEvent) => {
      const isDark = e.detail.darkMode;
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
    };

    window.addEventListener('junas-theme-change', handleThemeChange as EventListener);

    // Check every second for message changes
    const interval = setInterval(checkMessages, 1000);
    
    return () => {
      clearInterval(interval);
      window.removeEventListener('junas-theme-change', handleThemeChange as EventListener);
    };
  }, [chatKey]);

  // Global Cmd/Ctrl+Shift+P listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
      const isCmdOrCtrl = isMac ? e.metaKey : e.ctrlKey;
      
      if (isCmdOrCtrl && e.shiftKey && e.key.toLowerCase() === 'p') {
        e.preventDefault();
        setShowCommandPalette(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleNewChat = () => {
    setShowNewChatDialog(true);
  };

  const handleConfirmNewChat = () => {
    // Clear chat state from localStorage
    StorageManager.clearChatState();

    // Force re-render of ChatInterface by changing key
    setChatKey(prev => prev + 1);

    // Close dialog
    setShowNewChatDialog(false);
  };

  const handleSelectConversation = (conversation: Conversation) => {
    // Save to current chat state
    StorageManager.saveChatState({
      messages: conversation.messages,
      artifacts: conversation.artifacts || [],
      isLoading: false,
      currentProvider: 'gemini', // Default or from metadata if we store it
      apiKeys: StorageManager.getApiKeys(),
      settings: StorageManager.getSettings(),
    });

    // Force re-render
    setChatKey(prev => prev + 1);
  };

  if (loading) {
    return <IntroAnimation onComplete={() => setLoading(false)} />;
  }

  return (
    <div className="fade-in">
      <Layout
        onShare={hasMessages ? () => setShowShareDialog(true) : undefined}
        onNewChat={hasMessages ? handleNewChat : undefined}
        onConfig={() => setShowConfigDialog(true)}
        onTheme={() => setShowThemeDialog(true)}
        onAbout={() => setShowAboutDialog(true)}
        onHistory={() => setShowHistoryDialog(true)}
      >
        <ChatInterface 
          key={chatKey} 
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        {/* New Chat Dialog */}
        <NewChatDialog
          isOpen={showNewChatDialog}
          onClose={() => setShowNewChatDialog(false)}
          onConfirm={handleConfirmNewChat}
        />

        {/* History Dialog */}
        <HistoryDialog
          isOpen={showHistoryDialog}
          onClose={() => setShowHistoryDialog(false)}
          onSelectConversation={handleSelectConversation}
        />

        {/* Share Dialog */}
        <ShareDialog
          isOpen={showShareDialog}
          onClose={() => setShowShareDialog(false)}
          messages={currentMessages}
        />

        {/* Config Dialog */}
        <ConfigDialog
          isOpen={showConfigDialog}
          onClose={() => setShowConfigDialog(false)}
        />

        {/* Theme Dialog */}
        <ThemeDialog
          isOpen={showThemeDialog}
          onClose={() => setShowThemeDialog(false)}
        />

        {/* About Dialog */}
        <AboutDialog
          isOpen={showAboutDialog}
          onClose={() => setShowAboutDialog(false)}
        />

        {/* Command Palette */}
        <CommandPalette
          isOpen={showCommandPalette}
          onClose={() => setShowCommandPalette(false)}
          onOpenConfig={() => setShowConfigDialog(true)}
          onOpenTheme={() => setShowThemeDialog(true)}
          onOpenShare={() => setShowShareDialog(true)}
          onOpenAbout={() => setShowAboutDialog(true)}
          onOpenHistory={() => setShowHistoryDialog(true)}
          onNewChat={hasMessages ? handleNewChat : undefined}
          onSwitchToChat={() => setActiveTab('chat')}
          onSwitchToArtifacts={() => setActiveTab('artifacts')}
          hasMessages={hasMessages}
        />
      </Layout>
    </div>
  );
}