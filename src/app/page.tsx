'use client';

import { useState, useEffect } from 'react';
import { Layout } from '@/components/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { NewChatDialog } from '@/components/chat/NewChatDialog';
import { ImportDialog } from '@/components/chat/ImportDialog';
import { ExportDialog } from '@/components/chat/ExportDialog';
import { ShareDialog } from '@/components/chat/ShareDialog';
import { ConfigDialog } from '@/components/ConfigDialog';
import { AboutDialog } from '@/components/AboutDialog';
import { ThemeDialog } from '@/components/ThemeDialog';
import { CommandPalette } from '@/components/chat/CommandPalette';
import { StorageManager } from '@/lib/storage';
import { Message } from '@/types/chat';
import IntroAnimation from '@/components/IntroAnimation';

export default function Home() {
  const [showNewChatDialog, setShowNewChatDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showAboutDialog, setShowAboutDialog] = useState(false);
  const [showThemeDialog, setShowThemeDialog] = useState(false);
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

  const handleImport = (importedMessages: Message[]) => {
    // Dispatch import event to ChatInterface
    const evt = new CustomEvent('junas-import', {
      detail: { messages: importedMessages }
    });
    window.dispatchEvent(evt);
  };

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

  if (loading) {
    return <IntroAnimation onComplete={() => setLoading(false)} />;
  }

  return (
    <div className="fade-in">
      <Layout
        onImport={!hasMessages ? () => setShowImportDialog(true) : undefined}
        onExport={hasMessages ? () => setShowExportDialog(true) : undefined}
        onShare={hasMessages ? () => setShowShareDialog(true) : undefined}
        onNewChat={hasMessages ? handleNewChat : undefined}
        onConfig={() => setShowConfigDialog(true)}
        onTheme={() => setShowThemeDialog(true)}
        onAbout={() => setShowAboutDialog(true)}
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

        {/* Import Dialog */}
        <ImportDialog
          isOpen={showImportDialog}
          onClose={() => setShowImportDialog(false)}
          onImport={handleImport}
        />

        {/* Export Dialog */}
        <ExportDialog
          isOpen={showExportDialog}
          onClose={() => setShowExportDialog(false)}
          messages={currentMessages}
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
          onOpenImport={() => setShowImportDialog(true)}
          onOpenExport={() => setShowExportDialog(true)}
          onOpenShare={() => setShowShareDialog(true)}
          onOpenAbout={() => setShowAboutDialog(true)}
          onNewChat={hasMessages ? handleNewChat : undefined}
          onSwitchToChat={() => setActiveTab('chat')}
          onSwitchToArtifacts={() => setActiveTab('artifacts')}
          hasMessages={hasMessages}
        />
      </Layout>
    </div>
  );
}
